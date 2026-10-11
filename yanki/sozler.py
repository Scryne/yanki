"""Sözler: Scryne'ın söz dosyası → LRCLIB → yok.

ACE-Step söz olmadan anlamsız vokal üretiyor (spike S1); söz bulunamayan şarkı hazırlıkta durur.

LRCLIB enstrümantal araları `♪` satırıyla yazıyor, düz sözde kıtalar arasında boş satır yok. `♪` modele söz olarak
gidip şarkı tek `[verse]` olunca söz WER'i 0,099; `♪`'ta kıta bölüp nakaratı etiketleyince 0,042 (S12; Scryne
dinledi: "gayet güzel").
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

from yanki import ag

LRCLIB = "https://lrclib.net/api"
NOTA = frozenset("♪♫♬♩")


@dataclass(frozen=True)
class Soz:
    metin: str  # ACE-Step biçimi: [verse]/[chorus] etiketli kıtalar
    kaynak: str  # "dosya" | "lrclib"
    sure_sn: float | None  # LRCLIB'deki kaydın süresi; kaynak sesi doğrulamak için
    # zaman damgalı satırlar [(sn, metin)]; parçalı üretimde sözleri parçalara dağıtmak için (LRCLIB syncedLyrics)
    satirlar: tuple[tuple[float, str], ...] = field(default=())


def _ara_mi(satir: str) -> bool:
    """Boş ya da yalnız nota işaretlerinden oluşan satır: kıta sınırı, söz değil."""
    s = "".join(satir.split())
    return not s or set(s) <= NOTA


def etiketle(duz: str) -> str:
    """Kıtaları etiketler: birden çok geçen kıta [chorus], diğerleri [verse]. `♪` satırları kıta sınırıdır.
    Var olan etiketlere dokunmaz (yalnız `♪` satırlarını çıkarır)."""
    satirlar = duz.replace("\r", "").split("\n")
    if "[" in duz and "]" in duz.split("\n", 1)[0]:
        return "\n".join(x for x in satirlar if not x.strip() or not _ara_mi(x)).strip()
    duz = "\n".join("" if _ara_mi(x) else x for x in satirlar)
    kitalar = [k.strip() for k in duz.split("\n\n") if k.strip()]
    tekrar = {k for k in kitalar if kitalar.count(k) > 1}
    return "\n\n".join(("[chorus]" if k in tekrar else "[verse]") + "\n" + k for k in kitalar)


def bolumler(satirlar: list[tuple[float, str]]) -> list[tuple[str, list[tuple[float, str]]]]:
    """Zaman damgalı satırları `♪`/boş satırda kıtalara böler; birden çok geçen kıta [chorus], diğerleri [verse]."""
    kitalar, kita = [], []
    for t, m in satirlar:
        if _ara_mi(m):
            if kita:
                kitalar.append(kita)
            kita = []
        else:
            kita.append((t, m.strip()))
    if kita:
        kitalar.append(kita)
    metinler = [tuple(m for _, m in k) for k in kitalar]
    tekrar = {k for k in metinler if metinler.count(k) > 1}
    return [("[chorus]" if mt in tekrar else "[verse]", k) for k, mt in zip(kitalar, metinler, strict=True)]


def aralik_sozu(satirlar: list[tuple[float, str]], bas: float, son: float) -> str:
    """[bas, son) aralığında başlayan satırlar, bölüm etiketleriyle; aralıkta söz yoksa boş."""
    bloklar = []
    for etiket, kita in bolumler(satirlar):
        if icinde := [m for t, m in kita if bas <= t < son]:
            bloklar.append(etiket + "\n" + "\n".join(icinde))
    return "\n\n".join(bloklar)


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
    return Soz(etiketle(d["plainLyrics"]), "lrclib", float(d["duration"]) if d.get("duration") else None,
               senkron(d.get("syncedLyrics")))


def bul(sanatci: str, ad: str, dosya: Path, json_al=ag.json_al) -> Soz:
    """Scryne `girdi/sozler/<kimlik>.txt` bıraktıysa o esastır."""
    if dosya.exists() and dosya.read_text(encoding="utf-8").strip():
        # Scryne'ın sözü esastır; LRCLIB yalnız süre ve zaman damgaları için. Damgalar ancak satırlar büyük ölçüde
        # aynıysa kullanılır (farklı bir söz metnini LRCLIB zamanlarına dağıtmak yanlış parçaya söz koyar).
        metin = etiketle(dosya.read_text(encoding="utf-8"))
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
