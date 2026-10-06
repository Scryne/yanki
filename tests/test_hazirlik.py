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


def test_stil_kur():
    assert hazirlik.stil_kur(Sarki("A", "B", stil="benim stilim"), "lm") == "benim stilim"
    assert hazirlik.stil_kur(Sarki("A", "B", vokal="kadin"), "piano ballad.") == (
        "piano ballad, female lead vocal, clean modern studio recording")
    assert hazirlik.stil_kur(Sarki("A", "B"), None) == "clean modern studio recording"


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


def test_analiz_lm_ve_liste_birlesir(tmp_path, monkeypatch):
    c = tmp_path / "c"
    d = durum.Durum(S.kimlik, S.sanatci, S.ad, kaynak={"dosya": "kaynak.wav"})
    d.gec("hazir")
    durum.yaz(c, d)
    gorulen = []

    def sahte_calistir(a, isler, klasor, zaman_asimi_sn):
        gorulen.extend(isler)
        return [motor.Sonuc(i.id, True, analiz={"caption": "piano ballad", "bpm": "67.5", "keyscale": "A major"})
                for i in isler]

    monkeypatch.setattr(motor, "calistir", sahte_calistir)
    hazirlik.analiz_et(ayarlar.yukle(), [Sarki("Adele", "Someone Like You", vokal="kadin", bpm=68)], c)
    o = durum.oku(c, S.kimlik)
    assert o.asama == "analiz" and gorulen[0].gorev == "anla" and Path(gorulen[0].kaynak).name == "kaynak.wav"
    assert o.analiz["bpm"] == 68 and o.analiz["ton"] == "A major"
    assert o.analiz["stil"] == "piano ballad, female lead vocal, clean modern studio recording"


def test_analiz_basarisizsa_liste_degerleri_kalir(tmp_path, monkeypatch):
    c = tmp_path / "c"
    d = durum.Durum(S.kimlik, S.sanatci, S.ad, kaynak={"dosya": "kaynak.wav"})
    d.gec("hazir")
    durum.yaz(c, d)
    monkeypatch.setattr(motor, "calistir",
                        lambda a, isler, k, z: [motor.Sonuc(i.id, False, "LM yüklenemedi") for i in isler])
    hazirlik.analiz_et(ayarlar.yukle(), [S], c)
    o = durum.oku(c, S.kimlik)
    assert o.analiz["lm_hata"] == "LM yüklenemedi" and o.analiz["bpm"] is None
