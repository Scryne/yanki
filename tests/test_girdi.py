import pytest

from yanki import ag, kaynak, kunye, liste, sozler


def test_kimlik_ascii_ve_kararli():
    assert liste.kimlik("Adele", "Someone Like You") == "adele-someone-like-you"
    assert liste.kimlik("Beyoncé", "Halo!") == "beyonce-halo"
    assert liste.kimlik("Sezen Aksu", "Şarkı Söylemek Lazım") == "sezen-aksu-sarki-soylemek-lazim"


def _liste(tmp_path, metin):
    yol = tmp_path / "liste.toml"
    yol.write_text(metin, encoding="utf-8")
    return yol


def test_liste_yuklenir(tmp_path):
    s = liste.yukle(_liste(tmp_path, '[[sarki]]\nsanatci = " Adele "\nad = "Someone Like You"\nvokal = "kadin"\n'))
    assert s == [liste.Sarki("Adele", "Someone Like You", vokal="kadin")]


@pytest.mark.parametrize(
    ("metin", "hata"),
    [
        ('[[sarki]]\nsanatci = "A"\n', "eksik alan: ad"),
        ('[[sarki]]\nsanatci = "A"\nad = "B"\nrenk = "x"\n', "bilinmeyen alan: renk"),
        ('[[sarki]]\nsanatci = "A"\nad = "B"\nvokal = "bas"\n', "vokal"),
        ('[[sarki]]\nsanatci = "A"\nad = "B"\n[[sarki]]\nsanatci = "a"\nad = "b"\n', "iki kez"),
    ],
)
def test_liste_hatalari(tmp_path, metin, hata):
    with pytest.raises(ValueError, match=hata):
        liste.yukle(_liste(tmp_path, metin))


def test_etiketle_tekrar_eden_kita_nakarat():
    duz = "a\nb\n\nnakarat\nla\n\nc\nd\n\nnakarat\nla"
    assert sozler.etiketle(duz) == "[verse]\na\nb\n\n[chorus]\nnakarat\nla\n\n[verse]\nc\nd\n\n[chorus]\nnakarat\nla"


def test_etiketli_soz_dokunulmaz():
    assert sozler.etiketle("[verse]\nx\n\n[bridge]\ny\n") == "[verse]\nx\n\n[bridge]\ny"


def test_lrclib_get_bulamazsa_arama(monkeypatch):
    def sahte(url, parametre=None, **_):
        if url.endswith("/get"):
            raise ag.Bulunamadi(url)
        return [{"instrumental": True, "plainLyrics": ""}, {"plainLyrics": "x\ny", "duration": 200}]

    s = sozler.lrclib("A", "B", json_al=sahte)
    assert s.metin == "[verse]\nx\ny" and s.sure_sn == 200 and s.kaynak == "lrclib"


def test_lrclib_sozsuz_kayit_hata():
    with pytest.raises(ag.Bulunamadi, match="sözsüz"):
        sozler.lrclib("A", "B", json_al=lambda *a, **k: {"instrumental": True, "plainLyrics": None})


def test_soz_dosyasi_oncelikli(tmp_path):
    dosya = tmp_path / "s.txt"
    dosya.write_text("benim\nsözüm", encoding="utf-8")
    s = sozler.bul("A", "B", dosya, json_al=lambda *a, **k: {"plainLyrics": "lrclib", "duration": 180})
    assert s.kaynak == "dosya" and "benim" in s.metin and s.sure_sn == 180


def test_kunye_eser_bagli_kaydi_secer():
    yanitlar = {
        "/recording/": {"recordings": [
            {"id": "r1", "title": "Song", "score": 100},
            {"id": "r2", "title": "Song", "score": 95, "first-release-date": "2011-01-24"},
            {"id": "r3", "title": "Song (Live)", "score": 99},
        ]},
        "/recording/r1": {"relations": []},
        "/recording/r2": {"isrcs": ["GBBKS1000351"], "relations": [
            {"type": "performance", "work": {"id": "w1", "title": "Song"}}]},
        "/work/w1": {"relations": [
            {"type": "composer", "artist": {"name": "Adele Adkins"}},
            {"type": "lyricist", "artist": {"name": "Adele Adkins"}},
            {"type": "writer", "artist": {"name": "Dan Wilson"}},
            {"type": "publishing", "label": {"name": "X"}},
        ]},
    }

    def sahte(url, parametre=None, **_):
        return yanitlar[url.split("/ws/2", 1)[1]]

    k = kunye.bul("Adele", "Song", json_al=sahte, uyku=lambda _: None)
    assert (k.kayit_mbid, k.eser_mbid, k.ilk_yayin) == ("r2", "w1", "2011-01-24")
    assert k.yazarlar == ("Adele Adkins", "Dan Wilson")
    assert k.isrc == ("GBBKS1000351",)


def test_kunye_kayit_yoksa_hata():
    with pytest.raises(ag.Bulunamadi):
        kunye.bul("A", "B", json_al=lambda *a, **k: {"recordings": [{"id": "x", "title": "Başka", "score": 100}]},
                  uyku=lambda _: None)


def test_kaynak_secimi_sure_ve_istenmeyen():
    adaylar = [
        kaynak.Aday("1", "Song (Live at Royal Albert Hall)", 290),
        kaynak.Aday("2", "Song (Official Music Video)", 300),
        kaynak.Aday("3", "Song (Official Audio)", 286),
        kaynak.Aday("4", "Song - Karaoke", 285),
        kaynak.Aday("5", "Song preview", 30),
    ]
    assert kaynak.sec(adaylar, 285).id == "3"


def test_kaynak_secimi_uygun_yoksa_hata():
    with pytest.raises(kaynak.KaynakYok):
        kaynak.sec([kaynak.Aday("5", "Song", 30)], 285)


def test_kaynak_sure_bilinmiyorsa_ilk_temiz():
    assert kaynak.sec([kaynak.Aday("1", "Song cover", 200), kaynak.Aday("2", "Song", 210)], None).id == "2"


def test_klasorde_kaynak(tmp_path):
    (tmp_path / "a-b.mp3").write_bytes(b"x")
    assert kaynak.klasorden(tmp_path, "a-b") == tmp_path / "a-b.mp3"
    assert kaynak.klasorden(tmp_path, "c-d") is None
