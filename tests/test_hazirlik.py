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

    def kyn(kimlik, sanatci, ad, beklenen, klasor, calisma, youtube=None):
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
