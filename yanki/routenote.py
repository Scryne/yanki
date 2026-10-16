"""RouteNote'a tarayıcıyla yükleme (Scryne 2026-10-15: "RouteNote'a otomatik yüklemeyi yapmanı istiyorum").

RouteNote'un API'si yok (`docs/arastirma/08`). Hat, formu Scryne'ın elle doldurduğu sırayla (`paket._routenote_formu`,
ilk yükleme 2026-10-08) Playwright ile doldurur. Şart metni (routenote.com/termsandconditions, madde 2, 2026-10-15)
botla veri toplamayı ve dinlenme şişirmeyi yasaklıyor; hesap sahibinin kendi yayınını yüklemesini değil. Bu yüzden:
yalnız kendi hesabımız, yalnız yükleme formu, insan hızında; yayın listesi okunmaz (durum e-postadan / `yanki
yuklendi`'den).

Oturum: `calisma/.routenote_profil` kalıcı Chrome profili (Scryne'ın asıl Chrome'u değil). Giriş bir kez elle
(`yanki routenote giris`); şifre hiçbir yerde tutulmaz. Oturum düşerse yükleme durur ve bildirir, giriş denemez.
"""

import contextlib
import json
import re
import time
from datetime import date, timedelta
from pathlib import Path

GIRIS_URL = "https://www.routenote.com/rn/login"
ANA_URL = "https://www.routenote.com/rn/"
RN = "https://www.routenote.com/rn"
PROFIL = ".routenote_profil"
YENI_PROFIL = "Create a new profile"  # sanatçı önerilerinin son satırı (Spotify'da profil yokken)


class OturumYok(RuntimeError):
    """RouteNote oturumu yok ya da düştü: `yanki routenote giris` gerekir."""


class Mesgul(RuntimeError):
    """RouteNote tarayıcı profili başka bir işte açık (oda işi, gece yüklemesi, giriş) ya da paket o an yenileniyor."""


TARAYICI_KILIDI = ".routenote.kilit"


@contextlib.contextmanager
def _tarayici_kilidi(calisma: Path):
    """Profil aynı anda tek tarayıcıda açılabilir; ikinci iş Chrome'un belirsiz hatası yerine açık bir hatayla durur."""
    from yanki import kilit

    with kilit.tek_kosu(calisma / TARAYICI_KILIDI) as alindi:
        if not alindi:
            raise Mesgul("RouteNote tarayıcısı başka bir işte açık (oda işi, gece yüklemesi ya da giriş); bitince "
                         "yeniden dene")
        yield


def baglam(calisma: Path, pw, gorunur: bool = True):
    """Kalıcı profil: sistemdeki Chrome (Playwright'ın Chromium'u değil; giriş sayfası Cloudflare arkasında)."""
    return pw.chromium.launch_persistent_context(
        str(calisma / PROFIL), channel="chrome", headless=not gorunur, viewport={"width": 1366, "height": 900},
        locale="en-GB", args=["--disable-blink-features=AutomationControlled"])


def giris_sayfasinda(sayfa) -> bool:
    return "/login" in sayfa.url


def giris(calisma: Path, bekle_sn: int = 600) -> bool:
    """Tarayıcıyı giriş sayfasında açar, Scryne giriş yapana kadar bekler (URL giriş sayfasından çıkınca)."""
    from playwright.sync_api import sync_playwright

    with _tarayici_kilidi(calisma), sync_playwright() as pw:
        b = baglam(calisma, pw)
        s = b.pages[0] if b.pages else b.new_page()
        s.goto(GIRIS_URL)
        son = time.time() + bekle_sn
        while time.time() < son:
            s.wait_for_timeout(2000)
            if not giris_sayfasinda(s) and "routenote.com" in s.url:
                s.wait_for_timeout(3000)  # çerezler yazılsın
                b.close()
                return True
        b.close()
        return False


def kesif(calisma: Path, url: str, ad: str) -> Path:
    """Bir sayfanın yapısını kaydeder (geliştirme: seçiciler buradan). Hiçbir şeye tıklamaz, form doldurmaz."""
    from playwright.sync_api import sync_playwright

    hedef = calisma / "_spike" / "routenote"
    hedef.mkdir(parents=True, exist_ok=True)
    with _tarayici_kilidi(calisma), sync_playwright() as pw:
        b = baglam(calisma, pw)
        s = b.pages[0] if b.pages else b.new_page()
        s.goto(url)
        s.wait_for_load_state("networkidle")
        if giris_sayfasinda(s):
            b.close()
            raise OturumYok("RouteNote oturumu yok: `yanki routenote giris`")
        s.screenshot(path=str(hedef / f"{ad}.png"), full_page=True)
        (hedef / f"{ad}.html").write_text(s.content(), encoding="utf-8")
        (hedef / f"{ad}.aria.txt").write_text(s.locator("body").aria_snapshot(), encoding="utf-8")
        (hedef / f"{ad}.json").write_text(json.dumps({"url": s.url, "baslik": s.title()}, ensure_ascii=False),
                                          encoding="utf-8")
        b.close()
    return hedef


# ── form ──────────────────────────────────────────────────
# Sayfalar Drupal formu; açılır listeler salt okunur kutu + tıklanan `div` (değeri sayfanın kendi JS'i yazar). Bu
# yüzden alanlar gerçek tıklamayla doldurulur, değer JS'le basılmaz (tarih hariç: takvim kutusu salt okunur, biçim
# `Calendar.setup` → `%Y/%m/%d`). Seçiciler 2026-10-15'te `calisma/_spike/routenote/` kayıtlarından.


def _sohbeti_kapat(s) -> None:
    """RouteNote'un "Luna" sohbet penceresi kendiliğinden açılıp alanların üstünü örtebiliyor."""
    s.add_style_tag(content="df-messenger {display: none !important}")  # Dialogflow Messenger


def _sec(s, kutu: str, secenek: str) -> None:
    """Açılır liste: kutuya tıkla, seçeneği (`div#<değer>`) tıkla, kutunun değerini doğrula."""
    s.click(kutu)
    s.locator(f'div[id="{secenek}"]').filter(visible=True).first.click()
    deger = s.input_value(kutu)
    if deger.rstrip("*") != secenek and not deger.startswith(secenek.split("_")[0]):
        raise RuntimeError(f"{kutu}: '{secenek}' seçilemedi (kutuda '{deger}')")


