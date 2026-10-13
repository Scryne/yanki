"""Kaldırılmış şarkı keşfi: Spotify'dan kalkmış, hâlâ aranan şarkılar → cover adayı.

Fikir (Scryne, 2026-10-09): kaldırılan bir şarkıyı arayan dinleyici Spotify'da onu bulamıyor; o şarkının cover'ı
aramada ilk sıraya çıkar. Fikrin kaynağı STILLMORE FINDER'ın playlist "kaldırılmış şarkı bulucu"su
(github.com/Caferlyy/distro-finder-bulmaca); Yanki onu kendi hattına bağlar ve üstüne iki adım ekler:

1. **Bulma:** STILLMORE'un playlist taraması ("Kaldırılmış şarkıları bul → CSV indir"; Spotify istemcisinin içinden
   her playlist'i okur) ya da Web API ile Scryne'ın kendi/ortak playlist'leri (Şubat 2026'dan beri API başkasının
   playlist'ini vermiyor). Spotify kaldırılmış parçayı listede gri bırakır: `is_playable: false`.
2. **Boşluk doğrulama:** aynı şarkı başka bir sürümle geri gelmiş mi (aynı ISRC ya da aynı sanatçı + aynı ad çalınabilir
   durumda)? Geri geldiyse boşluk yok, aday düşer. Aynı adlı çalınabilir başka parçalar (başka cover'lar) sayılır.
3. **Talep:** YouTube'daki en çok izlenen orijinal yüklemenin izlenme sayısı (anahtarsız, hat zaten yt-dlp kullanıyor).
   STILLMORE CSV'sinde Spotify dinlenme sayısı varsa o da tutulur.

Sıra: izlenme / (1 + rakip cover sayısı); hattın yapamadığı türdeki aday (Deezer sanatçı türlerinden; liste
`config/kesif.toml` → `[kesif] haric_turler`) puan almaz, dinleme odasından elle eklenebilir. Formül kasıtlı olarak
basit; ilk yayınların arama sırası ölçüldükçe (`yanki takip`) düzeltilir. Sonuç `calisma/kesif/adaylar.json`;
listeye ekleme açık bir adım (`--ekle N`).
"""

import csv
import functools
import io
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from yanki import liste

PARANTEZ = re.compile(r"\s*[\(\[][^)\]]*[\)\]]")
# Şarkı değil düzenleme: cover'ı yapılmaz (2026-10-09, Scryne'ın playlist'lerindeki 70 çalınamayanın ~10'u böyleydi)
DUZENLEME = re.compile(r"\b(sped ?up|speed ?up|slowed|reverb|bass ?boost(ed)?|nightcore|8d audio|remix|tik ?tok|"
                       r"mashup|edit audio|phonk edit|final set)\b", re.I)
EK = re.compile(r"\s+-\s+.*$")  # "Song - Remastered 2011", "Song - From the film ..."


def _duz(s: str) -> str:
    s = unicodedata.normalize("NFKD", s.replace("ı", "i").replace("İ", "I")).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def sade_ad(ad: str) -> str:
    """Parça adlarını karşılaştırmak için: parantez/köşeli ekler ve ' - …' sonekleri atılır, küçük harf, aksansız."""
    return _duz(EK.sub("", PARANTEZ.sub("", ad)))


