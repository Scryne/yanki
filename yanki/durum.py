"""Şarkı başına durum kaydı: `calisma/<kimlik>/durum.json`.

Tek dosya, insan okunur; hattın her adımı buraya yazar, dinleme sayfası buradan okur.

Aşamalar:
  yeni → hazir (kaynak + söz + künye) → analiz (stil/BPM/ton) → uretildi (adaylar kapıdan geçti)
  → onarim (Scryne aralık işaretledi, motor bekliyor) → uretildi … → onaylandi → paketlendi → yuklendi
  → yayinda (`yanki takip` parçayı Spotify'da buldu)
  her aşamadan → hata (neden yazılı) ya da reddedildi (Scryne)
"""

import contextlib
import json
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

from yanki import dosya, kilit

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
    # ACE-Step söz hizalama puanı (motor_isci._hizalama; parça başına {"lm", "dit"}): seçim ölçüsü olarak sınanacak
    hizalama: list | None = None
    # üretildiği tarif: {"model", "lora" (eğitim adı, yoksa None), "lora_olcek", "stil_kaynak", "tarih"}; eski
    # adaylarda yok. Hat değişince (yeni LoRA, betim) dinleme odası eski ve yeni adayları ayırt eder.
    tarif: dict | None = None


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
    # bilinmeyen alan atlanır: yeni sürümün yazdığı kaydı eski kodla açık süreç (dinleme odası) okuyabilsin
    # (2026-10-12: adaya `hizalama` eklenince açık oda her isteğe 500 verdi)
    d["adaylar"] = [Aday(**{k: v for k, v in x.items() if k in Aday.__dataclass_fields__})
                    for x in d.get("adaylar", [])]
    return Durum(**{k: v for k, v in d.items() if k in Durum.__dataclass_fields__})


def yaz(calisma: Path, d: Durum) -> Path:
    return dosya.json_yaz(klasor(calisma, d.kimlik) / "durum.json", asdict(d))  # yarım yazılmış dosya bırakma


class Yok(LookupError):
    pass


@contextlib.contextmanager
def guncelle(calisma: Path, kimlik: str, yoksa: Durum | None = None) -> Iterator[Durum]:
    """Süreçler arası güvenli oku-değiştir-yaz: şarkının kilidi alınır, durum diskten taze okunur, blok hatasız biterse
    yazılır. Uzun süren işler (üretim saatler sürer) başta okudukları kopyayı sonda yazarsa dinleme odasında o arada
    verilen kararı (onay, onarım isteği, ret) ezerdi; bu yüzden sonuçlar burada taze kopyaya işlenir.
    Dosya yoksa `yoksa` kullanılır (o da yoksa `Yok`)."""
    with kilit.bekleyerek(klasor(calisma, kimlik) / ".durum.kilit"):
        d = oku(calisma, kimlik) or yoksa
        if d is None:
            raise Yok(kimlik)
        yield d
        yaz(calisma, d)


def hepsi(calisma: Path) -> list[Durum]:
    """Bütün şarkılar. Okunamayan tek bir durum.json (güç kesintisinde boş kalmış dosya) atlanır ve yazılır: önce
    bütün adımlar ve dinleme odasının listesi o tek dosya yüzünden düşüyordu."""
    sonuc = []
    for p in sorted(calisma.glob("*/durum.json")):
        try:
            if d := oku(calisma, p.parent.name):
                sonuc.append(d)
        except (ValueError, TypeError) as e:  # bozuk JSON ya da beklenmeyen alan
            print(f"✗ {p.parent.name}/durum.json okunamadı, atlandı: {type(e).__name__}: {e}")
    return sonuc
