"""Sözler: Scryne'ın söz dosyası → LRCLIB → yok.

ACE-Step söz olmadan anlamsız vokal üretiyor (spike S1); söz bulunamayan şarkı hazırlıkta durur.

LRCLIB enstrümantal araları `♪` satırıyla yazıyor, düz sözde kıtalar arasında boş satır yok. `♪` modele söz olarak
gidip şarkı tek `[verse]` olunca söz WER'i 0,099; `♪`'ta kıta bölüp nakaratı etiketleyince 0,042 (S12; Scryne
dinledi: "gayet güzel"). Bölüm yapısı (giriş, kıta, ön nakarat, nakarat, köprü, ara, çıkış) `yapi.coz`'dan.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from yanki import ag, yapi

LRCLIB = "https://lrclib.net/api"


@dataclass(frozen=True)
class Soz:
    metin: str  # ACE-Step biçimi: [Verse 1]/[Chorus]/[Bridge]… etiketli bölümler (`yapi`)
    kaynak: str  # "dosya" | "lrclib"
    sure_sn: float | None  # LRCLIB'deki kaydın süresi; kaynak sesi doğrulamak için
    # zaman damgalı satırlar [(sn, metin)]; parçalı üretimde sözleri parçalara dağıtmak için (LRCLIB syncedLyrics)
    satirlar: tuple[tuple[float, str], ...] = field(default=())


_ara_mi = yapi.ara_mi


def etiketle(duz: str, ad: str = "") -> str:
    """Etiketsiz söze bölüm etiketleri (`yapi.coz`: nakarat, ön nakarat, köprü…). `♪`/boş satırlar bölüm sınırıdır.
    Var olan etiketlere dokunmaz (yalnız `♪` satırlarını çıkarır): Scryne'ın elle etiketlediği söz esastır."""
    satirlar = duz.replace("\r", "").split("\n")
    if "[" in duz and "]" in duz.split("\n", 1)[0]:
        return "\n".join(x for x in satirlar if not x.strip() or not _ara_mi(x)).strip()
    return yapi.metin(yapi.coz([(None, x) for x in satirlar], ad=ad))


def aralik_sozu(satirlar: list[tuple[float, str]], bas: float, son: float, sure_sn: float | None = None,
                ad: str = "") -> str:
    """[bas, son) aralığında başlayan satırlar ve enstrümantal bölümler, bölüm etiketleriyle; aralıkta söz yoksa boş."""
    return yapi.aralik(yapi.coz(satirlar, sure_sn, ad), bas, son)


def nakarat_gecisleri(satirlar) -> list[float]:
    """Nakaratın ilk satırının geçtiği anlar: en az 3 kez tekrarlanan satırlardan şarkıda en erken gelen. Kıta tabanlı
    [chorus] etiketi 15 şarkının 12'sinde nakaratı bulamadı (LRCLIB'de kıta arası `♪` çoğu kayıtta yok); bu kural 15'te
    15 buldu (2026-10-08)."""
    temiz = [(float(t), s.strip().lower()) for t, s in satirlar if not _ara_mi(s)]
    sayim: dict[str, int] = {}
    for _, s in temiz:
        sayim[s] = sayim.get(s, 0) + 1
    ilk = next((s for _, s in temiz if sayim[s] >= 3), None)
    return [t for t, s in temiz if s == ilk] if ilk else []


def kesitler(satirlar, sure_sn: float | None, uzunluk: float = 30.0, on_pay: float = 1.0,
             kume_arasi: float = 25.0) -> list[dict]:
    """Hızlı dinleme kesitleri, kaynağın zaman damgalarıyla (parçalı üretim kaynağın zamanlamasını izler): ilk kıta,
    ilk nakarat, son nakarat. Son nakarat, son geçişten geriye `kume_arasi`'ndan kısa aralıklarla gelen geçişlerin
    ilki (nakarat içinde tekrarlanan satır ayrı nakarat sayılmasın). Çakışmada önceki kesit kısalır; yarıdan kısa
    kalacaksa yeni kesit atlanır."""
    temiz = [float(t) for t, s in satirlar if not _ara_mi(s)]
    if not temiz:
        return []
    gecis = nakarat_gecisleri(satirlar)
    son = len(gecis) - 1
    while son > 0 and gecis[son] - gecis[son - 1] < kume_arasi:
        son -= 1
    adaylar = [("ilk_kita", "İlk kıta", temiz[0])]
    if gecis:
        adaylar += [("nakarat", "Nakarat", gecis[0]), ("son_nakarat", "Son nakarat", gecis[son])]
    sonuc: list[dict] = []
    for kimlik, ad, t in adaylar:
        bas = max(0.0, t - on_pay)
        bitis = bas + uzunluk if sure_sn is None else min(float(sure_sn), bas + uzunluk)
        if bitis - bas < uzunluk / 2:
            continue
        if sonuc and bas < sonuc[-1]["son"]:
            if bas - sonuc[-1]["bas"] < uzunluk / 2:
                continue
            sonuc[-1]["son"] = round(bas, 2)
        sonuc.append({"kimlik": kimlik, "ad": ad, "bas": round(bas, 2), "son": round(bitis, 2)})
    return sonuc