def _isaretle(s, kutu: str) -> None:
    if not s.is_checked(kutu):
        s.click(kutu)


def _satirlar(s, ekle: str, ad: str, soyad: str, kisiler: list[tuple[str, str]]) -> None:
    """Çok satırlı kişi alanı (yazar, söz yazarı): her ek kişi için "Add …", sonra adın son görünür kutusu.
    Satır kimlikleri tutarsız (first_composer2, first_lyricist1), alan adı aynı kalıyor."""
    for i, (a, sa) in enumerate(kisiler):
        if i:
            s.click(ekle)
        s.locator(f'input[name="{ad}"]').filter(visible=True).nth(i).fill(a)
        s.locator(f'input[name="{soyad}"]').filter(visible=True).nth(i).fill(sa)


def _sanatci(s, kutu: str, ad: str, spotify_id: str | None) -> None:
    """Sanatçı Spotify aramasından seçilmeli (yazmak yetmez: "Primary Artist field is required"). Profil kimliği
    biliniyorsa o; yoksa yeni profil. Hesapta aynı ada bağlı profil varsa RouteNote sorar: var olan kullanılır."""
    s.click(kutu)
    s.fill(kutu, "")
    s.type(kutu, ad, delay=80)
    oneri = s.locator(".autocomplete-suggestion").filter(visible=True)
    oneri.first.wait_for()
    if spotify_id:
        hedef = oneri.locator(f'xpath=self::*[contains(@data-langartisturi, "{spotify_id}")]').first
        try:
            hedef.wait_for(timeout=15000)  # öneriler sırayla geliyor: ilk satır görünürken profil henüz yok olabilir
        except Exception as e:  # noqa: BLE001 — Playwright zaman aşımı
            raise RuntimeError(f"Spotify profili ({spotify_id}) önerilerde yok; yeni profil açılmadı") from e
        hedef.click()
    else:
        oneri.filter(has_text=YENI_PROFIL).first.click()
    s.wait_for_timeout(1200)
    if s.locator("#rn_btn_exist").is_visible():
        s.click("#rn_btn_exist")
    if s.input_value(kutu) != ad:
        raise RuntimeError(f"sanatçı seçilemedi: kutuda '{s.input_value(kutu)}'")


def _tarih(s, kutu: str, gun: date | None) -> None:
    # boş tarih sayfanın "Clear Date"i gibi olaysız yazılır: `change` sayfanın check_ssd'sini çağırıyor, o da boş
    # değeri geçersiz tarih sayıp hata penceresi (#Comp_terms5) açıyor, pencere sonraki tıkları yutuyor (2026-10-16)
    s.eval_on_selector(kutu, "(e, v) => { e.value = v; if (v) e.dispatchEvent(new Event('change', {bubbles: true})) }",
                       gun.strftime("%Y/%m/%d") if gun else "")


def _tarihler(s, yayin: date | None, ilk: date | None = None) -> None:
    """"Originally Released" ve "Sales Start Date". `yayin` None: satış tarihi boş kalır, yayın onaylanınca mağazalara
    gider (form: "If blank, your release is delivered immediately after approval"; Scryne 2026-10-15 "en erken"). Boş
    satış tarihiyle ileri ilk yayın tarihi kabul edilmiyor, ilk yayın o zaman bugün. `ilk`: daha önce yayınlanmış
    şarkının ilk yayın tarihi (elle taslak)."""
    _tarih(s, "#edit_album_info_org_date", ilk or yayin or date.today())
    _tarih(s, "#edit_album_info_sale_date", yayin)


def _secim(s, evet: str, hayir: str, deger: bool) -> None:
    """Evet/Hayır kutu çifti: istenen işaretlenir (sayfanın kendi JS'i karşıtını boşaltır; Yanki'nin cover yolu
    2026-10-15'ten beri böyle), karşıtı hâlâ işaretliyse o da boşaltılır."""
    istenen, karsit = (evet, hayir) if deger else (hayir, evet)
    _isaretle(s, istenen)
    if s.is_checked(karsit):
        s.click(karsit)
    if not s.is_checked(istenen) or s.is_checked(karsit):
        raise RuntimeError(f"{istenen} / {karsit} seçimi tutmadı")


def kisi_adi(ad: str) -> str:
    """Künyedeki takma ad mağazaya gitmez: `Joseph “Joe”` → `Joseph`."""
    return " ".join(re.sub(r"[\"“”„«»][^\"“”„«»]*[\"“”„«»]|\([^)]*\)", " ", ad).split())


def yazarlar(meta: dict) -> list[tuple[str, str]]:
    """Besteciler: elle taslakta `yazar_adlari` (Scryne yazar), Yanki cover paketinde orijinalin künyesi."""
    from yanki import paket

    if adlar := meta.get("yazar_adlari"):
        return [(kisi_adi(a), kisi_adi(s)) for a, s in adlar]
    return [(kisi_adi(a), kisi_adi(s)) for a, s in paket._yazarlar(meta)]


def soz_yazarlari(meta: dict) -> list[tuple[str, str]]:
    if adlar := meta.get("soz_yazari_adlari"):
        return [(kisi_adi(a), kisi_adi(s)) for a, s in adlar]
    return yazarlar(meta)


def rn_dil(meta: dict) -> str | None:
    """RouteNote'un dil seçeneği: Yanki paketinde Whisper kodu ("en"), elle taslakta doğrudan RouteNote adı."""
    d = meta.get("dil")
    return RN_DIL.get(d) or (d if d in RN_DILLER else None)


