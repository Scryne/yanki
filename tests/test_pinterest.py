"""Pinterest kapağı: sorgu, insan/yazı süzgeci, tekrar kullanmama, paketlemeye bağlanma (sahte arama; ağ yok)."""

import io
import json

import pytest

from yanki import durum, olay, paket, pinterest


def _pin(no, aciklama, en=1200, boy=1200, **k):
    return {"id": str(no), "type": "pin", "seo_alt_text": aciklama, "image_signature": f"imza{no}",
            "images": {"orig": {"url": f"https://i.pinimg.com/{no}.jpg", "width": en, "height": boy}}, **k}


def _jpeg_bayt(renk=(30, 60, 90), boyut=(900, 1200)):
    from PIL import Image

    b = io.BytesIO()
    Image.new("RGB", boyut, renk).save(b, "JPEG")
    return b.getvalue()


def _sarki(c, kimlik="a", stil="melancholic piano ballad, male lead vocal", soz=None, asama="onaylandi"):
    d = durum.Durum(kimlik, "X", kimlik.upper(), asama=asama, analiz={"stil": stil})
    durum.yaz(c, d)
    if soz:
        (c / kimlik / "soz.txt").write_text(soz, encoding="utf-8")
    return d


def test_sorgu_moddan_ve_sozdeki_imgeden_sarki_adi_yok():
    d = durum.Durum("a", "Adele", "Someone Like You", analiz={"stil": "emotional piano ballad, romantic"})
    assert pinterest.sorgu(d) == "romantic emotional rainy window scenery aesthetic"  # sözsüz: türün sahnesi
    soz = "[verse]\n[00:01.00] the ocean calls\nby the ocean\nunder the stars\nall night long"
    q = pinterest.sorgu(d, soz)
    assert q == "romantic emotional ocean scenery aesthetic" and "adele" not in q.casefold()
    assert pinterest.imge("I fall in love and fall again") is None  # "fall" fiil, sonbahar değil
    assert pinterest.imge("all night, the night") == "night"  # genel imge yalnız başka yoksa
    assert pinterest.imge("night night night ocean") == "ocean"
    rap = durum.Durum("b", "X", "Y", analiz={"stil": "rap, hip hop song"})
    assert pinterest.sorgu(rap) == "moody city night scenery aesthetic"


@pytest.mark.parametrize("aciklama", [
    "a woman laying in the grass with her eyes closed", "two people kissing in front of the sun",
    "a couple sitting on a bench", "a poster with the words kiss me forever", "an open book next to raindrops",
    "a record player next to flowers", "a laptop on a bed by the window", "Adele album cover",
])
def test_insan_ya_da_yazi_iceren_gorsel_elenir(aciklama):
    assert not pinterest.uygun(_pin(1, aciklama))


def test_uygun_gorsel_ve_secim_kurallari():
    iyi = _pin(1, "a foggy forest filled with lots of trees", 1440, 1918)
    assert pinterest.uygun(iyi)
    assert not pinterest.uygun(_pin(2, "a foggy forest", 500, 800))  # küçük
    assert not pinterest.uygun(_pin(3, "a foggy forest", is_promoted=True))  # reklam
    assert not pinterest.uygun(_pin(4, ""))  # açıklamasız: içeriği bilinmiyor
    assert not pinterest.uygun(_pin(5, "a foggy forest", type="story"))
    kare = _pin(6, "a calm lake at dawn", 1500, 1500)
    uzun = _pin(7, "a calm lake at dawn", 1600, 4000)
    assert pinterest.sec([iyi, uzun, kare], set())["id"] == "6"  # kareye yakın büyük görsel
    assert pinterest.sec([iyi, uzun, kare], {"6"})["id"] == "1"
    assert pinterest.sec([iyi, kare], {"imza1", "6"}) is None  # imza ile de tekrar yok


