"""Elle yayın taslağı (Scryne 2026-10-16: "bir taslak olsun, ben şarkı yüklemek istediğimde elimle doldurayım, sonra
dağıtıcıyı seçeyim, sen otomatik at; ISRC falan, bilgisayarımdan yükleme").

Yanki'nin cover hattından bağımsız: kendi şarkın, başka bir kayıt, elle hazırladığın her şey. Dinleme odası → Yükle'de
form doldurulur, ses ve kapak bilgisayardan seçilir; hat dosyaları dağıtıcının istediği biçime çevirir (ses: FLAC
44,1 kHz 16 bit; kapak: 3000×3000 RGB JPG, ortadan kare), alanları denetler ve seçilen dağıtıcıya gönderir.

Dağıtıcılar (`DAGITICILAR`):
- **RouteNote:** form tarayıcıyla doldurulur ve aynı oturumda gönderilir (`routenote.RouteNote.yukle_klasor`; yayın
  sayfası yalnız taslağı dolduran oturumda dolu, 2026-10-16). UPC'yi RouteNote atar; ISRC boşsa o da.
- **FreshTunes:** Scryne'ın kendi (insan yapımı) şarkıları için, Orvane'den ayrı hesap (2026-10-16: "normal şarkıları da
  paylaşabileceğim bir dağıtıcı, para vermeden"; docs/arastirma/09). Ücretsiz plan, akış gelirinin %100'ü. Şartları
  otomatik erişimi (§9g) ve yapay zekâyla üretilmiş kaydı (§1) yasaklıyor: hat paketi FreshTunes'un biçiminde hazırlar,
  formu Scryne doldurur, sonra odada "FreshTunes'a gönderdim". 3 ayda bir giriş şart (yoksa askı, açmak 50 $):
  `freshtunes_hatirlatma` gece koşusunda hatırlatır.
- **Elle paket:** DistroKid, TuneCore ve benzerlerinin şartları botla erişimi yasaklıyor (docs/arastirma/08): ses,
  kapak ve bütün bilgiler tek ZIP'te, alanlar dağıtıcı formlarının diliyle yazılı.

Taslaklar `calisma/elle/<kimlik>/`: `metadata.json` (form + dağıtıcı kayıtları), `ses.flac`, `kapak.jpg`, `kaynak/`
(yüklenen asıl dosyalar). Gece koşusu bunlara dokunmaz; gönderim yalnız Scryne'ın odadaki tıklamasıyla.
"""

import io
import json
import re
import subprocess
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

from yanki import dosya, routenote

DAGITICILAR = {
    "routenote": {"ad": "RouteNote", "otomatik": True,
                  "aciklama": "Ücretsiz, gelirin %85'i sende. Form tarayıcıyla doldurulup gönderilir; inceleme 5–10 iş "
                              "günü. UPC'yi RouteNote atar, ISRC boşsa onu da."},
    "freshtunes": {"ad": "FreshTunes", "otomatik": False,
                   "aciklama": "Kendi şarkıların için, Orvane'den ayrı. Ücretsiz, akış gelirinin %100'ü sende. "
                               "Yapay zekâ kaydı almıyor, botu yasaklıyor: paketi indir, formu FreshTunes'ta "
                               "doldur, sonra \"FreshTunes'a gönderdim\"."},
    "elle": {"ad": "Başka dağıtıcı (elle)", "otomatik": False,
             "aciklama": "DistroKid, TuneCore, CD Baby, Amuse… şartları otomasyonu yasaklıyor: ses, kapak ve bütün "
                         "bilgiler tek ZIP'te iner, formu oradan doldurursun."},
}
# RouteNote'un mağaza kutuları (routenote.KAPALI_MAGAZALAR): yapay zekâ içeriği almayanlar ve Content ID
YAPAY_ZEKA_KAPALI = ("Amazon", "Melon", "Bugs!", "FLO", "Genie Music")
KORE = ("Melon", "Bugs!", "FLO", "Genie Music")  # cover için yazılı sanatçı izni istiyorlar
MEKANIK_LISANS_ULKELER = routenote.HARIC_BOLGELER  # cover: mekanik lisans yoksa bu ülkeler hariç
SES_UZANTILARI = (".wav", ".flac", ".mp3", ".aif", ".aiff", ".m4a", ".ogg")
EN_BUYUK_YUKLEME = 400 * 2**20
KAPAK_EN_AZ = 1400  # dağıtıcıların çoğu en az 1400 (RouteNote 3000 istiyor: büyütülür, uyarılır)
ISRC = re.compile(r"[A-Z]{2}[A-Z0-9]{3}\d{7}")
UPC = re.compile(r"\d{12,13}")
SPOTIFY_ID = re.compile(r"[A-Za-z0-9]{22}")
# FreshTunes yardım merkezi (2026): yayın tarihi yüklemeden en erken 7 gün sonra (14–28 önerilir); başta/sonda en çok
# 5 sn sessizlik; 0 dBFS'e dayanan (kırpılmış) ses reddedilir; kapak en çok 3000×3000, 10 MB. ToS §4: 3 ayda bir giriş.
FRESHTUNES_YAYIN_ASGARI_GUN = 7
FRESHTUNES_YAYIN_ONERI_GUN = 14
FRESHTUNES_SESSIZLIK_SN = 5.0
FRESHTUNES_GIRIS_GUN = 90
FRESHTUNES_HATIRLAT_GUN = 75
FRESHTUNES_URL = "https://freshtunes.com"

# alan → (tür, zorunlu mu); metin alanlarında en çok uzunluk
ALANLAR: dict[str, tuple] = {
    "baslik": (str, 200), "surum": (str, 100), "sanatci": (str, 120), "spotify_sanatci_id": (str, 200),
    "yeni_profil": (bool,), "dil": (str, 40), "tur": (str, 40), "acik_icerik": (bool,), "soz_var": (bool,),
    "cover": (bool,), "orijinal_sanatci": (str, 120), "yazar_adlari": (list,), "soz_ayni": (bool,),
    "soz_yazari_adlari": (list,), "uretici": (str, 120), "c_yil": (int,), "c_sahibi": (str, 200),
    # ISRC/UPC boşluk ya da tireyle yazılabilir (sonra sadeleşir), profil linkle
    "p_yil": (int,), "p_sahibi": (str, 200), "etiket": (str, 120), "isrc": (str, 20), "upc": (str, 20),
    "yayin_tarihi": (str, 10), "orijinal_tarih": (str, 10), "onizleme_sn": (int,), "yapay_zeka": (bool,),
    "content_id": (bool,), "mekanik_lisans": (bool,), "dagiticilar": (list,), "notlar": (str, 2000),
}