# Söz dili (Whisper kodu) → RouteNote'un dil seçeneği (`div#<kimlik>`, album.html 2026-10-15). Listede olmayan dil
# taslak açılmadan durdurulur: yanlış dil seçmek yerine Scryne seçer.
RN_DIL = {"en": "English", "tr": "Turkish", "fr": "French", "es": "Spanish", "pt": "Portuguese", "de": "German",
          "it": "Italian", "nl": "Dutch", "ru": "Russian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese_Simplified",
          "yue": "Cantonese", "ar": "Arabic", "pl": "Polish", "sv": "Swedish", "id": "Indonesian", "hi": "Hindi",
          "tl": "Tagalog", "uk": "Ukrainian", "vi": "Vietnamese", "th": "Thai", "he": "Hebrew", "el": "Greek",
          "fi": "Finnish", "da": "Danish", "no": "Norwegian", "nb": "Norwegian", "cs": "Czech", "sk": "Slovak",
          "hu": "Hungarian", "ro": "Romanian", "bg": "Bulgarian", "hr": "Croatian", "sl": "Slovenian", "ms": "Malay",
          "fa": "Persian", "ur": "Urdu", "ta": "Tamil", "te": "Telugu", "bn": "Bengali", "pa": "Punjabi",
          "ca": "Catalan", "et": "Estonian", "lv": "Latvian", "lt": "Lithuanian", "is": "Icelandic", "ga": "Irish",
          "af": "Afrikaans", "zu": "Zulu", "kk": "Kazakh", "lo": "Lao", "ht": "Haitian", "la": "Latin"}
# RouteNote formunun seçenekleri (album.html, 2026-10-15): dil ve tür `div#<ad>`
RN_DILLER = (
    "Arabic", "Bengali", "Bulgarian", "Cantonese", "Catalan", "Chinese_Simplified", "Chinese_Traditional", "Croatian",
    "Czech", "Danish", "Dutch", "English", "Estonian", "Finnish", "French", "German", "Greek", "Haitian", "Hebrew",
    "Hindi", "Hungarian", "Icelandic", "Indonesian", "Irish", "Italian", "Japanese", "Kazakh", "Korean", "Lao", "Latin",
    "Latvian", "Lithuanian", "Malay", "Norwegian", "Persian", "Polish", "Portuguese", "Punjabi", "Romanian", "Russian",
    "Sanskrit", "Slovak", "Slovenian", "Spanish", "Spanish_Latin_America", "Swedish", "Tagalog", "Tamil", "Telugu",
    "Thai", "Turkish", "Ukrainian", "Urdu", "Vietnamese", "Zulu")
RN_TURLER = (
    "Alternative", "Anime", "Blues", "Brazilian", "Children's Music", "Christian & Gospel", "Classical", "Comedy",
    "Country", "Dance", "Easy Listening", "Electronic", "Enka", "Fitness & Workout", "French Pop", "German Folk",
    "German Pop", "Hip Hop/Rap", "Holiday", "Indian", "Instrumental", "J-Pop", "Jazz", "K-Pop", "Karaoke", "Kayokyoku",
    "Korean", "Latin", "New Age", "Opera", "Pop", "R&B/Soul", "Reggae", "Rock", "Singer/Songwriter", "Soundtrack",
    "Spoken Word", "Vocal", "World")
# Playwright dosyayı bellekten gönderir ve 50 MB'tan büyüğünü reddeder (`set_input_files`); pay bırakılır
EN_BUYUK_SES = 48 * 2**20
UPC = re.compile(r"\d{12,13}")


def on_kontrol(meta: dict, ses: Path, kapak: Path) -> None:
    """RouteNote'ta taslak açılmadan önce: eksik bilgi taslak açıldıktan sonra fark edilirse yarım taslak kalır.
    Gönderimden sonra değişmeyen alanlar: yazar ad/soyadı (© satırı), açık içerik, dil."""
    from PIL import Image

    from yanki import paket

    if not (meta.get("sanatci") or "").strip() or not (meta.get("baslik") or "").strip():
        raise ValueError("sanatçı adı ya da şarkı adı boş (config/yayin.toml → sanatci_adi, sonra paketle --yeniden)")
    if meta.get("yazar_adlari"):  # elle taslak: Scryne yazdı
        ham = list(meta["yazar_adlari"]) + list(meta.get("soz_yazari_adlari") or [])
    else:
        ham = paket._yazarlar(meta) if (meta.get("orijinal_yazar_adlari") or meta.get("orijinal_yazarlar")) else []
    if not ham:
        raise ValueError("pakette orijinal yazarlar yok: `yanki kunye <kimlik>`, sonra `yanki paketle --yeniden`")
    if eksik := [f"{a} {s}".strip() for a, s in ham if not kisi_adi(a) or not kisi_adi(s) or paket.SOYAD_YOK in (a, s)]:
        raise ValueError(f"yazar ad/soyadı eksik: {eksik} (girdi/liste.toml → yazarlar, sonra paketle --yeniden)")
    if meta.get("acik_icerik") not in (True, False):
        raise ValueError("açık içerik bilinmiyor (sözü taranmamış): metadata.json → acik_icerik true/false")
    if rn_dil(meta) is None:
        raise ValueError(f"söz dili RouteNote listesinde eşlenmemiş: {meta.get('dil')!r} (routenote.RN_DIL)")
    if meta.get("rn_tur") is not None and meta["rn_tur"] not in RN_TURLER:  # elle taslağın türü (`tur` = "cover")
        raise ValueError(f"tür RouteNote listesinde yok: {meta['rn_tur']!r}")
    if ses.stat().st_size > EN_BUYUK_SES:
        raise ValueError(f"ses {ses.stat().st_size / 2**20:.1f} MB; tarayıcıdan en çok {EN_BUYUK_SES // 2**20} MB")
    with Image.open(kapak) as im:
        if im.size != (3000, 3000) or im.mode != "RGB" or kapak.stat().st_size >= 25 * 2**20:
            raise ValueError(f"kapak RouteNote kuralına uymuyor: {im.size} {im.mode} {kapak.stat().st_size} B")