@dataclass
class Aday:
    sanatci: str
    ad: str
    kaynak: str  # "playlist:<id>" | "stillmore:<dosya>" | "deezer:<id>"
    spotify_id: str | None = None
    isrc: str | None = None
    album: str | None = None
    cikis: str | None = None
    # "kaldirildi": bakılan her pazarda kapalı | "kismi": bazılarında | "spotify_yok": katalogda hiç yok |
    # "populer": Spotify'da duruyor, hattın iyi yaptığı türde çok dinlenen şarkı (katalog.populer; Scryne 2026-10-13:
    # "kaldırılmamış bile olsa ... en iyi sonuç verdiği tarzda popüler şarkılar üret")
    neden: str = "kaldirildi"
    bakilan_pazarlar: list = field(default_factory=list)
    kapali_pazarlar: list = field(default_factory=list)
    spotify_dinlenme: int | None = None  # STILLMORE CSV'sinden (kaldırılmadan önceki toplam)
    youtube_izlenme: int | None = None
    youtube_baslik: str | None = None
    youtube_id: str | None = None  # dinleme odasında "Dinle" bağlantısı
    youtube_kanit: list = field(default_factory=list)  # ilk 5 sonuç {title, channel, views}: özgünlük kararının kanıtı
    ozgunluk: dict | None = None  # Jev kararı (yanki/yargi.py), model sürümüyle dondurulmuş
    # YouTube'daki en çok izlenen yüklemede listedeki sanatçı geçiyor mu. Geçmiyorsa takma adla yüklenmiş bir sızıntı
    # ya da taklit olabilir (2026-10-09: "Lizzy Rey", "Del" adıyla Lana Del Rey sızıntıları) → listeye eklenmez
    sanatci_uyusuyor: bool | None = None
    soz_var: bool | None = None  # LRCLIB'de sözlü kayıt
    ingilizce: bool | None = None  # LRCLIB sözü ağırlıkla İngilizce mi (popüler adaylar yalnız İngilizce)
    sure_sn: float | None = None
    geri_geldi: bool | None = None  # None: doğrulanmadı
    geri_gelen: list = field(default_factory=list)  # [{"id", "sanatci", "ad", "neden": "isrc"|"ad"}]
    rakip_cover: int | None = None
    # sanatçının Deezer türleri ("rap, hip hop"); hattın yapamadığı tür kendiliğinden listeye girmez (`uygun`)
    turler: list | None = None
    kontrol: str | None = None  # Spotify doğrulamasının zamanı
    olcum: str | None = None  # ücretsiz ölçümlerin (YouTube, LRCLIB) zamanı
    ilk_gorulme: str | None = None
    elendi: bool = False  # Scryne dinleme odasında eledi: listeye kendiliğinden girmez

    @property
    def kimlik(self) -> str:
        return liste.kimlik(self.sanatci, sade_ad_gorunur(self.ad))  # listeye yazılan adla aynı kimlik

    @property
    def duzenleme(self) -> bool:
        return bool(DUZENLEME.search(self.ad))

    @property
    def uygun(self) -> bool | None:
        """Tür hattın tarifi dinlenmiş türlerinden mi (balad, pop, piyano rock…). None: tür bilinmiyor."""
        if self.turler is None:
            return None
        kalip = haric_kalip()
        return not (kalip and kalip.search(" ".join(self.turler)))

    @property
    def puan(self) -> float:
        if (self.geri_geldi or not self.youtube_izlenme or self.sanatci_uyusuyor is not True or self.duzenleme
                or self.soz_var is False or (self.sure_sn or 0) > SURE_SINIRI_SN or self.uygun is False
                or (self.populer and self.ingilizce is False)):
            return 0.0
        if self.populer:  # boşluk yok: aynı talepte kaldırılmış şarkı önce gelir
            kapsam = POPULER_KAPSAM
        else:  # global çalışılıyor (Scryne, 2026-10-09): boşluk ne kadar çok pazarda açıksa o kadar değerli
            kapsam = len(self.kapali_pazarlar) / len(self.bakilan_pazarlar) if self.bakilan_pazarlar else 1.0
        return self.talep * kapsam / (1 + (self.rakip_cover or 0))

    @property
    def populer(self) -> bool:
        return self.neden == "populer"

    @property
    def talep(self) -> int:
        """YouTube izlenmesi ya da (varsa) kaldırılmadan önceki Spotify dinlenmesi, büyüğü: Spotify'da arayan
        dinleyicinin doğrudan ölçüsü STILLMORE'dan geliyor (sızıntılarda 0, gerçek boşlukta milyonlar)."""
        return max(self.youtube_izlenme or 0, self.spotify_dinlenme or 0)


def haric_kalip_oku(yol: Path | None = None):
    """Keşfin kendiliğinden almadığı türler (`config/kesif.toml` → `[kesif] haric_turler`; yoksa onay varsayılanı)."""
    import tomllib

    from yanki import ayarlar, onay

    try:
        with open(yol or ayarlar.KOK / "config" / "kesif.toml", "rb") as f:
            turler = tomllib.load(f).get("kesif", {}).get("haric_turler", onay.DENENMEMIS_VARSAYILAN)
    except OSError:
        turler = onay.DENENMEMIS_VARSAYILAN
    return onay.tur_kalibi(turler)


