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
