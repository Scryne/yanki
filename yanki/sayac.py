"""Dış servis sayaçları: koşu başına istek ve hata sayısı (Roadmap Faz 13, kota bütçeleri).

YouTube, LRCLIB, MusicBrainz, Deezer ve Spotify sessizce bozulabiliyor (2026-10-08: YouTube ilk parçada 0 bayt,
2026-10-09: Spotify 23 saatlik kilit). Sayaç süreç içinde tutulur; gece koşusu sonunda özeti günlüğe yazar ve günlük
toplamı `calisma/gunluk/servisler.json`'a ekler, eğilim oradan okunur.
"""

import json
from collections import Counter
from datetime import date
from pathlib import Path

ISTEK: Counter = Counter()
HATA: Counter = Counter()
SERVIS_ADI = {"lrclib.net": "LRCLIB", "musicbrainz.org": "MusicBrainz", "api.deezer.com": "Deezer",
              "api.spotify.com": "Spotify", "accounts.spotify.com": "Spotify"}


def servis(url: str) -> str:
    from urllib.parse import urlparse

    host = urlparse(url).hostname or url
    return SERVIS_ADI.get(host, host)


def say(ad: str, basarili: bool) -> None:
    ISTEK[ad] += 1
    if not basarili:
        HATA[ad] += 1


def sifirla() -> None:
    ISTEK.clear()
    HATA.clear()


def ozet() -> str:
    if not ISTEK:
        return "dış servis isteği yok"
    return " · ".join(f"{ad} {ISTEK[ad]}" + (f" ({HATA[ad]} hata, %{100 * HATA[ad] / ISTEK[ad]:.0f})" if HATA[ad]
                                             else "") for ad in sorted(ISTEK))


def yaz(calisma: Path, gun: date | None = None) -> Path:
    """Bugünün toplamına ekler (bir günde birden çok koşu olabilir: gece + gündüz)."""
    from yanki import dosya

    yol = calisma / "gunluk" / "servisler.json"
    try:
        kayit = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        kayit = {}
    bugun = kayit.setdefault((gun or date.today()).isoformat(), {})
    for ad in ISTEK:
        s = bugun.setdefault(ad, {"istek": 0, "hata": 0})
        s["istek"] += ISTEK[ad]
        s["hata"] += HATA[ad]
    return dosya.json_yaz(yol, dict(sorted(kayit.items())[-90:]), indent=1)
