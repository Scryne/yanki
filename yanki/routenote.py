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
from datetime import date
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
    s.add_style_tag(content="[id*='luna' i], [class*='luna' i], iframe[src*='chat' i] {display: none !important}")


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
