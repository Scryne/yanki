"""RouteNote'a tarayıcıyla yükleme (Scryne 2026-10-15: "RouteNote'a otomatik yüklemeyi yapmanı istiyorum").

RouteNote'un API'si yok (`docs/arastirma/08`). Hat, formu Scryne'ın elle doldurduğu sırayla (`paket._routenote_formu`,
ilk yükleme 2026-10-08) Playwright ile doldurur. Şart metni (routenote.com/termsandconditions, madde 2, 2026-10-15)
botla veri toplamayı ve dinlenme şişirmeyi yasaklıyor; hesap sahibinin kendi yayınını yüklemesini değil. Bu yüzden:
yalnız kendi hesabımız, yalnız yükleme formu, insan hızında; yayın listesi okunmaz (durum e-postadan / `yanki
yuklendi`'den).

Oturum: `calisma/.routenote_profil` kalıcı Chrome profili (Scryne'ın asıl Chrome'u değil). Giriş bir kez elle
(`yanki routenote giris`); şifre hiçbir yerde tutulmaz. Oturum düşerse yükleme durur ve bildirir, giriş denemez.
"""

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

    with sync_playwright() as pw:
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
    with sync_playwright() as pw:
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
    hedef = oneri.locator(f'xpath=self::*[contains(@data-langartisturi, "{spotify_id}")]') if spotify_id else None
    (hedef.first if hedef is not None and hedef.count() else oneri.filter(has_text=YENI_PROFIL).first).click()
    s.wait_for_timeout(1200)
    if s.locator("#rn_btn_exist").is_visible():
        s.click("#rn_btn_exist")
    if s.input_value(kutu) != ad:
        raise RuntimeError(f"sanatçı seçilemedi: kutuda '{s.input_value(kutu)}'")


def _tarih(s, kutu: str, gun: date) -> None:
    s.eval_on_selector(kutu, "(e, v) => { e.value = v; e.dispatchEvent(new Event('change', {bubbles: true})) }",
                       gun.strftime("%Y/%m/%d"))


def kisi_adi(ad: str) -> str:
    """Künyedeki takma ad mağazaya gitmez: `Joseph “Joe”` → `Joseph`."""
    return " ".join(re.sub(r"[\"“”„«»][^\"“”„«»]*[\"“”„«»]|\([^)]*\)", " ", ad).split())


def yazarlar(meta: dict) -> list[tuple[str, str]]:
    from yanki import paket

    return [(kisi_adi(a), kisi_adi(s)) for a, s in paket._yazarlar(meta)]


def album_bilgisi(s, meta: dict, yayin_tarihi: date, tur: str, spotify_id: str | None = None) -> None:
    """1. adım (Album Details), `paket._routenote_formu` 1–15 ile aynı sıra. Kaydetmez."""
    from yanki import paket

    sanatci = meta["sanatci"]
    yazarlar_ = yazarlar(meta)
    if not yazarlar_ or any(a == paket.SOYAD_YOK or s_ == paket.SOYAD_YOK for a, s_ in yazarlar_):
        raise ValueError(f"yazar ad/soyadı eksik: {yazarlar_}")
    _sohbeti_kapat(s)
    _sec(s, "#edit_album_info_language", paket.DIL_ADI.get(meta["dil"], "English"))
    s.fill("#edit_album_info_title", meta["baslik"])
    s.fill("#album_version", "")
    _isaretle(s, "#Yes2")  # cover içeriyor
    _isaretle(s, "#No")  # derleme değil
    _sanatci(s, "#edit_album_info_artist", sanatci, spotify_id)
    _satirlar(s, "#add_mul1", "edit_album_first_composer", "edit_album_last_composer", yazarlar_)
    _isaretle(s, "#Yes1")  # söz var → söz yazarı satırları açılır
    _satirlar(s, "#add_mul2", "edit_album_info_first_lyricist", "edit_album_info_last_lyricist", yazarlar_)
    s.click("#mainContribBtn")  # RouteNote'un önceden doldurduğu katkıcıyı boşalt ("Change")
    s.select_option("#role_contrib", "Producer")
    s.fill("#edit_album_first_contributor", sanatci)
    _sec(s, "#edit_album_info_genre", tur)
    s.fill("#cpy_year", str(meta.get("orijinal_yil") or yayin_tarihi.year))
    s.fill("#cpy_name", ", ".join(f"{a} {s_}" for a, s_ in yazarlar_))
    s.fill("#edit_album_info_pcopyyear", str(date.today().year))
    s.fill("#edit_album_info_pcopyname", sanatci)
    s.fill("#edit_album_info_label", meta.get("etiket") or sanatci)
    _tarih(s, "#edit_album_info_org_date", yayin_tarihi)
    _tarih(s, "#edit_album_info_sale_date", yayin_tarihi)
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
    _isaretle(s, "#Yes0")
    _isaretle(s, "#dflt0")  # mekanik lisans yok (Scryne 2026-10-07)
    if s.is_checked("#cnfrm0"):
        raise RuntimeError("mekanik lisans 'Yes' işaretli kaldı")
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