haric_kalip = functools.cache(haric_kalip_oku)


def spotifya_sorulur(a: Aday) -> bool:
    """Ücretsiz elemeleri geçti mi: talep ölçüldü, sanatçı eşleşti, sözlü ve süresi uygun. Popüler aday sorulmaz:
    boşluk aranmıyor, Spotify kotası (günlük ~1.000 istek) kaldırılmış şarkılara kalsın."""
    return (not a.populer and not a.duzenleme and bool(a.youtube_izlenme) and a.sanatci_uyusuyor is True
            and a.soz_var is True and (a.sure_sn or 0) <= SURE_SINIRI_SN and a.uygun is not False)


def hal(a: Aday) -> str:
    """Tek kelimelik durum: tabloda ve dinleme odasında. Elemeler uygulandıkları sırayla."""
    if a.duzenleme:
        return "düzenleme"
    if a.geri_geldi:
        return "geri geldi"
    if a.youtube_izlenme is None and a.sanatci_uyusuyor is None:
        return "talep yok"
    if a.ozgunluk and a.ozgunluk.get("hayran", 0) >= 0.5:
        return "hayran yapımı"
    if a.sanatci_uyusuyor is None and a.ozgunluk:
        return "sanatçı belirsiz"
    if a.sanatci_uyusuyor is not True:
        return "sanatçı uymuyor"
    if a.soz_var is False:
        return "söz yok"
    if (a.sure_sn or 0) > SURE_SINIRI_SN:
        return "çok uzun"
    if a.uygun is False:
        return "tür uymuyor"
    if a.populer and a.ingilizce is False:
        return "İngilizce değil"
    if a.geri_geldi is None:
        return "doğrulanmadı"
    return {"kaldirildi": "kaldırılmış", "kismi": "kısmen kapalı", "spotify_yok": "Spotify'da yok",
            "populer": "popüler"}.get(a.neden,
                                                                                                         a.neden)


# ── Bulma ───────────────────────────────────────────────────
def _sayi(s: str | None) -> int | None:
    s = re.sub(r"[^\d]", "", s or "")
    return int(s) if s else None


def stillmore_csv(yol: Path) -> list[Aday]:
    """STILLMORE playlist taraması CSV'si (`Kaldırılmış şarkılar → CSV indir` ya da tam liste). Yalnız
    çalınamayanlar alınır. Sütunlar `spicetify/stillmore-finder.js` → `csv.playlist` (v12.1)."""
    metin = yol.read_text(encoding="utf-8-sig")
    adaylar = []
    for r in csv.DictReader(io.StringIO(metin)):
        if (r.get("Çalınabilir") or "").strip() != "Hayır" or not (r.get("Parça") or "").strip():
            continue
        if (r.get("Yeniden yüklenmiş") or "").strip():
            continue  # STILLMORE aynı ISRC'nin çalınabilir kopyasını buldu: boşluk yok
        durum = (r.get("Durum") or "").strip()
        adaylar.append(Aday(
            sanatci=(r.get("Sanatçı") or "").split(",")[0].strip(), ad=r["Parça"].strip(),
            kaynak=f"stillmore:{yol.name}", spotify_id=(r.get("Spotify ID") or "").strip() or None,
            isrc=(r.get("ISRC") or "").strip().upper() or None, cikis=(r.get("Çıkış") or "").strip() or None,
            neden="kismi" if durum.startswith("Ülkende kapalı") else "kaldirildi",
            spotify_dinlenme=_sayi(r.get("Dinlenme")),
        ))
    return adaylar


def kapali_pazarlar(sp, parca_id: str | None, pazarlar, bilinen_kapali=()) -> list[str]:
    """Parçanın çalınamadığı pazarlar (pazar başına bir istek). Kaldırılmış ile "bazı ülkelerde kapalı"yı ayırmanın tek
    yolu: `restrictions.reason` ikisinde de "market" (2026-10-09 ölçümü, CN'de her parça false/market)."""
    if not parca_id:
        return list(pazarlar)
    return [m for m in pazarlar if m in bilinen_kapali or sp.parca(parca_id, m).get("is_playable") is False]


def neden_sec(kapali: list, pazarlar) -> str:
    return "kaldirildi" if len(kapali) == len(pazarlar) else "kismi"


