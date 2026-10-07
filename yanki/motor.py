"""Motor köprüsü: işleri ACE-Step işçisine (ayrı süreç, motorun venv'i) verir, sonuçları okur.

Hat torch yüklemez. İşçi çökse de hat ayakta kalır; her iş için başarı/hata ayrı döner.
Başlamadan önce GPU kapısı: başka bir iş (ör. Otomat) VRAM'i tutuyorsa üretim 50 kat yavaşlıyor (spike: 12 sn → 600 sn),
bu yüzden kullanılan VRAM eşiğin altına inene kadar beklenir.
"""

import json
import subprocess
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from pathlib import Path

from yanki import saglik
from yanki.ayarlar import Ayarlar

ISCI = Path(__file__).with_name("motor_isci.py")


@dataclass(frozen=True)
class Is:
    id: str
    gorev: str  # "cover" | "repaint" | "anla"
    kaynak: str
    cikti_klasor: str = ""
    stil: str = ""
    soz: str = ""
    adim: int = 0
    tohum: int = 0
    guc: float = 1.0
    dil: str = "en"
    bpm: int | None = None
    ton: str = ""
    bolge: tuple[float, float] | None = None
    referans: str | None = None  # tını referansı (parçalı üretimde ilk parçanın çıktısı)
    # ACE-Step GenerationParams'a olduğu gibi giden ek ayarlar (shift, guidance_scale, use_adg, sampler_mode …)
    ek: dict = field(default_factory=dict, hash=False)

    def __post_init__(self):
        if self.gorev not in ("cover", "repaint", "anla"):
            raise ValueError(f"görev cover, repaint ya da anla olmalı: {self.gorev}")
        if self.gorev == "anla":
            return
        if self.adim <= 0 or not self.cikti_klasor:
            raise ValueError("cover/repaint için adim ve cikti_klasor gerekli")
        if self.gorev == "repaint" and (self.bolge is None or not 0 <= self.bolge[0] < self.bolge[1]):
            raise ValueError(f"repaint için geçerli bir bölge gerekli: {self.bolge}")
        if not self.soz.strip():
            raise ValueError("söz boş: sözsüz vokal anlamsız çıkıyor (spike S1, wer 0,94–0,98)")


@dataclass
class Sonuc:
    id: str | None
    basari: bool
    hata: str | None = None
    cikti: str | None = None
    sure_sn: float | None = None
    cikti_sure_sn: float | None = None
    vram_tepe_gb: float | None = None
    yukleme_sn: float | None = None
    analiz: dict | None = None
    iz: str | None = field(default=None, repr=False)


class GpuMesgul(TimeoutError):
    pass


def gpu_bekle(
    a: Ayarlar,
    en_fazla_sn: float,
    okuyucu: Callable[[], int | None] = saglik.gpu_kullanilan_mib,
    uyku: Callable[[float], None] = time.sleep,
    saat: Callable[[], float] = time.monotonic,
) -> int:
    """Kullanılan VRAM eşiğin altına inene kadar bekler; kullanılan MiB'i döner."""
    bitis = saat() + en_fazla_sn
    while True:
        kullanilan = okuyucu()
        if kullanilan is None:
            raise RuntimeError("GPU okunamadı (nvidia-smi)")
        if kullanilan < a.gpu.bos_esik_mib:
            return kullanilan
        if saat() >= bitis:
            raise GpuMesgul(f"GPU {en_fazla_sn:.0f} sn boşalmadı: {kullanilan} MiB kullanımda")
        uyku(a.gpu.bekleme_sn)


def calistir(
    a: Ayarlar,
    isler: list[Is],
    klasor: Path,
    zaman_asimi_sn: float,
    gpu_bekleme_sn: float = 6 * 3600,
    python: Path | None = None,
    isci: Path = ISCI,
    bekle: Callable[..., int] = gpu_bekle,
    model: str | None = None,
) -> list[Sonuc]:
    """İşleri tek işçi sürecinde (tek model yüklemesi) çalıştırır. `model` verilirse ayardaki model yerine o
    (nicelemesiz) yüklenir — analiz gibi hafif işler için."""
    if not isler:
        return []
    # işçi motor klasöründe başlar (cwd); göreli yol orada çözülemez
    klasor = klasor.resolve()
    klasor.mkdir(parents=True, exist_ok=True)
    is_yolu, sonuc_yolu = klasor / "motor_is.json", klasor / "motor_sonuc.json"
    sonuc_yolu.unlink(missing_ok=True)
    is_yolu.write_text(
        json.dumps(
            {
                "motor": {
                    "klasor": str(a.motor.klasor),
                    "model": model or a.motor.model,
                    "niceleme": None if model else a.motor.niceleme,
                    "cpu_offload": a.motor.cpu_offload,
                    "lm_model": a.motor.lm_model,
                    "lm_backend": a.motor.lm_backend,
                },
                "isler": [asdict(i) for i in isler],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    if python is None and not a.motor.python.exists():
        hata = f"motor bulunamadı: {a.motor.python} (README: motor kurulumu)"
        return [Sonuc(i.id, False, hata) for i in isler]
    bekle(a, gpu_bekleme_sn)
    gunluk = klasor / "motor.log"
    with open(gunluk, "wb") as log:
        try:
            surec = subprocess.run(
                [str(python or a.motor.python), str(isci), str(is_yolu), str(sonuc_yolu)],
                stdout=log, stderr=subprocess.STDOUT, timeout=zaman_asimi_sn,
                env=_ortam(a), cwd=str(a.motor.klasor if a.motor.klasor.is_dir() else klasor),
            )
            cikis = surec.returncode
        except subprocess.TimeoutExpired:
            cikis = None
    okunan = json.loads(sonuc_yolu.read_text(encoding="utf-8")) if sonuc_yolu.exists() else []
    sonuclar = {r["id"]: Sonuc(**r) for r in okunan if r.get("id") is not None}
    genel = next((r["hata"] for r in okunan if r.get("id") is None), None)
    if cikis is None:
        genel = f"zaman aşımı ({zaman_asimi_sn:.0f} sn)"
    elif genel is None and cikis not in (0, 1):
        genel = f"işçi {cikis} koduyla çıktı, ayrıntı: {gunluk}"
    return [sonuclar.get(i.id) or Sonuc(i.id, False, genel or f"sonuç yazılmadı, ayrıntı: {gunluk}") for i in isler]


def _ortam(a: Ayarlar) -> dict[str, str]:
    import os

    e = dict(os.environ)
    # ACE-Step checkpoints'i proje kökünden bulur; kök yoksa çalışma klasörünü kullanıyor
    e["ACESTEP_PROJECT_ROOT"] = str(a.motor.klasor)
    e["PYTHONUTF8"] = "1"
    e["PYTHONIOENCODING"] = "utf-8"
    # ACE-Step'in iç üretim zaman aşımı varsayılan 600 sn; parça başına bizim zaman aşımımız esas
    e.setdefault("ACESTEP_GENERATION_TIMEOUT", "1800")
    return e
