"""Keşif adayının özgünlük kararı: TypeSafe (Jev).

Soru: listede "Del — Put Me in a Movie" yazıyor; bu gerçekten Del'in şarkısı mı, yoksa başka bir sanatçının (çoğunlukla
ünlü birinin yayınlanmamış, sızdırılmış) şarkısının takma adla yüklenmiş hâli mi, ya da bir oyun/film müziğinin hayran
yapımı mı? Kanıt YouTube'un ilk sonuçları (başlık, kanal, izlenme). Bu anlam gerektiren bir karar: regex sürümü bir
günde dört kez yamandı ("Del" ≠ "Lana Del Rey", boşluksuz tire, "||") ve yine de Vinnie Vincent Invasion'ı kaçırdı,
Vipraz'ın Indila şarkısını kabul etti.

Spike (2026-10-09, jev-1.13.0, 30 elle etiketli gerçek örnek; `docs/arastirma/03`): kabul kuralı
"listedeki sanatçı ≥ 0,90 ve hayran < 0,5" ile 20 sızıntı/hayran örneğinde sıfır yanlış kabul; gerçek sanatçılarda
regex'in kaçırdığını buldu. Belirsiz kanıtta (505bubble, ¥$) "belirsiz" ya da düşük güven → kendiliğinden eklenmez.

Anahtar `TYPESAFE_API_KEY` (kullanıcı ortam değişkeni ya da `.env`); yoksa ya da servis düşerse çağıran regex
yedeğinde kalır (`kesif.sanatci_eslesir`). Cevap ve çözülen model sürümü adayın kaydına dondurulur.
"""

import os
from pathlib import Path

MODEL = "jev-latest"  # çözülen sürüm kayda yazılır; sabit sürüm API'den kalkınca sessizce ölürdü
KABUL = 0.90
RED = 0.60
HAYRAN = 0.50

SORULAR = {
    "kimin": {
        "type": "choice",
        "instructions": "A streaming catalog lists a track under `listed_artist` with title `listed_title`. "
                        "`youtube_results` are the top YouTube search results for that artist and title. "
                        "Based on this evidence, whose song is it?",
        "criteria": {
            "listed_artist": "The evidence shows it as a song performed and released by the listed artist itself "
                             "(results credit the listed artist, e.g. 'Listed Artist - Title' or the artist's own "
                             "channel), even if the artist is small or obscure.",
            "other_artist": "The evidence shows the song belongs to a different artist; the listed name looks like "
                            "an alias, misspelling, or impersonation used to re-upload someone else's song (for "
                            "example a leaked or unreleased song of a famous artist uploaded under a fake name).",
            "unclear": "The results do not show who the song belongs to (no matching results, or unrelated ones).",
        },
    },
    "hayran": {
        "type": "noul",
        "instructions": "Is the listed track a fan-made recreation, remake, or soundtrack re-recording of music from "
                        "a video game, film, or show, rather than an original release by the listed artist?",
    },
}


def anahtar(kok: Path | None = None) -> str | None:
    if os.environ.get("TYPESAFE_API_KEY"):
        return os.environ["TYPESAFE_API_KEY"]
    if kok:
        from yanki.spotify import env_oku

        return env_oku(kok).get("TYPESAFE_API_KEY") or None
    return None


class Yargic:
    """Koşu boyunca tek istemci (her çağrı ~0,3 sn; IPv4 zorlanır: bu makinede IPv6 DNS ilk bağlantıyı 12 sn
    bekletiyor, TypeSafe notu)."""

    def __init__(self, api_key: str, istemci=None):
        if istemci is None:
            import httpx2
            import typesafe_sdk

            istemci = typesafe_sdk.TypeSafeClient(api_key=api_key, model=MODEL, timeout=20,
                                                  transport=httpx2.HTTPTransport(local_address="0.0.0.0"))
        self.istemci = istemci

    def ozgunluk(self, sanatci: str, ad: str, kanit: list[dict]) -> dict:
        """{"model", "listed_artist", "other_artist", "unclear", "guven", "hayran", "karar"}; karar True (kabul),
        False (ret) ya da None (belirsiz)."""
        state = {"listed_artist": sanatci, "listed_title": ad, "youtube_results": kanit}
        y = self.istemci.system_one(state=state, questions=SORULAR)
        kim, hayran = y.answers["kimin"], y.answers["hayran"].noul
        p = {k: round(float(v), 3) for k, v in kim.probabilities.items()}
        if p.get("listed_artist", 0) >= KABUL and hayran < HAYRAN:
            karar = True
        elif p.get("other_artist", 0) >= RED or hayran >= HAYRAN:
            karar = False
        else:
            karar = None
        return {"model": y.model, **p, "guven": round(float(kim.confidence), 3), "hayran": round(float(hayran), 3),
                "karar": karar}

    def kapat(self) -> None:
        close = getattr(self.istemci, "close", None)
        if close:
            close()


SINIR_SN = 60  # bir kararın en çok süresi (SDK zaman aşımı + yeniden denemeler dahil)


def sinirli(fn, sn: float = SINIR_SN):
    """`fn()` en çok `sn` saniye: 2026-10-13 gecesi TypeSafe isteği SDK'nın 20 sn zaman aşımına rağmen 20 dakikadan
    uzun ssl okumasında kaldı, gece keşfi (ve arkasındaki hazırlık/üretim) bekledi. Süre dolunca TimeoutError; asılı
    istek arka planda (daemon) kalır, süreç kapanırken beklenmez."""
    import threading

    sonuc: dict = {}

    def is_():
        try:
            sonuc["deger"] = fn()
        except BaseException as e:  # noqa: BLE001 — çağırana taşınır
            sonuc["hata"] = e

    t = threading.Thread(target=is_, daemon=True)
    t.start()
    t.join(sn)
    if t.is_alive():
        raise TimeoutError(f"{sn:g} sn'de cevap gelmedi")
    if "hata" in sonuc:
        raise sonuc["hata"]
    return sonuc["deger"]


def ac(kok: Path | None = None) -> Yargic | None:
    k = anahtar(kok)
    return Yargic(k) if k else None