def album_bilgisi(s, meta: dict, yayin_tarihi: date | None, tur: str, spotify_id: str | None = None) -> None:
    """1. adım (Album Details), `paket._routenote_formu` 1–15 ile aynı sıra. Kaydetmez. Alanlar `on_kontrol`'den
    geçmiş olmalı."""
    sanatci = meta["sanatci"]
    yazarlar_ = yazarlar(meta)
    _sohbeti_kapat(s)
    _sec(s, "#edit_album_info_language", rn_dil(meta))
    s.fill("#edit_album_info_title", meta["baslik"])
    s.fill("#album_version", meta.get("surum") or "")
    _secim(s, "#Yes2", "#No3", meta.get("cover", True))  # cover içeriyor mu (Yanki paketi: evet)
    _isaretle(s, "#No")  # derleme değil
    _sanatci(s, "#edit_album_info_artist", sanatci, spotify_id)
    _satirlar(s, "#add_mul1", "edit_album_first_composer", "edit_album_last_composer", yazarlar_)
    if meta.get("soz_var", True):
        _secim(s, "#Yes1", "#No1", True)  # söz var → söz yazarı satırları açılır
        _satirlar(s, "#add_mul2", "edit_album_info_first_lyricist", "edit_album_info_last_lyricist",
                  soz_yazarlari(meta))
    else:
        _secim(s, "#Yes1", "#No1", False)
    s.click("#mainContribBtn")  # RouteNote'un önceden doldurduğu katkıcıyı boşalt ("Change")
    s.select_option("#role_contrib", "Producer")
    s.fill("#edit_album_first_contributor", meta.get("uretici") or sanatci)
    _sec(s, "#edit_album_info_genre", meta.get("rn_tur") or tur)
    s.fill("#cpy_year", str(meta.get("c_yil") or meta.get("orijinal_yil") or (yayin_tarihi or date.today()).year))
    s.fill("#cpy_name", meta.get("c_sahibi") or ", ".join(f"{a} {s_}" for a, s_ in yazarlar_))
    s.fill("#edit_album_info_pcopyyear", str(meta.get("p_yil") or date.today().year))
    s.fill("#edit_album_info_pcopyname", meta.get("p_sahibi") or sanatci)
    s.fill("#edit_album_info_label", meta.get("etiket") or sanatci)
    ilk = meta.get("orijinal_tarih")
    _tarihler(s, yayin_tarihi, date.fromisoformat(ilk) if ilk else None)
    _sec(s, "#edit_album_info_explicit", "Explicit" if meta.get("acik_icerik") is True else "Not Explicit")


def ses_yukle(s, upc: str, dosya: Path, baslik: str, bekle_sn: int = 600) -> None:
    """2. adım (Add Audio): dosya `cloud_upload`'a XHR ile gider; sayfa cevapta `…,success` görünce %100 yazar. Tür
    açıkça `audio/flac`: Playwright'ın verdiği `audio/x-flac`'ı sunucu MP3 sanıp reddediyor ("wrong file",
    2026-10-15). Kaydetmez."""
    cevap = []

    def yakala(route):
        cevap.append(f := route.fetch(timeout=bekle_sn * 1000))
        route.fulfill(response=f)

    s.route("**/cloud_upload/**", yakala)
    try:
        s.goto(f"{RN}/addaudiomp3/form/{upc}")
        s.wait_for_load_state("networkidle")
        _sohbeti_kapat(s)
        s.fill("#edit-tracknio1", baslik)
        tur = {".flac": "audio/flac", ".mp3": "audio/mpeg"}[dosya.suffix.lower()]
        s.set_input_files("#edit-Origin1", files=[{"name": dosya.name, "mimeType": tur, "buffer": dosya.read_bytes()}])
        son = time.time() + bekle_sn
        while not cevap and time.time() < son:
            s.wait_for_timeout(1000)
        if not cevap:
            raise RuntimeError(f"ses yüklemesi {bekle_sn} sn'de cevap almadı")
        govde = cevap[0].text()
        if cevap[0].status != 200 or not govde.rstrip(",").endswith("success"):
            raise RuntimeError(f"RouteNote sesi kabul etmedi: {cevap[0].status} {govde[:120]!r}")
        s.wait_for_function("document.getElementById('progressBar1').value == 100", timeout=30000)
    finally:
        s.unroute("**/cloud_upload/**")


def parca_bilgisi(s, upc: str, meta: dict) -> None:
    """3. sayfa (Audio Metadata, ses kaydedilince açılır): yazar/söz/katkıcı ve ISRC albümden dolu gelir (ISRC
    RouteNote'un atadığı kalır). Elle: cover = Yes (varsayılan No!) → mekanik lisans = No (`dflt0`), önizleme
    başlangıcı (nakarat, `onizleme_sn`). Kaydetmez."""
    if "trackmetadata" not in s.url:
        s.goto(f"{RN}/?q=trackmetadata/form/{upc}")
        s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    s.fill("#edit-audio-tags0-title", meta["baslik"])
    if meta.get("surum"):
        s.fill("#edit-audio-tags0-version", meta["surum"])
    if meta.get("cover", True):
        _secim(s, "#Yes0", "#No0", True)
        _isaretle(s, "#dflt0")  # mekanik lisans yok (Scryne 2026-10-07)
        if s.is_checked("#cnfrm0"):
            raise RuntimeError("mekanik lisans 'Yes' işaretli kaldı")
    else:
        _secim(s, "#Yes0", "#No0", False)
    if meta.get("isrc"):  # kendi ISRC'si (elle taslak); yoksa RouteNote'un atadığı kalır
        s.fill("#edit-audio-tags0-isrc", meta["isrc"])
    if (on := meta.get("onizleme_sn")) is not None:
        dk, sn = divmod(int(on), 60)
        s.fill("#numOnly0", f"{dk:02d}")
        s.fill("#numOnlysec0", f"{sn:02d}")
    s.select_option("#edit_album_info_explicit0", "Explicit" if meta.get("acik_icerik") is True else "Not Explicit")
    if s.input_value("#edit-audio-tags0-artist") != meta["sanatci"]:
        raise RuntimeError(f"parçanın sanatçısı albümden gelmedi: {s.input_value('#edit-audio-tags0-artist')!r}")


def isrc(s) -> str:
    return s.input_value("#edit-audio-tags0-isrc")


