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

Sıra: izlenme / (1 + rakip cover sayısı). Formül kasıtlı olarak basit; ilk yayınların arama sırası ölçüldükçe
(`yanki takip`) düzeltilir. Sonuç `calisma/kesif/adaylar.json`; listeye ekleme açık bir adım (`--ekle N`).
"""

import csv
import io
import json
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime
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
    kaynak: str  # "playlist:<id>" | "stillmore:<dosya>"
    spotify_id: str | None = None
    isrc: str | None = None
    album: str | None = None
    cikis: str | None = None
    neden: str = "kaldirildi"  # "kaldirildi" | "ulkede_kapali"
    spotify_dinlenme: int | None = None  # STILLMORE CSV'sinden (kaldırılmadan önceki toplam)
    youtube_izlenme: int | None = None
    youtube_baslik: str | None = None
    # YouTube'daki en çok izlenen yüklemede listedeki sanatçı geçiyor mu. Geçmiyorsa takma adla yüklenmiş bir sızıntı
    # ya da taklit olabilir (2026-10-09: "Lizzy Rey", "Del" adıyla Lana Del Rey sızıntıları) → listeye eklenmez
    sanatci_uyusuyor: bool | None = None
    soz_var: bool | None = None  # LRCLIB'de sözlü kayıt
    sure_sn: float | None = None
    geri_geldi: bool | None = None  # None: doğrulanmadı
    geri_gelen: list = field(default_factory=list)  # [{"id", "sanatci", "ad", "neden": "isrc"|"ad"}]
    rakip_cover: int | None = None
    kontrol: str | None = None
    ilk_gorulme: str | None = None

    @property
    def kimlik(self) -> str:
        return liste.kimlik(self.sanatci, sade_ad_gorunur(self.ad))  # listeye yazılan adla aynı kimlik

    @property
    def duzenleme(self) -> bool:
        return bool(DUZENLEME.search(self.ad))

    @property
    def puan(self) -> float:
        if (self.geri_geldi or not self.youtube_izlenme or self.sanatci_uyusuyor is not True or self.duzenleme
                or self.soz_var is False or (self.sure_sn or 0) > SURE_SINIRI_SN):
            return 0.0
        return self.youtube_izlenme / (1 + (self.rakip_cover or 0))


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
            neden="ulkede_kapali" if durum.startswith("Ülkende kapalı") else "kaldirildi",
            spotify_dinlenme=_sayi(r.get("Dinlenme")),
        ))
    return adaylar


# Kaldırılmış ile "yalnız bu ülkede kapalı"yı ayırmak için bakılan pazarlar. `restrictions.reason` ikisinde de
# "market" dönüyor (2026-10-09 ölçümü: Spotify'ın olmadığı CN'de her parça is_playable false, reason market).
DIS_PAZARLAR = ("US", "GB", "DE")


def baska_pazarda_acik(sp, parca_id: str, pazarlar: tuple[str, ...] = DIS_PAZARLAR) -> bool:
    for m in pazarlar:
        if sp.parca(parca_id, m).get("is_playable") is not False:
            return True
    return False


def playlist_tara(sp, playlist_id: str, market: str) -> list[Aday]:
    """Playlist'te `market`te çalınamayan parçalar. Spotify bir parçayı kaldırınca listede gri bırakır; Web API'de
    `is_playable: false` görünür. Başka büyük pazarlarda açıksa `ulkede_kapali`, hiçbirinde değilse `kaldirildi`."""
    adaylar = []
    for t in sp.playlist_parcalari(playlist_id, market):
        if t.get("is_playable") is not False:
            continue
        acik = bool(t.get("id")) and baska_pazarda_acik(sp, t["id"], tuple(m for m in DIS_PAZARLAR if m != market))
        adaylar.append(Aday(
            sanatci=(t.get("artists") or [{}])[0].get("name") or "", ad=t.get("name") or "",
            kaynak=f"playlist:{playlist_id}", spotify_id=t.get("id"),
            isrc=((t.get("external_ids") or {}).get("isrc") or "").upper() or None,
            album=(t.get("album") or {}).get("name"), cikis=(t.get("album") or {}).get("release_date"),
            neden="ulkede_kapali" if acik else "kaldirildi",
        ))
    return [a for a in adaylar if a.sanatci and a.ad]


# ── Boşluk doğrulama ────────────────────────────────────────
def bosluk_dogrula(sp, a: Aday, market: str, kendi_sanatci: str = "") -> Aday:
    """Aynı şarkının çalınabilir bir sürümü var mı (geri gelmiş) ve kaç rakip cover var."""
    sade, sanatci = sade_ad(a.ad), a.sanatci.casefold()
    geri: list[dict] = []
    if a.isrc:
        for t in sp.isrc_ara(a.isrc, market):
            if t.get("id") != a.spotify_id and t.get("is_playable") is not False:
                geri.append({"id": t["id"], "sanatci": t["artists"][0]["name"], "ad": t["name"], "neden": "isrc"})
    sonuclar = sp.ara(f'track:"{sade}"', market, adet=10)
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
    en_iyi: tuple[int, str] | None = None
    for baslik, izlenme in arama(f"{a.sanatci} {a.ad}"):
        # YouTube başlığı "Sanatçı - Şarkı (Official Video)": sonek silinmeden, kelime sınırıyla aranır
        if izlenme is None or kaynak.ISTENMEYEN.search(baslik) or f" {sade} " not in f" {_duz(baslik)} ":
            continue
        if en_iyi is None or izlenme > en_iyi[0]:
            en_iyi = (izlenme, baslik)
    if en_iyi:
        a.youtube_izlenme, a.youtube_baslik = en_iyi
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


def soz_kontrol(a: Aday, json_al=None) -> Aday:
    """Hattın söz kaynağı LRCLIB'de sözlü kayıt var mı ve süresi ne. Sözsüz (enstrümantal) ya da kaydı olmayan şarkı
    kendiliğinden listeye girmez: cover tarifi gerçek sözlere dayanıyor ve söz kapısı sözsüz adayı düşürür."""
    from yanki import ag, sozler

    try:
        s = sozler.lrclib(a.sanatci, sade_ad_gorunur(a.ad), **({"json_al": json_al} if json_al else {}))
        a.soz_var, a.sure_sn = True, s.sure_sn
    except ag.Bulunamadi:
        a.soz_var = False
    return a


def _youtube_ara(sorgu: str, adet: int = 5) -> list[tuple[str, int | None]]:
    import yt_dlp

    ayar = {"quiet": True, "no_warnings": True, "extract_flat": True, "skip_download": True}
    with yt_dlp.YoutubeDL(ayar) as ydl:
        bilgi = ydl.extract_info(f"ytsearch{adet}:{sorgu}", download=False)
    return [(g.get("title") or "", g.get("view_count")) for g in bilgi.get("entries") or [] if g]


# ── Kayıt ve liste ──────────────────────────────────────────
def kayit_yolu(calisma: Path) -> Path:
    return calisma / "kesif" / "adaylar.json"


def oku(calisma: Path) -> dict[str, Aday]:
    yol = kayit_yolu(calisma)
    if not yol.exists():
        return {}
    return {k: Aday(**v) for k, v in json.loads(yol.read_text(encoding="utf-8")).items()}


def birlestir(calisma: Path, yeniler: list[Aday]) -> dict[str, Aday]:
    """Aynı şarkı birden çok kaynaktan gelirse tek kayıt; ilk görülme korunur, ölçümler en yenisiyle güncellenir."""
    kayit = oku(calisma)
    simdi = datetime.now().isoformat(timespec="seconds")
    for a in yeniler:
        eski = kayit.get(a.kimlik)
        a.ilk_gorulme = eski.ilk_gorulme if eski else simdi
        if eski:
            for alan in ("spotify_dinlenme", "isrc", "spotify_id", "album", "cikis", "youtube_izlenme",
                         "youtube_baslik", "sanatci_uyusuyor", "soz_var", "sure_sn", "geri_geldi", "rakip_cover",
                         "kontrol"):
                if getattr(a, alan) is None and getattr(eski, alan) is not None:
                    setattr(a, alan, getattr(eski, alan))
            if not a.geri_gelen and eski.geri_gelen:
                a.geri_gelen = eski.geri_gelen
        kayit[a.kimlik] = a
    yol = kayit_yolu(calisma)
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_suffix(".tmp")
    gecici.write_text(json.dumps({k: asdict(v) for k, v in sorted(kayit.items())}, ensure_ascii=False, indent=2),
                      encoding="utf-8")
    gecici.replace(yol)
    return kayit


def sirala(kayit: dict[str, Aday]) -> list[Aday]:
    return sorted(kayit.values(), key=lambda a: (-a.puan, a.sanatci, a.ad))


def listeye_ekle(adaylar: list[Aday], liste_yolu: Path, calisma: Path, adet: int) -> list[Aday]:
    """Doğrulanmış (geri gelmemiş, talebi ölçülmüş) ilk `adet` adayı `liste.toml`'un sonuna ekler. Listede ya da
    çalışma alanında zaten olan şarkı atlanır. Dosyanın açıklamaları korunur (sona metin eklenir)."""
    mevcut = {s.kimlik for s in liste.yukle(liste_yolu)} | {p.name for p in calisma.iterdir() if p.is_dir()}
    secilen = [a for a in adaylar if a.geri_geldi is False and a.puan > 0 and a.kimlik not in mevcut][:adet]
    if not secilen:
        return []
    bloklar = [f"\n# kesif {datetime.now():%Y-%m-%d}: Spotify'da kaldırılmış şarkılar (yanki kesif)"]
    for a in secilen:
        ek = f", rakip cover {a.rakip_cover}" if a.rakip_cover else ""
        bloklar.append(f"\n[[sarki]]  # YouTube {a.youtube_izlenme:,} izlenme{ek}; {a.kaynak}\n"
                       f"sanatci = {json.dumps(a.sanatci, ensure_ascii=False)}\n"
                       f"ad = {json.dumps(sade_ad_gorunur(a.ad), ensure_ascii=False)}\n")
    with open(liste_yolu, "a", encoding="utf-8") as f:
        f.write("".join(bloklar))
    liste.yukle(liste_yolu)  # yazılan dosya hâlâ geçerli mi
    return secilen


def sade_ad_gorunur(ad: str) -> str:
    """Listeye yazılacak ad: ' - Remastered 2011' gibi sürüm ekleri atılır, büyük/küçük harf korunur."""
    return EK.sub("", re.sub(r"\s*[\(\[](?:[^)\]]*(?:remaster|version|edit|mono|stereo|live|feat)[^)\]]*)[\)\]]",
                             "", ad, flags=re.I)).strip() or ad
