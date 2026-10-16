"""Yayından sonra ne oluyor: şarkı ve tür bazında dinlenme ve kazanç, keşfe geri besleme.

Kaynaklar (RouteNote paneli botla okunmaz: site şartları madde 2, "collecting data … using bots … or other automated
data gathering methods"; Scryne 2026-10-16 "kurala uygun"):
- **Dinlenme:** takip her gece canlı parçamızın Spotify sayacını Spotify uygulamasının içinden okur (STILLMORE köprüsü,
  `yanki/takip.py`), `durum.yayin["dinlenme"]`'ye günlük nokta yazar. Sayaç toplamdır; günlük dinlenme iki nokta
  arasındaki farktan.
- **Kazanç:** RouteNote'un aylık satış raporu; Scryne indirip `girdi/kazanc/`'a koyar (`yanki/kazanc.py`).

Geri besleme: hangi türde şarkılarımız daha çok dinleniyorsa keşif o türdeki adayı öne alır (`Aday.performans`, puanla
çarpılır). Çarpan türün ortanca günlük dinlenmesinin bütün şarkıların ortancasına oranının karekökü, [0,6, 1,6]
arasında: tek şarkının şansı keşfi savurmasın. Yeterli veri yokken (en az 4 şarkı, türde en az 2, her biri en az 14
gün yayında) çarpan 1.
"""

import statistics
from datetime import date, datetime
from pathlib import Path

from yanki import durum

SERI_SINIRI = 400
PENCERE_GUN = 28  # günlük dinlenme son bu kadar günün ortalaması
EN_AZ_GUN = 14  # tür hesabına girmek için yayında geçen gün
EN_AZ_SARKI = 4
EN_AZ_SARKI_TUR = 2
CARPAN_ALT, CARPAN_UST = 0.6, 1.6


def dinlenme_ekle(d: durum.Durum, sayi: int, gun: date | None = None) -> None:
    """Spotify sayacından günlük nokta (aynı gün yeniden ölçülürse üstüne yazar)."""
    gun_s = (gun or date.today()).isoformat()
    seri = [x for x in (d.yayin or {}).get("dinlenme") or [] if x[0] != gun_s]
    seri.append([gun_s, int(sayi)])
    d.yayin = {**(d.yayin or {}), "dinlenme": sorted(seri)[-SERI_SINIRI:]}


def seri(d: durum.Durum) -> list[tuple[date, int]]:
    return [(date.fromisoformat(g), int(n)) for g, n in (d.yayin or {}).get("dinlenme") or []]


def yayin_gunu(d: durum.Durum) -> date | None:
    """Spotify'da ilk görüldüğü gün (takip geçmişinin ilk canlı kaydı)."""
    for g in (d.yayin or {}).get("gecmis") or []:
        if g.get("canli"):
            return datetime.fromisoformat(g["zaman"]).date()
    son = (d.yayin or {}).get("son") or {}
    return datetime.fromisoformat(son["zaman"]).date() if son.get("canli") and son.get("zaman") else None


def gunluk(d: durum.Durum) -> float | None:
    """Son `PENCERE_GUN` günün ortalama günlük dinlenmesi; en az 3 gün aralıklı iki ölçüm gerekir."""
    s = seri(d)
    if len(s) < 2:
        return None
    son_gun, son_sayi = s[-1]
    ilk = next(((g, n) for g, n in s if (son_gun - g).days <= PENCERE_GUN), s[0])
    gun = (son_gun - ilk[0]).days
    if gun < 3:
        return None
    return max(0.0, (son_sayi - ilk[1]) / gun)


def sarki_gunluk(calisma: Path) -> dict[str, float]:
    return {d.kimlik: g for d in durum.hepsi(calisma) if (g := gunluk(d)) is not None}


def _tur(kayit: dict, kimlik: str) -> str | None:
    a = kayit.get(kimlik)
    return (a.turler[0].casefold() if a is not None and a.turler else None)


def tur_tablosu(calisma: Path, kayit: dict | None = None, bugun: date | None = None) -> dict:
    """{"turler": {tür: {"sarki", "gunluk", "carpan"}}, "ortanca", "sarki", "yeterli"}. Tür, orijinal sanatçının
    keşif kaydındaki ilk Deezer türü (keşfin süzdüğü türle aynı dil)."""
    from yanki import kesif

    bugun = bugun or date.today()
    kayit = kesif.oku(calisma) if kayit is None else kayit
    olcum: dict[str, list[float]] = {}
    for d in durum.hepsi(calisma):
        bas, g = yayin_gunu(d), gunluk(d)
        tur = _tur(kayit, d.kimlik)
        if g is None or bas is None or tur is None or (bugun - bas).days < EN_AZ_GUN:
            continue
        olcum.setdefault(tur, []).append(g)
    hepsi = [x for v in olcum.values() for x in v]
    ortanca = statistics.median(hepsi) if hepsi else None
    yeterli = len(hepsi) >= EN_AZ_SARKI and bool(ortanca)
    turler = {}
    for tur, v in olcum.items():
        carpan = 1.0
        if yeterli and len(v) >= EN_AZ_SARKI_TUR:
            carpan = min(CARPAN_UST, max(CARPAN_ALT, (statistics.median(v) / ortanca) ** 0.5))
        turler[tur] = {"sarki": len(v), "gunluk": round(statistics.median(v), 1), "carpan": round(carpan, 2)}
    return {"turler": turler, "ortanca": round(ortanca, 1) if ortanca is not None else None, "sarki": len(hepsi),
            "yeterli": yeterli}


def uygula(kayit: dict, calisma: Path) -> int:
    """Keşif kaydındaki her adaya türünün çarpanı (`Aday.performans`; çarpanı olmayan türe 1 değil None: puan
    değişmez). Değişen aday sayısı."""
    tablo = tur_tablosu(calisma, kayit)["turler"]
    degisen = 0
    for a in kayit.values():
        tur = a.turler[0].casefold() if a.turler else None
        yeni = tablo[tur]["carpan"] if tur in tablo and tablo[tur]["carpan"] != 1.0 else None
        if a.performans != yeni:
            a.performans = yeni
            degisen += 1
    return degisen


def ozet(calisma: Path, kok: Path) -> dict:
    """Odanın performans görünümü: şarkılar (dinlenme, günlük, kazanç), türler, kazanç toplamı."""
    from yanki import kazanc, kesif, takip

    kayit = kesif.oku(calisma)
    rapor = kazanc.sarki_kazanclari(kok, calisma)
    sarkilar = []
    for d in durum.hepsi(calisma):
        if d.asama not in ("yuklendi", "yayinda"):
            continue
        s = seri(d)
        y = takip.yukleme_bilgisi(calisma, d.kimlik) or {}
        k = rapor["sarkilar"].get(d.kimlik) or {}
        bas, gun = yayin_gunu(d), gunluk(d)
        sarkilar.append({"kimlik": d.kimlik, "sanatci": d.sanatci, "ad": d.ad, "asama": d.asama,
                         "tur": _tur(kayit, d.kimlik), "yayin": bas.isoformat() if bas else None,
                         "dinlenme": s[-1][1] if s else None, "gunluk": None if gun is None else round(gun, 1),
                         "seri": [[x.isoformat(), n] for x, n in s[-90:]], "isrc": y.get("isrc"),
                         "kazanc": k.get("tutar"), "kazanc_akis": k.get("akis")})
    sarkilar.sort(key=lambda x: (-(x["gunluk"] or 0), -(x["dinlenme"] or 0), x["ad"]))
    return {"sarkilar": sarkilar, "turler": tur_tablosu(calisma, kayit), "kazanc": rapor["ozet"]}
