"""Stok kapak (Unsplash/Pexels): süzgeç, seçim, tekrar kullanmama, anahtarsız hata, paketlemeye bağlanma (sahte
arama; ağ yok)."""

import io
import json

import pytest

from yanki import durum, olay, paket, stok


def _aday(no, aciklama, en=4000, boy=4000, kaynak="unsplash"):
    return {"kaynak": kaynak, "id": f"{kaynak}:{no}", "en": en, "boy": boy, "aciklama": aciklama,
            "indir": f"https://images.example/{no}.jpg", "bildir": None, "fotografci": f"Foto {no}",
            "fotografci_url": f"https://example/u/{no}", "sayfa": f"https://example/p/{no}"}


def _jpeg_bayt(renk=(30, 60, 90), boyut=(3200, 4000)):
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


@pytest.mark.parametrize("aciklama", [
    "a woman standing on a beach at sunset", "two people walking in the rain", "a neon sign that says open",
    "an open book on a wooden table", "a vinyl record next to a lamp",
])
def test_insan_ya_da_yazi_iceren_gorsel_elenir(aciklama):
    assert not stok.uygun(_aday(1, aciklama))


def test_uygun_ve_secim_kurallari():
    iyi = _aday(1, "a foggy forest filled with tall trees", 4000, 6000)
    assert stok.uygun(iyi)
    assert not stok.uygun(_aday(2, "a foggy forest", 2400, 3600))  # kısa kenar 3000'den küçük: büyütme yok
    assert not stok.uygun(_aday(3, ""))  # açıklamasız: içeriği bilinmiyor
    kare = _aday(4, "a calm lake at dawn", 3500, 3500)
    sirali = stok.sirali_adaylar([iyi, kare], set())
    assert [a["id"] for a in sirali] == ["unsplash:4", "unsplash:1"]  # kare 3500 > 4000×6000 (kırpılan kısım)
    assert stok.sirali_adaylar([iyi, kare], {"unsplash:1", "unsplash:4"}) == []


def test_getir_kaydeder_lisansi_yazar_tekrar_kullanmaz_yeni_ile_degistirir(tmp_path):
    c = tmp_path / "c"
    a, b = _sarki(c, "a"), _sarki(c, "b")
    sorgular = []
    sonuclar = [_aday(1, "a foggy forest"), _aday(2, "a misty lake", kaynak="pexels")]

    def arayici(q, anahtar):
        sorgular.append(q)
        return sonuclar

    hedef = stok.getir(c, a, arayici=arayici, indirici=lambda url: _jpeg_bayt(), anahtar={"unsplash": "x"})
    k = json.loads((c / "a" / "kapak_kaynak.json").read_text(encoding="utf-8"))
    assert hedef.name == "kapak_stok.jpg" and hedef.exists()
    assert k["stok_id"] == "unsplash:1" and k["lisans"].startswith("Unsplash License") and k["fotografci"] == "Foto 1"
    assert "aesthetic" not in k["sorgu"] and k["onceki"] == []
    # var olan kapak yeniden aranmaz
    assert stok.getir(c, a, arayici=arayici, indirici=lambda url: b"", anahtar={"unsplash": "x"}) == hedef
    assert len(sorgular) == 1
    stok.getir(c, b, arayici=arayici, indirici=lambda url: _jpeg_bayt(), anahtar={"pexels": "x"})
    kb = json.loads((c / "b" / "kapak_kaynak.json").read_text(encoding="utf-8"))
    assert kb["stok_id"] == "pexels:2" and kb["lisans"].startswith("Pexels License")  # 1 a'nın
    with pytest.raises(stok.Bulunamadi):  # ikisi de kullanıldı
        stok.getir(c, a, yeni=True, arayici=arayici, indirici=lambda url: _jpeg_bayt(), anahtar={"unsplash": "x"})
    sonuclar.append(_aday(3, "a quiet snowy road"))
    stok.getir(c, a, yeni=True, arayici=arayici, indirici=lambda url: _jpeg_bayt(), anahtar={"unsplash": "x"})
    k = json.loads((c / "a" / "kapak_kaynak.json").read_text(encoding="utf-8"))
    assert k["stok_id"] == "unsplash:3" and k["onceki"] == ["unsplash:1"]


