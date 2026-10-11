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
    assert sozler.etiketle(duz) == ("[Verse 1]\na\nb\n\n[Chorus]\nnakarat\nla\n\n[Verse 2]\nc\nd\n\n"
                                   "[Chorus]\nnakarat\nla")


def test_etiketli_soz_dokunulmaz():
    assert sozler.etiketle("[verse]\nx\n\n[bridge]\ny\n") == "[verse]\nx\n\n[bridge]\ny"


def test_lrclib_get_bulamazsa_arama(monkeypatch):
    def sahte(url, parametre=None, **_):
        if url.endswith("/get"):
            raise ag.Bulunamadi(url)
        # başka sanatçının (karaoke, cover) kaydı ilk sırada gelebilir: alınmaz (Denetim 4)
        return [{"instrumental": True, "plainLyrics": "", "artistName": "A"},
                {"plainLyrics": "karaoke", "duration": 190, "artistName": "Karaoke Hits Band"},
                {"plainLyrics": "x\ny", "duration": 200, "artistName": "A feat. C"}]

    s = sozler.lrclib("A", "B", json_al=sahte)
    assert s.metin == "[Verse 1]\nx\ny" and s.sure_sn == 200 and s.kaynak == "lrclib"
    with pytest.raises(ag.Bulunamadi):
        sozler.lrclib("Z", "B", json_al=sahte)


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


def test_kunye_en_erken_yil_tipografik_baslik_ve_yazar_adlari():
    """Gerçek bulgular (2026-10-08): eser bağlı kayıt yeniden yayın (Keane 2021 → asıl 2004); MusicBrainz başlığı
    ’ ile yazıyor (James Arthur'da künye hiç yoktu); "Del Rey, Lana" son boşluktan bölünemez; "Adele" yasal addan."""
    yanitlar = {
        "/recording/": {"recordings": [
            {"id": "r1", "title": "Say You Won’t Let Go", "score": 100, "first-release-date": "2021-04-02"},
            {"id": "r2", "title": "Say You Won't Let Go", "score": 99, "first-release-date": "2016-09-09"},
            {"id": "r3", "title": "Say You Won’t Let Go", "score": 99},
        ]},
        "/recording/r1": {"relations": [{"type": "performance", "work": {"id": "w1", "title": "S"}}]},
        "/work/w1": {"relations": [
            {"type": "composer", "artist": {"id": "a1", "name": "Lana Del Rey", "sort-name": "Del Rey, Lana"}},
            {"type": "lyricist", "artist": {"id": "a1", "name": "Lana Del Rey", "sort-name": "Del Rey, Lana"}},
            {"type": "composer", "artist": {"id": "a2", "name": "Tim Rice‐Oxley", "sort-name": "Rice‐Oxley, Tim"}},
            {"type": "composer", "artist": {"id": "a3", "name": "Tobias Jesso Jr.", "sort-name": "Jesso, Tobias, Jr."}},
            {"type": "composer", "artist": {"id": "a4", "name": "Adele", "sort-name": "Adele"}},
            {"type": "composer", "artist": {"id": "a5", "name": "Mono", "sort-name": "Mono"}},
        ]},
        "/artist/a4": {"aliases": [
            {"type": "Legal name", "name": "Adele Laurie Blue Adkins", "sort-name": "Adkins, Adele Laurie Blue"},
            {"type": "Legal name", "name": "Adele Adkins", "sort-name": "Adele Adkins"},
            {"type": "Search hint", "name": "A"},
        ]},
        "/artist/a5": {"aliases": []},
    }

    def sahte(url, parametre=None, **_):
        return yanitlar[url.split("/ws/2", 1)[1]]

    k = kunye.bul("James Arthur", "Say You Won't Let Go", json_al=sahte, uyku=lambda _: None)
    assert k.ilk_yayin == "2016-09-09"
    assert k.yazarlar == ("Lana Del Rey", "Tim Rice-Oxley", "Tobias Jesso Jr.", "Adele", "Mono")
    assert k.yazar_adlari == (("Lana", "Del Rey"), ("Tim", "Rice-Oxley"), ("Tobias", "Jesso Jr."),
                              ("Adele", "Adkins"), ("Mono", ""))


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


def test_senkron_satirlar():
    lrc = "[00:14.08] I heard\n[01:02.5]  that you\n[ar:Adele]\n"
    assert sozler.senkron(lrc) == ((14.08, "I heard"), (62.5, "that you"))
    assert sozler.senkron(None) == ()


