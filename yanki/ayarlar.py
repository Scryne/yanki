"""Proje yolları ve `config/motor.toml`."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Motor:
    klasor: Path
    model: str
    niceleme: str | None
    cpu_offload: bool
    lm_model: str
    lm_backend: str
    analiz_model: str
    analiz_kesit_sn: float
    analiz_yontemi: str
    # DiT'i aşamalar arasında CPU'ya al (nicelemesiz XL'de VAE çözme 8 GB'a sığmıyor, S18)
    dit_offload: bool = False
    # eğitilmiş tür LoRA'sı (yanki/egitim.py; bağdaştırıcı klasörü) ve ölçeği; yalnız nicelemesiz motorda
    lora: Path | None = None
    lora_olcek: float = 1.0

    @property
    def python(self) -> Path:
        return self.klasor / ".venv" / "Scripts" / "python.exe"

    @property
    def checkpoints(self) -> Path:
        return self.klasor / "checkpoints"


@dataclass(frozen=True)
class Cover:
    gorev: str
    guc: float
    adim: int
    aday_sayisi: int
    tohumlar: tuple[int, ...]


@dataclass(frozen=True)
class Onarim:
    gorev: str
    adim: int
    pay_sn: float
    tohumlar: tuple[int, ...]


@dataclass(frozen=True)
class Gpu:
    bos_esik_mib: int
    bekleme_sn: int


@dataclass(frozen=True)
class Uzak:
    """Kiralık GPU (`yanki/uzak.py`); yoksa ya da kapalıysa üretim evdeki kartta."""
    acik: bool = False
    gpu: str = "NVIDIA A40"
    en_az_bakiye: float = 3.0
    aylik_butce: float = 15.0
    sarki: int = 8
    tek_parca_sn: float = 480.0
    yerel_yedek: bool = True  # sunucu yoksa evdeki kartta üret


@dataclass(frozen=True)
class Ayarlar:
    kok: Path
    motor: Motor
    cover: Cover
    onarim: Onarim
    gpu: Gpu
    fpcalc: Path
    uzak: Uzak = Uzak()


def yukle(yol: Path | None = None, kok: Path = KOK) -> Ayarlar:
    yol = yol or kok / "config" / "motor.toml"
    with open(yol, "rb") as f:
        d = tomllib.load(f)
    m, c, o, g = d["motor"], d["cover"], d["onarim"], d["gpu"]
    if len(c["tohumlar"]) < c["aday_sayisi"]:
        raise ValueError(f"cover.tohumlar ({len(c['tohumlar'])}) aday_sayisi ({c['aday_sayisi']}) kadar olmalı")
    if m.get("analiz_yontemi", "musicbrainz") not in ("musicbrainz", "lm"):
        raise ValueError(f"motor.analiz_yontemi musicbrainz ya da lm olmalı: {m['analiz_yontemi']}")
    if not 0.0 < c["guc"] <= 1.0:
        raise ValueError(f"cover.guc 0 ile 1 arasında olmalı: {c['guc']}")
    lora = Path(m["lora"]) if m.get("lora") else None
    if lora is not None and not lora.is_absolute():
        lora = kok / lora
    if lora is not None and not (lora / "adapter_config.json").is_file():
        raise ValueError(f"motor.lora bir LoRA klasörü değil (adapter_config.json yok): {lora}")
    if not 0.0 <= float(m.get("lora_olcek", 1.0)) <= 1.0:
        raise ValueError(f"motor.lora_olcek 0 ile 1 arasında olmalı: {m['lora_olcek']}")
    return Ayarlar(
        kok=kok,
        motor=Motor(kok / m["klasor"], m["model"], m.get("niceleme") or None, bool(m["cpu_offload"]), m["lm_model"],
                    m.get("lm_backend", "pt"), m.get("analiz_model", m["model"]),
                    float(m.get("analiz_kesit_sn", 40)), m.get("analiz_yontemi", "musicbrainz"),
                    bool(m.get("dit_offload", False)), lora, float(m.get("lora_olcek", 1.0))),
        cover=Cover(c["gorev"], float(c["guc"]), int(c["adim"]), int(c["aday_sayisi"]), tuple(c["tohumlar"])),
        onarim=Onarim(o["gorev"], int(o["adim"]), float(o["pay_sn"]), tuple(o["tohumlar"])),
        gpu=Gpu(int(g["bos_esik_mib"]), int(g["bekleme_sn"])),
        fpcalc=kok / d["araclar"]["fpcalc"],
        uzak=_uzak(d.get("uzak", {})),
    )


def _uzak(u: dict) -> Uzak:
    return Uzak(bool(u.get("acik", False)), str(u.get("gpu", "NVIDIA A40")), float(u.get("en_az_bakiye", 3.0)),
                float(u.get("aylik_butce", 15.0)), max(1, int(u.get("sarki", 8))), float(u.get("tek_parca_sn", 480)),
                bool(u.get("yerel_yedek", True)))


@dataclass(frozen=True)
class Operasyon:
    """`config/operasyon.toml`: gece koşusunun bakım adımları (yedek, disk temizliği). Dosya yoksa varsayılanlar."""
    yedek_klasor: Path
    yedek_gun: int = 7
    yedek_sakla: int = 8
    temizlik_gun: int = 14
    gunduz_acik: bool = True
    gunduz_bosta_dk: int = 20
    gunduz_sarki: int = 1
    gunduz_saatler: tuple[int, int] = (8, 1)  # [başlangıç, bitiş) saat; gece yarısını geçebilir
    # sürekli koşu (\Yanki\Surekli, her 30 dk): bir koşuda en çok kaç şarkı üretilsin (uzun üretim yükleme ve yoklamayı
    # saatlerce kilitlemesin); kullanıcı etkinken de üretilsin mi
    surekli_uretim_sarki: int = 2
    surekli_bosta_bekle: bool = False

    def gunduz_saatinde(self, saat: int) -> bool:
        bas, son = self.gunduz_saatler
        return bas <= saat < son if bas < son else saat >= bas or saat < son


def operasyon_oku(kok: Path = KOK) -> Operasyon:
    yol = kok / "config" / "operasyon.toml"
    d = tomllib.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    y, t, g, sk = d.get("yedek", {}), d.get("temizlik", {}), d.get("gunduz", {}), d.get("surekli", {})
    klasor = Path(y.get("klasor", "calisma/yedek"))
    saatler = tuple(int(x) % 24 for x in g.get("saatler", (8, 1)))
    if len(saatler) != 2:
        raise ValueError(f"gunduz.saatler [başlangıç, bitiş] olmalı: {g.get('saatler')}")
    return Operasyon(klasor if klasor.is_absolute() else kok / klasor, max(1, int(y.get("gun", 7))),
                     max(1, int(y.get("sakla", 8))), max(0, int(t.get("gun", 14))), bool(g.get("acik", True)),
                     max(1, int(g.get("bosta_dk", 20))), max(1, int(g.get("sarki", 1))), saatler,
                     max(1, int(sk.get("uretim_sarki", 2))), bool(sk.get("bosta_bekle", False)))