def playlist_tara(sp, playlist_id: str, pazarlar, sayac=None) -> list[Aday]:
    """Playlist'te ana pazarda (ilk) çalınamayan parçalar. Spotify kaldırılan parçayı listede gri bırakır; Web API'de
    `is_playable: false`. Diğer pazarlar burada sorulmaz: elemelerden (düzenleme, ölçülmüş) sonra `bosluk_dogrula`
    sorar; playlist'lerdeki çalınamayanların çoğu zaten eleniyor (2026-10-09: 70'te 3 aday)."""
    if isinstance(pazarlar, str):
        pazarlar = (pazarlar,)
    adaylar = []
    for t in sp.playlist_parcalari(playlist_id, pazarlar[0]):
        if sayac is not None:  # katalog farkı için tohum: playlist'teki sanatçıların sıklığı
            sayac.update(a["name"] for a in t.get("artists") or [] if a.get("name"))
        if t.get("is_playable") is not False:
            continue
        adaylar.append(Aday(
            sanatci=(t.get("artists") or [{}])[0].get("name") or "", ad=t.get("name") or "",
            kaynak=f"playlist:{playlist_id}", spotify_id=t.get("id"),
            isrc=((t.get("external_ids") or {}).get("isrc") or "").upper() or None,
            album=(t.get("album") or {}).get("name"), cikis=(t.get("album") or {}).get("release_date"),
            kapali_pazarlar=[pazarlar[0]],  # ana pazarda kapalı olduğu biliniyor; diğerleri doğrulamada
        ))
    return [a for a in adaylar if a.sanatci and a.ad]


PLAYLIST_TAZELEME_GUN = 7


def playlist_tara_onbellekli(sp, playlist_id: str, pazarlar, calisma: Path, sayac, simdi: datetime | None = None
                             ) -> list[Aday] | None:
    """İçerik değişmediyse (`snapshot_id`) ve son tam tarama `PLAYLIST_TAZELEME_GUN`'den yeniyse taramaz: sanatçı
    sayımı kayıttan gelir, `None` döner (adaylar zaten `adaylar.json`'da). Değişmeyen playlist'te de parça sonradan
    kaldırılabilir; bu yüzden haftada bir yine tam tarama. Maliyet: değişmeyen playlist 1 istek, tam tarama ~4."""
    from collections import Counter

    simdi = simdi or datetime.now()
    yol = calisma / "kesif" / "playlistler.json"
    kayit = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    eski = kayit.get(playlist_id) or {}
    snapshot = sp.playlist(playlist_id).get("snapshot_id")
    if (eski.get("snapshot") == snapshot and snapshot
            and datetime.fromisoformat(eski["tarih"]) > simdi - timedelta(days=PLAYLIST_TAZELEME_GUN)):
        sayac.update(eski.get("sanatcilar") or {})
        return None
    yerel: Counter = Counter()
    adaylar = playlist_tara(sp, playlist_id, pazarlar, yerel)
    sayac.update(yerel)
    kayit[playlist_id] = {"snapshot": snapshot, "tarih": simdi.isoformat(timespec="seconds"),
                          "sanatcilar": dict(yerel), "calinamayan": len(adaylar)}
    from yanki import dosya

    dosya.json_yaz(yol, kayit, indent=1)
    return adaylar


