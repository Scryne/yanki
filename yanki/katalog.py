"""Katalog farkı: başka bir platformda çok dinlenen ama Spotify'da (`market`) çalınamayan ya da hiç olmayan şarkılar.

STILLMORE'a (Spotify istemcisi + lisans) bağlı kalmadan kendi keşfimiz (2026-10-09). Referans katalog Deezer:
herkese açık API anahtarsız, her parçada popülerlik (`rank`) ve ISRC var, coğrafi olarak bu ağda Türkiye listelerini
veriyor. Akış:

1. **Tohum sanatçılar:** `config/kesif.toml` → `[katalog]`: elle yazılanlar (ör. kataloğunu Spotify'dan çektiği
   bilinenler; doğrulamayı hat yapar), Deezer tür listelerinin sanatçıları, Scryne'ın playlist'lerindeki sanatçılar,
   tohumların benzerleri.
2. **Aday parçalar:** her sanatçının Deezer'daki en çok dinlenenleri; `rank` eşiğinin altı ve düzenlemeler atılır.
   Sorma sırası önce kaynağın önceliği (elle tohum → playlist sanatçısı → benzer → tür listesi), sonra `rank`:
   ilk canlı koşuda bütçe tür listelerinin güncel hitlerine gitti, 146'sı Spotify'da vardı (2026-10-09). Deezer
   listeleri IP'ye göre geliyor; bu ağda Fransa listesi döndü.
3. **Spotify'da var mı:** `track:"ad" artist:"sanatçı"` araması (1 istek). Çalınabilir eşleşme → var. Eşleşme var ama
   çalınamıyor → kaldırılmış/kapalı. Eşleşme yoksa Deezer ISRC'siyle ikinci bakış (ad yazımı farklı olabilir).
4. Sonuç `calisma/kesif/katalog.json`'da önbellek: sorulan parça `tazeleme_gun` boyunca yeniden sorulmaz.
   Spotify istekleri koşu başına `butce` ile sınırlı (sınırlar sert, bkz. `spotify.py`).

Bulunan adaylar `kesif.Aday` olarak keşfin geri kalanına (rakip sayımı, YouTube talebi, söz kontrolü) girer.
"""

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path

from yanki import ag
from yanki.kesif import DUZENLEME, Aday, _duz, sade_ad, sade_ad_gorunur

DEEZER = "https://api.deezer.com"


class DeezerHatasi(RuntimeError):
    pass


def deezer(yol: str, parametre: dict | None = None, json_al=ag.json_al) -> dict:
    """Deezer hatayı 200 içinde döndürür: kod 4 kota (50 istek / 5 sn) → bekle, 800 bulunamadı."""
    for _ in range(3):
        d = json_al(DEEZER + yol, parametre)
        hata = d.get("error") if isinstance(d, dict) else None
        if not hata:
            return d
        if hata.get("code") == 4:
            time.sleep(5)
            continue
        if hata.get("code") == 800:
            raise ag.Bulunamadi(yol)
        raise DeezerHatasi(f"{yol}: {hata}")
    raise DeezerHatasi(f"{yol}: kota aşıldı")


@dataclass
class Parca:
    deezer_id: int
    sanatci: str
    ad: str
    rank: int
    sure_sn: int | None = None
    oncelik: int = 3  # 0 elle tohum, 1 playlist sanatçısı, 2 benzer, 3 tür listesi


@dataclass
class Kontrol:
    durum: str  # "var" | "kapali" | "yok"
    zaman: str
    sanatci: str
    ad: str
    rank: int
    spotify_id: str | None = None
    kapali_pazarlar: list | None = None


# ── Deezer ──────────────────────────────────────────────────
def sanatci_bul(ad: str, json_al=ag.json_al) -> dict | None:
    """Adı birebir (aksansız, büyük/küçük harfsiz) eşleşenlerden en çok hayranlısı; yoksa None (yanlış sanatçı tahmini
    yok). İlk eşleşen alınmaz: 2026-10-26 "Michael Jackson" araması önce 227 hayranlı adaşı (rap single) döndürdü."""
    eslesen = [a for a in deezer("/search/artist", {"q": ad, "limit": 5}, json_al).get("data") or []
               if _duz(a.get("name") or "") == _duz(ad)]
    return max(eslesen, key=lambda a: a.get("nb_fan") or 0, default=None)


def liste_sanatcilari(tur: int, adet: int, json_al=ag.json_al) -> list[dict]:
    return (deezer(f"/chart/{tur}/artists", {"limit": adet}, json_al).get("data") or [])[:adet]


def benzerler(sanatci_id: int, adet: int, json_al=ag.json_al) -> list[dict]:
    return (deezer(f"/artist/{sanatci_id}/related", {"limit": adet}, json_al).get("data") or [])[:adet]