def kapak_yukle(s, upc: str, kapak: Path) -> None:
    """4. sayfa (Add Artwork): dosya seçilince sayfa renk uzayını sorar (`colortype.php` → `rgb,image/jpeg`), önizleme
    gösterir; "Save and Continue" (`#addart_savbtn`) kaydeder. Kurallar: 3000×3000, RGB JPG, < 25 MB."""
    from PIL import Image

    with Image.open(kapak) as im:
        if im.size != (3000, 3000) or im.mode != "RGB" or kapak.stat().st_size >= 25 * 2**20:
            raise ValueError(f"kapak RouteNote kuralına uymuyor: {im.size} {im.mode} {kapak.stat().st_size} B")
    s.goto(f"{RN}/addart/form/{upc}")
    s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    with s.expect_response(lambda r: "colortype" in r.url, timeout=60000) as renk:
        s.set_input_files("#audio_images", files=[{"name": kapak.name, "mimeType": "image/jpeg",
                                                   "buffer": kapak.read_bytes()}])
    if not renk.value.text().startswith("rgb"):
        raise RuntimeError(f"RouteNote kapağın renk uzayını kabul etmedi: {renk.value.text()[:80]!r}")
    s.click("#addart_savbtn")
    s.wait_for_load_state("networkidle")


# Mağaza kutuları (`#edit-did<n>`, 2026-10-15). Kapatılanlar `paket._routenote_formu` 24 ile aynı gerekçe: Amazon ve
# Kore mağazaları yapay zekâ içeriği almıyor (Kore cover için ayrıca yazılı sanatçı izni), Content ID cover'ı
# orijinalle eşleştirir. VIBE bu listede yok.
KAPALI_MAGAZALAR = {"Amazon": 12, "Melon": 34, "Bugs!": 38, "FLO": 49, "Genie Music": 53, "YouTube Content ID": 22}
HARIC_BOLGELER = ("United States", "Canada", "Mexico", "India", "Pakistan")  # mekanik lisans yok (Scryne 2026-10-07)


def _secili_bolgeler(s) -> list[str]:
    return [x.strip() for x in s.locator("#ms1 .ms-sel-item").all_inner_texts()]


def magazalar(s, upc: str, kapali: dict[str, int] | None = None, haric: tuple[str, ...] | None = None) -> None:
    """5. sayfa (Manage Stores): mağazaları kapat, fiyat Standard (varsayılan), bölge: Exclude + ülkeler. Bölge kutusu
    MagicSuggest (`#ms1`; gizli alan ülke kimliklerini tutar). Kaydetmez. Varsayılan Yanki cover'ı; elle taslak kendi
    seçimini verir (hariç ülke yoksa bölge adımına dokunulmaz: dünya geneli)."""
    kapali = KAPALI_MAGAZALAR if kapali is None else kapali
    haric = HARIC_BOLGELER if haric is None else haric
    s.goto(f"{RN}/addstore/form/{upc}")
    s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    for no in kapali.values():
        if s.is_checked(f"#edit-did{no}"):
            s.click(f"#edit-did{no}")
    if acik := [ad for ad, no in kapali.items() if s.is_checked(f"#edit-did{no}")]:
        raise RuntimeError(f"mağaza kapatılamadı: {acik}")
    if not haric:
        return
    if not s.is_checked("#exclud"):
        s.click("#excluds")  # kutu gizli, etiketi düğme
    if not s.is_checked("#exclud") or s.is_checked("#includ"):
        # Include kalırsa beş ülke yayının TEK bölgesi olur: mekanik lisansın olmadığı ülkeler
        raise RuntimeError("bölge modu Exclude'a geçmedi; mağazalar kaydedilmedi")
    for ulke in haric:
        if any(x.startswith(ulke) for x in _secili_bolgeler(s)):
            continue
        s.click("#ms-input-0")
        s.type("#ms-input-0", ulke, delay=40)
        oneri = s.locator(".ms-res-item").filter(visible=True)
        oneri.filter(has_text=re.compile(rf"^{re.escape(ulke)}( \(the\))?$")).first.click()  # ISO adı: "… (the)"
    secili = _secili_bolgeler(s)
    if eksik := [u for u in haric if not any(x.startswith(u) for x in secili)]:
        raise RuntimeError(f"bölge seçilemedi: {eksik} (seçili: {secili})")


# ── yükleyici (dagitim.Dagitimci) ──────────────────────────


ISRC = re.compile(r"\b[A-Z]{2}[A-Z0-9]{3}\d{7}\b")


def yayin_isrc(s, upc: str) -> str | None:
    """RouteNote'un atadığı ISRC, yayın sayfasının "Track Data" tablosundan. Sayfa doğrudan açılınca boş gelebiliyor
    (yalnız bir adımın kaydından sonra dolu); o zaman adım sayfasından yönlendirmeyle açılır."""
    if "/edit_album/" not in s.url or not s.locator("body").inner_text().strip():
        s.goto(f"{RN}/edit_album/{upc}", referer=f"{RN}/editalbum/{upc}")
        s.wait_for_load_state("networkidle")
    metin = s.locator("body").inner_text()
    i = metin.find("Track Data")
    bulunan = ISRC.findall(metin[i:]) if i >= 0 else []
    return bulunan[0] if bulunan else None


def _bekle_adres(s, parca: str, ne: str) -> None:
    """Kayıttan sonra beklenen sayfa gelmezse sayfadaki hata yazısıyla dur (form doğrulaması)."""
    s.wait_for_load_state("networkidle")
    if parca not in s.url:
        hata = s.evaluate("""() => [...document.querySelectorAll('div,span,li')].filter(e => e.offsetWidth &&
            e.children.length == 0 && /error|required|invalid|oops|please (enter|select)/i.test(e.innerText))
            .map(e => e.innerText.trim().slice(0, 160)).slice(0, 5)""")
        raise RuntimeError(f"RouteNote {ne} kaydetmedi ({s.url}): {hata}")


YAYIN_ASGARI_GUN = 10  # RouteNote incelemesi 5–10 iş günü (form uyarısı); daha yakın tarih incelemede geçer
ONAY_EN_GEC_GUN = 14  # tarihsiz ("onaylanınca") yayın: 10 iş günü sonra hâlâ Spotify'da yoksa takip gecikme bildirir


def tarihleri_guncelle(s, upc: str, gun: date | None) -> None:
    """Bekleyen taslağın tarihleri (`_tarihler`; None: onaylanınca). Albüm sayfası yeniden kaydedilir; diğer alanlar
    sayfada kayıtlı halleriyle gider."""
    s.goto(f"{RN}/editalbum/{upc}")
    s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    _tarihler(s, gun)
    s.click("#edit-album-save-image")
    _bekle_adres(s, "/edit_album/", "yeni yayın tarihini")


