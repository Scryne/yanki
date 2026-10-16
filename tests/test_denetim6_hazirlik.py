"""Denetim 6: girdi hazırlığı, kapılar ve ses için regresyon testleri."""

import pytest

from yanki import ayarlar, hazirlik, kapilar, kaynak, kunye, liste, ses, sozler


def test_dosya_sozu_latin_disi_farkli_metin_damga_almaz(tmp_path):
    """Korece söz dosyası ile tamamen başka Korece LRCLIB sözü: `_sade` yalnız a-z tuttuğu için iki taraf da boş satıra
    düşüp %100 "eşleşiyor", başka metnin zaman damgaları alınıyordu."""
    uzak = {"plainLyrics": "x", "duration": 180,
            "syncedLyrics": "[00:01.00] 보란 듯이 무너졌어\n[00:05.00] 바닥을 뚫고 저 지하까지"}
    farkli, ayni = tmp_path / "a.txt", tmp_path / "b.txt"
    farkli.write_text("사랑해 너를\n영원히 함께", encoding="utf-8")
    ayni.write_text("보란 듯이 무너졌어\n바닥을 뚫고 저 지하까지", encoding="utf-8")
    assert sozler.bul("A", "B", farkli, json_al=lambda *a, **k: uzak).satirlar == ()
    assert len(sozler.bul("A", "B", ayni, json_al=lambda *a, **k: uzak).satirlar) == 2


def test_dosya_sozu_turkce_harfler_korunur(tmp_path):
    uzak = {"plainLyrics": "x", "duration": 180,
            "syncedLyrics": "[00:01.00] Şarkı söylemek lazım\n[00:05.00] Gönlüm çok güzel"}
    dosya = tmp_path / "a.txt"
    dosya.write_text("şarkı söylemek lazım\ngönlüm çok güzel", encoding="utf-8")
    assert len(sozler.bul("A", "B", dosya, json_al=lambda *a, **k: uzak).satirlar) == 2


def test_senkron_cok_damgali_satir():
    """Sıkıştırılmış LRC: tekrar eden satır tek satırda birden çok damgayla ("[00:12.00][00:45.00] nakarat"); önce
    ikinci damga söz metnine karışıyordu."""
    lrc = "[00:12.00][00:45.50]Nakarat\n[00:20.00] Kıta\n"
    assert sozler.senkron(lrc) == ((12.0, "Nakarat"), (20.0, "Kıta"), (45.5, "Nakarat"))


def test_lrclib_duz_soz_yoksa_zamanli_sozden(monkeypatch):
    d = {"plainLyrics": None, "duration": 100, "syncedLyrics": "[00:01.00] hello\n[00:03.00] world"}
    s = sozler.lrclib("A", "B", json_al=lambda *a, **k: d)
    assert "hello" in s.metin and s.satirlar


def _sahte_ses(monkeypatch, sure):
    monkeypatch.setattr(ses, "wav48", lambda g, c: (c.parent.mkdir(parents=True, exist_ok=True),
                                                     c.write_bytes(b"x"), c)[-1])
    monkeypatch.setattr(ses, "sure", lambda _y: sure)


def test_klasordeki_kaynak_lrclib_surumune_uyar(tmp_path, monkeypatch):
    """Scryne `girdi/kaynak`'a doğru kaydı bıraktı ama LRCLIB `/get` başka sürümü verdi (Dark Horse 297/216): hatanın
    önerdiği çözüm hiç çalışmıyordu, yedek sürüm süreleri yalnız YouTube'da deneniyordu."""
    klasor = tmp_path / "g"
    klasor.mkdir()
    (klasor / "a-b.mp3").write_bytes(b"x")
    _sahte_ses(monkeypatch, 216.4)
    with pytest.raises(kaynak.KaynakYok):
        kaynak.hazirla("a-b", "A", "B", 297.0, klasor, tmp_path / "c")
    k = kaynak.hazirla("a-b", "A", "B", 297.0, klasor, tmp_path / "c", yedek_sureler=[180.0, 216.0])
    assert k.nereden == "klasor" and k.beklenen_sn == 216.0


def test_sabit_video_bulunamazsa_kaynak_yok(tmp_path, monkeypatch):
    monkeypatch.setattr(kaynak, "youtube_adaylari", lambda *_a, **_k: [])
    with pytest.raises(kaynak.KaynakYok):
        kaynak.hazirla("a-b", "A", "B", 200.0, tmp_path / "g", tmp_path / "c", youtube="https://youtu.be/x")


def test_indirme_aralik_yok_sayilirsa_tekrar_eklemez(tmp_path, monkeypatch):
    """Sunucu Range'i yok sayıp 200 + bütün dosya dönerse aynı içerik tekrar tekrar eklenip dosya bozuluyordu."""
    import curl_cffi.requests
    import yt_dlp

    govde = b"a" * (kaynak.PARCA + 10)
    cagri = []

    class Ydl:
        def __init__(self, *_a, **_k): ...
        def __enter__(self): return self
        def __exit__(self, *_a): return False
        def extract_info(self, *_a, **_k): return {"url": "u"}

    class Cevap:
        status_code, content = 200, govde

    class Oturum:
        def __init__(self, *_a, **_k): ...
        def __enter__(self): return self
        def __exit__(self, *_a): return False

        def get(self, *_a, **_k):
            cagri.append(1)
            if len(cagri) > 3:
                raise AssertionError("döngü")
            return Cevap()

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Ydl)
    monkeypatch.setattr(curl_cffi.requests, "Session", Oturum)
    hedef = kaynak._indir_bir("v", tmp_path / "x.indirilen")
    assert hedef.read_bytes() == govde and len(cagri) == 1


