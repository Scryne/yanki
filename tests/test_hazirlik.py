from pathlib import Path

from yanki import ag, ayarlar, durum, hazirlik, kaynak, kunye, motor, sozler
from yanki.liste import Sarki

S = Sarki("Adele", "Someone Like You")


def test_durum_gidis_donus(tmp_path):
    d = durum.Durum("a-b", "A", "B")
    d.adaylar.append(durum.Aday(1, "x.flac", 42, {"parmak_izi": {"gecti": True}}, True))
    d.gec("hazir")
    durum.yaz(tmp_path, d)
    o = durum.oku(tmp_path, "a-b")
    assert o.asama == "hazir" and o.adaylar[0].tohum == 42 and o.gecmis[-1]["asama"] == "hazir"
    assert [x.kimlik for x in durum.hepsi(tmp_path)] == ["a-b"]


def test_bilinmeyen_asama_reddedilir():
    import pytest

    with pytest.raises(ValueError):
        durum.Durum("a", "A", "B").gec("bitti")


def _lm_ayarlari():
    from dataclasses import replace

    a = ayarlar.yukle()
    return replace(a, motor=replace(a.motor, analiz_yontemi="lm"))


def test_stil_kur():
    assert hazirlik.stil_kur(Sarki("A", "B", stil="benim stilim"), "lm") == "benim stilim"
    assert hazirlik.stil_kur(Sarki("A", "B", vokal="kadin"), "piano ballad.") == (
        "piano ballad, female lead vocal, clean modern studio recording")
    assert hazirlik.stil_kur(Sarki("A", "B"), None) == "clean modern studio recording"


def test_stil_kur_musicbrainz():
    solo = {"sanatci_turleri": ["pop", "soul", "r&b"], "sanatci_tipi": "Person", "sanatci_cinsiyeti": "Female"}
    beklenen = "pop, soul song, female lead vocal, clean modern studio recording"
    assert hazirlik.stil_kur(Sarki("A", "B"), kunye=solo) == beklenen
    grup = {"sanatci_turleri": ["alternative rock"], "sanatci_tipi": "Group", "sanatci_cinsiyeti": None}
    assert hazirlik.stil_kur(Sarki("A", "B"), kunye=grup) == "alternative rock song, clean modern studio recording"
    # liste vokali sanatçı cinsiyetini ezer (ör. düet ya da grup)
    assert "male lead vocal" in hazirlik.stil_kur(Sarki("A", "B", vokal="erkek"), kunye=grup)


def test_musicbrainz_analizi_gpu_kullanmaz_ve_tahmin_gondermez(tmp_path, monkeypatch):
    c = tmp_path / "c"
    _hazir_sarki(c)
    d = durum.oku(c, S.kimlik)
    d.kunye = {"sanatci_turleri": ["pop"], "sanatci_tipi": "Person", "sanatci_cinsiyeti": "Female"}
    durum.yaz(c, d)
    monkeypatch.setattr(motor, "calistir", lambda *a, **k: (_ for _ in ()).throw(AssertionError("motor çağrıldı")))
    hazirlik.analiz_et(ayarlar.yukle(), [S], c)
    o = durum.oku(c, S.kimlik)
    assert o.asama == "analiz" and o.analiz["bpm"] is None and o.analiz["ton"] == ""
    assert o.analiz["stil"] == "pop song, female lead vocal, clean modern studio recording"


def _sahteler(monkeypatch, soz_hata=False, kaynak_hata=False, kunye_hata=False):
    def soz(*_a, **_k):
        if soz_hata:
            raise ag.Bulunamadi("yok")
        return sozler.Soz("[verse]\nla", "lrclib", 285.0)

    def kn(*_a, **_k):
        if kunye_hata:
            raise ag.Bulunamadi("mb yok")
        return kunye.Kunye("r", "w", "Song", ("Adele Adkins", "Dan Wilson"))

    def kyn(kimlik, sanatci, ad, beklenen, klasor, calisma, youtube=None, yedek_sureler=None):
        assert beklenen == 285.0
        if kaynak_hata:
            raise kaynak.KaynakYok("önizleme")
        calisma.mkdir(parents=True, exist_ok=True)
        (calisma / "kaynak.wav").write_bytes(b"x")
        return kaynak.Kaynak(calisma / "kaynak.wav", "youtube:abc", "Song (Official Audio)", 285.5)

    monkeypatch.setattr(sozler, "bul", soz)
    monkeypatch.setattr(kunye, "bul", kn)
    monkeypatch.setattr(kaynak, "hazirla", kyn)


