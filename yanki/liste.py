"""Scryne'ın şarkı listesi: `girdi/liste.toml`.

Hat şarkı seçmez; yalnız bu listedekileri işler (Scryne, 2026-10-06).

    [[sarki]]
    sanatci = "Adele"
    ad = "Someone Like You"
    # isteğe bağlı:
    # youtube = "https://www.youtube.com/watch?v=..."   # kaynak videoyu sabitle
    # stil = "acoustic guitar ballad, warm female vocal"  # cover'ın stil tanımı (yoksa otomatik)
    # vokal = "kadin"                                     # "kadin" | "erkek"
    # bpm = 68
    # ton = "A major"
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

    @property
    def kimlik(self) -> str:
        return kimlik(self.sanatci, self.ad)


def kimlik(sanatci: str, ad: str) -> str:
    """Dosya sistemi dostu, kararlı şarkı kimliği: 'adele-someone-like-you'."""
    duz = unicodedata.normalize("NFKD", f"{sanatci} {ad}".replace("ı", "i").replace("İ", "I"))
    duz = duz.encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", duz).strip("-")


def yukle(yol: Path) -> list[Sarki]:
    with open(yol, "rb") as f:
        d = tomllib.load(f)
    sarkilar, gorulen = [], set()
    for i, s in enumerate(d.get("sarki", []), 1):
        eksik = [k for k in ("sanatci", "ad") if not str(s.get(k, "")).strip()]
        if eksik:
            raise ValueError(f"{yol.name}: {i}. şarkıda eksik alan: {', '.join(eksik)}")
        bilinmeyen = set(s) - {"sanatci", "ad", "youtube", "stil", "vokal", "bpm", "ton"}
        if bilinmeyen:
            raise ValueError(f"{yol.name}: {i}. şarkıda bilinmeyen alan: {', '.join(sorted(bilinmeyen))}")
        if s.get("vokal") is not None and s["vokal"] not in VOKAL:
            raise ValueError(f"{yol.name}: {i}. şarkı vokal 'kadin' ya da 'erkek' olmalı: {s['vokal']}")
        sarki = Sarki(**{k: (v.strip() if isinstance(v, str) else v) for k, v in s.items()})
        if sarki.kimlik in gorulen:
            raise ValueError(f"{yol.name}: aynı şarkı iki kez: {sarki.sanatci} — {sarki.ad}")
        gorulen.add(sarki.kimlik)
        sarkilar.append(sarki)
    return sarkilar
