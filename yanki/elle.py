"""Elle yayın taslağı (Scryne 2026-10-16: "bir taslak olsun, ben şarkı yüklemek istediğimde elimle doldurayım, sonra
dağıtıcıyı seçeyim, sen otomatik at; ISRC falan, bilgisayarımdan yükleme").

Yanki'nin cover hattından bağımsız: kendi şarkın, başka bir kayıt, elle hazırladığın her şey. Dinleme odası → Yükle'de
form doldurulur, ses ve kapak bilgisayardan seçilir; hat dosyaları dağıtıcının istediği biçime çevirir (ses: FLAC
44,1 kHz 16 bit; kapak: 3000×3000 RGB JPG, ortadan kare), alanları denetler ve seçilen dağıtıcıya gönderir.

Dağıtıcılar (`DAGITICILAR`):
- **RouteNote:** form tarayıcıyla doldurulur ve aynı oturumda gönderilir (`routenote.RouteNote.yukle_klasor`; yayın
  sayfası yalnız taslağı dolduran oturumda dolu, 2026-10-16). UPC'yi RouteNote atar; ISRC boşsa o da.
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


def yeni(calisma: Path, kok: Path, baslik: str = "") -> dict:
    from yanki import liste

    v = varsayilanlar(kok)
    taban = liste.kimlik(v["sanatci"] or "taslak", baslik or f"taslak {datetime.now():%Y%m%d %H%M%S}")
    kimlik, n = taban, 2
    while kok_klasor(calisma).joinpath(kimlik).exists():
        kimlik, n = f"{taban}-{n}", n + 1
    klasor(calisma, kimlik).mkdir(parents=True)
    return _yaz(calisma, kimlik, {"kimlik": kimlik, "baslik": baslik.strip(), **{k: v[k] for k in v if k != "baslik"},
                                  "varsayilan_sanatci": v["sanatci"],
                                  "olusturma": datetime.now().isoformat(timespec="seconds")})


def kilitli(meta: dict) -> str | None:
    """Gönderilmiş ya da RouteNote'ta taslağı açılmış kaydın alanları değişmez (dağıtıcıdaki kopya ayrışır)."""
    rn = meta.get("routenote") or {}
    if rn.get("adim") in ("gonderiliyor", "gonderildi"):
        return "RouteNote'a gönderildi; bilgiler artık RouteNote panelinden değişir"
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
    gecici = k / "ses.yaziliyor.flac"
    r = subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(kaynak), "-vn",
                        "-ac", "2", "-ar", "44100", "-c:a", "flac", "-sample_fmt", "s16", str(gecici)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode or not gecici.exists():
        kaynak.unlink(missing_ok=True)
        raise Hata(f"ses okunamadı: {(r.stderr or '').strip()[:200] or 'ffmpeg hata verdi'}")
    gecici.replace(k / "ses.flac")
    sure = ses.sure(k / "ses.flac")
    bilgi = {"ad": _guvenli_ad(ad), "boyut": len(veri), "sure": round(sure, 1),
             "flac_boyut": (k / "ses.flac").stat().st_size, "kayipli": uzanti in (".mp3", ".m4a", ".ogg"),
             "zaman": datetime.now().isoformat(timespec="seconds")}
    meta = oku(calisma, kimlik)
    meta["ses"] = bilgi
    _yaz(calisma, kimlik, meta)
    return bilgi


def kapak_kaydet(calisma: Path, kimlik: str, ad: str, veri: bytes) -> dict:
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
            if min(en, boy) < KAPAK_EN_AZ:
                raise Hata(f"kapak en az {KAPAK_EN_AZ}×{KAPAK_EN_AZ} olmalı ({en}×{boy})")
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
    elif (meta.get("ses") or {}).get("kayipli"):
        uyari.append("Ses kayıplı biçimden (MP3/M4A) çevrildi; mümkünse WAV ya da FLAC yükle")
    if not (k / "kapak.jpg").exists():
        eksik.append("Kapak görseli")
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
        uyari.append("Spotify profil kimliği yok: RouteNote hesaptaki aynı adlı profili kullanır, yoksa yeni profil "
                     "açar (ilk yayında normal)")
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
        if t := meta.get("yayin_tarihi"):
            gun = date.fromisoformat(t)
            if date.today() < gun < date.today() + timedelta(days=routenote.YAYIN_ASGARI_GUN):
                rn.append(f"Yayın tarihi en erken {date.today() + timedelta(days=routenote.YAYIN_ASGARI_GUN)} "
                          "(inceleme 5–10 iş günü) ya da boş bırak: onaylanınca yayında")
        dag["routenote"] = rn
    if "elle" in (meta.get("dagiticilar") or []):
        dag["elle"] = []
    return {"eksik": eksik, "uyari": uyari, "dagitici": dag}