def en_cok_dinlenenler(sanatci: dict, adet: int, json_al=ag.json_al) -> list[Parca]:
    veri = deezer(f"/artist/{sanatci['id']}/top", {"limit": adet}, json_al).get("data") or []
    return [Parca(t["id"], (t.get("artist") or {}).get("name") or sanatci["name"], t.get("title_short") or t["title"],
                  int(t.get("rank") or 0), t.get("duration")) for t in veri if t.get("id") and t.get("title")]


FILM = re.compile(r"\bfilm|\bgames?\b|soundtrack", re.I)


def sanatci_turleri(ad: str, json_al=ag.json_al, album_adet: int = 3) -> list[str]:
    """Sanatçının Deezer'daki son albümlerinin türleri, sıklık sırasıyla ("Rap/Hip Hop" → "rap, hip hop").
    MusicBrainz'de türü olmayan sanatçılar için stil yedeği (2026-10-09: keşiften gelen üç rap şarkısında MusicBrainz
    boş, stil yalnız "clean modern studio recording" kalıyordu)."""
    from collections import Counter

    a = sanatci_bul(ad, json_al)
    if a is None:
        return []
    sayac: Counter = Counter()
    for alb in (deezer(f"/artist/{a['id']}/albums", {"limit": album_adet}, json_al).get("data") or [])[:album_adet]:
        try:
            turler = (deezer(f"/album/{alb['id']}", None, json_al).get("genres") or {}).get("data") or []
        except ag.Bulunamadi:
            continue
        sayac.update(t["name"] for t in turler if t.get("name"))
    # Film/oyun türü albümün soundtrack olduğunu söyler, sanatçının türünü değil (2026-10-26: Ariana Grande'nin son iki
    # albümü Wicked soundtrack'i, "films, games" haric türüne düştü). Başka tür yoksa sayılır: soundtrack sanatçısı.
    if any(not FILM.search(t) for t in sayac):
        sayac = Counter({t: n for t, n in sayac.items() if not FILM.search(t)})
    return [", ".join(p.strip().lower() for p in ad_.split("/")) for ad_, _ in sayac.most_common(2)]


def isrc(deezer_id: int, json_al=ag.json_al) -> str | None:
    try:
        return (deezer(f"/track/{deezer_id}", None, json_al).get("isrc") or "").upper() or None
    except ag.Bulunamadi:
        return None


# ── Spotify karşılaştırması ─────────────────────────────────
def _eslesir(t: dict, sade: str, sanatci: str) -> bool:
    return sade_ad(t.get("name") or "") == sade and any(
        _duz(a.get("name") or "") == _duz(sanatci) for a in t.get("artists") or [])


def spotify_durumu(sp, p: Parca, pazarlar, json_al=ag.json_al) -> tuple[str, str | None, list[str]]:
    """(durum, Spotify kimliği, kapalı pazarlar). Aramalar ana pazarda; ana pazarda kapalı çıkan parçanın diğer
    pazarları tek tek sorulur (global: bir pazarda açık olması boşluğu o pazar için kapatır)."""
    from yanki.kesif import kapali_pazarlar

    if isinstance(pazarlar, str):
        pazarlar = (pazarlar,)
    market = pazarlar[0]
    sade = sade_ad(p.ad)
    # aramada özgün ad (kesme işareti/aksan Spotify eşleşmesi için gerekli: "C'est" ≠ "c est"), karşılaştırmada sade
    sonuc = sp.ara(f'track:"{sade_ad_gorunur(p.ad)}" artist:"{p.sanatci}"', market, adet=5)
    eslesen = [t for t in sonuc if _eslesir(t, sade, p.sanatci)]
    if not eslesen:  # ad yazımı farklı olabilir: Deezer ISRC'siyle ikinci bakış
        kod = isrc(p.deezer_id, json_al)
        eslesen = sp.isrc_ara(kod, market) if kod else []
    if any(t.get("is_playable") is not False for t in eslesen):
        return "var", None, []
    if eslesen:
        sid = eslesen[0].get("id")
        kapali = kapali_pazarlar(sp, sid, pazarlar, bilinen_kapali=(market,))
        return ("kapali" if kapali else "var"), sid, kapali
    return "yok", None, list(pazarlar)


# ── Önbellek ────────────────────────────────────────────────
def onbellek_yolu(calisma: Path) -> Path:
    return calisma / "kesif" / "katalog.json"


def onbellek_oku(calisma: Path) -> dict[str, Kontrol]:
    yol = onbellek_yolu(calisma)
    if not yol.exists():
        return {}
    return {k: Kontrol(**v) for k, v in json.loads(yol.read_text(encoding="utf-8")).items()}