def test_indirilen_gorsel_kucukse_siradakine_gecer(tmp_path):
    c = tmp_path / "c"
    a = _sarki(c, "a")
    adaylar = [_aday(1, "a foggy forest", 6000, 6000), _aday(2, "a misty lake", 5000, 5000)]
    boyutlar = {"https://images.example/1.jpg": (1200, 1200), "https://images.example/2.jpg": (3000, 3000)}
    stok.getir(c, a, arayici=lambda q, k: adaylar, indirici=lambda url: _jpeg_bayt(boyut=boyutlar[url]),
               anahtar={"unsplash": "x"})
    assert json.loads((c / "a" / "kapak_kaynak.json").read_text(encoding="utf-8"))["stok_id"] == "unsplash:2"


def test_anahtar_yoksa_aciklayici_hata(tmp_path, monkeypatch):
    c = tmp_path / "c"
    a = _sarki(c, "a")
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    monkeypatch.delenv("PEXELS_API_KEY", raising=False)
    with pytest.raises(stok.Bulunamadi, match="UNSPLASH_ACCESS_KEY"):
        stok.getir(c, a)


def test_anahtarlar_env_ve_ortamdan(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("UNSPLASH_ACCESS_KEY=dosyadan\nPEXELS_API_KEY=\n", encoding="utf-8")
    monkeypatch.delenv("UNSPLASH_ACCESS_KEY", raising=False)
    monkeypatch.setenv("PEXELS_API_KEY", "ortamdan")
    assert stok.anahtarlar(tmp_path) == {"unsplash": "dosyadan", "pexels": "ortamdan"}


def test_paketleme_stok_kapagi_kullanir_lisans_kaydeder(tmp_path, monkeypatch):
    import numpy as np
    import soundfile as sf

    try:
        from yanki import ses

        ses.arac("ffmpeg")
    except FileNotFoundError:
        pytest.skip("ffmpeg gerekli")
    c = tmp_path / "c"
    d = _sarki(c, "s")
    (c / "s" / "adaylar" / "1").mkdir(parents=True)
    t = np.arange(20 * 44100) / 44100
    x = 0.05 * np.sin(2 * np.pi * 220 * t)
    sf.write(str(c / "s" / "adaylar" / "1" / "tam.flac"), np.stack([x, x], 1).astype("float32"), 44100)
    d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, {}, True)]
    d.secilen = 1
    durum.yaz(c, d)

    def sahte_getir(calisma, d, yeni=False):
        (calisma / d.kimlik / "kapak_stok.jpg").write_bytes(_jpeg_bayt())
        (calisma / d.kimlik / "kapak_kaynak.json").write_text(json.dumps(
            {"kaynak": "unsplash", "stok_id": "unsplash:9", "sayfa": "https://unsplash.com/photos/9",
             "fotografci": "Foto 9", "lisans": stok.LISANS["unsplash"], "aciklama": "a misty lake"}), "utf-8")
        return calisma / d.kimlik / "kapak_stok.jpg"

    monkeypatch.setattr(stok, "getir", sahte_getir)
    yol = tmp_path / "yayin.toml"
    yol.write_text('[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "tunearo"\n[kapak]\nkaynak = "stok"\n'
                   "[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.0\nornekleme = 44100\n", encoding="utf-8")
    paket.paketle(c, yol)
    meta = json.loads((c / "s" / "paket" / "metadata.json").read_text(encoding="utf-8"))
    assert meta["kapak"]["kaynak"] == "stok" and meta["kapak"]["fotografci"] == "Foto 9"
    assert meta["kapak"]["lisans"].startswith("Unsplash License") and meta["kapak"]["sayfa"].endswith("/9")
    assert meta["kapak"]["islem"].startswith("ortadan kare kırpıldı (3200×4000")
    (o,) = olay.oku(c)
    assert o["tur"] == "kapak" and "--yeni" in o["metin"]


def test_kapak_ayari_stok_kabul_edilir(tmp_path):
    yol = tmp_path / "yayin.toml"
    yol.write_text('[yayin]\nsanatci_adi = ""\ndagitimci = ""\n[kapak]\nkaynak = "stok"\n'
                   "[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.0\nornekleme = 44100\n", encoding="utf-8")
    assert paket.yayin_ayarlari(yol).kapak == "stok"