def _acik_pencereler(s) -> list[str]:
    return s.evaluate("""() => [...document.querySelectorAll('.rn-modal-container, [role=dialog], .modal')]
        .filter(e => e.offsetWidth).map(e => e.innerText.trim().slice(0, 300))""")


ONAY_PENCERESI = "#agree_terms .rn-modal"


def dagit(s, upc: str, son_tiktan_once=None) -> None:
    """Son adım: şartları kabul (`#submit_chk`) + "Distribute Free". Düğme sayfanın `free()`'sini çağırır: tarih
    doğrulaması, sonra kendi onay penceresi (`#agree_terms`, "No further changes can be made…") ve "Complete Release"
    (`#rn_btn_ok`) formu gönderir (son.html, 2026-10-15). Geri alınamaz. Beklenmeyen bir pencere (tarih, sanatçı rolü)
    çıkarsa tıklamaz, durur. `son_tiktan_once`: "Complete Release"tan hemen önce çağrılır (yarıda kalan gönderim
    yeniden denenmesin diye işaret)."""
    if "/edit_album/" not in s.url or not s.locator("#submit_chk").count():
        s.goto(f"{RN}/edit_album/{upc}", referer=f"{RN}/editalbum/{upc}")
        s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    metin = s.locator("body").inner_text()
    if not metin.strip():
        # RouteNote yayın sayfasını yalnız taslağı dolduran oturuma gösteriyor; başka oturumda (önceki koşuda
        # hazırlanmış taslak) boş gövde dönüyor, Scryne'ın tarayıcısında açılıyor (2026-10-16, Shape of You, Lean On)
        raise RuntimeError("RouteNote yayın sayfası bu oturumda boş (taslak önceki bir oturumda hazırlandı); "
                           "gönderilmedi. Panelde taslağı sil ve `yanki routenote taslak-silindi <kimlik>`: sonraki "
                           f"koşu yeniden açıp tek oturumda gönderir. Ya da panelde kendin gönder (UPC {upc}) ve "
                           "`yanki routenote gonderildi <kimlik>` (odada \"Panelde gönderdim\")")
    if metin.count("Complete") < 4 or "Incomplete" in metin:
        raise RuntimeError("yayının dört adımı tamamlanmamış, gönderilmedi")
    _isaretle(s, "#submit_chk")
    s.locator('input[value="Distribute Free"]').click()
    # pencerenin kendisi beklenir: `#agree_terms` kabı görünür olsa da boyu sıfır (içi `position: fixed`), Playwright
    # onu hiç "görünür" saymıyor; 2026-10-15 ilk canlı gönderim bu yüzden 15 sn bekleyip durdu
    onay = s.locator(ONAY_PENCERESI)
    try:
        onay.wait_for(state="visible", timeout=15000)
    except Exception as e:  # noqa: BLE001 — Playwright zaman aşımı: başka bir pencere ya da hiçbir şey
        raise RuntimeError(f"gönderim onay penceresi açılmadı; açık pencere: {_acik_pencereler(s)}") from e
    if "Free Distribution" not in onay.inner_text():
        raise RuntimeError(f"beklenmeyen onay penceresi: {onay.inner_text()[:200]!r}")
    if son_tiktan_once:
        son_tiktan_once()
    with s.expect_navigation(timeout=120000):
        s.click("#agree_terms #rn_btn_ok")
    s.wait_for_load_state("networkidle")
    if s.locator('input[value="Distribute Free"]').is_visible():
        raise RuntimeError(f"Complete Release sonrası yayın hâlâ taslakta; açık pencere: {_acik_pencereler(s)}")


