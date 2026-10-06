"""Künye: MusicBrainz'den orijinal şarkının söz yazarları ve bestecileri.

Dağıtımcıların cover formu orijinal yazarları ister (RouteNote: publishing alanı). Kayıt → eser → yazar ilişkileri.
MusicBrainz istek sınırı saniyede 1; aralar korunur.
"""

import time
from dataclasses import dataclass, field

from yanki import ag

MB = "https://musicbrainz.org/ws/2"
YAZAR_ROLLERI = {"composer", "lyricist", "writer"}


@dataclass(frozen=True)
class Kunye:
    kayit_mbid: str
    eser_mbid: str | None
    eser_adi: str | None
    yazarlar: tuple[str, ...] = field(default=())
    isrc: tuple[str, ...] = field(default=())
    ilk_yayin: str | None = None


def bul(sanatci: str, ad: str, json_al=ag.json_al, uyku=time.sleep) -> Kunye:
    sorgu = f'recording:"{ad}" AND artist:"{sanatci}" AND status:official'
    kayitlar = json_al(f"{MB}/recording/", {"query": sorgu, "limit": 10, "fmt": "json"}).get("recordings", [])
    kayitlar = [k for k in kayitlar if k.get("score", 0) >= 90 and k.get("title", "").lower() == ad.lower()]
    if not kayitlar:
        raise ag.Bulunamadi(f"MusicBrainz'de kayıt yok: {sanatci} — {ad}")
    # eser bağlantısı olan ilk kaydı bul (canlı/remix kayıtlarında çoğu zaman yok)
    for kayit in kayitlar[:5]:
        uyku(1.1)
        ayrinti = json_al(f"{MB}/recording/{kayit['id']}", {"inc": "work-rels+isrcs", "fmt": "json"})
        eserler = [r["work"] for r in ayrinti.get("relations", []) if r.get("type") == "performance" and "work" in r]
        if not eserler:
            continue
        eser = eserler[0]
        uyku(1.1)
        e = json_al(f"{MB}/work/{eser['id']}", {"inc": "artist-rels", "fmt": "json"})
        yazarlar = []
        for r in e.get("relations", []):
            if r.get("type") in YAZAR_ROLLERI and r.get("artist", {}).get("name") not in yazarlar:
                yazarlar.append(r["artist"]["name"])
        return Kunye(kayit["id"], eser["id"], eser.get("title"), tuple(yazarlar), tuple(ayrinti.get("isrcs", [])),
                     kayit.get("first-release-date"))
    raise ag.Bulunamadi(f"MusicBrainz kaydında eser bağlantısı yok: {sanatci} — {ad}")
