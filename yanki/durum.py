"""Şarkı başına durum kaydı: `calisma/<kimlik>/durum.json`.

Tek dosya, insan okunur; hattın her adımı buraya yazar, dinleme sayfası buradan okur.

Aşamalar:
  yeni → hazir (kaynak + söz + künye) → analiz (stil/BPM/ton) → uretildi (adaylar kapıdan geçti)
  → onarim (Scryne aralık işaretledi, motor bekliyor) → uretildi … → onaylandi → paketlendi → yuklendi
  → yayinda (`yanki takip` parçayı Spotify'da buldu)
  her aşamadan → hata (neden yazılı) ya da reddedildi (Scryne)
"""

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

ASAMALAR = (
    "yeni", "hazir", "analiz", "uretildi", "onarim", "onaylandi", "paketlendi", "yuklendi", "yayinda", "hata",
    "reddedildi",
)


@dataclass
class Aday:
    no: int
    dosya: str
    tohum: int
    kapilar: dict = field(default_factory=dict)  # ad → {"gecti": bool, "deger": float, "esik": float}
    gecti: bool = False
    # [{"id", "bolge": [bas, son], "tohum", "temel": onarılan dosya, "durum": bekliyor|hazir|kabul|ret|hata,
    #   "dosya", "kapilar", "hata"}]
    onarimlar: list = field(default_factory=list)
    stil: str | None = None  # üretildiği stil tanımı (stil değiştirilip yeniden üretilince adaylar ayırt edilsin)


@dataclass
class Durum:
    kimlik: str
    sanatci: str
    ad: str
    asama: str = "yeni"
    hata: str | None = None
    kaynak: dict = field(default_factory=dict)
    soz: dict = field(default_factory=dict)
    kunye: dict = field(default_factory=dict)
    analiz: dict = field(default_factory=dict)  # stil, bpm, ton, dil (+ nereden geldiği)
    adaylar: list[Aday] = field(default_factory=list)
    secilen: int | None = None
    notlar: list = field(default_factory=list)
    gecmis: list = field(default_factory=list)
    yayin: dict = field(default_factory=dict)  # `yanki takip`: {"son": {...}, "gecmis": [...]}

    def gec(self, asama: str, hata: str | None = None) -> None:
        if asama not in ASAMALAR:
            raise ValueError(f"bilinmeyen aşama: {asama}")
        self.asama, self.hata = asama, hata
        self.gecmis.append({"zaman": datetime.now().isoformat(timespec="seconds"), "asama": asama, "hata": hata})


def klasor(calisma: Path, kimlik: str) -> Path:
    return calisma / kimlik


def oku(calisma: Path, kimlik: str) -> Durum | None:
    yol = klasor(calisma, kimlik) / "durum.json"
    if not yol.exists():
        return None
    d = json.loads(yol.read_text(encoding="utf-8"))
    d["adaylar"] = [Aday(**x) for x in d.get("adaylar", [])]
    return Durum(**d)


def yaz(calisma: Path, d: Durum) -> Path:
    yol = klasor(calisma, d.kimlik) / "durum.json"
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps(asdict(d), ensure_ascii=False, indent=2), encoding="utf-8")
    gecici.replace(yol)  # yarım yazılmış dosya bırakma
    return yol


def hepsi(calisma: Path) -> list[Durum]:
    return [d for p in sorted(calisma.glob("*/durum.json")) if (d := oku(calisma, p.parent.name))]