def test_girdi_hazir(tmp_path, monkeypatch):
    _sahteler(monkeypatch)
    d = hazirlik.girdi_hazirla(ayarlar.yukle(), S, tmp_path / "c", tmp_path / "g")
    assert d.asama == "hazir"
    assert list(d.kunye["yazarlar"]) == ["Adele Adkins", "Dan Wilson"]
    assert (tmp_path / "c" / S.kimlik / "soz.txt").read_text(encoding="utf-8") == "[verse]\nla"
    assert durum.oku(tmp_path / "c", S.kimlik).kaynak["nereden"] == "youtube:abc"


def test_soz_yoksa_hata_ve_cozum_yolu(tmp_path, monkeypatch):
    _sahteler(monkeypatch, soz_hata=True)
    d = hazirlik.girdi_hazirla(ayarlar.yukle(), S, tmp_path / "c", tmp_path / "g")
    assert d.asama == "hata" and f"girdi/sozler/{S.kimlik}.txt" in d.hata


def test_kaynak_yoksa_hata(tmp_path, monkeypatch):
    _sahteler(monkeypatch, kaynak_hata=True)
    d = hazirlik.girdi_hazirla(ayarlar.yukle(), S, tmp_path / "c", tmp_path / "g")
    assert d.asama == "hata" and "önizleme" in d.hata


def test_kunye_yoksa_uyari_ama_devam(tmp_path, monkeypatch):
    _sahteler(monkeypatch, kunye_hata=True)
    d = hazirlik.girdi_hazirla(ayarlar.yukle(), S, tmp_path / "c", tmp_path / "g")
    assert d.asama == "hazir" and "uyari" in d.kunye


def test_kaynak_lrclib_surum_yedegi(tmp_path, monkeypatch):
    """`/get` başka sürümün süresini verdi: video diğer sürümlerin süresiyle bulunur, söz o sürümden yazılır."""
    _sahteler(monkeypatch)
    cagri = []

    def kyn(kimlik, sanatci, ad, beklenen, klasor, calisma, youtube=None, yedek_sureler=None):
        cagri.append(yedek_sureler)
        if not yedek_sureler:
            raise kaynak.KaynakYok("uygun video yok")
        calisma.mkdir(parents=True, exist_ok=True)
        (calisma / "kaynak.wav").write_bytes(b"x")
        return kaynak.Kaynak(calisma / "kaynak.wav", "youtube:abc", "Song (Audio)", 216.3, 216.0)

    surum = [sozler.Soz("[verse]\nkisa", "lrclib", 180.0, ((1.0, "kisa"),)),
             sozler.Soz("[verse]\ndogru", "lrclib", 216.0, ((2.0, "dogru"),))]
    monkeypatch.setattr(kaynak, "hazirla", kyn)
    monkeypatch.setattr(sozler, "lrclib_surumleri", lambda *_a, **_k: surum)
    d = hazirlik.girdi_hazirla(ayarlar.yukle(), S, tmp_path / "c", tmp_path / "g")
    assert d.asama == "hazir" and cagri == [None, [180.0, 216.0]]
    k = tmp_path / "c" / S.kimlik
    assert (k / "soz.txt").read_text(encoding="utf-8") == "[verse]\ndogru"
    assert "dogru" in (k / "soz_zaman.json").read_text(encoding="utf-8") and d.soz["sure_sn"] == 216.0


def test_kaynak_surum_yedegi_de_tutmazsa_hata(tmp_path, monkeypatch):
    _sahteler(monkeypatch, kaynak_hata=True)
    monkeypatch.setattr(sozler, "lrclib_surumleri", lambda *_a, **_k: [sozler.Soz("x", "lrclib", 200.0)])
    d = hazirlik.girdi_hazirla(ayarlar.yukle(), S, tmp_path / "c", tmp_path / "g")
    assert d.asama == "hata" and "önizleme" in d.hata


def _hazir_sarki(c, sure=120):
    import numpy as np
    import soundfile as sf

    d = durum.Durum(S.kimlik, S.sanatci, S.ad, kaynak={"dosya": "kaynak.wav"})
    d.gec("hazir")
    durum.yaz(c, d)
    sf.write(str(c / S.kimlik / "kaynak.wav"), np.zeros((int(sure * 8000), 2), "float32"), 8000)


