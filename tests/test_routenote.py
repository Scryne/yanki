from yanki import routenote


def test_kisi_adi_takma_adi_atar():
    assert routenote.kisi_adi("Joseph “Joe”") == "Joseph"
    assert routenote.kisi_adi('Chester "Chaz" Bennington') == "Chester Bennington"
    assert routenote.kisi_adi("David Michael (Phoenix)") == "David Michael"
    assert routenote.kisi_adi("Adele") == "Adele"


def test_yazarlar_temiz_ad_soyad():
    meta = {"orijinal_yazar_adlari": [["Joseph “Joe”", "Hahn"], ["Mike", "Shinoda"]]}
    assert routenote.yazarlar(meta) == [("Joseph", "Hahn"), ("Mike", "Shinoda")]


def test_routenote_ayardan_guvenli_baslar(tmp_path):
    from yanki import dagitim

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "yayin.toml").write_text('[routenote]\nspotify_sanatci_id = "abc"\n', encoding="utf-8")
    d = dagitim.sec("routenote", tmp_path)
    assert isinstance(d, routenote.RouteNote) and d.otomatik
    assert d.gece is False and d.spotify_id == "abc"  # takvim yalnız bildirir, yükleme elle tetiklenir
    assert not hasattr(d, "yokla") and not hasattr(d, "geri_cek")  # yayın listesi okunmaz, kaldırma panelden


def test_isrc_deseni():
    assert routenote.ISRC.findall("Track Data ... ZZA192606238 View") == ["ZZA192606238"]
    assert routenote.ISRC.findall("UPC 5064150100534") == []