class RouteNote:
    """Formu tarayıcıyla dolduran dağıtımcı. Adım adım ilerler, her adımın sonunda RouteNote kaydeder; yarıda kalırsa
    taslağın UPC'si `metadata.json` → `routenote`'ta durur ve sonraki deneme aynı taslaktan sürer (yeni taslak
    açılmaz). `gonder=False`: dört adım tamamlanır, "Distribute" basılmaz (taslak, insan kontrol eder).
    Adımlar: olusturuldu → album → ses_kaydedildi → ses → kapak → hazir → (gonderiliyor) → gonderildi."""

    ad, otomatik = "routenote", True

    def __init__(self, kok: Path, gorunur: bool = True, spotify_id: str | None = None, gece: bool = False):
        self.kok, self.gorunur, self.spotify_id, self.gece = kok, gorunur, spotify_id, gece

    @classmethod
    def ayardan(cls, kok: Path) -> "RouteNote":
        """`config/yayin.toml` → `[routenote]`. `gece`: takvim (gece/sürekli koşu) sırası geleni kendisi yüklesin mi;
        kapalıyken yalnız bildirir, yükleme `yanki yukle` ile elle tetiklenir."""
        import tomllib

        with open(kok / "config" / "yayin.toml", "rb") as f:
            r = tomllib.load(f).get("routenote", {})
        return cls(kok, bool(r.get("gorunur", True)), r.get("spotify_sanatci_id") or None, bool(r.get("gece", False)))

    def yukle(self, calisma: Path, d, yayin_tarihi: date, gonder: bool = True) -> dict:
        """Yanki'nin cover paketi (`calisma/<kimlik>/paket`)."""
        from yanki import durum, tunearo

        tur = tunearo.tur_sec(d.analiz.get("stil", ""), (d.kunye or {}).get("sanatci_turleri"))
        return self.yukle_klasor(calisma, durum.klasor(calisma, d.kimlik) / "paket", d.kimlik, yayin_tarihi, tur,
                                 gonder, f"yanki routenote gonderildi {d.kimlik}`, taslakta duruyorsa `yanki "
                                         f"routenote gonderilmedi {d.kimlik}")

    def yukle_klasor(self, calisma: Path, p: Path, kimlik: str, yayin_tarihi: date | None, tur: str,
                     gonder: bool = True, kurtarma: str = "") -> dict:
        """Bir paket klasörü (`metadata.json` + FLAC + 3000² JPG): Yanki paketi ya da odadan elle doldurulan taslak
        (`yanki/elle.py`). `yayin_tarihi` None ya da bugün/geçmiş: onaylanınca yayında. `kurtarma`: yarıda kalan
        gönderimin sonucunu kaydetme yolu (hata mesajında)."""
        from yanki import kilit, paket

        # paket bu iş boyunca yenilenemez (`paket._paketle_bir` aynı kilidi ister): yeniden paketleme ses/kapak
        # dosyasını yükleme sürerken değiştirmesin, eski metadata yenisinin üstüne yazılmasın
        with _tarayici_kilidi(calisma), kilit.tek_kosu(paket.yukleme_kilidi(p)) as alindi:
            if not alindi:
                raise Mesgul(f"{kimlik}: paket şu an yeniden hazırlanıyor ya da başka bir işte yükleniyor")
            return self._yukle_kilitli(calisma, p, kimlik, yayin_tarihi, tur, gonder, kurtarma)

    def _yukle_kilitli(self, calisma: Path, p: Path, kimlik: str, yayin_tarihi: date | None, tur: str,
                       gonder: bool, kurtarma: str) -> dict:
        from playwright.sync_api import sync_playwright

        from yanki import dosya

        meta_yolu = p / "metadata.json"
        meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
        ses, kapak = paket_dosyalari(p)
        kayit = meta.get("routenote") or {}
        if kayit.get("adim") == "gonderildi":
            # gönderilmiş ama yükleme kaydı yazılamamış (koşu Distribute'tan hemen sonra düştü): tarayıcı açılmaz,
            # bilgi kayıttan döner, çağıran yüklemeyi kaydeder (oturum düşmüş olsa da)
            return _bilgi(meta, kayit)
        if kayit.get("adim") == "gonderiliyor":
            raise RuntimeError(
                f"son gönderim yarıda kaldı: RouteNote panelinde (Discography) yayına bak. Gönderildiyse `{kurtarma}`"
                if kurtarma else "son gönderim yarıda kaldı: RouteNote panelinde (Discography) yayına bak; odada "
                                 "sonucu seç")
        if kayit.get("adim") not in ("hazir", "gonderildi"):
            on_kontrol(meta, ses, kapak)
        # bugün ya da geçmiş tarih (takvim yayin_on_gun = 0): tarihsiz, onaylanınca yayında. İleri tarih en az
        # YAYIN_ASGARI_GUN sonrası: inceleme 5–10 iş günü, daha yakın tarih incelemede geçer
        hemen = yayin_tarihi is None or yayin_tarihi <= date.today()
        yayin_tarihi = None if hemen else max(yayin_tarihi, date.today() + timedelta(days=YAYIN_ASGARI_GUN))
        iso = yayin_tarihi.isoformat() if yayin_tarihi else None

        def isle(**alan):
            kayit.update(alan)
            meta["routenote"] = kayit
            dosya.json_yaz(meta_yolu, meta)

        kapali = ({ad: no for ad, no in KAPALI_MAGAZALAR.items() if ad in meta["kapali_magazalar"]}
                  if "kapali_magazalar" in meta else None)
        haric = tuple(meta["haric_bolgeler"]) if "haric_bolgeler" in meta else None
        if "rn_spotify_id" in meta:  # elle taslak: profil `elle.routenote_meta`'da çözüldü (None: ada göre / yeni)
            spotify_id = meta["rn_spotify_id"] or (None if meta.get("yeni_profil") else self.spotify_id)
        else:
            spotify_id = meta.get("spotify_sanatci_id") or (None if meta.get("yeni_profil") else self.spotify_id)
        with sync_playwright() as pw:
            b = baglam(calisma, pw, self.gorunur)
            try:
                s = b.pages[0] if b.pages else b.new_page()
                s.set_default_timeout(45000)
                s.goto(ANA_URL)
                if giris_sayfasinda(s):
                    raise OturumYok("RouteNote oturumu yok: `yanki routenote giris`")
                if not (upc := kayit.get("upc")):
                    s.goto(f"{RN}/create_album")
                    s.fill("#edit_album_info_release", meta["baslik"])
                    s.click("#edit-album-save-image")
                    _bekle_adres(s, "/edit_album/", "yeni yayını")
                    upc = s.url.rstrip("/").split("/")[-1]
                    if not UPC.fullmatch(upc):
                        raise RuntimeError(f"yeni yayının UPC'si adresten okunamadı: {s.url}")
                    isle(upc=upc, adim="olusturuldu", tarih=date.today().isoformat())
                if kayit.get("adim") == "olusturuldu":
                    s.goto(f"{RN}/editalbum/{upc}")
                    s.wait_for_load_state("networkidle")
                    album_bilgisi(s, meta, yayin_tarihi, tur, spotify_id)
                    s.click("#edit-album-save-image")
                    _bekle_adres(s, "/edit_album/", "albüm bilgisini")
                    isle(adim="album", yayin_tarihi=iso)
                if kayit.get("adim") == "album":
                    ses_yukle(s, upc, ses, meta["baslik"])
                    s.click("#edit-submit")
                    _bekle_adres(s, "trackmetadata", "sesi")
                    isle(adim="ses_kaydedildi")  # yarıda kalırsa ses ikinci kez yüklenmez (ikinci parça olurdu)
                if kayit.get("adim") == "ses_kaydedildi":
                    parca_bilgisi(s, upc, meta)
                    s.click("#edit-submit")
                    _bekle_adres(s, "confirm_upload", "parça bilgisini")
                    s.click("#edit-Im-Finished")
                    _bekle_adres(s, "/edit_album/", "parça listesini")
                    isle(adim="ses")
                if kayit.get("adim") == "ses":
                    kapak_yukle(s, upc, kapak)
                    _bekle_adres(s, "/edit_album/", "kapağı")
                    isle(adim="kapak")
                if kayit.get("adim") == "kapak":
                    magazalar(s, upc, kapali, haric)
                    s.click("#album_save")
                    _bekle_adres(s, "/edit_album/", "mağazaları")
                    isle(adim="hazir")
                if not kayit.get("isrc"):
                    isle(isrc=yayin_isrc(s, upc))
                if gonder and kayit.get("adim") == "hazir":
                    eski = kayit.get("yayin_tarihi")
                    # taslak beklerken tarih yaklaştı ya da ayar değişti (tarihli ↔ onaylanınca)
                    if (eski is not None if hemen else
                            not eski or date.fromisoformat(eski) < date.today() + timedelta(days=YAYIN_ASGARI_GUN)):
                        tarihleri_guncelle(s, upc, yayin_tarihi)
                        isle(yayin_tarihi=iso)
                    dagit(s, upc, son_tiktan_once=lambda: isle(adim="gonderiliyor"))
                    isle(adim="gonderildi", gonderim=date.today().isoformat())
            finally:
                b.close()
        return _bilgi(meta, kayit)