def test_analiz_lm_ve_liste_birlesir(tmp_path, monkeypatch):
    import soundfile as sf

    c = tmp_path / "c"
    _hazir_sarki(c)
    gorulen, modeller = [], []

    def sahte_calistir(a, isler, klasor, zaman_asimi_sn, model=None):
        modeller.append(model)
        gorulen.extend(isler)
        return [motor.Sonuc(i.id, True, analiz={"caption": "piano ballad", "bpm": "67.5", "keyscale": "A major"})
                for i in isler]

    monkeypatch.setattr(motor, "calistir", sahte_calistir)
    hazirlik.analiz_et(_lm_ayarlari(), [Sarki("Adele", "Someone Like You", vokal="kadin", bpm=68)], c)
    o = durum.oku(c, S.kimlik)
    assert o.asama == "analiz" and gorulen[0].gorev == "anla"
    # tüm şarkı değil, ayardaki uzunlukta kesit; ağır XL değil analiz modeli
    assert Path(gorulen[0].kaynak).name == "analiz_kesit.wav"
    assert sf.info(gorulen[0].kaynak).duration == ayarlar.yukle().motor.analiz_kesit_sn
    assert modeller == [ayarlar.yukle().motor.analiz_model]
    assert o.analiz["bpm"] == 68 and o.analiz["ton"] == "A major"
    assert o.analiz["stil"] == "piano ballad, female lead vocal, clean modern studio recording"


def test_analiz_basarisizsa_liste_degerleri_kalir(tmp_path, monkeypatch):
    c = tmp_path / "c"
    _hazir_sarki(c, sure=20)  # kesitten kısa şarkı: tamamı kullanılır
    monkeypatch.setattr(motor, "calistir",
                        lambda a, isler, k, z, model=None: [motor.Sonuc(i.id, False, "LM yüklenemedi") for i in isler])
    hazirlik.analiz_et(_lm_ayarlari(), [S], c)
    o = durum.oku(c, S.kimlik)
    assert o.analiz["lm_hata"] == "LM yüklenemedi" and o.analiz["bpm"] is None


def test_dil_bul_esik_ve_hata(tmp_path):
    from yanki import durum, hazirlik

    d = durum.Durum("a-b", "A", "B", kaynak={"dosya": "kaynak.wav"})
    assert hazirlik.dil_bul(d, tmp_path, lambda _: ("tr", 0.97)) == {"dil": "tr", "dil_tespit": "tr 0.97"}
    assert hazirlik.dil_bul(d, tmp_path, lambda _: ("fr", 0.31))["dil"] == "en"  # emin değil: kalibre dil

    def bozuk(_):
        raise RuntimeError("ses okunamadı")

    assert hazirlik.dil_bul(d, tmp_path, bozuk) == {"dil": "en", "dil_tespit": "başarısız: ses okunamadı"}


def test_dil_bul_ses_belirsizse_soz_karar_verir(tmp_path):
    # Nyoy Volante: ses "tl 0,25" → "en" sayılıyordu, Tagalog söz İngilizce söylenip ölçülüyordu (WER ~1,0)
    from yanki import durum, hazirlik

    d = durum.Durum("a-b", "A", "B", kaynak={"dosya": "kaynak.wav"}, soz={"dosya": "soz.txt"})
    (tmp_path / "soz.txt").write_text("[Verse 1]\nIpagpatawad mo, aking kapangahasan\nalam kong kailan lang tayo "
                                      "nagkatagpo", encoding="utf-8")
    assert hazirlik.dil_bul(d, tmp_path, lambda _: ("tl", 0.25))["dil"] == "tl"
    (tmp_path / "soz.txt").write_text("[Verse 1]\nI heard that you're settled down\nThat you found a girl and you're "
                                      "married now", encoding="utf-8")
    assert hazirlik.dil_bul(d, tmp_path, lambda _: ("tl", 0.25))["dil"] == "en"


def test_stil_deezer_yedegi_yalniz_musicbrainz_bossa():
    from yanki import hazirlik, liste

    s = liste.Sarki("HAARPER", "Cadavers")
    assert hazirlik.stil_kur(s, kunye={}, yedek_turler=["rap, hip hop"]).startswith("rap, hip hop song, ")
    mb = {"sanatci_turleri": ["pop"], "sanatci_tipi": "Person", "sanatci_cinsiyeti": "Female"}
    assert hazirlik.stil_kur(s, kunye=mb, yedek_turler=["rap, hip hop"]).startswith("pop song, female lead vocal")