def onbellek_yaz(calisma: Path, kayit: dict[str, Kontrol]) -> None:
    from yanki import dosya

    dosya.json_yaz(onbellek_yolu(calisma), {k: asdict(v) for k, v in kayit.items()}, indent=1)


def taze_mi(k: Kontrol, gun: int, simdi: datetime) -> bool:
    """Her durum `gun` sonra yeniden sorulur: "var" kalkmış olabilir, "kapalı/yok" geri gelmiş olabilir."""
    return datetime.fromisoformat(k.zaman) > simdi - timedelta(days=gun)


# ── Tarama ──────────────────────────────────────────────────
@dataclass
class Ayar:
    tohumlar: tuple[str, ...] = ()
    liste_turleri: tuple[int, ...] = (0,)
    liste_adet: int = 30
    benzer_adet: int = 5
    parca_adet: int = 15
    min_rank: int = 200_000
    butce: int = 150
    tazeleme_gun: int = 30

    @classmethod
    def oku(cls, d: dict) -> "Ayar":
        return cls(tuple(d.get("tohumlar", ())), tuple(d.get("liste_turleri", (0,))), int(d.get("liste_adet", 30)),
                   int(d.get("benzer_adet", 5)), int(d.get("parca_adet", 15)), int(d.get("min_rank", 200_000)),
                   int(d.get("butce", 150)), int(d.get("tazeleme_gun", 30)))


def sanatcilar(ayar: Ayar, ek_adlar: list[str], json_al=ag.json_al, bildir=print) -> list[tuple[dict, int]]:
    """(Deezer sanatçısı, öncelik): elle tohumlar 0, playlist sanatçıları 1, benzerleri 2, tür listeleri 3."""
    gorulen: dict[int, tuple[dict, int]] = {}
    tohumlar = []
    for oncelik, adlar in ((0, ayar.tohumlar), (1, ek_adlar)):
        for ad in dict.fromkeys(adlar):
            a = sanatci_bul(ad, json_al)
            if a is None:
                bildir(f"  Deezer'da bulunamadı: {ad}")
                continue
            if a["id"] not in gorulen:
                gorulen[a["id"]] = (a, oncelik)
                tohumlar.append(a)
    for a in tohumlar[:20] if ayar.benzer_adet else []:  # benzer genişletme tohum başına bir istek
        for b in benzerler(a["id"], ayar.benzer_adet, json_al):
            gorulen.setdefault(b["id"], (b, 2))
    for tur in ayar.liste_turleri:
        for a in liste_sanatcilari(tur, ayar.liste_adet, json_al):
            gorulen.setdefault(a["id"], (a, 3))
    return list(gorulen.values())


def tara(sp, calisma: Path, pazarlar, ayar: Ayar, ek_adlar: list[str] | None = None, json_al=ag.json_al,
         bildir=print, simdi: datetime | None = None) -> list[Aday]:
    simdi = simdi or datetime.now()
    kayit = onbellek_oku(calisma)
    havuz: dict[int, Parca] = {}
    liste = sanatcilar(ayar, ek_adlar or [], json_al, bildir)
    for a, oncelik in liste:
        for p in en_cok_dinlenenler(a, ayar.parca_adet, json_al):
            # elle tohumlarda rank eşiği yok: kataloğunu çeken sanatçının Deezer'daki dinlenmesi de düşebilir
            if (p.rank >= ayar.min_rank or oncelik == 0) and not DUZENLEME.search(p.ad):
                p.oncelik = oncelik
                havuz.setdefault(p.deezer_id, p)
    sirali = sorted(havuz.values(), key=lambda p: (p.oncelik, -p.rank))
    sorulacak = [p for p in sirali if not (str(p.deezer_id) in kayit and taze_mi(kayit[str(p.deezer_id)],
                                                                                    ayar.tazeleme_gun, simdi))]
    bildir(f"katalog: {len(liste)} sanatçı, {len(sirali)} parça (rank ≥ {ayar.min_rank:,}), "
           f"{len(sorulacak)} sorulacak, bütçe {ayar.butce} Spotify isteği")
    from yanki.spotify import Sinirli, SpotifyHatasi

    baslangic = sp.istek_sayisi
    try:
        for p in sorulacak:
            # parça başı en kötü: ad + ISRC araması + kapalıysa her pazar
            if sp.istek_sayisi - baslangic + 2 + len(pazarlar) > ayar.butce:
                break
            durum, sid, kapali = spotify_durumu(sp, p, pazarlar, json_al)
            kayit[str(p.deezer_id)] = Kontrol(durum, simdi.isoformat(timespec="seconds"), p.sanatci, p.ad, p.rank, sid,
                                              kapali)
    except Sinirli as e:
        bildir(f"✗ {e}; o ana kadarki sonuçlar kaydedildi")
    except SpotifyHatasi as e:  # tek parçanın 404'ü / art arda 5xx: o ana kadarki istekler boşa gitmesin
        bildir(f"✗ Spotify: {e}; o ana kadarki sonuçlar kaydedildi")
    finally:  # Deezer'ın ağ/kota hatası da yükselir: harcanan Spotify istekleri yine kayda geçsin
        onbellek_yaz(calisma, kayit)
    from yanki.kesif import neden_sec

    adaylar = []
    for k_id, k in kayit.items():
        if k.durum in ("kapali", "yok"):
            kapali = k.kapali_pazarlar if k.kapali_pazarlar is not None else list(pazarlar)
            adaylar.append(Aday(k.sanatci, k.ad, f"deezer:{k_id}", spotify_id=k.spotify_id,
                                neden="spotify_yok" if k.durum == "yok" else neden_sec(kapali, pazarlar),
                                bakilan_pazarlar=list(pazarlar), kapali_pazarlar=kapali))
    bildir(f"katalog: bu koşuda {sp.istek_sayisi - baslangic} Spotify isteği; önbellekte {len(kayit)} parça, "
           f"{len(adaylar)} aday (Spotify'da kapalı/yok)")
    return adaylar