# ── Boşluk doğrulama ────────────────────────────────────────
def bosluk_dogrula(sp, a: Aday, pazarlar, kendi_sanatci: str = "") -> Aday:
    """Aynı şarkının çalınabilir bir sürümü var mı (geri gelmiş) ve kaç rakip cover var; aramalar ana pazarda
    (`pazarlar[0]`). Pazar dağılımı bilinmiyorsa (CSV) Spotify kimliğiyle her pazar sorulur."""
    if isinstance(pazarlar, str):
        pazarlar = (pazarlar,)
    market = pazarlar[0]
    if a.spotify_id and not a.bakilan_pazarlar:
        a.kapali_pazarlar = kapali_pazarlar(sp, a.spotify_id, pazarlar, bilinen_kapali=tuple(a.kapali_pazarlar))
        a.bakilan_pazarlar = list(pazarlar)
        if not a.kapali_pazarlar:  # aynı parça her pazarda yeniden çalınabilir: boşluk kapandı
            a.geri_geldi, a.rakip_cover = True, a.rakip_cover
            a.geri_gelen = [{"id": a.spotify_id, "sanatci": a.sanatci, "ad": a.ad, "neden": "ayni_parca"}]
            a.kontrol = datetime.now().isoformat(timespec="seconds")
            return a
        a.neden = neden_sec(a.kapali_pazarlar, pazarlar)
    sade, sanatci = sade_ad(a.ad), a.sanatci.casefold()
    geri: list[dict] = []
    if a.isrc:
        for t in sp.isrc_ara(a.isrc, market):
            if t.get("id") != a.spotify_id and t.get("is_playable") is not False:
                geri.append({"id": t["id"], "sanatci": t["artists"][0]["name"], "ad": t["name"], "neden": "isrc"})
    sonuclar = sp.ara(f'track:"{sade_ad_gorunur(a.ad)}"', market, adet=10)  # aramada özgün ad, karşılaştırmada sade
    rakip = 0
    for t in sonuclar:
        if t.get("is_playable") is False or sade_ad(t.get("name") or "") != sade or t.get("id") == a.spotify_id:
            continue
        sanatcilar = [x.get("name", "").casefold() for x in t.get("artists") or []]
        if sanatci in sanatcilar:
            if not any(x["id"] == t["id"] for x in geri):
                geri.append({"id": t["id"], "sanatci": t["artists"][0]["name"], "ad": t["name"], "neden": "ad"})
        elif not (kendi_sanatci and kendi_sanatci.casefold() in sanatcilar):
            rakip += 1
    a.geri_gelen, a.geri_geldi, a.rakip_cover = geri, bool(geri), rakip
    a.kontrol = datetime.now().isoformat(timespec="seconds")
    return a


# ── Talep ───────────────────────────────────────────────────
def talep_olc(a: Aday, arama=None) -> Aday:
    """YouTube'da orijinalin izlenmesi: ilk 5 sonuçtan istenmeyen sürümler (canlı, cover, karaoke…) atılır, adında
    şarkının adı geçenlerin en çok izleneni alınır."""
    from yanki import kaynak

    if arama is None:
        arama = _youtube_ara
    sade = sade_ad(a.ad)
    en_iyi: tuple[int, str, str | None] | None = None
    sonuclar = arama(f"{a.sanatci} {a.ad}")
    a.youtube_kanit = [{"title": r[0], "channel": r[3] if len(r) > 3 else None, "views": r[1]} for r in sonuclar[:5]]
    for baslik, izlenme, *kimlik in sonuclar:
        # YouTube başlığı "Sanatçı - Şarkı (Official Video)": sonek silinmeden, kelime sınırıyla aranır
        if izlenme is None or kaynak.ISTENMEYEN.search(baslik) or f" {sade} " not in f" {_duz(baslik)} ":
            continue
        if en_iyi is None or izlenme > en_iyi[0]:
            en_iyi = (izlenme, baslik, kimlik[0] if kimlik else None)  # kimlik: [video id, kanal]
    if en_iyi:
        a.youtube_izlenme, a.youtube_baslik, a.youtube_id = en_iyi
        a.sanatci_uyusuyor = sanatci_eslesir(a.sanatci, en_iyi[1])
    return a


SANATCI_AYRAC = re.compile(r"\s*(?:,|&|\+|\bx\b|\bfeat\.?|\bft\.?|\band\b|\bve\b)\s*", re.I)


def sanatci_eslesir(sanatci: str, baslik: str) -> bool | None:
    """YouTube başlığında sanatçı bütün olarak geçiyor mu. "Sanatçı - Şarkı" biçiminde sol taraftaki adlardan biri
    birebir aynı olmalı: "Del", "Lana Del Rey - Put Me in a Movie" ile eşleşmez (2026-10-09 canlı koşuda kaçmıştı).
    Ad harfsizse (ör. "¥$") karar verilmez."""
    sd = _duz(sanatci)
    if not sd:
        return None
    # "A - B", "A- B", "A || B" (canlı başlıklarda görüldü); "Jay-Z" gibi boşluksuz tire ayraç değil
    parcalar = BASLIK_AYRAC.split(PARANTEZ.sub("", baslik))
    if len(parcalar) > 1:
        return any(_duz(x) == sd for p in parcalar for x in SANATCI_AYRAC.split(p) if x)
    # ayraçsız başlık: sanatçı başta, sonda ya da boşluksuz tireyle ayrılmış bir parça olarak bütün hâlde
    # ("Lana Del Rey-Mermaid Motel" → "Del" eşleşmez; "JAY-Z Empire State" eşleşir)
    tam = _duz(PARANTEZ.sub("", baslik))
    return (tam.startswith(sd + " ") or tam.endswith(" " + sd) or tam == sd
            or any(_duz(p) == sd for p in baslik.split("-")))