@pytest.mark.parametrize(("satir", "hata"), [
    ('bpm = "68"', "bpm"), ("bpm = 0", "bpm"), ("bpm = true", "bpm"), ("bpm = 68.5", "bpm"),
    ("stil = 5", "stil"), ("ton = 3", "ton"), ('youtube = ["x"]', "youtube"),
])
def test_liste_alan_turleri(satir, hata):
    with pytest.raises(ValueError, match=hata):
        liste.coz(f'[[sarki]]\nsanatci = "A"\nad = "B"\n{satir}\n')


def test_liste_dogru_turler_gecer():
    s = liste.coz('[[sarki]]\nsanatci = "A"\nad = "B"\nbpm = 68\nton = "A major"\nstil = "x"\n')[0]
    assert s.bpm == 68 and s.ton == "A major"


def test_kunye_sanatci_kredisi_tipografik_kesme():
    """MusicBrainz "Guns N’ Roses", liste "Guns N' Roses": tür/tip/cinsiyet hiç alınmıyordu."""
    yanitlar = {
        "/recording/": {"recordings": [{"id": "r1", "title": "Patience", "score": 100,
                                        "artist-credit": [{"artist": {"id": "g", "name": "Guns N’ Roses"}}]}]},
        "/recording/r1": {"relations": [{"type": "performance", "work": {"id": "w1", "title": "Patience"}}]},
        "/work/w1": {"relations": [{"type": "composer", "artist": {"id": "a1", "name": "Axl Rose",
                                                                   "sort-name": "Rose, Axl"}}]},
        "/artist/g": {"genres": [{"name": "hard rock", "count": 5}], "type": "Group"},
    }
    k = kunye.bul("Guns N' Roses", "Patience", json_al=lambda url, *_a, **_k: yanitlar[url.split("/ws/2", 1)[1]],
                  uyku=lambda _: None)
    assert k.sanatci_turleri == ("hard rock",) and k.sanatci_tipi == "Group"


def test_ingilizce_orani_kivrik_kesme():
    assert kapilar.ingilizce_orani("don’t") == kapilar.ingilizce_orani("don't") == 1.0


def test_ton_sessiz_ses_acik_hata(tmp_path):
    import numpy as np
    import soundfile as sf

    from yanki import ton

    yol = tmp_path / "s.wav"
    sf.write(str(yol), np.zeros((48000 * 2, 2), "float32"), 48000)
    with pytest.raises(ValueError, match="sessiz"):
        ton.bant_spektrumu(yol)


def test_lm_analizi_soz_dilini_de_denetler(tmp_path, monkeypatch):
    """LM yolu (analiz_yontemi = "lm") çeviri sürümü sözü denetlemiyordu: Japonca sese İngilizce söz gidiyordu."""
    from dataclasses import replace

    import numpy as np
    import soundfile as sf

    from yanki import durum, motor
    from yanki.liste import Sarki

    s = Sarki("YOASOBI", "Idol")
    c = tmp_path / "c"
    d = durum.Durum(s.kimlik, s.sanatci, s.ad, kaynak={"dosya": "kaynak.wav", "sure_sn": 10.0},
                    soz={"kaynak": "lrclib", "dosya": "soz.txt"})
    d.gec("hazir")
    durum.yaz(c, d)
    sf.write(str(c / s.kimlik / "kaynak.wav"), np.zeros((8000 * 60, 2), "float32"), 8000)
    (c / s.kimlik / "soz.txt").write_text("[Verse 1]\nyou are the one and only idol in the world", encoding="utf-8")
    monkeypatch.setattr(kapilar, "dil_tespit", lambda _y: ("ja", 0.99))
    monkeypatch.setattr(sozler, "lrclib_surumleri", lambda *_a, **_k: [])
    monkeypatch.setattr(motor, "calistir", lambda a, isler, *_a, **_k: [
        motor.Sonuc(i.id, True, None, analiz={"caption": "j-pop"}) for i in isler])
    a = ayarlar.yukle()
    hazirlik.analiz_et(replace(a, motor=replace(a.motor, analiz_yontemi="lm")), [s], c)
    o = durum.oku(c, s.kimlik)
    assert o.asama == "hata" and "LRCLIB" in o.hata



def test_klasordeki_kaynak_uymazsa_hata_dogru_cozumu_soyler(tmp_path, monkeypatch):
    """Dosya zaten `girdi/kaynak`'tayken hata "girdi/kaynak/<kimlik>.mp3 olarak bırakılabilir" diyordu."""
    from yanki.liste import Sarki

    s = Sarki("Adele", "Hello")
    (tmp_path / "g" / "kaynak").mkdir(parents=True)
    (tmp_path / "g" / "kaynak" / f"{s.kimlik}.flac").write_bytes(b"x")
    monkeypatch.setattr(sozler, "bul", lambda *_a, **_k: sozler.Soz("[Verse 1]\nla", "dosya", 295.0))
    monkeypatch.setattr(kunye, "bul", lambda *_a, **_k: kunye.Kunye("r", "w", "Hello", ("Adele Adkins",)))
    _sahte_ses(monkeypatch, 120.0)
    d = hazirlik.girdi_hazirla(ayarlar.yukle(), s, tmp_path / "c", tmp_path / "g")
    assert d.asama == "hata" and f"{s.kimlik}.flac" in d.hata and "youtube" in d.hata