# ── Popüler şarkılar ────────────────────────────────────────
# Scryne (2026-10-13): "kaldırılmamış bile olsa elimizdeki şarkı üretmenin en iyi sonuç verdiği tarzda popüler
# şarkılar üret; üretim kapsamını olabildiğince genişlet". Kaynak Deezer'ın tür listeleri (editörlerin seçtiği,
# anahtarsız, her parçada `rank`); sorgular kulaktan geçen türlerden (S31: balad/pop, rock, metal, pop-punk, country).
@dataclass
class PopulerAyar:
    sorgular: tuple[str, ...] = ()
    liste_basina: int = 2
    min_rank: int = 400_000
    yeni_aday: int = 60

    @classmethod
    def oku(cls, d: dict) -> "PopulerAyar":
        return cls(tuple(d.get("sorgular", ())), int(d.get("liste_basina", 2)), int(d.get("min_rank", 400_000)),
                   int(d.get("yeni_aday", 60)))


def _editor_once(liste: dict) -> bool:
    """Deezer editörünün listesi mi ("Rod - Deezer Rock Editor"): seçilmiş ve güncel; kullanıcı listeleri karışık."""
    return "deezer" not in ((liste.get("user") or {}).get("name") or "").casefold()


def populer(ayar: PopulerAyar, pazarlar, bilinen: set[str], json_al=ag.json_al, bildir=print) -> list[Aday]:
    """Sorgulardaki Deezer listelerinin parçaları → popüler aday (`neden="populer"`). Kayıtta olan (`bilinen`
    kimlikler) atlanır; en çok `yeni_aday` yeni aday, `rank` sırasıyla (ücretsiz ölçümler aday başına saniyeler)."""
    havuz: dict[str, tuple[int, Aday]] = {}
    for sorgu in ayar.sorgular:
        try:
            listeler = deezer("/search/playlist", {"q": sorgu, "limit": 10}, json_al).get("data") or []
        except (ag.Bulunamadi, DeezerHatasi) as e:
            bildir(f"  Deezer listesi aranamadı ({sorgu}): {e}")
            continue
        for liste_ in sorted(listeler, key=_editor_once)[: ayar.liste_basina]:
            try:
                parcalar = deezer(f"/playlist/{liste_['id']}/tracks", {"limit": 100}, json_al).get("data") or []
            except (ag.Bulunamadi, DeezerHatasi):
                continue
            for t in parcalar:
                sanatci, ad = (t.get("artist") or {}).get("name"), t.get("title_short") or t.get("title")
                rank = int(t.get("rank") or 0)
                if not (t.get("id") and sanatci and ad) or rank < ayar.min_rank or DUZENLEME.search(ad):
                    continue
                a = Aday(sanatci, ad, f"deezer-populer:{t['id']}", neden="populer", bakilan_pazarlar=list(pazarlar),
                         kapali_pazarlar=[], geri_geldi=False)
                if a.kimlik not in bilinen and (a.kimlik not in havuz or havuz[a.kimlik][0] < rank):
                    havuz[a.kimlik] = (rank, a)
    secilen = [a for _, a in sorted(havuz.values(), key=lambda x: -x[0])][: ayar.yeni_aday]
    bildir(f"popüler: {len(ayar.sorgular)} sorgu, {len(havuz)} yeni parça (rank ≥ {ayar.min_rank:,}); "
           f"bu koşuda {len(secilen)} ölçülecek")
    return secilen