def senkron(lrc: str | None) -> tuple[tuple[float, str], ...]:
    satirlar = []
    for satir in (lrc or "").splitlines():
        if m := re.match(r"\[(\d+):(\d+(?:\.\d+)?)\]\s*(.*)", satir.strip()):
            satirlar.append((round(int(m.group(1)) * 60 + float(m.group(2)), 2), m.group(3).strip()))
    return tuple(satirlar)


def _sozcukler(s: str) -> tuple[str, ...]:
    """Büyük/küçük harf, aksan ve noktalama yok sayılmış sözcükler ("Beyoncé" = "BEYONCE")."""
    import unicodedata

    s = unicodedata.normalize("NFKD", s.casefold())
    return tuple(re.findall(r"[^\W_]+", "".join(c for c in s if not unicodedata.combining(c))))


def ayni_sanatci(aranan: str, bulunan: str) -> bool:
    """`bulunan` sanatçı alanı aranan sanatçıyı bütün sözcükleriyle, art arda içeriyor mu ("Adele" ⊂ "Adele feat. X";
    "A" ⊄ "Karaoke Hits Band")."""
    a, b = _sozcukler(aranan), _sozcukler(bulunan)
    return bool(a) and any(b[i: i + len(a)] == a for i in range(len(b) - len(a) + 1))


def lrclib(sanatci: str, ad: str, json_al=ag.json_al) -> Soz:
    try:
        d = json_al(f"{LRCLIB}/get", {"artist_name": sanatci, "track_name": ad})
    except ag.Bulunamadi:
        bulunan = json_al(f"{LRCLIB}/search", {"artist_name": sanatci, "track_name": ad})
        # arama başka sanatçının (karaoke, cover) kaydını da döndürüyor: ilk sonuç doğrulanmadan alınmaz
        bulunan = [b for b in bulunan if b.get("plainLyrics") and not b.get("instrumental")
                   and ayni_sanatci(sanatci, b.get("artistName") or "")]
        if not bulunan:
            raise ag.Bulunamadi(f"LRCLIB'de söz yok: {sanatci} — {ad}") from None
        d = bulunan[0]
    if d.get("instrumental") or not (d.get("plainLyrics") or "").strip():
        raise ag.Bulunamadi(f"LRCLIB kaydı sözsüz: {sanatci} — {ad}")
    sure = float(d["duration"]) if d.get("duration") else None
    satirlar = senkron(d.get("syncedLyrics"))
    # zaman damgası varsa yapı ondan (boşluklar bölüm sınırı, giriş/ara/çıkış); yoksa düz sözün tekrarlarından
    metin = yapi.metin(yapi.coz(satirlar, sure, ad)) if satirlar else etiketle(d["plainLyrics"], ad)
    return Soz(metin, "lrclib", sure, satirlar)


def bul(sanatci: str, ad: str, dosya: Path, json_al=ag.json_al) -> Soz:
    """Scryne `girdi/sozler/<kimlik>.txt` bıraktıysa o esastır."""
    if dosya.exists() and dosya.read_text(encoding="utf-8").strip():
        # Scryne'ın sözü esastır; LRCLIB yalnız süre ve zaman damgaları için. Damgalar ancak satırlar büyük ölçüde
        # aynıysa kullanılır (farklı bir söz metnini LRCLIB zamanlarına dağıtmak yanlış parçaya söz koyar).
        metin = etiketle(dosya.read_text(encoding="utf-8"), ad)
        sure, satirlar = None, ()
        try:
            uzak = lrclib(sanatci, ad, json_al)
            sure = uzak.sure_sn
            benim = {_sade(x) for x in metin.splitlines() if x.strip() and not x.startswith("[")}
            onlarin = {_sade(m) for _, m in uzak.satirlar if m.strip()}
            if benim and onlarin and len(benim & onlarin) / len(benim) >= 0.8:
                satirlar = uzak.satirlar
        except (ag.Bulunamadi, OSError, ValueError, KeyError):  # LRCLIB yalnız yardımcı: düşerse söz dosyası yeter
            pass
        return Soz(metin, "dosya", sure, satirlar)
    return lrclib(sanatci, ad, json_al)


def _sade(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()
