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
    gorev: str  # "cover" | "repaint" | "anla" | "betimle" | "puanla"
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
    # yüklü LoRA'nın bu işteki ölçeği (karşılaştırmalı dinleme: aynı işçide 0 / 0,5 / 1); None: motor ayarındaki ölçek
    lora_olcek: float | None = None
    # işe özel LoRA (işçinin gördüğü yol): aynı işçide farklı bağdaştırıcılar (eğitimin ara kayıtları)
    lora: str | None = None
    # aynı işçideki bir "betimle" işinin id'si: stil o betimden kurulur (motor_isci.betim_stili; önce dinle, sonra üret)
    stil_betimden: str | None = None
    puanlanan: str | None = None  # "puanla": puanlanacak hazır aday
    # ACE-Step GenerationParams'a olduğu gibi giden ek ayarlar (shift, guidance_scale, use_adg, sampler_mode …)
    ek: dict = field(default_factory=dict, hash=False)

    def __post_init__(self):
        if self.gorev not in ("cover", "repaint", "anla", "betimle", "puanla"):
            raise ValueError(f"görev cover, repaint, anla, betimle ya da puanla olmalı: {self.gorev}")
        if self.gorev == "puanla" and not self.puanlanan:
            raise ValueError("puanla için puanlanan aday gerekli")
        if self.gorev in ("anla", "betimle"):
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
    stil: str | None = None  # işin gerçekten kullandığı stil (betimden kurulduysa)
    lora_olcek: float | None = None
    # ACE-Step'in söz hizalama puanı (çapraz dikkat; yüksek = söz sese daha iyi oturmuş): {"lm", "dit"}
    hizalama: dict | None = None

    @classmethod
    def okunan(cls, r: dict) -> "Sonuc":
        """İşçinin yazdığı kayıt; bilinmeyen alan (yeni işçi, eski hat) atlanır."""
        return cls(**{k: v for k, v in r.items() if k in cls.__dataclass_fields__})


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
    hareketsiz_sn: float = 20 * 60,
    bekci_aralik_sn: float = 5,
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
                    "dit_offload": a.motor.dit_offload,
                    "lm_model": a.motor.lm_model,
                    "lm_backend": a.motor.lm_backend,
                    **lora_ayari(a, model),
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
    takildi = False
    with open(gunluk, "wb") as log:
        surec = subprocess.Popen(
            [str(python or a.motor.python), str(isci), str(is_yolu), str(sonuc_yolu)],
            stdout=log, stderr=subprocess.STDOUT, env=_ortam(a),
            cwd=str(a.motor.klasor if a.motor.klasor.is_dir() else klasor),
        )
        bitis, son_hareket = time.monotonic() + zaman_asimi_sn, time.monotonic()
        boyut = -1
        while surec.poll() is None:
            try:  # işçi bitince hemen döner; bitmediyse bekçi aralığında bir bakar
                surec.wait(timeout=bekci_aralik_sn)
                break
            except subprocess.TimeoutExpired:
                pass
            yeni = gunluk.stat().st_size if gunluk.exists() else 0
            if yeni != boyut:
                boyut, son_hareket = yeni, time.monotonic()
            # bekçi: işçi günlüğe hiç yazmadan HAREKETSIZ_SN geçerse takılmıştır (2026-10-10: VAE çözme boş VRAM
            # 0,76 GB'ta paylaşımlı belleğe taştı, bir saat ilerlemedi; toplam zaman aşımı 3 saat 45 dk sonraydı)
            takildi = time.monotonic() - son_hareket > hareketsiz_sn
            if takildi or time.monotonic() > bitis:
                surec.kill()
                surec.wait()
                break
        cikis = None if surec.returncode is None or takildi or time.monotonic() > bitis else surec.returncode
    try:
        okunan = json.loads(sonuc_yolu.read_text(encoding="utf-8")) if sonuc_yolu.exists() else []
    except (OSError, ValueError):  # işçi yazarken öldürüldü (zaman aşımı): yarım JSON
        okunan = []
    sonuclar = {r["id"]: Sonuc.okunan(r) for r in okunan if r.get("id") is not None}
    genel = next((r["hata"] for r in okunan if r.get("id") is None), None)
    if takildi:
        genel = f"işçi {hareketsiz_sn / 60:.0f} dk ilerlemedi, durduruldu (ayrıntı: {gunluk})"
    elif cikis is None:
        genel = f"zaman aşımı ({zaman_asimi_sn:.0f} sn)"
    elif genel is None and cikis not in (0, 1):
        genel = f"işçi {cikis} koduyla çıktı, ayrıntı: {gunluk}"
    return [sonuclar.get(i.id) or Sonuc(i.id, False, genel or f"sonuç yazılmadı, ayrıntı: {gunluk}") for i in isler]


def lora_ayari(a: Ayarlar, model: str | None = None, yol: str | None = None) -> dict:
    """İşçinin motor ayarına LoRA: yalnız üretim modelinde (analiz modeli değil) ve nicelemesiz motorda (INT8'e PEFT
    bağdaştırıcısı uygulanmıyor). `yol`: sunucudaki karşılığı (uzak motor)."""
    if a.motor.lora is None or model or a.motor.niceleme:
        return {}
    return {"lora": yol or str(a.motor.lora), "lora_olcek": a.motor.lora_olcek}


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
