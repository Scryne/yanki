"""Şarkı yapısı: zaman damgalı sözlerden ACE-Step bölüm etiketleri.

ACE-Step'te söz bir "zaman senaryosu": [Intro], [Verse 1], [Pre-Chorus], [Chorus], [Bridge], [Instrumental], [Outro]
modelin enerji ve düzenleme planı (motor/ACE-Step-1.5/docs/en/Tutorial.md, "Structure Tags are Key"). Eski etiketleyici
yalnız `♪`/boş satırda kıta bölüp birebir tekrar eden kıtaya [chorus] diyordu; LRCLIB'de kıta arası çoğu kayıtta yok →
31 şarkının 7'sinde bütün şarkı bir-iki [verse], 19'unda hiç [chorus] yoktu (2026-10-11): model nakaratı, köprüyü,
girişi bilmeden baştan sona aynı düzenlemeyi çalıyordu.

Yöntem: satır benzerliğinden tekrar eden satır dizileri (aile) bulunur; dizi bölüm sınırını (boş satır, uzun boşluk)
aşmaz. En çok satırı kaplayan aile nakarattır; şarkının adını taşıyan aile nakaratla komşuysa nakarat odur
(Somewhere Only We Know). Nakarattan hemen önce gelen aile ön nakarat, hemen sonra gelen nakarat sonrası. Tekrar
etmeyen satırlar: nakaratın kelimelerinin çoğunu taşıyorsa nakarat çeşitlemesi (When I Was Your Man'in son nakaratı),
son iki nakarat arasındaysa köprü, son nakarattan sonra çıkış, yoksa kıta. Zaman damgasından: giriş, ara
enstrümantal ve çıkış.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from statistics import median

NOTA = frozenset("♪♫♬♩")
BENZERLIK = 0.8  # iki satır aynı sayılır (nakarat tekrarında küçük yazım farkları: "So," / "So")
BOSLUK_KAT, BOSLUK_EN_AZ_SN = 1.8, 6.0  # satır başları arası tipik aralığın bu katını aşarsa bölüm sınırı
BOSLUK_EN_COK_SN = 15.0  # bundan uzun boşluk her zaman sınır (seyrek sözde tipik aralık büyür)
SATIR_EN_UZUN_SN = 8.0  # sonrasında boş satır yoksa vokalin bittiği an: satır başı + tipik aralık, en çok bu kadar
GIRIS_SN = 5.0  # ilk söz bundan geç başlıyorsa [Intro]
ENSTRUMANTAL_SN = 10.0  # bu kadar uzun vokalsiz ara: [Instrumental]; sonda [Outro]
CESITLEME_ORANI = 0.45  # tekrar etmeyen bölüm nakaratın kelimelerinin bu kadarını taşıyorsa nakarat çeşitlemesi
CIKIS_EN_COK_SATIR = 6
NAKARAT_AILESI = ("Chorus", "Pre-Chorus", "Post-Chorus")
KUNYE_SATIRI = re.compile(r"^\s*(feat\.|ft\.|featuring)", re.IGNORECASE)  # LRCLIB'de sözün başına yazılan künye
_DOLGU = frozenset("that this with your have just like what when will from they them there were been would could "
                   "should about into only then than know cause because over some more ever".split())


def ara_mi(satir: str) -> bool:
    """Boş ya da yalnız nota işaretlerinden oluşan satır: bölüm sınırı, söz değil."""
    s = "".join(satir.split())
    return not s or set(s) <= NOTA


@dataclass(frozen=True)
class Bolum:
    ad: str  # "Verse 1", "Chorus", "Intro"…
    satirlar: tuple[tuple[float | None, str], ...] = ()  # boşsa enstrümantal bölüm
    bas: float | None = None


def _normal(s: str) -> str:
    s = re.sub(r"\([^)]*\)", " ", s.casefold())  # parantez içi arka vokal tekrarlar arasında değişebiliyor
    return " ".join(re.findall(r"[^\W_]+", s))


def _benzer(a: str, b: str) -> bool:
    return bool(a) and bool(b) and (a == b or SequenceMatcher(None, a, b).ratio() >= BENZERLIK)


def _icerik(norm: str) -> set[str]:
    return {w for w in norm.split() if len(w) >= 4 and w not in _DOLGU}


def _zayif(a: str, b: str) -> bool:
    """Çeşitleme eşleşmesi: ortak içerik kelimesi ya da gevşek benzerlik."""
    return bool(_icerik(a) & _icerik(b)) or (bool(a) and bool(b) and SequenceMatcher(None, a, b).ratio() >= 0.6)


def coz(satirlar, sure_sn: float | None = None, ad: str = "") -> list[Bolum]:
    """[(sn | None, satır)] → bölümler. Boş/`♪` satırlar bölüm sınırıdır (ve vokalin bittiği an)."""
    satir: list[tuple[float | None, str]] = []
    sinir: set[int] = set()  # bu indeksli satırdan önce bölüm sınırı var
    bitis: dict[int, float] = {}  # boş satırın damgası: önceki satırın vokali orada biter
    for t, m in satirlar:
        if KUNYE_SATIRI.match(m):
            continue
        if ara_mi(m):
            if satir:
                sinir.add(len(satir))
                if t is not None:
                    bitis.setdefault(len(satir) - 1, float(t))
            continue
        satir.append((None if t is None else float(t), m.strip()))
    if not satir:
        return []
    n = len(satir)
    zamanli = all(t is not None for t, _ in satir)
    tipik = median(b[0] - a[0] for a, b in zip(satir, satir[1:], strict=False)) if zamanli and n > 1 else 4.0
    if zamanli:
        esik = min(max(BOSLUK_EN_AZ_SN, BOSLUK_KAT * tipik), BOSLUK_EN_COK_SN)
        sinir |= {i for i in range(1, n) if satir[i][0] - satir[i - 1][0] > esik}

    def vokal_sonu(i: int) -> float:
        if i in bitis:
            return bitis[i]
        sonraki = satir[i + 1][0] if i + 1 < n else float("inf")
        return min(sonraki, satir[i][0] + min(tipik, SATIR_EN_UZUN_SN))

    norm = [_normal(m) for _, m in satir]
    # kosu[i][j]: i ve j'den başlayan, sınır aşmayan, eşleşen satır dizisinin uzunluğu
    kosu = [[0] * (n + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for j in range(n - 1, -1, -1):
            if i != j and _benzer(norm[i], norm[j]):
                devam = (i + 1 < n and j + 1 < n and (i + 1) not in sinir and (j + 1) not in sinir)
                kosu[i][j] = 1 + (kosu[i + 1][j + 1] if devam else 0)

    aile: list[int | None] = [None] * n
    aileler: list[tuple[int, list[int]]] = []  # (uzunluk, başlangıçlar)

    def tekrarlar(i: int, uz: int) -> list[int]:
        """i'den başlayan uz satırlık dizinin atanmamış, çakışmayan tekrarları (i dahil)."""
        baslar, son = [], -1
        for p in range(n - uz + 1):
            if (p == i or kosu[i][p] >= uz) and p > son and all(aile[p + k] is None for k in range(uz)):
                baslar.append(p)
                son = p + uz - 1
        return baslar

    while True:
        en_iyi = None
        for i in range(n):
            for uz in sorted({kosu[i][p] for p in range(n)} - {0, 1}, reverse=True):
                if any(aile[i + k] is not None for k in range(uz)):
                    continue
                baslar = tekrarlar(i, uz)
                if len(baslar) >= 2 and (en_iyi is None or uz * len(baslar) > en_iyi[0] * len(en_iyi[1])):
                    en_iyi = (uz, baslar)
        if en_iyi is None or en_iyi[0] * len(en_iyi[1]) < 4:
            break
        # Ön nakarat + nakarat arada sınır yoksa tek dizi görünür; dizinin bir başı ya da sonu bu tekrarların dışında
        # da geçiyorsa (ilk nakarattan önceki ön nakarat) o parça ayrı aile olur, kalanı sonraki turda bulunur.
        # Dışarıdaki tekrarın komşu satırı dizinin devamına benziyorsa o bir nakarat çeşitlemesidir, ayrılmaz.
        uz, baslar = en_iyi
        icerde = {p + k for p in baslar for k in range(uz)}

        def cesitleme(p: int, bas: int, parca_uz: int, ilk: int = baslar[0], icerde: set[int] = icerde) -> bool:
            if bas == ilk:  # baş parça: dışarıdakinin ardından gelen satır ↔ dizinin devamı
                q, desen = p + parca_uz, ilk + parca_uz
            else:  # son parça: dışarıdakinden önceki satır ↔ dizide parçadan önceki satır
                q, desen = p - 1, bas - 1
            return 0 <= q < n and q not in icerde and _zayif(norm[q], norm[desen])

        for s in range(uz - 1, 1, -1):
            for bas, parca_uz in ((baslar[0], s), (baslar[0] + uz - s, s)):
                parca = tekrarlar(bas, parca_uz)
                disarida = [p for p in parca if p not in icerde]
                if disarida and len(parca) > len(baslar) and not any(cesitleme(p, bas, parca_uz) for p in disarida):
                    en_iyi = (parca_uz, parca)
                    break
            else:
                continue
            break
        uz, baslar = en_iyi
        for p in baslar:
            for k in range(uz):
                aile[p + k] = len(aileler)
        aileler.append(en_iyi)

    etiket: dict[int, str] = {}
    baslik = _normal(re.sub(r"\(.*?\)|\[.*?\]", " ", ad))
    if aileler:

        def komsu(a: int, b: int) -> bool:  # a ailesinin bir tekrarı b'ninkinden hemen önce/sonra
            (ua, ba), (ub, bb) = aileler[a], aileler[b]
            return any(p + ua == q or q + ub == p for p in ba for q in bb)

        def baslikli(a: int) -> bool:
            uz, baslar = aileler[a]
            return bool(baslik) and any(baslik in norm[baslar[0] + k] for k in range(uz))

        nakarat = 0
        if not baslikli(0):
            nakarat = next((a for a in range(1, len(aileler)) if baslikli(a) and komsu(a, 0)), 0)
        etiket[nakarat] = "Chorus"
        un, bn = aileler[nakarat]
        for a, (ua, ba) in enumerate(aileler):
            if a == nakarat:
                continue
            once = sum(any(p + ua == q for q in bn) for p in ba)
            sonra = sum(any(q + un == p for q in bn) for p in ba)
            etiket[a] = ("Pre-Chorus" if once * 2 >= len(ba) else "Post-Chorus" if sonra * 2 >= len(ba)
                         else "Verse")

        # nakaratın hemen ardından gelen, nakarattaki bir satırın tekrarı nakarata aittir ("…hurts instead" ×2)
        desen = [norm[bn[0] + k] for k in range(un)]
        for p in bn:
            e = p + un
            while e < n and aile[e] is None and e not in sinir and any(_benzer(norm[e], x) for x in desen):
                aile[e] = nakarat
                e += 1

    # yeni bir nakaratın başladığı satırlar (çift nakarat iki bölüm kalır; araya sınır düşen nakarat birleşir)
    nakarat_basi: set[int] = set(bn) if aileler else set()

    # sözlü bölümler: aile tekrarları ve aradaki tekrar etmeyen parçalar (sınırda bölünür)
    parcalar: list[tuple[str | None, list[int]]] = []
    for i in range(n):
        # nakaratla komşu olmayan tekrar (tekrarlanan kıta, sondaki "When I was your man" ×2) yerine göre adlanır
        anahtar = None if aile[i] is None or etiket[aile[i]] == "Verse" else etiket[aile[i]]
        yeni = (not parcalar or i in sinir or aile[i] != aile[i - 1]
                or (aile[i] is not None and i in aileler[aile[i]][1]))
        if yeni:
            parcalar.append((anahtar, [i]))
        else:
            parcalar[-1][1].append(i)

    # nakarat çeşitlemesi: tekrar etmeyen parçada nakaratla sırayla kelime paylaşan satır dizisi ("I hope he buys you
    # flowers" ↔ "That I should've bought you flowers"); en az 3 satır ve nakaratın yarısı
    if aileler:
        nakarat_satir = [norm[bn[0] + k] for k in range(un)]
        yeni_parcalar: list[tuple[str | None, list[int]]] = []
        for e, idx in parcalar:
            en_uzun = (0, 0)  # (uzunluk, parçadaki başlangıç)
            if e is None:
                for s in range(len(idx)):
                    for o in range(un):
                        r = 0
                        while s + r < len(idx) and o + r < un and _zayif(norm[idx[s + r]], nakarat_satir[o + r]):
                            r += 1
                        en_uzun = max(en_uzun, (r, -s))
            r, s = en_uzun[0], -en_uzun[1]
            if r >= 3 and r * 2 >= un:
                nakarat_basi.add(idx[s])
                yeni_parcalar += [x for x in ((None, idx[:s]), ("Chorus", idx[s:s + r]), (None, idx[s + r:])) if x[1]]
            else:
                yeni_parcalar.append((e, idx))
        parcalar = yeni_parcalar

    nakarat_yerleri = [k for k, (e, _) in enumerate(parcalar) if e == "Chorus"]
    adlar: list[str] = []
    for k, (e, idx) in enumerate(parcalar):
        if e is not None:
            adlar.append(e)
            continue
        oncesi = sum(y < k for y in nakarat_yerleri)
        sonda = not any(x in NAKARAT_AILESI for x, _ in parcalar[k + 1:])
        # nakaratın kuyruğu: enstrümantal aradan önceki tek satır ("Oh, take me back to the start") ya da şarkının
        # adını taşıyan kısa parça ("So, why don't we go somewhere only we know?")
        kuyruk = k > 0 and adlar[-1] == "Chorus" and k + 1 < len(parcalar) and (
            (zamanli and len(idx) == 1
             and satir[parcalar[k + 1][1][0]][0] - vokal_sonu(idx[-1]) >= ENSTRUMANTAL_SN)
            or (len(idx) <= 2 and bool(baslik) and any(baslik in norm[i] for i in idx)))
        if kuyruk:
            adlar.append("Chorus")
        elif not nakarat_yerleri or oncesi == 0:
            adlar.append("Verse")
        elif sonda:
            adlar.append("Outro" if len(idx) <= CIKIS_EN_COK_SATIR else "Verse")
        elif oncesi >= 2 and oncesi < len(nakarat_yerleri):
            adlar.append("Bridge")
        else:
            adlar.append("Verse")

    # aynı adlı ardışık parçalar tek bölüm (arada uzun enstrümantal yoksa); nakarat tekrarı (çift nakarat) da
    bolumler: list[Bolum] = []
    kita = 0
    son_bitis = None
    for ad_, (_, idx) in zip(adlar, parcalar, strict=True):
        bas = satir[idx[0]][0]
        ara = zamanli and son_bitis is not None and bas - son_bitis >= ENSTRUMANTAL_SN
        if zamanli and not bolumler and bas >= GIRIS_SN:
            bolumler.append(Bolum("Intro", bas=0.0))
        elif ara:
            bolumler.append(Bolum("Instrumental", bas=round(son_bitis, 2)))
        yeni_satirlar = tuple(satir[i] for i in idx)
        onceki = bolumler[-1] if bolumler else None
        birlesir = ad_ in ("Verse", "Bridge", "Outro") or (ad_ == "Chorus" and idx[0] not in nakarat_basi)
        if onceki and onceki.satirlar and not ara and onceki.ad.split(" ")[0] == ad_ and birlesir:
            bolumler[-1] = Bolum(onceki.ad, onceki.satirlar + yeni_satirlar, onceki.bas)
        else:
            if ad_ == "Verse":
                kita += 1
                ad_ = f"Verse {kita}"
            bolumler.append(Bolum(ad_, yeni_satirlar, bas))
        son_bitis = vokal_sonu(idx[-1]) if zamanli else None
    if zamanli and sure_sn and son_bitis is not None and sure_sn - son_bitis >= ENSTRUMANTAL_SN \
            and bolumler[-1].ad != "Outro":
        bolumler.append(Bolum("Outro", bas=round(son_bitis, 2)))
    return bolumler


def metin(bolumler: list[Bolum]) -> str:
    """ACE-Step söz biçimi: her bölüm etiketiyle, bölümler arasında boş satır."""
    return "\n\n".join(f"[{b.ad}]" + "".join("\n" + m for _, m in b.satirlar) for b in bolumler)


def aralik(bolumler: list[Bolum], bas: float, son: float) -> str:
    """[bas, son) aralığında başlayan satırlar ve enstrümantal bölümler, etiketleriyle (parçalı üretim)."""
    secilen = []
    for b in bolumler:
        if b.satirlar:
            if icinde := tuple(x for x in b.satirlar if x[0] is not None and bas <= x[0] < son):
                secilen.append(Bolum(b.ad, icinde, b.bas))
        elif b.bas is not None and bas <= b.bas < son:
            secilen.append(b)
    return metin(secilen) if any(b.satirlar for b in secilen) else ""