def _paket(tmp_path, **meta_ek):
    import json

    from PIL import Image

    p = tmp_path / "paket"
    p.mkdir(parents=True, exist_ok=True)
    (p / "ses.flac").write_bytes(b"fLaC" + b"\0" * 64)
    Image.new("RGB", (3000, 3000)).save(p / "kapak.jpg")
    meta = {"sanatci": "Orvane", "baslik": "Song", "dil": "en", "acik_icerik": False,
            "orijinal_yazar_adlari": [["Adele", "Adkins"], ["Dan", "Wilson"]], **meta_ek}
    (p / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta, p / "ses.flac", p / "kapak.jpg"


def test_on_kontrol_taslak_acilmadan_durdurur(tmp_path):
    import pytest

    from yanki import paket

    meta, ses, kapak = _paket(tmp_path)
    routenote.on_kontrol(meta, ses, kapak)  # tam paket geçer
    for bozuk, ne in [({"orijinal_yazar_adlari": [["Adele", paket.SOYAD_YOK]]}, "soyad"),
                      ({"orijinal_yazar_adlari": [["Adele", ""]]}, "soyad"),
                      ({"orijinal_yazar_adlari": []}, "yazar"),
                      ({"acik_icerik": None}, "açık içerik"),
                      ({"dil": "az"}, "dil")]:
        with pytest.raises(ValueError, match=ne):
            routenote.on_kontrol({**meta, **bozuk}, ses, kapak)
    assert routenote.RN_DIL["zh"] == "Chinese_Simplified"  # RouteNote'ta düz "Chinese" yok


def test_yarida_kalan_gonderim_yeniden_denenmez(tmp_path, monkeypatch):
    """Son tıktan sonra süreç düştüyse (gonderiliyor) tarayıcı hiç açılmaz: ikinci "Distribute" yok."""
    import json

    import pytest

    from yanki import durum

    meta, _, _ = _paket(tmp_path / "s" / "a-b", routenote={"upc": "5064150700802", "adim": "gonderiliyor"})
    monkeypatch.setattr(durum, "klasor", lambda calisma, kimlik: tmp_path / "s" / "a-b")
    d = durum.Durum("a-b", "A", "B", analiz={"stil": "pop"})
    rn = routenote.RouteNote(tmp_path)
    monkeypatch.setattr(routenote, "baglam", lambda *a, **k: pytest.fail("tarayıcı açıldı"))
    with pytest.raises(RuntimeError, match="yanki routenote gonderildi a-b"):
        rn.yukle(tmp_path, d, __import__("datetime").date(2026, 12, 1))
    assert json.loads((tmp_path / "s" / "a-b" / "paket" / "metadata.json").read_text())["routenote"]["adim"] == \
        "gonderiliyor"


class _Oge:
    def __init__(self, sayfa, secici):
        self.s, self.secici = sayfa, secici

    def count(self):
        return 1

    def inner_text(self):
        return self.s.metinler.get(self.secici, "")

    def click(self):
        self.s.olaylar.append(("tik", self.secici))
        if self.secici == 'input[value="Distribute Free"]':
            self.s.gorunen.add(routenote.ONAY_PENCERESI)

    def wait_for(self, state="visible", timeout=None):
        if self.secici not in self.s.gorunen:
            raise TimeoutError(self.secici)

    def is_visible(self):
        return self.secici in self.s.gorunen


class _Sayfa:
    url = "https://www.routenote.com/rn/edit_album/5064150700802"

    def __init__(self, pencere_metni="Release with Free Distribution. No further changes can be made"):
        self.olaylar, self.gorunen = [], {'input[value="Distribute Free"]'}
        self.metinler = {"body": "Complete Complete Complete Complete", routenote.ONAY_PENCERESI: pencere_metni}

    def locator(self, secici):
        return _Oge(self, secici)

    def add_style_tag(self, **_):
        pass

    def is_checked(self, _):
        return False

    def click(self, secici):
        self.olaylar.append(("tik", secici))
        if secici == "#agree_terms #rn_btn_ok":
            self.gorunen.clear()  # form gönderildi, sayfa değişti

    def expect_navigation(self, **_):
        import contextlib

        return contextlib.nullcontext()

    def wait_for_load_state(self, *_):
        pass

    def evaluate(self, _):
        return []


def test_dagit_onay_penceresinden_gonderir_isaret_once():
    s = _Sayfa()
    routenote.dagit(s, "5064150700802", son_tiktan_once=lambda: s.olaylar.append(("isaret", None)))
    assert s.olaylar == [("tik", "#submit_chk"), ("tik", 'input[value="Distribute Free"]'), ("isaret", None),
                         ("tik", "#agree_terms #rn_btn_ok")]


def test_dagit_beklenmeyen_pencerede_tiklamaz():
    import pytest

    s = _Sayfa(pencere_metni="Please check the release date")
    with pytest.raises(RuntimeError, match="beklenmeyen"):
        routenote.dagit(s, "5064150700802", son_tiktan_once=lambda: pytest.fail("işaret yazıldı"))
    assert ("tik", "#agree_terms #rn_btn_ok") not in s.olaylar


def test_dagit_bos_yayin_sayfasinda_ne_yapilacagini_soyler():
    """Önceki oturumda hazırlanmış taslağın yayın sayfası boş gelir: hiçbir şeye tıklanmaz, çıkış yolu söylenir."""
    import pytest

    s = _Sayfa()
    s.metinler["body"] = ""
    with pytest.raises(RuntimeError, match="taslak-silindi"):
        routenote.dagit(s, "5064150700802", son_tiktan_once=lambda: pytest.fail("işaret yazıldı"))
    assert s.olaylar == []


class _TarihSayfasi:
    def __init__(self):
        self.kutular = {}

    def eval_on_selector(self, secici, _js, deger):
        self.kutular[secici] = deger


def test_tarihsiz_yayin_satis_tarihini_bos_birakir():
    """yayin_on_gun = 0 (en erken): satış tarihi boş → RouteNote onaylar onaylamaz yayında; ilk yayın bugün."""
    from datetime import date

    s = _TarihSayfasi()
    routenote._tarihler(s, None)
    assert s.kutular == {"#edit_album_info_org_date": date.today().strftime("%Y/%m/%d"),
                         "#edit_album_info_sale_date": ""}
    routenote._tarihler(s, date(2026, 11, 5))
    assert set(s.kutular.values()) == {"2026/11/05"}