def magazalar(s, upc: str) -> None:
    """5. sayfa (Manage Stores): mağazaları kapat, fiyat Standard (varsayılan), bölge: Exclude + beş ülke. Bölge kutusu
    MagicSuggest (`#ms1`; gizli alan ülke kimliklerini tutar). Kaydetmez."""
    s.goto(f"{RN}/addstore/form/{upc}")
    s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    for no in KAPALI_MAGAZALAR.values():
        if s.is_checked(f"#edit-did{no}"):
            s.click(f"#edit-did{no}")
    if acik := [ad for ad, no in KAPALI_MAGAZALAR.items() if s.is_checked(f"#edit-did{no}")]:
        raise RuntimeError(f"mağaza kapatılamadı: {acik}")
    if not s.is_checked("#exclud"):
        s.click("#excluds")  # kutu gizli, etiketi düğme
    for ulke in HARIC_BOLGELER:
        if any(x.startswith(ulke) for x in _secili_bolgeler(s)):
            continue
        s.click("#ms-input-0")
        s.type("#ms-input-0", ulke, delay=40)
        oneri = s.locator(".ms-res-item").filter(visible=True)
        oneri.filter(has_text=re.compile(rf"^{re.escape(ulke)}( \(the\))?$")).first.click()  # ISO adı: "… (the)"
    secili = _secili_bolgeler(s)
    if eksik := [u for u in HARIC_BOLGELER if not any(x.startswith(u) for x in secili)]:
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


def tarihleri_guncelle(s, upc: str, gun: date) -> None:
    """Bekleyen taslağın "Originally Released" ve "Sales Start Date"i (ikisi aynı gün). Albüm sayfası yeniden
    kaydedilir; diğer alanlar sayfada kayıtlı halleriyle gider."""
    s.goto(f"{RN}/editalbum/{upc}")
    s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    _tarih(s, "#edit_album_info_org_date", gun)
    _tarih(s, "#edit_album_info_sale_date", gun)
    s.click("#edit-album-save-image")
    _bekle_adres(s, "/edit_album/", "yeni yayın tarihini")