def test_dosya_sozu_lrclib_damgalarini_yalniz_uyusursa_alir(tmp_path):
    uzak = {"plainLyrics": "x", "duration": 180, "syncedLyrics": "[00:01.00] Hello there\n[00:05.00] General Kenobi"}
    ayni, farkli = tmp_path / "a.txt", tmp_path / "b.txt"
    ayni.write_text("hello there!\ngeneral kenobi", encoding="utf-8")
    farkli.write_text("tamamen\nbaşka söz", encoding="utf-8")
    beklenen = ((1.0, "Hello there"), (5.0, "General Kenobi"))
    assert sozler.bul("A", "B", ayni, json_al=lambda *a, **k: uzak).satirlar == beklenen
    assert sozler.bul("A", "B", farkli, json_al=lambda *a, **k: uzak).satirlar == ()


def test_etiketle_nota_satiri_kita_siniri():
    # LRCLIB düz sözü: kıtalar arasında boş satır yok, enstrümantal ara "♪"
    duz = "a\nb\n♪\nnakarat\nla\n♪\nc\n♪\nnakarat\nla\n"
    assert sozler.etiketle(duz) == ("[Verse 1]\na\nb\n\n[Chorus]\nnakarat\nla\n\n[Verse 2]\nc\n\n"
                                   "[Chorus]\nnakarat\nla")
    assert sozler.etiketle("[verse]\nx\n♪\n\n[bridge]\ny") == "[verse]\nx\n\n[bridge]\ny"


def test_aralik_sozu_bolum_etiketli():
    satirlar = [(1, "a"), (2, "b"), (3, "♪"), (4, "n1"), (5, "n2"), (6, ""), (7, "c"), (8, "♪"), (9, "n1"), (10, "n2")]
    assert sozler.aralik_sozu(satirlar, 0, 20) == ("[Verse 1]\na\nb\n\n[Chorus]\nn1\nn2\n\n[Verse 2]\nc\n\n"
                                                  "[Chorus]\nn1\nn2")
    assert sozler.aralik_sozu(satirlar, 2, 5) == "[Verse 1]\nb\n\n[Chorus]\nn1"  # ♪ söz olarak gitmez
    assert sozler.aralik_sozu(satirlar, 11, 20) == ""


def test_youtube_indir_bos_parcada_yeniden_dener(tmp_path, monkeypatch):
    cagri = []

    def bir(video_id, hedef, bicim=kaynak.BICIM):
        cagri.append(video_id)
        if len(cagri) < 3:
            raise OSError("eksik indirme: 0/100 bayt, HTTP 403")
        return hedef

    monkeypatch.setattr(kaynak, "_indir_bir", bir)
    assert kaynak.youtube_indir("v", tmp_path / "a.m4a", bekleme_sn=0) == tmp_path / "a.m4a"
    assert len(cagri) == 3
    cagri.clear()
    monkeypatch.setattr(kaynak, "_indir_bir", lambda v, h, b=None: (_ for _ in ()).throw(OSError("eksik")))
    with pytest.raises(OSError):
        kaynak.youtube_indir("v", tmp_path / "a.m4a", deneme=2, bekleme_sn=0)


def _nakaratli(nakaratlar, ilk=14.0):
    satirlar = [[ilk, "Verse one"], [ilk + 4, "Verse two"]]
    for t in nakaratlar:
        satirlar += [[t, "Never mind"], [t + 5, "chorus two"]]
    return satirlar


def test_kesitler_ilk_kita_nakarat_son_nakarat():
    k = sozler.kesitler(_nakaratli([74.0, 157.0, 204.0, 232.0]), 285.0)
    assert [(x["kimlik"], x["bas"], x["son"]) for x in k] == [
        ("ilk_kita", 13.0, 43.0), ("nakarat", 73.0, 103.0), ("son_nakarat", 231.0, 261.0)]
    # son geçişler birbirine yakınsa (nakarat içi tekrar) son nakarat kümenin başıdır; şarkı sonu keser
    k = sozler.kesitler(_nakaratli([60.0, 130.0, 190.0, 200.0, 210.0]), 215.0)
    assert k[-1] == {"kimlik": "son_nakarat", "ad": "Son nakarat", "bas": 189.0, "son": 215.0}


def test_kesitler_cakisan_ilk_kita_kisalir_nakarat_kalir():
    k = sozler.kesitler(_nakaratli([47.0, 91.0, 147.0], ilk=24.0), 236.0)
    assert [(x["kimlik"], x["bas"], x["son"]) for x in k][:2] == [("ilk_kita", 23.0, 46.0), ("nakarat", 46.0, 76.0)]


def test_kesitler_nakarat_yoksa_yalniz_ilk_kita_sozsuzse_bos():
    assert [x["kimlik"] for x in sozler.kesitler([[5.0, "a"], [9.0, "b"], [12.0, "a"]], None)] == ["ilk_kita"]
    assert sozler.kesitler([[3.0, "♪"], [8.0, ""]], 100.0) == []