BASLIK_AYRAC = re.compile(r"\s+[-–—]+\s*|\s*[-–—]+\s+|\s*\|+\s*")


SURE_SINIRI_SN = 420  # hattın parçalı üretimi ölçüldüğü aralığın üstü (285–290 sn şarkılar); uzun parça atlanır
# Popüler (Spotify'da duran) adayın puanı talebin bu kadarı: aynı talepte boşluğu her pazarda açık kaldırılmış şarkı
# 5 kat önde. Popüler hitlerin talebi (YouTube'da yüz milyonlar) yine de çoğu kaldırılmış şarkının üstünde kalır.
POPULER_KAPSAM = 0.2
INGILIZCE_ESIGI = 0.15  # yanki/hazirlik.py ile aynı: İngilizce sözde sık kelimelerin payı ~0,3–0,5, başka dilde ~0


def soz_kontrol(a: Aday, json_al=None) -> Aday:
    """Hattın söz kaynağı LRCLIB'de sözlü kayıt var mı ve süresi ne. Sözsüz (enstrümantal) ya da kaydı olmayan şarkı
    kendiliğinden listeye girmez: cover tarifi gerçek sözlere dayanıyor ve söz kapısı sözsüz adayı düşürür."""
    from yanki import ag, sozler

    try:
        s = sozler.lrclib(a.sanatci, sade_ad_gorunur(a.ad), **({"json_al": json_al} if json_al else {}))
        a.soz_var, a.sure_sn = True, s.sure_sn
        from yanki.kapilar import ingilizce_orani

        oran = ingilizce_orani(s.metin)
        a.ingilizce = None if oran is None else oran >= INGILIZCE_ESIGI
    except ag.Bulunamadi:
        a.soz_var = False
    return a


def _youtube_ara(sorgu: str, adet: int = 5) -> list[tuple[str, int | None, str | None, str | None]]:
    import yt_dlp

    from yanki import sayac

    ayar = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    try:
        with yt_dlp.YoutubeDL(ayar) as ydl:
            bilgi = ydl.extract_info(f"ytsearch{adet}:{sorgu}", download=False)
    except Exception:
        sayac.say("YouTube", False)
        raise
    sayac.say("YouTube", True)
    return [(g.get("title") or "", g.get("view_count"), g.get("id"), g.get("channel") or g.get("uploader"))
            for g in bilgi.get("entries") or [] if g]


# ── Kayıt ve liste ──────────────────────────────────────────
def kayit_yolu(calisma: Path) -> Path:
    return calisma / "kesif" / "adaylar.json"


def oku(calisma: Path) -> dict[str, Aday]:
    yol = kayit_yolu(calisma)
    if not yol.exists():
        return {}
    return {k: Aday(**v) for k, v in json.loads(yol.read_text(encoding="utf-8")).items()}


def kayit_kilidi(calisma: Path):
    """`adaylar.json` oku-değiştir-yaz kilidi: dinleme odasındaki "Ele" ile gece keşfi aynı anda yazmasın."""
    from yanki import kilit

    return kilit.bekleyerek(calisma / "kesif" / ".adaylar.kilit")


def birlestir(calisma: Path, yeniler: list[Aday]) -> dict[str, Aday]:
    """Aynı şarkı birden çok kaynaktan gelirse tek kayıt; ilk görülme korunur, ölçümler en yenisiyle güncellenir.
    Eleme kararı kayıttakinden gelir: keşif sürerken dinleme odasında verilen "Ele"/"Geri al" geçerli."""
    with kayit_kilidi(calisma):
        kayit = oku(calisma)
        simdi = datetime.now().isoformat(timespec="seconds")
        for a in yeniler:
            eski = kayit.get(a.kimlik)
            a.ilk_gorulme = eski.ilk_gorulme if eski else simdi
            tasi(a, eski)
            if eski is not None:
                a.elendi = eski.elendi
            kayit[a.kimlik] = a
        kaydet(calisma, kayit)
    return kayit