def test_deezer_sanatci_turleri():
    from yanki import katalog

    cevap = {"/search/artist": {"data": [{"id": 9, "name": "Haarper"}]},
             "/artist/9/albums": {"data": [{"id": 1}, {"id": 2}]},
             "/album/1": {"genres": {"data": [{"name": "Rap/Hip Hop"}]}},
             "/album/2": {"genres": {"data": [{"name": "Rap/Hip Hop"}, {"name": "Alternative"}]}}}
    ja = lambda url, p=None: cevap[url.replace(katalog.DEEZER, "")]  # noqa: E731
    assert katalog.sanatci_turleri("HAARPER", ja) == ["rap, hip hop", "alternative"]


def test_ses_ingilizce_disi_soz_ingilizceyse_dili_tutan_surum_alinir(tmp_path):
    # YOASOBI "Idol": Japonca ses, LRCLIB İngilizce sürümün sözünü verdi
    from yanki import durum, hazirlik, sozler

    d = durum.Durum("y-i", "YOASOBI", "Idol", kaynak={"dosya": "kaynak.wav", "sure_sn": 213.0},
                    soz={"dosya": "soz.txt", "kaynak": "lrclib"})
    (tmp_path / "soz.txt").write_text("[Verse 1]\nCouldn't beat her smile it stirred up all the media\nYou are so "
                                      "mysterious and I want to know", encoding="utf-8")
    satir = "無敵の笑顔で荒らすメディア"
    japonca = sozler.Soz(f"[Verse 1]\n{satir}", "lrclib", 214.0, ((1.0, satir),))
    ingilizce = sozler.Soz("[Verse 1]\nyou are the one and I love you", "lrclib", 213.0, ((1.0, "you"),))
    assert hazirlik.soz_dili_uyumu(d, tmp_path, "ja", surumler=lambda *_: [ingilizce, japonca]) is None
    assert "無敵" in (tmp_path / "soz.txt").read_text(encoding="utf-8")
    assert "無敵" in (tmp_path / "soz_zaman.json").read_text(encoding="utf-8")
    # dili tutan sürüm yoksa yanlış dilde söyletilmez: hata
    (tmp_path / "soz.txt").write_text("[Verse 1]\nyou are the one and I love you so", encoding="utf-8")
    assert "çeviri" in hazirlik.soz_dili_uyumu(d, tmp_path, "ja", surumler=lambda *_: [ingilizce])
    assert hazirlik.soz_dili_uyumu(d, tmp_path, "en", surumler=lambda *_: []) is None  # İngilizce şarkı: dokunulmaz


def test_karisik_dilli_kpop_sozu_ceviri_sayilmaz(tmp_path):
    # BLACKPINK: Korece söz İngilizce nakaratlarla (İngilizce payı 0,42) — çeviri değil, dokunulmaz
    from yanki import durum, hazirlik

    d = durum.Durum("b-h", "BLACKPINK", "How You Like That", kaynak={"dosya": "kaynak.wav", "sure_sn": 181.0},
                    soz={"dosya": "soz.txt", "kaynak": "lrclib"})
    (tmp_path / "soz.txt").write_text("[Verse 1]\nBLACKPINK in your area\n보란 듯이 무너졌어\n바닥을 뚫고 저 지하까지\n"
                                      "[Chorus]\nHow you like that\nYou gon' like that that that", encoding="utf-8")
    assert hazirlik.soz_dili_uyumu(d, tmp_path, "ko", surumler=lambda *_: []) is None


def test_deezer_adas_sanatci_en_cok_hayranlisi_soundtrack_turu_sayilmaz():
    # 2026-10-26: "Michael Jackson" önce 227 hayranlı adaşı (rap), Ariana Grande'nin son albümleri Wicked soundtrack'i
    from yanki import katalog

    cevap = {"/search/artist": {"data": [{"id": 8, "name": "Ariana Grande", "nb_fan": 227},
                                         {"id": 9, "name": "Ariana Grande", "nb_fan": 13_000_000}]},
             "/artist/9/albums": {"data": [{"id": 1}, {"id": 2}, {"id": 3}]},
             "/album/1": {"genres": {"data": [{"name": "Films/Games"}, {"name": "Film Scores"}]}},
             "/album/2": {"genres": {"data": [{"name": "Films/Games"}]}},
             "/album/3": {"genres": {"data": [{"name": "Pop"}]}}}
    ja = lambda url, p=None: cevap[url.replace(katalog.DEEZER, "")]  # noqa: E731
    assert katalog.sanatci_bul("ariana grande", ja)["id"] == 9
    assert katalog.sanatci_turleri("Ariana Grande", ja) == ["pop"]
    cevap["/album/3"] = {"genres": {"data": [{"name": "Film Scores"}]}}  # yalnız soundtrack: tür odur
    assert katalog.sanatci_turleri("Ariana Grande", ja)[0] == "films, games"
