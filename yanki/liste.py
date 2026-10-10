"""Scryne'ın şarkı listesi: `girdi/liste.toml`.

Hat yalnız bu listedekileri işler (Scryne, 2026-10-06). `yanki kesif --ekle N` doğrulanmış kaldırılmış şarkıları
bu dosyanın sonuna ekler (2026-10-09).

    [[sarki]]
    sanatci = "Adele"
    ad = "Someone Like You"
    # isteğe bağlı:
    # youtube = "https://www.youtube.com/watch?v=..."   # kaynak videoyu sabitle
    # stil = "acoustic guitar ballad, warm female vocal"  # cover'ın stil tanımı (yoksa otomatik)
    # vokal = "kadin"                                     # "kadin" | "erkek"
    # bpm = 68
    # ton = "A major"
    # yazarlar = ["Ad Soyad", "Ad Soyad"]                # orijinal söz yazarı/besteciler (MusicBrainz'de yoksa)
"""

import re
import tomllib
import unicodedata
from dataclasses import dataclass
from pathlib import Path

VOKAL = {"kadin": "female", "erkek": "male"}


@dataclass(frozen=True)
class Sarki:
    sanatci: str
    ad: str
    youtube: str | None = None
    stil: str | None = None
    vokal: str | None = None
    bpm: int | None = None
    ton: str | None = None
    # orijinal yazarlar, "Ad Soyad" (MusicBrainz'de kaydı olmayan şarkı: dağıtımcı cover'da yazarsız yayın almıyor)
    yazarlar: tuple[str, ...] | None = None

    @property
    def kimlik(self) -> str:
        return kimlik(self.sanatci, self.ad)


def kimlik(sanatci: str, ad: str) -> str:
    """Dosya sistemi dostu, kararlı şarkı kimliği: 'adele-someone-like-you'."""
    duz = unicodedata.normalize("NFKD", f"{sanatci} {ad}".replace("ı", "i").replace("İ", "I"))
    duz = duz.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", duz).strip("-")


def yukle(yol: Path) -> list[Sarki]:
    return coz(yol.read_text(encoding="utf-8-sig"), yol.name)  # Not Defteri BOM ekleyebilir


def coz(metin: str, ad: str = "liste.toml") -> list[Sarki]:
    """Liste metnini doğrular ve çözer (eksik/bilinmeyen alan, aynı şarkı iki kez: ValueError)."""
    yol = Path(ad)
    d = tomllib.loads(metin)
    sarkilar, gorulen = [], set()
    for i, s in enumerate(d.get("sarki", []), 1):
        eksik = [k for k in ("sanatci", "ad") if not str(s.get(k, "")).strip()]
        if eksik:
            raise ValueError(f"{yol.name}: {i}. şarkıda eksik alan: {', '.join(eksik)}")
        bilinmeyen = set(s) - {"sanatci", "ad", "youtube", "stil", "vokal", "bpm", "ton", "yazarlar"}
        if bilinmeyen:
            raise ValueError(f"{yol.name}: {i}. şarkıda bilinmeyen alan: {', '.join(sorted(bilinmeyen))}")
        if s.get("vokal") is not None and s["vokal"] not in VOKAL:
            raise ValueError(f"{yol.name}: {i}. şarkı vokal 'kadin' ya da 'erkek' olmalı: {s['vokal']}")
        yazarlar = s.get("yazarlar")
        if yazarlar is not None and (not isinstance(yazarlar, list) or not yazarlar
                                     or not all(isinstance(x, str) and x.strip() for x in yazarlar)):
            raise ValueError(f"{yol.name}: {i}. şarkı yazarlar [\"Ad Soyad\", …] biçiminde olmalı: {yazarlar}")
        alanlar = {k: (v.strip() if isinstance(v, str) else v) for k, v in s.items()}
        if yazarlar is not None:
            alanlar["yazarlar"] = tuple(" ".join(x.split()) for x in yazarlar)
        sarki = Sarki(**alanlar)
        if sarki.kimlik in gorulen:
            raise ValueError(f"{yol.name}: aynı şarkı iki kez: {sarki.sanatci} — {sarki.ad}")
        gorulen.add(sarki.kimlik)
        sarkilar.append(sarki)
    return sarkilar