KIMLIK_ALANLARI = ("spotify_dinlenme", "isrc", "spotify_id", "album", "cikis")
# Aynı adımda birlikte ölçülen alanlar grup olarak taşınır: taze ölçümde None da geçerli bir sonuçtur ("belirsiz"),
# eski kaydın değeriyle doldurulmaz (2026-10-09: Jev "belirsiz" dediği aday eski regex "uymuyor"uyla eziliyordu).
UCRETSIZ_ALANLAR = ("youtube_izlenme", "youtube_baslik", "youtube_id", "youtube_kanit", "sanatci_uyusuyor", "soz_var",
                    "ingilizce", "sure_sn", "ozgunluk", "olcum", "turler")
SPOTIFY_ALANLARI = ("geri_geldi", "geri_gelen", "rakip_cover", "kontrol", "bakilan_pazarlar", "kapali_pazarlar")


def tasi(a: Aday, eski: Aday | None) -> Aday:
    """Kayıttaki ölçümleri yeni gelen adaya taşır: kimlik alanları tek tek (boşsa), ücretsiz ölçüm ve Spotify
    doğrulaması grup olarak (yeni aday o adımda ölçülmediyse). Eleme kararı korunur."""
    if eski is None:
        return a
    for alan in KIMLIK_ALANLARI:
        if getattr(a, alan) is None and getattr(eski, alan) is not None:
            setattr(a, alan, getattr(eski, alan))
    if a.olcum is None:
        for alan in UCRETSIZ_ALANLAR:
            setattr(a, alan, getattr(eski, alan))
    if a.kontrol is None and not a.bakilan_pazarlar:
        for alan in SPOTIFY_ALANLARI:
            setattr(a, alan, getattr(eski, alan))
    elif a.kontrol is None:  # pazar dağılımı kaynaktan geldi (katalog), boşluk doğrulaması eskiden
        for alan in ("geri_geldi", "geri_gelen", "rakip_cover"):
            if getattr(a, alan) in (None, []):
                setattr(a, alan, getattr(eski, alan))
    a.elendi = a.elendi or eski.elendi
    return a


def taze(zaman: str | None, gun: int = 14, simdi: datetime | None = None) -> bool:
    return bool(zaman) and datetime.fromisoformat(zaman) > (simdi or datetime.now()) - timedelta(days=gun)


def kaydet(calisma: Path, kayit: dict[str, Aday]) -> None:
    from yanki import dosya

    dosya.json_yaz(kayit_yolu(calisma), {k: asdict(v) for k, v in sorted(kayit.items())})


def sirala(kayit: dict[str, Aday]) -> list[Aday]:
    return sorted(kayit.values(), key=lambda a: (-a.puan, a.sanatci, a.ad))


def listeye_ekle(adaylar: list[Aday], liste_yolu: Path, calisma: Path, adet: int,
                 egitim_sanatcilari: set[str] = frozenset()) -> list[Aday]:
    """Doğrulanmış (geri gelmemiş, talebi ölçülmüş) ilk `adet` adayı `liste.toml`'un sonuna ekler. Listede ya da
    çalışma alanında zaten olan şarkı atlanır. Dosyanın açıklamaları korunur (sona metin eklenir).
    `egitim_sanatcilari` (küçük harf) eklenmez: eğitim verisi cover listesindeki sanatçıları içermez, tersi de
    (`egitim.veri`; bir sesin kopyası olmasın)."""
    mevcut = listedekiler(liste_yolu, calisma)
    # Aynı sanatçıdan sırada bekleyen şarkı varken yenisi eklenmez: kataloğunu Spotify'dan çeken bir sanatçının her
    # şarkısı "Spotify'da yok" ve aynı puan aralığında; 2026-10-10 keşfinde ilk 10'un 6'sı Xiu Xiu'ydu, gece eklemesi
    # her gün aynı sanatçıyı listeye koyacaktı (profil tek bir sanatçının cover kanalına döner, kulak da aynı tarzı
    # dinler). Sanatçının şarkısı yayına çıkınca ya da reddedilince sıradaki eklenebilir.
    sanatcilar = bekleyen_sanatcilar(liste_yolu, calisma) | set(egitim_sanatcilari)
    secilen: list[Aday] = []
    for a in adaylar:
        if len(secilen) >= adet:
            break
        if (a.geri_geldi is False and a.puan > 0 and not a.elendi and a.kimlik not in mevcut
                and a.sanatci.casefold() not in sanatcilar):
            secilen.append(a)
            sanatcilar.add(a.sanatci.casefold())
    return listeye_yaz(secilen, liste_yolu)


