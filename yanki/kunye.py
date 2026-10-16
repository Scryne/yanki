"""Künye: MusicBrainz'den orijinal şarkının söz yazarları ve bestecileri.

Dağıtımcıların cover formu orijinal yazarları ister (RouteNote: publishing alanı). Kayıt → eser → yazar ilişkileri.
MusicBrainz istek sınırı saniyede 1; aralar korunur.
"""

import time
from dataclasses import dataclass, field

from yanki import ag

MB = "https://musicbrainz.org/ws/2"
YAZAR_ROLLERI = {"composer", "lyricist", "writer"}
# MusicBrainz tipografik işaret kullanıyor ("Say You Won’t Let Go", "Tim Rice‐Oxley"); karşılaştırma ve form için düz
DUZ = str.maketrans({"’": "'", "‘": "'", "‐": "-", "‑": "-", "–": "-"})


def duz(s: str) -> str:
    return s.translate(DUZ)


@dataclass(frozen=True)
class Kunye:
    kayit_mbid: str
    eser_mbid: str | None
    eser_adi: str | None
    yazarlar: tuple[str, ...] = field(default=())
    # dağıtımcı formu ad + soyad ister: (ad, soyad); soyad bilinmiyorsa ""
    yazar_adlari: tuple[tuple[str, str], ...] = field(default=())
    isrc: tuple[str, ...] = field(default=())
    # eşleşen kayıtların en erkeni (eser bağlı kayıt çoğu zaman derleme/yeniden yayın: Keane 2021, asıl 2004)
    ilk_yayin: str | None = None
    # stil tanımı için: sanatçının MusicBrainz türleri (oy sırasıyla), tür (Person/Group) ve cinsiyet
    sanatci_turleri: tuple[str, ...] = field(default=())
    sanatci_tipi: str | None = None
    sanatci_cinsiyeti: str | None = None


def ad_soyad(ad: str, sirali: str) -> tuple[str, str] | None:
    """MusicBrainz sıralama adından ("Del Rey, Lana", "Jesso, Tobias, Jr.") ad + soyad; virgülsüzse None."""
    parca = [p.strip() for p in duz(sirali).split(",")]
    if len(parca) < 2 or not parca[0] or not parca[1]:
        return None
    return parca[1], " ".join([parca[0], *parca[2:]])


def _yazar_adi(sanatci: dict, json_al, uyku) -> tuple[str, str]:
    """Künyedeki ad sıralama adından bölünür. Tek sözcüklü sahne adında ("Adele", "RØMANS") yasal ad takma adı:
    boşluklu en kısası ("Adele Adkins"; ilk yüklemede elle girilenle aynı)."""
    if bolunmus := ad_soyad(sanatci["name"], sanatci.get("sort-name", "")):
        return bolunmus
    if sanatci.get("id"):
        uyku(1.1)
        try:
            a = json_al(f"{MB}/artist/{sanatci['id']}", {"inc": "aliases", "fmt": "json"})
        except ag.Bulunamadi:
            a = {}
        yasal = sorted((x for x in a.get("aliases", []) if x.get("type") == "Legal name" and " " in x.get("name", "")),
                       key=lambda x: len(x["name"]))
        if yasal:
            x = yasal[0]
            return ad_soyad(x["name"], x.get("sort-name", "")) or tuple(duz(x["name"]).rsplit(" ", 1))
    parca = duz(sanatci["name"]).rsplit(" ", 1)
    return (parca[0], parca[1]) if len(parca) == 2 else (parca[0], "")


def bul(sanatci: str, ad: str, json_al=ag.json_al, uyku=time.sleep) -> Kunye:
    sorgu = f'recording:"{ad}" AND artist:"{sanatci}" AND status:official'
    kayitlar = json_al(f"{MB}/recording/", {"query": sorgu, "limit": 25, "fmt": "json"}).get("recordings", [])
    kayitlar = [k for k in kayitlar
                if k.get("score", 0) >= 90 and duz(k.get("title", "")).casefold() == duz(ad).casefold()]
    if not kayitlar:
        raise ag.Bulunamadi(f"MusicBrainz'de kayıt yok: {sanatci} — {ad}")
    ilk_yayin = min((k["first-release-date"] for k in kayitlar if k.get("first-release-date")), default=None)
    # eser bağlantısı olan ilk kaydı bul (canlı/remix kayıtlarında çoğu zaman yok). Eserinde yazar ilişkisi olmayan
    # kayıtta durulmaz: sonraki kayıtların eseri yazarlıdır çoğu zaman (yazarsız paket dağıtımcıya yüklenemiyor)
    yedek: Kunye | None = None
    for kayit in kayitlar[:5]:
        uyku(1.1)
        ayrinti = json_al(f"{MB}/recording/{kayit['id']}", {"inc": "work-rels+isrcs", "fmt": "json"})
        eserler = [r["work"] for r in ayrinti.get("relations", []) if r.get("type") == "performance" and "work" in r]
        if not eserler:
            continue
        eser = eserler[0]
        uyku(1.1)
        e = json_al(f"{MB}/work/{eser['id']}", {"inc": "artist-rels", "fmt": "json"})
        yazarlar, kisiler = [], []
        for r in e.get("relations", []):
            if r.get("type") in YAZAR_ROLLERI and duz(r.get("artist", {}).get("name", "")) not in yazarlar:
                yazarlar.append(duz(r["artist"]["name"]))
                kisiler.append(r["artist"])
        yazar_adlari = tuple(_yazar_adi(k, json_al, uyku) for k in kisiler)
        turler, tip, cinsiyet = (), None, None
        kredi = (kayit.get("artist-credit") or [{}])[0].get("artist", {})
        # yalnız aranan sanatçının kendisiyse (başka birinin cover kaydının türleri yanıltır)
        if kredi.get("id") and duz(kredi.get("name", "")).casefold() == duz(sanatci).casefold():
            uyku(1.1)
            sn = json_al(f"{MB}/artist/{kredi['id']}", {"inc": "genres", "fmt": "json"})
            turler = tuple(g["name"] for g in sorted(sn.get("genres", []), key=lambda g: -g.get("count", 0)))
            tip, cinsiyet = sn.get("type"), sn.get("gender")
        sonuc = Kunye(kayit["id"], eser["id"], eser.get("title"), tuple(yazarlar), yazar_adlari,
                      tuple(ayrinti.get("isrcs", [])), ilk_yayin, turler, tip, cinsiyet)
        if yazarlar:
            return sonuc
        yedek = yedek or sonuc
    if yedek is not None:
        return yedek
    raise ag.Bulunamadi(f"MusicBrainz kaydında eser bağlantısı yok: {sanatci} — {ad}")


def elle_yazarlar(kunye: dict, yazarlar: tuple[str, ...] | list[str]) -> dict:
    """Listedeki elle yazılmış yazarlar (`liste.toml` → `yazarlar`) künyeye işlenir; MusicBrainz'in yazarlarının
    yerine geçer (Scryne'ın bilgisi esas). Ad + soyad son boşluktan bölünür ("Rick Price" → Rick / Price)."""
    adlar = [duz(" ".join(x.split())) for x in yazarlar]
    bolunmus = [tuple(a.rsplit(" ", 1)) if " " in a else (a, "") for a in adlar]
    return {k: v for k, v in kunye.items() if k != "uyari"} | {
        "yazarlar": adlar, "yazar_adlari": [list(x) for x in bolunmus], "yazar_kaynak": "liste"}