class Hata(ValueError):
    pass


def kok_klasor(calisma: Path) -> Path:
    return calisma / "elle"


def klasor(calisma: Path, kimlik: str) -> Path:
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", kimlik or ""):
        raise Hata("geçersiz taslak")
    return kok_klasor(calisma) / kimlik


def _meta_yolu(calisma: Path, kimlik: str) -> Path:
    return klasor(calisma, kimlik) / "metadata.json"


def oku(calisma: Path, kimlik: str) -> dict:
    try:
        return json.loads(_meta_yolu(calisma, kimlik).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Hata("taslak bulunamadı") from e


def _yaz(calisma: Path, kimlik: str, meta: dict) -> dict:
    meta["guncel"] = datetime.now().isoformat(timespec="seconds")
    dosya.json_yaz(_meta_yolu(calisma, kimlik), meta)
    return meta


def varsayilanlar(kok: Path) -> dict:
    """Yeni taslağın başlangıcı: Orvane ve kayıtlı Spotify profili (`config/yayin.toml`)."""
    import tomllib

    from yanki import paket

    y = paket.yayin_ayarlari(kok / "config" / "yayin.toml")
    try:
        with open(kok / "config" / "yayin.toml", "rb") as f:
            sid = tomllib.load(f).get("routenote", {}).get("spotify_sanatci_id") or ""
    except OSError:
        sid = ""
    yil = date.today().year
    return {"sanatci": y.sanatci_adi, "spotify_sanatci_id": sid, "yeni_profil": False, "dil": "English", "tur": "Pop",
            "acik_icerik": False, "soz_var": True, "cover": False, "soz_ayni": True, "yazar_adlari": [["", ""]],
            "soz_yazari_adlari": [], "c_yil": yil, "p_yil": yil, "etiket": y.etiket or y.sanatci_adi,
            "yapay_zeka": True, "content_id": False, "mekanik_lisans": False, "dagiticilar": ["routenote"],
            "isrc": "", "upc": "", "yayin_tarihi": "", "orijinal_tarih": "", "surum": "", "uretici": "",
            "c_sahibi": "", "p_sahibi": "", "orijinal_sanatci": "", "notlar": ""}


def _son_freshtunes(calisma: Path) -> dict:
    """En son düzenlenen FreshTunes taslağı (yeni "kendi şarkım" taslağı sanatçı, profil, label ve yazarları ondan
    alır: FreshTunes'ta ücretsiz planda tek sanatçı)."""
    son = {}
    for p in kok_klasor(calisma).glob("*/metadata.json"):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if ("freshtunes" in (m.get("dagiticilar") or []) and m.get("sanatci")
                and (m.get("guncel") or "") > (son.get("guncel") or "")):
            son = m
    return son


def yeni(calisma: Path, kok: Path, baslik: str = "", sablon: str | None = None, sanatci: str | None = None) -> dict:
    """Yeni taslak. `sablon="freshtunes"`: Scryne'ın kendi şarkısı (Orvane değil, yapay zekâ yok, FreshTunes, yayın
    tarihi önerilen en erken gün)."""
    from yanki import liste

    v = taban_v = varsayilanlar(kok)  # Orvane'in sanatçı/profili: başka adlı yayına bağlanmasın diye saklanır
    if sablon == "freshtunes":
        son = _son_freshtunes(calisma)
        v = v | {"sanatci": son.get("sanatci", ""), "spotify_sanatci_id": son.get("spotify_sanatci_id", ""),
              "etiket": son.get("etiket", ""), "yazar_adlari": son.get("yazar_adlari") or [["", ""]],
              "dil": son.get("dil") or v["dil"], "tur": son.get("tur") or v["tur"], "yapay_zeka": False,
              "cover": False, "content_id": False, "dagiticilar": ["freshtunes"],
              "yayin_tarihi": (date.today() + timedelta(days=FRESHTUNES_YAYIN_ONERI_GUN)).isoformat()}
    elif sablon is not None:
        raise Hata("bilinmeyen şablon")
    if sanatci:  # kimlik de bu adla ("taslak-<ad>" değil)
        v = v | {"sanatci": sanatci}
    taban = liste.kimlik(v["sanatci"] or "taslak", baslik or f"taslak {datetime.now():%Y%m%d %H%M%S}")
    kimlik, n = taban, 2
    while kok_klasor(calisma).joinpath(kimlik).exists():
        kimlik, n = f"{taban}-{n}", n + 1
    klasor(calisma, kimlik).mkdir(parents=True)
    return _yaz(calisma, kimlik, {"kimlik": kimlik, "baslik": baslik.strip(), **{k: v[k] for k in v if k != "baslik"},
                                  "varsayilan_sanatci": taban_v["sanatci"],
                                  "varsayilan_spotify_id": taban_v["spotify_sanatci_id"],
                                  "olusturma": datetime.now().isoformat(timespec="seconds")})


def kilitli(meta: dict) -> str | None:
    """Gönderilmiş ya da RouteNote'ta taslağı açılmış kaydın alanları değişmez (dağıtıcıdaki kopya ayrışır)."""
    rn = meta.get("routenote") or {}
    if rn.get("adim") in ("gonderiliyor", "gonderildi"):
        return "RouteNote'a gönderildi; bilgiler artık RouteNote panelinden değişir"
    if (meta.get("freshtunes") or {}).get("adim") == "gonderildi":
        return "FreshTunes'a gönderildi; bilgiler artık FreshTunes panelinden değişir"
    if rn.get("upc"):
        return "RouteNote'ta taslağı açıldı; değiştirmek için panelden taslağı sil ve kaydı sıfırla"
    return None


def _kisiler(deger) -> list[list[str]]:
    if not isinstance(deger, list) or len(deger) > 20:
        raise Hata("kişi listesi geçersiz")
    sonuc = []
    for x in deger:
        if not (isinstance(x, list) and len(x) == 2 and all(isinstance(y, str) and len(y) <= 80 for y in x)):
            raise Hata("kişi: [ad, soyad]")
        sonuc.append([x[0].strip(), x[1].strip()])
    return sonuc


def guncelle(calisma: Path, kimlik: str, alanlar: dict) -> dict:
    """Formdan gelen alanlar (yalnız `ALANLAR`'dakiler, türüyle). Boş metin "yok" demek; tarihler, kodlar biçim
    denetiminden geçer, eksiklik `kontrol`'ün işi (taslak yarım kaydedilebilir)."""
    meta = oku(calisma, kimlik)
    if neden := kilitli(meta):
        raise Hata(neden)
    for k, v in alanlar.items():
        if k not in ALANLAR:
            raise Hata(f"bilinmeyen alan: {k}")
        tur, *uzunluk = ALANLAR[k]
        if k in ("yazar_adlari", "soz_yazari_adlari"):
            v = _kisiler(v)
        elif k == "dagiticilar":
            if not isinstance(v, list) or any(x not in DAGITICILAR for x in v):
                raise Hata("bilinmeyen dağıtıcı")
            v = list(dict.fromkeys(v))
        elif tur is int:
            if v in (None, ""):
                v = None
            elif not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= 9999:
                raise Hata(f"{k}: sayı olmalı")
        elif tur is bool:
            if not isinstance(v, bool):
                raise Hata(f"{k}: evet/hayır olmalı")
        else:
            if not isinstance(v, str) or len(v) > uzunluk[0]:
                raise Hata(f"{k}: en çok {uzunluk[0]} karakter")
            v = v.strip()
            if k == "isrc":
                v = re.sub(r"[\s-]", "", v).upper()
                if v and not ISRC.fullmatch(v):
                    raise Hata("ISRC biçimi CC-XXX-YY-NNNNN olmalı (12 karakter, ör. TR-A1B-26-00001)")
            elif k == "upc":
                v = re.sub(r"\D", "", v)
                if v and not UPC.fullmatch(v):
                    raise Hata("UPC/EAN 12 ya da 13 rakam olmalı")
            elif k in ("yayin_tarihi", "orijinal_tarih") and v:
                try:
                    date.fromisoformat(v)
                except ValueError:
                    raise Hata(f"{k}: tarih YYYY-AA-GG olmalı") from None
            elif k == "spotify_sanatci_id" and v:
                bul = re.search(r"artist[/:]([A-Za-z0-9]{22})", v)
                v = bul[1] if bul else v
                if not SPOTIFY_ID.fullmatch(v):
                    raise Hata("Spotify sanatçı kimliği 22 karakter (ya da profil linki)")
            elif k == "dil" and v and v not in routenote.RN_DILLER:
                raise Hata("dil listeden seçilmeli")
            elif k == "tur" and v and v not in routenote.RN_TURLER:
                raise Hata("tür listeden seçilmeli")
        meta[k] = v
    return _yaz(calisma, kimlik, meta)


# ── dosyalar ─────────────────────────────────────────────────────────────────────────────────────────────────────
def _guvenli_ad(ad: str) -> str:
    ad = re.sub(r"[^\w.\- ]", "_", Path(ad or "dosya").name)[:120]
    return ad or "dosya"


def ses_kaydet(calisma: Path, kimlik: str, ad: str, veri: bytes) -> dict:
    """Bilgisayardan seçilen ses → `kaynak/` + `ses.flac` (44,1 kHz, 16 bit, stereo; RouteNote ve mağazaların ortak
    tabanı). Kayıplı kaynak (MP3, M4A, OGG) uyarılır: mağazalar kabul eder ama kalite düşük."""
    from yanki import ses

    meta = oku(calisma, kimlik)
    if neden := kilitli(meta):
        raise Hata(neden)
    uzanti = Path(ad).suffix.lower()
    if uzanti not in SES_UZANTILARI:
        raise Hata(f"ses WAV, FLAC, AIFF ya da MP3 olmalı ({uzanti or 'uzantısız'})")
    if not veri or len(veri) > EN_BUYUK_YUKLEME:
        raise Hata(f"ses boş ya da {EN_BUYUK_YUKLEME // 2**20} MB'tan büyük")
    k = klasor(calisma, kimlik)
    (k / "kaynak").mkdir(exist_ok=True)
    for eski in (k / "kaynak").glob("ses.*"):
        eski.unlink()
    kaynak = k / "kaynak" / f"ses{uzanti}"
    kaynak.write_bytes(veri)
    gecici = k / ".ses.yaziliyor.flac"
    r = subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(kaynak), "-vn",
                        "-ac", "2", "-ar", "44100", "-c:a", "flac", "-sample_fmt", "s16", str(gecici)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode or not gecici.exists():
        kaynak.unlink(missing_ok=True)
        gecici.unlink(missing_ok=True)  # yarım FLAC kalmasın (yükleyici yalnız ses.flac'ı alır, yine de)
        raise Hata(f"ses okunamadı: {(r.stderr or '').strip()[:200] or 'ffmpeg hata verdi'}")
    gecici.replace(k / "ses.flac")
    sure = ses.sure(k / "ses.flac")
    bilgi = {"ad": _guvenli_ad(ad), "boyut": len(veri), "sure": round(sure, 1),
             "flac_boyut": (k / "ses.flac").stat().st_size, "kayipli": uzanti in (".mp3", ".m4a", ".ogg"),
             **ses_olcumu(k / "ses.flac"), "zaman": datetime.now().isoformat(timespec="seconds")}
    meta = oku(calisma, kimlik)
    meta["ses"] = bilgi
    _yaz(calisma, kimlik, meta)
    return bilgi


SESSIZ_ESIK = 33  # 16 bit örnekte −60 dBFS: bunun altı sessizlik sayılır
TAM_OLCEK = 32766  # bu genliğe dayanan örnek kırpılmış sayılır (0 dBFS)


def ses_olcumu(yol: Path) -> dict:
    """Dağıtıcıların ses kuralları için (FreshTunes: başta/sonda en çok 5 sn sessizlik, 0 dBFS'e dayanmayan ses):
    baştaki ve sondaki sessizlik (sn), tepe (dBFS), tam ölçeğe dayanan örnek oranı. Dosya bloklarla okunur (uzun
    kayıt belleğe bütün alınmaz)."""
    import math

    import numpy as np
    import soundfile as sf

    ilk = son = None
    tepe = kirpik = n = 0
    with sf.SoundFile(str(yol)) as f:
        sr = f.samplerate
        for blok in f.blocks(blocksize=sr * 30, dtype="int16", always_2d=True):
            genlik = np.abs(blok.astype(np.int32)).max(axis=1)
            if (dolu := np.flatnonzero(genlik > SESSIZ_ESIK)).size:
                ilk = n + int(dolu[0]) if ilk is None else ilk
                son = n + int(dolu[-1])
            tepe = max(tepe, int(genlik.max(initial=0)))
            kirpik += int((genlik >= TAM_OLCEK).sum())
            n += len(blok)
    if ilk is None:
        return {"bas_sessizlik": round(n / sr, 1), "son_sessizlik": round(n / sr, 1), "tepe_db": None, "kirpik": 0.0}
    return {"bas_sessizlik": round(ilk / sr, 1), "son_sessizlik": round((n - 1 - son) / sr, 1),
            "tepe_db": round(20 * math.log10(tepe / 32768), 1), "kirpik": kirpik / n}


def kapak_kaydet(calisma: Path, kimlik: str, ad: str, veri: bytes, en_az: int = KAPAK_EN_AZ) -> dict:
    """Bilgisayardan seçilen görsel → `kapak.jpg`: ortadan kare, 3000×3000, RGB, JPG (RouteNote kuralı; diğer
    dağıtıcılar da kabul eder). 1400'den küçük reddedilir; 3000'den küçük büyütülür ve uyarılır."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    meta = oku(calisma, kimlik)
    if neden := kilitli(meta):
        raise Hata(neden)
    if not veri or len(veri) > 60 * 2**20:
        raise Hata("görsel boş ya da 60 MB'tan büyük")
    try:
        with Image.open(io.BytesIO(veri)) as im:
            im = ImageOps.exif_transpose(im)
            en, boy = im.size
            if min(en, boy) < en_az:
                raise Hata(f"kapak en az {en_az}×{en_az} olmalı ({en}×{boy})")
            kenar = min(en, boy)
            kare = im.convert("RGB").crop(((en - kenar) // 2, (boy - kenar) // 2, (en + kenar) // 2,
                                           (boy + kenar) // 2)).resize((3000, 3000), Image.Resampling.LANCZOS)
    except (UnidentifiedImageError, OSError) as e:
        raise Hata("görsel okunamadı (JPG ya da PNG olmalı)") from e
    k = klasor(calisma, kimlik)
    (k / "kaynak").mkdir(exist_ok=True)
    for eski in (k / "kaynak").glob("kapak.*"):
        eski.unlink()
    (k / "kaynak" / f"kapak{Path(ad).suffix.lower() or '.jpg'}").write_bytes(veri)
    gecici = k / "kapak.yaziliyor"
    kare.save(gecici, "JPEG", quality=92, optimize=True)
    gecici.replace(k / "kapak.jpg")
    bilgi = {"ad": _guvenli_ad(ad), "asil": [en, boy], "kirpildi": en != boy, "buyutuldu": kenar < 3000,
             "zaman": datetime.now().isoformat(timespec="seconds")}
    meta = oku(calisma, kimlik)
    meta["kapak"] = bilgi
    _yaz(calisma, kimlik, meta)
    return bilgi


# ── denetim ──────────────────────────────────────────────────────────────────────────────────────────────────────
def _dolu_kisiler(liste) -> list[list[str]]:
    return [x for x in liste or [] if (x[0] or x[1])]


def kontrol(calisma: Path, kimlik: str) -> dict:
    """{"eksik": [genel eksikler], "uyari": [...], "dagitici": {ad: [o dağıtıcıya özel eksikler]}}. Boş liste: hazır."""
    meta = oku(calisma, kimlik)
    k = klasor(calisma, kimlik)
    eksik, uyari = [], []
    if not meta.get("baslik"):
        eksik.append("Şarkının adı")
    if not meta.get("sanatci"):
        eksik.append("Ana sanatçı")
    if not (k / "ses.flac").exists():
        eksik.append("Ses dosyası")
    elif (meta.get("ses") or {}).get("youtube"):
        uyari.append("Ses YouTube'dan (kayıplı): master dosyan (WAV/FLAC) varsa sürükle, kalite daha iyi olur")
    elif (meta.get("ses") or {}).get("kayipli"):
        uyari.append("Ses kayıplı biçimden (MP3/M4A) çevrildi; mümkünse WAV ya da FLAC yükle")
    if not (k / "kapak.jpg").exists():
        eksik.append("Kapak görseli")
    elif (meta.get("kapak") or {}).get("kaynak") == "pinterest":
        uyari.append("Kapak Pinterest'ten (yayının asıl kapağı değil); FreshTunes kapağın sende olmasını istiyor: "
                     "orijinal kapağın varsa onu sürükle")
    elif (meta.get("kapak") or {}).get("buyutuldu"):
        uyari.append("Kapak 3000×3000'den küçüktü, büyütüldü: keskinlik düşebilir")
    yazarlar = _dolu_kisiler(meta.get("yazar_adlari"))
    if not yazarlar:
        eksik.append("En az bir besteci (ad + soyad)")
    elif any(not a or not s for a, s in yazarlar):
        eksik.append("Bestecilerin adı ve soyadı ayrı ayrı (tek adlı sanatçı için yasal soyadı)")
    if meta.get("soz_var") and not meta.get("soz_ayni"):
        sozler = _dolu_kisiler(meta.get("soz_yazari_adlari"))
        if not sozler or any(not a or not s for a, s in sozler):
            eksik.append("Söz yazarlarının adı ve soyadı")
    if meta.get("acik_icerik") not in (True, False):
        eksik.append("Açık içerik (küfür/argo) var mı")
    if not meta.get("dil"):
        eksik.append("Şarkının dili")
    if not meta.get("tur"):
        eksik.append("Tür")
    if meta.get("cover") and not meta.get("orijinal_sanatci"):
        eksik.append("Cover: orijinal sanatçı")
    if not meta.get("spotify_sanatci_id"):
        if "freshtunes" in (meta.get("dagiticilar") or []):
            uyari.append("Spotify profil linki yok: ilk yayında profil yayından sonra açılır. Daha önce yayının varsa "
                         "FreshTunes'ta profil linkini yapıştır (sanatçı adı profildekiyle birebir aynı olmalı)")
        else:
            uyari.append("Spotify profil kimliği yok: RouteNote hesaptaki aynı adlı profili kullanır, yoksa yeni "
                         "profil açar (ilk yayında normal)")
    if not meta.get("dagiticilar"):
        eksik.append("En az bir dağıtıcı")
    ses_bilgi = meta.get("ses") or {}
    if ses_bilgi.get("sure") and ses_bilgi["sure"] < 30:
        uyari.append("Şarkı 30 saniyeden kısa: mağazalar dinlenme saymayabilir")
    dag: dict[str, list[str]] = {}
    if "routenote" in (meta.get("dagiticilar") or []):
        rn = []
        if ses_bilgi.get("flac_boyut", 0) > routenote.EN_BUYUK_SES:
            rn.append(f"FLAC {ses_bilgi['flac_boyut'] / 2**20:.0f} MB; tarayıcıdan en çok "
                      f"{routenote.EN_BUYUK_SES // 2**20} MB (şarkı çok uzun)")
        if (t := meta.get("yayin_tarihi")) and _tarih_mi(t):
            gun = date.fromisoformat(t)
            if date.today() < gun < date.today() + timedelta(days=routenote.YAYIN_ASGARI_GUN):
                rn.append(f"Yayın tarihi en erken {date.today() + timedelta(days=routenote.YAYIN_ASGARI_GUN)} "
                          "(inceleme 5–10 iş günü) ya da boş bırak: onaylanınca yayında")
        dag["routenote"] = rn
    if (ilk := meta.get("orijinal_tarih")) and _tarih_mi(ilk):
        # ilk yayın geçmişte olmalı: ileri tarih mağazalarda "henüz çıkmamış" sayılır, RouteNote kaydı reddeder
        if date.fromisoformat(ilk) > date.today():
            eksik.append("İlk yayın tarihi gelecekte olamaz (daha önce yayınlanmadıysa boş bırak)")
        elif (yt := meta.get("yayin_tarihi")) and _tarih_mi(yt) and date.fromisoformat(ilk) > date.fromisoformat(yt):
            eksik.append("İlk yayın tarihi yayın tarihinden sonra olamaz")
    if (meta.get("sanatci") != meta.get("varsayilan_sanatci") and meta.get("spotify_sanatci_id")
            and meta.get("spotify_sanatci_id") == meta.get("varsayilan_spotify_id")):
        uyari.append(f"Spotify profili {meta.get('varsayilan_sanatci')}'in; sanatçı farklı olduğu için profile "
                     "bağlanmaz (RouteNote aynı adlı profili kullanır ya da yeni profil açar)")
    secili = meta.get("dagiticilar") or []
    if "routenote" in secili and "freshtunes" in secili:
        eksik.append("Aynı kaydı iki dağıtıcıya gönderme (mağazada iki kopya olur): RouteNote ya da FreshTunes")
    if "freshtunes" in secili:
        dag["freshtunes"] = _freshtunes_eksik(meta, ses_bilgi)
        if meta.get("cover"):
            uyari.append("FreshTunes'un cover kuralı doğrulanmadı: yüklemeden önce yardım merkezine bak")
        if ses_bilgi.get("kirpik", 0) > 1e-5:
            uyari.append(f"Ses 0 dBFS'e dayanıyor (tepe {ses_bilgi.get('tepe_db')} dBFS, kırpılma): FreshTunes "
                         "reddedebilir; mastering'i −1 dBTP'ye indir")
    if "elle" in secili:
        dag["elle"] = []
    return {"eksik": eksik, "uyari": uyari, "dagitici": dag}


def _freshtunes_eksik(meta: dict, ses_bilgi: dict) -> list[str]:
    ft = []
    if meta.get("yapay_zeka"):
        ft.append("FreshTunes yapay zekâyla üretilmiş kaydı kabul etmiyor (Hizmet Şartları §1); AI kaydı RouteNote'tan")
    if meta.get("sanatci") and meta.get("sanatci") == meta.get("varsayilan_sanatci"):
        ft.append(f"{meta['sanatci']} AI cover sanatçısı (RouteNote): FreshTunes'ta kendi sanatçı adınla yayınla")
    en_erken = date.today() + timedelta(days=FRESHTUNES_YAYIN_ASGARI_GUN)
    t = meta.get("yayin_tarihi")
    if not t or not _tarih_mi(t) or date.fromisoformat(t) < en_erken:
        ft.append(f"Yayın tarihi en erken {en_erken} (FreshTunes \"onaylanınca\" seçeneği yok; "
                  f"{FRESHTUNES_YAYIN_ONERI_GUN}–28 gün sonrası önerilir)")
    for yer, anahtar in (("Başta", "bas_sessizlik"), ("Sonda", "son_sessizlik")):
        if (sn := ses_bilgi.get(anahtar)) is not None and sn > FRESHTUNES_SESSIZLIK_SN:
            ft.append(f"{yer} {sn:.1f} sn sessizlik: FreshTunes en çok {FRESHTUNES_SESSIZLIK_SN:.0f} sn kabul ediyor "
                      "(sesi kırpıp yeniden yükle)")
    return ft


def _tarih_mi(t: str) -> bool:
    try:
        date.fromisoformat(t)
    except (TypeError, ValueError):
        return False
    return True


def hazir_mi(calisma: Path, kimlik: str, dagitici: str) -> list[str]:
    k = kontrol(calisma, kimlik)
    return k["eksik"] + k["dagitici"].get(dagitici, ["bu dağıtıcı seçili değil"])


# ── dağıtıcıya çeviri ────────────────────────────────────────────────────────────────────────────────────────────
def routenote_meta(meta: dict, kayitli_sid: str | None = None) -> dict:
    """Formdaki seçimler → RouteNote doldurucusunun okuduğu alanlar (`routenote.album_bilgisi`, `magazalar`)."""
    kapali = set()
    if meta.get("yapay_zeka"):
        kapali |= set(YAPAY_ZEKA_KAPALI)
    if meta.get("cover"):
        kapali |= set(KORE)
    if not meta.get("content_id"):
        kapali.add("YouTube Content ID")
    yazarlar = _dolu_kisiler(meta.get("yazar_adlari"))
    # kayıtlı profil (config) yalnız varsayılan sanatçıya: başka adla yayına Orvane'in profili bağlanmasın. Form
    # yeni taslakta kayıtlı profille dolu geliyor; sanatçı değiştirilip kutu öyle kaldıysa o profil de bağlanmaz.
    varsayilan = meta.get("sanatci") == meta.get("varsayilan_sanatci")
    yeni_profil = bool(meta.get("yeni_profil")) or not varsayilan
    sid = meta.get("spotify_sanatci_id") or None
    if sid and not varsayilan and sid in {meta.get("varsayilan_spotify_id"), kayitli_sid}:
        sid = None
    return {"yazar_adlari": yazarlar, "rn_tur": meta.get("tur"), "yeni_profil": yeni_profil, "rn_spotify_id": sid,
            "soz_yazari_adlari": yazarlar if meta.get("soz_ayni", True) else _dolu_kisiler(
                meta.get("soz_yazari_adlari")),
            "kapali_magazalar": sorted(kapali),
            "haric_bolgeler": list(MEKANIK_LISANS_ULKELER) if meta.get("cover") and not meta.get("mekanik_lisans")
            else []}


def routenote_hazirla(calisma: Path, kimlik: str) -> Path:
    """RouteNote doldurucusunun okuyacağı `metadata.json`'u günceller (formun türetilmiş alanları). Klasör döner."""
    import tomllib

    meta = oku(calisma, kimlik)
    try:  # hattın kayıtlı profili (config/yayin.toml; `calisma`nın yanında)
        with open(calisma.parent / "config" / "yayin.toml", "rb") as f:
            kayitli = tomllib.load(f).get("routenote", {}).get("spotify_sanatci_id") or None
    except (OSError, ValueError):
        kayitli = None
    meta.update(routenote_meta(meta, kayitli))
    _yaz(calisma, kimlik, meta)
    return klasor(calisma, kimlik)


def yayin_tarihi(meta: dict) -> date | None:
    return date.fromisoformat(meta["yayin_tarihi"]) if meta.get("yayin_tarihi") else None


def gonderim_sonucu(calisma: Path, kimlik: str, gonderildi: bool) -> str:
    """Son tıktan sonra yarıda kalan RouteNote gönderiminin paneldeki sonucu (ya da panelde elle gönderilen hazır
    taslak)."""
    meta = oku(calisma, kimlik)
    rn = meta.get("routenote") or {}
    if rn.get("adim") != "gonderiliyor" and not (gonderildi and rn.get("adim") == "hazir"):
        raise Hata(f"yarıda kalan gönderim yok (adım: {rn.get('adim') or '—'})")
    rn["adim"] = "gonderildi" if gonderildi else "hazir"
    if gonderildi:
        rn.setdefault("gonderim", date.today().isoformat())
    meta["routenote"] = rn
    _yaz(calisma, kimlik, meta)
    if gonderildi:
        return "gönderildi olarak kaydedildi"
    return ("taslakta duruyor olarak işaretlendi; otomasyon bu taslağı artık gönderemez (başka oturumda açıldı): "
            "panelde gönder ve \"Panelde gönderdim\", ya da panelden sil ve kaydı sıfırla")


def freshtunes_gonderildi(calisma: Path, kimlik: str) -> str:
    """Scryne formu FreshTunes'ta doldurup gönderdi: kayıt kilitlenir (bilgiler artık FreshTunes panelinden değişir),
    hesap etkinliği sayılır (3 ayda bir giriş şartı, `freshtunes_hatirlatma`)."""
    meta = oku(calisma, kimlik)
    if "freshtunes" not in (meta.get("dagiticilar") or []):
        raise Hata("FreshTunes seçili değil")
    if (meta.get("freshtunes") or {}).get("adim") == "gonderildi":
        raise Hata("zaten FreshTunes'a gönderildi olarak kayıtlı")
    if eksik := hazir_mi(calisma, kimlik, "freshtunes"):
        raise Hata("eksik: " + "; ".join(eksik))
    meta["freshtunes"] = {"adim": "gonderildi", "gonderim": date.today().isoformat(),
                          "yayin_tarihi": meta.get("yayin_tarihi")}
    _yaz(calisma, kimlik, meta)
    freshtunes_girdim(calisma)
    return (f"FreshTunes'a gönderildi olarak kaydedildi; yayın {meta.get('yayin_tarihi')}. İnceleme ücretsiz planda "
            "birkaç gün sürebilir; reddedilirse kaydı sıfırla, düzeltip yeniden gönder.")


def _freshtunes_kayit_yolu(calisma: Path) -> Path:
    return kok_klasor(calisma) / ".freshtunes.json"


def _ft_kayit(calisma: Path) -> dict:
    try:
        v = json.loads(_freshtunes_kayit_yolu(calisma).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return v if isinstance(v, dict) else {}


def freshtunes_girdim(calisma: Path, gun: date | None = None) -> None:
    """FreshTunes hesabına girildi (ya da yayın gönderildi): hareketsizlik sayacı sıfırlanır."""
    dosya.json_yaz(_freshtunes_kayit_yolu(calisma), {**_ft_kayit(calisma),
                                                     "son_giris": (gun or date.today()).isoformat()})


def kendi_sanatcilar(calisma: Path) -> list[str]:
    """Scryne'ın kendi yayın adları (Bulucu'daki kalkmış parçadan FreshTunes taslağı yalnız bunlara açılır,
    `yeniden_yayin`). Orvane burada olamaz: AI cover sanatçısı RouteNote'ta."""
    return [x for x in _ft_kayit(calisma).get("sanatcilar") or [] if isinstance(x, str) and x.strip()]


def kendi_sanatcilar_yaz(calisma: Path, adlar: list[str], kok: Path | None = None) -> list[str]:
    if not isinstance(adlar, list) or len(adlar) > 10 or any(not isinstance(x, str) or len(x) > 120 for x in adlar):
        raise Hata("en çok 10 sanatçı adı")
    temiz = list(dict.fromkeys(x.strip() for x in adlar if x.strip()))
    varsayilan = varsayilanlar(kok)["sanatci"] if kok else None
    if varsayilan and any(x.casefold() == varsayilan.casefold() for x in temiz):
        raise Hata(f"{varsayilan} AI cover sanatçısı (RouteNote); kendi adların arasına girmez")
    dosya.json_yaz(_freshtunes_kayit_yolu(calisma), {**_ft_kayit(calisma), "sanatcilar": temiz})
    return temiz


def freshtunes_durumu(calisma: Path, bugun: date | None = None) -> dict | None:
    """FreshTunes hesabının hareketsizlik durumu; FreshTunes'a hiç gönderilmemişse None. ToS §4: 3 ayda bir giriş
    şart, yoksa askı ve açmak 50 $."""
    bugun = bugun or date.today()
    gonderimler = []
    for p in kok_klasor(calisma).glob("*/metadata.json"):
        try:
            g = (json.loads(p.read_text(encoding="utf-8")).get("freshtunes") or {}).get("gonderim")
            if g:
                gonderimler.append(date.fromisoformat(g))
        except (OSError, ValueError):
            continue
    if not gonderimler:
        return None
    try:
        giris = date.fromisoformat(_ft_kayit(calisma)["son_giris"])
    except (ValueError, KeyError, TypeError):
        giris = None
    son = max([*gonderimler, *([giris] if giris else [])])
    gun = (bugun - son).days
    return {"son": son.isoformat(), "gun": gun, "kalan": FRESHTUNES_GIRIS_GUN - gun,
            "hatirlat": gun >= FRESHTUNES_HATIRLAT_GUN}


def freshtunes_hatirlatma(calisma: Path, bildir, bugun: date | None = None) -> None:
    """Gece koşusu: hesaba 75 günü geçkin girilmediyse haftada bir bildirir (odada "Bugün girdim" sayacı sıfırlar)."""
    d = freshtunes_durumu(calisma, bugun)
    if not d or not d["hatirlat"]:
        return
    ne = (f"{-d['kalan']} gündür süre doldu: hesap askıya alınmış olabilir (açmak 50 $)" if d["kalan"] < 0
          else f"{d['kalan']} gün içinde gir, yoksa hesap askıya alınır (açmak 50 $)")
    bildir("dagitim", "FreshTunes'a giriş yap",
           f"Son giriş/gönderim {d['gun']} gün önce; FreshTunes 3 ayda bir giriş istiyor. {ne}. Girince dinleme "
           "odası → Yükle → \"Bugün girdim\".",
           f"freshtunes:giris:{d['son']}:{(d['gun'] - FRESHTUNES_HATIRLAT_GUN) // 7}")  # haftada bir


def sifirla(calisma: Path, kimlik: str, dagitici: str = "routenote") -> str:
    """Dağıtıcı kaydı geçmişe: form yeniden düzenlenebilir. RouteNote: panelden silinen taslak, sonraki gönderim
    yeni taslak açar. FreshTunes: reddedilen ya da yanlışlıkla "gönderdim" denen yayın."""
    meta = oku(calisma, kimlik)
    if dagitici == "freshtunes":
        if not meta.get("freshtunes"):
            raise Hata("FreshTunes kaydı yok")
        meta.setdefault("freshtunes_gecmisi", []).append({**meta.pop("freshtunes"),
                                                          "sifirlandi": date.today().isoformat()})
        _yaz(calisma, kimlik, meta)
        return "FreshTunes kaydı sıfırlandı; form yeniden düzenlenebilir"
    rn = meta.get("routenote") or {}
    if not rn or rn.get("adim") == "gonderildi":
        raise Hata("açık RouteNote taslağı yok")
    meta.setdefault("routenote_gecmisi", []).append({**meta.pop("routenote"), "silindi": date.today().isoformat()})
    _yaz(calisma, kimlik, meta)
    return "RouteNote kaydı sıfırlandı; form yeniden düzenlenebilir"


def sil(calisma: Path, kimlik: str) -> None:
    import shutil

    meta = oku(calisma, kimlik)
    if (meta.get("routenote") or {}).get("upc"):
        raise Hata("RouteNote'ta taslağı ya da yayını var; önce panelden sil ve kaydı sıfırla")
    if (meta.get("freshtunes") or {}).get("adim") == "gonderildi":
        raise Hata("FreshTunes'a gönderildi; önce kaydı sıfırla")
    shutil.rmtree(klasor(calisma, kimlik))


# ── elle paket (ZIP) ─────────────────────────────────────────────────────────────────────────────────────────────
def _kisi_metni(liste) -> str:
    return ", ".join(f"{a} {s}".strip() for a, s in _dolu_kisiler(liste)) or "—"


def bilgi_metni(meta: dict) -> str:
    """Dağıtıcı formlarının diliyle (İngilizce alan adları) bütün bilgiler; ZIP'te `BILGILER.txt`."""
    yazarlar = _kisi_metni(meta.get("yazar_adlari"))
    satirlar = [
        ("Title", meta.get("baslik")), ("Version", meta.get("surum")), ("Primary artist", meta.get("sanatci")),
        ("Spotify artist ID", meta.get("spotify_sanatci_id") or ("(new profile)" if meta.get("yeni_profil") else "")),
        ("Language", (meta.get("dil") or "").replace("_", " ")), ("Genre", meta.get("tur")),
        ("Explicit", "Yes" if meta.get("acik_icerik") else "No"),
        ("Lyrics", "Yes" if meta.get("soz_var") else "No (instrumental)"),
        ("Cover song", f"Yes — original by {meta.get('orijinal_sanatci')}" if meta.get("cover") else "No"),
        ("Composers", yazarlar),
        ("Lyricists", yazarlar if meta.get("soz_ayni", True) else _kisi_metni(meta.get("soz_yazari_adlari"))),
        ("Producer", meta.get("uretici") or meta.get("sanatci")),
        ("© (composition)", f"{meta.get('c_yil') or ''} {meta.get('c_sahibi') or yazarlar}".strip()),
        ("℗ (recording)", f"{meta.get('p_yil') or ''} {meta.get('p_sahibi') or meta.get('sanatci') or ''}".strip()),
        ("Label", meta.get("etiket") or meta.get("sanatci")),
        ("ISRC", meta.get("isrc") or "(assigned by distributor)"), ("UPC/EAN", meta.get("upc") or "(assigned)"),
        ("Release date", meta.get("yayin_tarihi") or "as soon as approved"),
        ("Original release date", meta.get("orijinal_tarih")),
        ("Preview start", f"{meta['onizleme_sn'] // 60}:{meta['onizleme_sn'] % 60:02d}"
         if meta.get("onizleme_sn") is not None else None),
        ("AI-generated audio", "Yes" if meta.get("yapay_zeka") else "No"),
        ("YouTube Content ID", "Yes" if meta.get("content_id") else "No"),
        ("Duration", f"{int((meta.get('ses') or {}).get('sure', 0)) // 60}:"
                     f"{int((meta.get('ses') or {}).get('sure', 0)) % 60:02d}" if meta.get("ses") else None),
    ]
    govde = "\n".join(f"{a + ':':24} {d}" for a, d in satirlar if d not in (None, ""))
    if meta.get("cover") and not meta.get("mekanik_lisans"):
        govde += ("\n\nCover without a mechanical licence: exclude United States, Canada, Mexico, India, Pakistan "
                  "(or buy a licence through the distributor).")
    if meta.get("notlar"):
        govde += f"\n\nNotes:\n{meta['notlar']}"
    return govde + "\n\nFiles: audio.flac (44.1 kHz / 16-bit), artwork.jpg (3000×3000 RGB)\n"


def freshtunes_metni(meta: dict) -> str:
    """FreshTunes formu için kopyala-yapıştır liste: alan adları formun dilinde (İngilizce), başta Türkçe kontrol
    listesi. Formun alan sırası giriş yapmadan görülemedi (docs/arastirma/09): sıra mantıksal, ilk yüklemede formla
    karşılaştırılıp düzeltilecek."""
    yazarlar = _dolu_kisiler(meta.get("yazar_adlari"))
    sozler = yazarlar if meta.get("soz_ayni", True) else _dolu_kisiler(meta.get("soz_yazari_adlari"))

    def kisiler(liste) -> str:
        return "\n".join(f"    First name: {a}   Last name: {s}" for a, s in liste) or "    —"

    sure = int((meta.get("ses") or {}).get("sure", 0))
    on = meta.get("onizleme_sn")
    satirlar = [
        ("Release type", "Single"), ("Release title", meta.get("baslik")), ("Version", meta.get("surum")),
        ("Artist (pseudonym)", meta.get("sanatci")),
        ("Spotify Artist ID", f"https://open.spotify.com/artist/{meta['spotify_sanatci_id']}"
         if meta.get("spotify_sanatci_id") else "(boş bırak: ilk yayında profil yayından sonra açılır)"),
        ("Genre", meta.get("tur")), ("Language", (meta.get("dil") or "").replace("_", " ")),
        ("Explicit", "Yes" if meta.get("acik_icerik") else "No"),
        ("Instrumental", "No" if meta.get("soz_var") else "Yes"),
        ("Track title", meta.get("baslik")), ("Duration", f"{sure // 60}:{sure % 60:02d}" if sure else None),
        ("ISRC", meta.get("isrc") or "(boş bırak: FreshTunes ücretsiz atar)"),
        ("UPC/EAN", meta.get("upc") or "(boş bırak: FreshTunes ücretsiz atar)"),
        ("Producer", meta.get("uretici") or None), ("Label", meta.get("etiket") or meta.get("sanatci")),
        ("© line", f"{meta.get('c_yil') or ''} {meta.get('c_sahibi') or _kisi_metni(yazarlar)}".strip()),
        ("℗ line", f"{meta.get('p_yil') or ''} {meta.get('p_sahibi') or meta.get('sanatci') or ''}".strip()),
        ("Release date", meta.get("yayin_tarihi")),
        ("Previously published", f"Yes — {meta['orijinal_tarih']}" if meta.get("orijinal_tarih") else "No"),
        ("Preview / TikTok start", f"{on // 60}:{on % 60:02d}" if on is not None else None),
        ("YouTube Content ID", "Yes (FreshTunes %20 alır)" if meta.get("content_id") else "No"),
    ]
    govde = "\n".join(f"{a + ':':26} {d}" for a, d in satirlar if d not in (None, ""))
    kontrol = [
        "FreshTunes → Artists: sanatçıyı bu adla aç (yayından sonra ad değişmez; ücretsiz planda tek sanatçı).",
        "Ses: audio.flac (44,1 kHz / 16 bit stereo). Kapak: artwork.jpg (3000×3000 RGB). Kapakta yalnız sanatçı ve "
        "şarkı adı yazabilir (metadata ile birebir); URL, logo, QR, \"Spotify'da\" gibi ifade yok.",
        "Besteci ve söz yazarları gerçek ad-soyadla (ayrı kutular).",
        "Yapay zekâ: FreshTunes AI kaydı almıyor; bu kayıt insan yapımı olmalı.",
        f"Yayın tarihi en erken yüklemeden {FRESHTUNES_YAYIN_ASGARI_GUN} gün sonra; Spotify'a özel saat için 14 gün.",
        "Sözler mağazalara gitmiyor: istersen Musixmatch'e ayrıca ekle.",
        "Gönderince dinleme odası → Yükle → bu taslak → \"FreshTunes'a gönderdim\".",
        "Para: Payoneer ile çek (ücretsiz planda en az 25 $). 3 ayda bir hesaba gir (yoksa askı, açmak 50 $).",
    ]
    return (f"FRESHTUNES — {meta.get('baslik') or ''}\n\nKontrol listesi:\n"
            + "\n".join(f"  [ ] {x}" for x in kontrol)
            + "\n\nForm alanları:\n" + govde
            + "\nComposers:\n" + kisiler(yazarlar)
            + "\nLyricists:\n" + (kisiler(sozler) if meta.get("soz_var") else "    —")
            + (f"\n\nNotlar:\n{meta['notlar']}" if meta.get("notlar") else "") + "\n")


def paket_zip(calisma: Path, kimlik: str, dagitici: str = "elle") -> tuple[bytes, str]:
    """Elle yüklenecek dağıtıcının paketi: ses, kapak, bilgi listesi (`elle`: genel, `freshtunes`: FreshTunes formunun
    alanları; FreshTunes'ta eksik varsa paket inmez)."""
    if dagitici not in ("elle", "freshtunes"):
        raise Hata("bu dağıtıcının elle paketi yok")
    meta = oku(calisma, kimlik)
    k = klasor(calisma, kimlik)
    if not (k / "ses.flac").exists() or not (k / "kapak.jpg").exists():
        raise Hata("önce ses ve kapak yükle")
    if dagitici == "freshtunes" and (eksik := hazir_mi(calisma, kimlik, "freshtunes")):
        raise Hata("eksik: " + "; ".join(eksik))
    ad = re.sub(r'[\\/:*?"<>|]+', " ", f"{meta.get('sanatci') or 'Sanatci'} - {meta.get('baslik') or kimlik}").strip()
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as z:
        z.write(k / "ses.flac", f"{ad}/audio.flac")
        z.write(k / "kapak.jpg", f"{ad}/artwork.jpg")
        if dagitici == "freshtunes":
            z.writestr(f"{ad}/FRESHTUNES.txt", freshtunes_metni(meta))
        else:
            z.writestr(f"{ad}/BILGILER.txt", bilgi_metni(meta))
        z.writestr(f"{ad}/metadata.json", json.dumps({x: meta.get(x) for x in ALANLAR}, ensure_ascii=False, indent=2))
    meta.setdefault(dagitici, {})["indirme"] = datetime.now().isoformat(timespec="seconds")
    _yaz(calisma, kimlik, meta)
    if dagitici == "freshtunes":
        return tampon.getvalue(), f"{ad} (FreshTunes).zip"
    return tampon.getvalue(), f"{ad}.zip"


# ── liste ────────────────────────────────────────────────────────────────────────────────────────────────────────
def hal(meta: dict) -> str:
    rn = meta.get("routenote") or {}
    if rn.get("adim") == "gonderildi":
        return "gonderildi"
    if rn.get("adim") == "gonderiliyor":
        return "kontrol"
    if rn.get("upc"):
        return "rn_taslak"
    if (meta.get("freshtunes") or {}).get("adim") == "gonderildi":
        return "gonderildi"
    return "taslak"


def liste(calisma: Path) -> list[dict]:
    sonuc = []
    for p in sorted(kok_klasor(calisma).glob("*/metadata.json")):
        try:
            m = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        k = p.parent
        sonuc.append({"kimlik": k.name, "baslik": m.get("baslik") or "Adsız taslak", "sanatci": m.get("sanatci"),
                      "hal": hal(m), "guncel": m.get("guncel"), "kapak": (k / "kapak.jpg").exists(),
                      "ses": (k / "ses.flac").exists(), "dagiticilar": m.get("dagiticilar") or [],
                      "upc": (m.get("routenote") or {}).get("upc"), "isrc": (m.get("routenote") or {}).get("isrc")
                      or m.get("isrc") or None, "adim": (m.get("routenote") or {}).get("adim")})
    return sorted(sonuc, key=lambda x: x["guncel"] or "", reverse=True)