def bekleyen_sanatcilar(liste_yolu: Path, calisma: Path) -> set[str]:
    """Listede olup henüz yayına çıkmamış ve reddedilmemiş şarkıların sanatçıları (küçük harf)."""
    from yanki import durum

    sonuc = set()
    for s in liste.yukle(liste_yolu):
        d = durum.oku(calisma, s.kimlik)
        if d is None or d.asama not in ("yayinda", "reddedildi"):
            sonuc.add(s.sanatci.casefold())
    return sonuc


def listedekiler(liste_yolu: Path, calisma: Path) -> set[str]:
    """Listede ya da çalışma alanında olan şarkı kimlikleri (eklenmiş sayılır)."""
    return {s.kimlik for s in liste.yukle(liste_yolu)} | {p.name for p in calisma.iterdir() if p.is_dir()}


def liste_kilidi(liste_yolu: Path):
    """`liste.toml` yazım kilidi: gece keşfi ile odadaki "Listeye ekle" aynı anda yazmasın. Koşunun genel kilidi
    (`.yanki.kilit`) değil: kiralık GPU'da üretim ~1 saat sürüyor, oda o süre boyunca listeye ekleyemiyordu."""
    from yanki import kilit

    return kilit.bekleyerek(liste_yolu.with_name(f".{liste_yolu.name}.kilit"))


def listeye_yaz(secilen: list[Aday], liste_yolu: Path, not_: str = "yanki kesif") -> list[Aday]:
    """Adayları `liste.toml`'un sonuna ekler (eleme yapmaz; çağıran seçer). Dosyanın açıklamaları korunur. Yeni metin
    yazılmadan önce doğrulanır (aynı şarkı iki kez, bozuk TOML: ValueError, dosyaya dokunulmaz) ve atomik yazılır:
    önce sona eklenip sonra doğrulanıyordu, bozuk ekleme bütün hattın listesini okunmaz bırakırdı."""
    from yanki import dosya

    if not secilen:
        return []
    ne = ("popüler şarkılar" if all(a.populer for a in secilen) else "Spotify'da kaldırılmış şarkılar"
          if not any(a.populer for a in secilen) else "kaldırılmış ve popüler şarkılar")
    bloklar = [f"\n# kesif {datetime.now():%Y-%m-%d}: {ne} ({not_})"]
    for a in secilen:
        ek = f", rakip cover {a.rakip_cover}" if a.rakip_cover else ""
        izlenme = f"YouTube {a.youtube_izlenme:,} izlenme" if a.youtube_izlenme is not None else "YouTube ölçülmedi"
        bloklar.append(f"\n[[sarki]]  # {izlenme}{ek}; {a.kaynak}\n"
                       f"sanatci = {json.dumps(a.sanatci, ensure_ascii=False)}\n"
                       f"ad = {json.dumps(sade_ad_gorunur(a.ad), ensure_ascii=False)}\n")
    with liste_kilidi(liste_yolu):
        eski = liste_yolu.read_text(encoding="utf-8-sig") if liste_yolu.exists() else ""
        yeni = eski + ("" if not eski or eski.endswith("\n") else "\n") + "".join(bloklar)
        liste.coz(yeni, liste_yolu.name)
        dosya.yaz(liste_yolu, yeni)
    return secilen


def sade_ad_gorunur(ad: str) -> str:
    """Listeye yazılacak ad: ' - Remastered 2011' gibi sürüm ekleri atılır, büyük/küçük harf korunur."""
    return EK.sub("", re.sub(r"\s*[\(\[](?:[^)\]]*(?:remaster|version|edit|mono|stereo|live|feat)[^)\]]*)[\)\]]",
                             "", ad, flags=re.I)).strip() or ad