def test_getir_kaydeder_tekrar_kullanmaz_yeni_ile_degistirir(tmp_path):
    c = tmp_path / "c"
    a, b = _sarki(c, "a"), _sarki(c, "b")
    sorgular = []
    sonuclar = [_pin(1, "a foggy forest"), _pin(2, "a misty lake")]

    def arayici(q):
        sorgular.append(q)
        return sonuclar

    hedef = pinterest.getir(c, a, arayici=arayici, indirici=lambda url: _jpeg_bayt())
    k = json.loads((c / "a" / "kapak_kaynak.json").read_text(encoding="utf-8"))
    assert hedef.exists() and k["pin_id"] == "1" and k["sorgu"] == sorgular[0] and k["onceki"] == []
    assert pinterest.getir(c, a, arayici=arayici, indirici=lambda url: b"") == hedef and len(sorgular) == 1
    pinterest.getir(c, b, arayici=arayici, indirici=lambda url: _jpeg_bayt())
    assert json.loads((c / "b" / "kapak_kaynak.json").read_text(encoding="utf-8"))["pin_id"] == "2"  # 1 a'nın
    with pytest.raises(pinterest.Bulunamadi):  # iki pin de kullanıldı, yedek sorgularda da yok
        pinterest.getir(c, a, yeni=True, arayici=arayici, indirici=lambda url: _jpeg_bayt())
    sonuclar.append(_pin(3, "a quiet snowy road"))
    pinterest.getir(c, a, yeni=True, arayici=arayici, indirici=lambda url: _jpeg_bayt())
    k = json.loads((c / "a" / "kapak_kaynak.json").read_text(encoding="utf-8"))
    assert k["pin_id"] == "3" and k["onceki"] == ["1", "imza1"]  # görsel imzası da: aynı görsel başka pinle dönmesin


def test_paketleme_pinterest_kapagi_kullanir_elle_secilen_once_gelir(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf

    try:
        from yanki import ses

        ses.arac("ffmpeg")
    except FileNotFoundError:
        pytest.skip("ffmpeg gerekli")
    c = tmp_path / "c"
    for kimlik in ("pin", "elle"):
        d = _sarki(c, kimlik)
        (c / kimlik / "adaylar" / "1").mkdir(parents=True)
        t = np.arange(20 * 44100) / 44100
        x = 0.05 * np.sin(2 * np.pi * 220 * t)
        sf.write(str(c / kimlik / "adaylar" / "1" / "tam.flac"), np.stack([x, x], 1).astype("float32"), 44100)
        d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, {}, True)]
        d.secilen = 1
        durum.yaz(c, d)
    (c / "elle" / "kapak_ozel.jpg").write_bytes(_jpeg_bayt((200, 0, 0), (3000, 3000)))
    cagri = []

    def sahte_getir(calisma, d, yeni=False):
        cagri.append(d.kimlik)
        (calisma / d.kimlik / "kapak_pinterest.jpg").write_bytes(_jpeg_bayt())
        (calisma / d.kimlik / "kapak_kaynak.json").write_text(json.dumps(
            {"pin_id": "9", "pin": "https://www.pinterest.com/pin/9/", "aciklama": "a misty lake"}), "utf-8")
        return calisma / d.kimlik / "kapak_pinterest.jpg"

    monkeypatch.setattr(pinterest, "getir", sahte_getir)
    yol = tmp_path / "yayin.toml"
    yol.write_text('[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "tunearo"\n[kapak]\nkaynak = "pinterest"\n'
                   "[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.0\nornekleme = 44100\n", encoding="utf-8")
    paket.paketle(c, yol)
    assert cagri == ["pin"]  # elle seçilen kapağı olan şarkıda Pinterest'e bakılmaz
    meta = json.loads((c / "pin" / "paket" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["kapak"]["kaynak"] == "pinterest" and meta["kapak"]["pin"].endswith("/9/")
    assert meta["kapak"]["islem"].startswith("ortadan kare kırpıldı (900×1200")
    assert json.loads((c / "elle" / "paket" / "metadata.json").read_text(encoding="utf-8"))["kapak"]["kaynak"] == "ozel"
    (o,) = olay.oku(c)
    assert o["tur"] == "kapak" and "--yeni" in o["metin"]


def test_kapak_ayari_dogrulanir(tmp_path):
    yol = tmp_path / "yayin.toml"
    yol.write_text('[yayin]\nsanatci_adi = ""\ndagitimci = ""\n[kapak]\nkaynak = "google"\n'
                   "[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.0\nornekleme = 44100\n", encoding="utf-8")
    with pytest.raises(ValueError, match="kapak.kaynak"):
        paket.yayin_ayarlari(yol)