def hazir_mi(calisma: Path, kimlik: str, dagitici: str) -> list[str]:
    k = kontrol(calisma, kimlik)
    return k["eksik"] + k["dagitici"].get(dagitici, ["bu dağıtıcı seçili değil"])


# ── dağıtıcıya çeviri ────────────────────────────────────────────────────────────────────────────────────────────
def routenote_meta(meta: dict) -> dict:
    """Formdaki seçimler → RouteNote doldurucusunun okuduğu alanlar (`routenote.album_bilgisi`, `magazalar`)."""
    kapali = set()
    if meta.get("yapay_zeka"):
        kapali |= set(YAPAY_ZEKA_KAPALI)
    if meta.get("cover"):
        kapali |= set(KORE)
    if not meta.get("content_id"):
        kapali.add("YouTube Content ID")
    yazarlar = _dolu_kisiler(meta.get("yazar_adlari"))
    # kayıtlı profil (config) yalnız varsayılan sanatçıya: başka adla yayına Orvane'in profili bağlanmasın
    yeni_profil = bool(meta.get("yeni_profil")) or meta.get("sanatci") != meta.get("varsayilan_sanatci")
    return {"yazar_adlari": yazarlar, "rn_tur": meta.get("tur"), "yeni_profil": yeni_profil,
            "soz_yazari_adlari": yazarlar if meta.get("soz_ayni", True) else _dolu_kisiler(
                meta.get("soz_yazari_adlari")),
            "kapali_magazalar": sorted(kapali),
            "haric_bolgeler": list(MEKANIK_LISANS_ULKELER) if meta.get("cover") and not meta.get("mekanik_lisans")
            else []}


def routenote_hazirla(calisma: Path, kimlik: str) -> Path:
    """RouteNote doldurucusunun okuyacağı `metadata.json`'u günceller (formun türetilmiş alanları). Klasör döner."""
    meta = oku(calisma, kimlik)
    meta.update(routenote_meta(meta))
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
    return "gönderildi olarak kaydedildi" if gonderildi else "taslak gönderime hazır olarak işaretlendi"


def sifirla(calisma: Path, kimlik: str) -> str:
    """Panelden silinen RouteNote taslağının kaydı geçmişe: form yeniden düzenlenebilir, sonraki gönderim yeni
    taslak açar."""
    meta = oku(calisma, kimlik)
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


def paket_zip(calisma: Path, kimlik: str) -> tuple[bytes, str]:
    meta = oku(calisma, kimlik)
    k = klasor(calisma, kimlik)
    if not (k / "ses.flac").exists() or not (k / "kapak.jpg").exists():
        raise Hata("önce ses ve kapak yükle")
    ad = re.sub(r'[\\/:*?"<>|]+', " ", f"{meta.get('sanatci') or 'Sanatci'} - {meta.get('baslik') or kimlik}").strip()
    tampon = io.BytesIO()
    with zipfile.ZipFile(tampon, "w", zipfile.ZIP_STORED) as z:
        z.write(k / "ses.flac", f"{ad}/audio.flac")
        z.write(k / "kapak.jpg", f"{ad}/artwork.jpg")
        z.writestr(f"{ad}/BILGILER.txt", bilgi_metni(meta))
        z.writestr(f"{ad}/metadata.json", json.dumps({x: meta.get(x) for x in ALANLAR}, ensure_ascii=False, indent=2))
    meta.setdefault("elle", {})["indirme"] = datetime.now().isoformat(timespec="seconds")
    _yaz(calisma, kimlik, meta)
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