def dagit(s, upc: str) -> None:
    """Son adım: şartları kabul (`#submit_chk`) + "Distribute Free". Geri alınamaz: ses ve playlist değişikliği
    bundan sonra yapılamıyor. Henüz canlıda sınanmadı (ilk gerçek gönderim Scryne'ın onayıyla); düğmeden sonra
    beklenmeyen bir onay penceresi çıkarsa tıklamaz, durur."""
    if "/edit_album/" not in s.url or not s.locator("#submit_chk").count():
        s.goto(f"{RN}/edit_album/{upc}", referer=f"{RN}/editalbum/{upc}")
        s.wait_for_load_state("networkidle")
    _sohbeti_kapat(s)
    metin = s.locator("body").inner_text()
    if metin.count("Complete") < 4 or "Incomplete" in metin:
        raise RuntimeError("yayının dört adımı tamamlanmamış, gönderilmedi")
    _isaretle(s, "#submit_chk")
    s.locator('input[value="Distribute Free"]').click()
    s.wait_for_load_state("networkidle")
    s.wait_for_timeout(3000)
    if s.locator('input[value="Distribute Free"]').is_visible():
        pencere = s.evaluate("""() => [...document.querySelectorAll('.rn-modal-container, [role=dialog], .modal')]
            .filter(e => e.offsetWidth).map(e => e.innerText.trim().slice(0, 300))""")
        raise RuntimeError(f"Distribute sonrası sayfa değişmedi; onay penceresi: {pencere}")


class RouteNote:
    """Formu tarayıcıyla dolduran dağıtımcı. Adım adım ilerler, her adımın sonunda RouteNote kaydeder; yarıda kalırsa
    taslağın UPC'si `metadata.json` → `routenote`'ta durur ve sonraki deneme aynı taslaktan sürer (yeni taslak
    açılmaz). `gonder=False`: dört adım tamamlanır, "Distribute" basılmaz (taslak, insan kontrol eder)."""

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
        from playwright.sync_api import sync_playwright

        from yanki import durum, tunearo

        p = durum.klasor(calisma, d.kimlik) / "paket"
        meta_yolu = p / "metadata.json"
        meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
        ses = next(p.glob("*.flac"), None)
        kapak = next(p.glob("*.jpg"), None)
        if ses is None or kapak is None:
            raise ValueError(f"pakette FLAC ya da kapak yok ({p}); RouteNote WAV almıyor: yanki paketle --yeniden")
        kayit = meta.get("routenote") or {}

        def isle(**alan):
            kayit.update(alan)
            meta["routenote"] = kayit
            meta_yolu.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

        tur = tunearo.tur_sec(d.analiz.get("stil", ""), (d.kunye or {}).get("sanatci_turleri"))
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
                    isle(upc=upc, adim="olusturuldu", tarih=date.today().isoformat())
                if kayit.get("adim") == "olusturuldu":
                    s.goto(f"{RN}/editalbum/{upc}")
                    s.wait_for_load_state("networkidle")
                    album_bilgisi(s, meta, yayin_tarihi, tur, self.spotify_id)
                    s.click("#edit-album-save-image")
                    _bekle_adres(s, "/edit_album/", "albüm bilgisini")
                    isle(adim="album", yayin_tarihi=yayin_tarihi.isoformat())
                if kayit.get("adim") == "album":
                    ses_yukle(s, upc, ses, meta["baslik"])
                    s.click("#edit-submit")
                    _bekle_adres(s, "trackmetadata", "sesi")
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
                    magazalar(s, upc)
                    s.click("#album_save")
                    _bekle_adres(s, "/edit_album/", "mağazaları")
                    isle(adim="hazir")
                if not kayit.get("isrc"):
                    isle(isrc=yayin_isrc(s, upc))
                if gonder and kayit.get("adim") == "hazir":
                    eski = date.fromisoformat(kayit.get("yayin_tarihi") or "2000-01-01")
                    if eski < date.today() + timedelta(days=YAYIN_ASGARI_GUN):  # taslak beklerken tarih yaklaştı
                        tarihleri_guncelle(s, upc, yayin_tarihi)
                        isle(yayin_tarihi=yayin_tarihi.isoformat())
                    dagit(s, upc)
                    isle(adim="gonderildi", gonderim=date.today().isoformat())
            finally:
                b.close()
        return {"upc": upc, "isrc": kayit.get("isrc"), "yayin_tarihi": kayit.get("yayin_tarihi"),
                "onizleme": f"{int(meta['onizleme_sn']) // 60}:{int(meta['onizleme_sn']) % 60:02d}"
                if meta.get("onizleme_sn") is not None else None, "dagitim_durumu": kayit.get("adim")}