def _bilgi(meta: dict, kayit: dict) -> dict:
    """Yükleme bilgisi (`takip.yukleme_kaydet` alanları) taslak kaydından."""
    tarihsiz = not kayit.get("yayin_tarihi")
    on = meta.get("onizleme_sn")
    return {"upc": kayit.get("upc"), "isrc": kayit.get("isrc"), "yayin_tarihi": kayit.get("yayin_tarihi"),
            "en_gec_yayin": (date.fromisoformat(kayit.get("gonderim") or date.today().isoformat())
                             + timedelta(days=ONAY_EN_GEC_GUN)).isoformat() if tarihsiz else None,
            "onizleme": f"{int(on) // 60}:{int(on) % 60:02d}" if on is not None else None,
            "dagitim_durumu": kayit.get("adim")}


def _paket_dosyasi(p: Path, uzanti: str) -> Path | None:
    """Paketteki asıl dosya: noktalı (gizli, eski küçük resim) ve yarım yazılmış (`.yaziliyor`) dosyalar sayılmaz.
    Birden çok aday varsa hangisinin gideceği belirsiz: yükleme durur (yanlış ses geri alınamaz biçimde gitmesin)."""
    adaylar = sorted(x for x in p.glob(f"*{uzanti}") if not x.name.startswith(".") and ".yaziliyor" not in x.name)
    if len(adaylar) > 1:
        raise ValueError(f"pakette birden çok {uzanti} var ({', '.join(x.name for x in adaylar)}): yanki paketle "
                         "--yeniden")
    return adaylar[0] if adaylar else None


def paket_dosyalari(p: Path) -> tuple[Path, Path]:
    ses, kapak = _paket_dosyasi(p, ".flac"), _paket_dosyasi(p, ".jpg")
    if ses is None or kapak is None:
        raise ValueError(f"pakette FLAC ya da kapak yok ({p}); RouteNote WAV almıyor: yanki paketle --yeniden")
    return ses, kapak


# ── insanın panelde gördüğünün kaydı ────────────────────────
def _meta(calisma: Path, kimlik: str) -> tuple[Path, dict]:
    from yanki import durum

    yol = durum.klasor(calisma, kimlik) / "paket" / "metadata.json"
    try:
        return yol, json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{kimlik}: paket yok") from e


def gonderim_sonucu(calisma: Path, kimlik: str, gonderildi: bool) -> str:
    """Son tıktan sonra süreç düştüyse (`adim = gonderiliyor`) hat yeniden denemez; Scryne RouteNote panelinde
    (Discography) bakar ve sonucu söyler. Gönderildiyse yükleme kaydedilir ve şarkı `yuklendi`; gönderilmediyse
    taslak yeniden gönderime hazır. Hazır taslağı (`hazir`) Scryne panelde kendisi gönderdiyse de `gonderildi`
    kaydedilir: önceki oturumda hazırlanmış taslağın yayın sayfası otomasyona boş geliyor (2026-10-16, lovely)."""
    from yanki import dosya, durum, takip

    yol, meta = _meta(calisma, kimlik)
    rn = meta.get("routenote") or {}
    if rn.get("adim") != "gonderiliyor" and not (gonderildi and rn.get("adim") == "hazir"):
        raise ValueError(f"{kimlik}: yarıda kalan gönderim yok (adım: {rn.get('adim') or '—'})")
    if not gonderildi:
        rn["adim"] = "hazir"
        dosya.json_yaz(yol, {**meta, "routenote": rn})
        # hazır taslak başka oturumda açıldığı için otomasyon gönderemez (yayın sayfası boş gelir); gece kuyruğu da
        # onu atlar (`dagitim.plan` → `elle_bekleyen`)
        return (f"{kimlik}: taslakta duruyor olarak işaretlendi. Otomasyon bu taslağı gönderemez: panelde gönder ve "
                f"`yanki routenote gonderildi {kimlik}`, ya da panelden sil ve `yanki routenote taslak-silindi "
                f"{kimlik}` (sonraki koşu yeniden açıp tek oturumda gönderir)")
    rn.update(adim="gonderildi", gonderim=rn.get("gonderim") or date.today().isoformat())
    dosya.json_yaz(yol, {**meta, "routenote": rn})
    takip.yukleme_kaydet(calisma, kimlik, {"upc": rn.get("upc"), "isrc": rn.get("isrc"),
                                           "yayin_tarihi": rn.get("yayin_tarihi"), "dagitimci": "routenote"},
                         "routenote")
    with durum.guncelle(calisma, kimlik) as d:
        if d.asama == "paketlendi":
            d.gec("yuklendi")
    return f"{kimlik}: gönderildi olarak kaydedildi (UPC {rn.get('upc')}), şarkı incelemede"


def taslak_silindi(calisma: Path, kimlik: str) -> str:
    """Panelden silinen taslağın kaydı geçmişe: paket yeniden hazırlanabilir, sonraki yükleme yeni taslak açar."""
    from yanki import dosya

    yol, meta = _meta(calisma, kimlik)
    rn = meta.get("routenote") or {}
    if not rn.get("adim") or rn.get("adim") == "gonderildi":
        raise ValueError(f"{kimlik}: açık taslak kaydı yok (adım: {rn.get('adim') or '—'})")
    meta.setdefault("routenote_gecmisi", []).append({**meta.pop("routenote"), "silindi": date.today().isoformat()})
    dosya.json_yaz(yol, meta)
    return f"{kimlik}: taslak kaydı geçmişe alındı; sonraki yükleme yeni taslak açar"
