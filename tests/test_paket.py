import json

import numpy as np
import pytest
import soundfile as sf

from yanki import durum, paket, ses

try:
    ses.arac("ffmpeg")
    FFMPEG = True
except FileNotFoundError:
    FFMPEG = False

ffmpeg_gerekli = pytest.mark.skipif(not FFMPEG, reason="ffmpeg gerekli")


def _yayin(tmp_path, sanatci="", dagitimci=""):
    yol = tmp_path / "yayin.toml"
    yol.write_text(f'[yayin]\nsanatci_adi = "{sanatci}"\ndagitimci = "{dagitimci}"\netiket = ""\n'
                   "[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.0\nornekleme = 44100\n", encoding="utf-8")
    return yol


def _muzik(yol, sure=20, sr=48000, genlik=0.05):
    t = np.arange(int(sure * sr)) / sr
    x = genlik * (np.sin(2 * np.pi * 220 * t) + 0.5 * np.sin(2 * np.pi * 330 * t) * (1 + np.sin(2 * np.pi * 0.5 * t)))
    sf.write(str(yol), np.stack([x, x], 1).astype("float32"), sr)


def test_dagitimci_dogrulanir(tmp_path):
    with pytest.raises(ValueError, match="dagitimci"):
        paket.yayin_ayarlari(_yayin(tmp_path, dagitimci="spotify"))


@ffmpeg_gerekli
def test_master_hedefe_iner(tmp_path):
    _muzik(tmp_path / "g.wav")
    y = paket.yayin_ayarlari(_yayin(tmp_path))
    o = paket.master(tmp_path / "g.wav", tmp_path / "m.wav", y)
    assert o["lufs"] == pytest.approx(-14.0, abs=0.7)
    assert o["gercek_tepe_dbtp"] <= -0.9
    bilgi = sf.info(str(tmp_path / "m.wav"))
    assert (bilgi.samplerate, bilgi.channels, bilgi.subtype) == (44100, 2, "PCM_16")


def test_kapak_boyut_ve_bicim(tmp_path):
    from PIL import Image

    yol = paket.kapak("Someone Like You", list(np.random.default_rng(0).random(800)), tmp_path / "k.jpg")
    with Image.open(yol) as im:
        assert im.size == (3000, 3000) and im.format == "JPEG" and im.mode == "RGB"


def _durum():
    d = durum.Durum("adele-someone-like-you", "Adele", "Someone Like You",
                    kunye={"yazarlar": ["Adele", "Dan Wilson"], "isrc": ["X"]}, analiz={"dil": "en"})
    return d


def test_metadata_orijinal_sanatci_basliga_girmez(tmp_path):
    y = paket.yayin_ayarlari(_yayin(tmp_path, sanatci="Yeni Ses"))
    m = paket.metadata(_durum(), y, {"lufs": -14.0, "gercek_tepe_dbtp": -1.2}, 284.98)
    assert m["baslik"] == "Someone Like You" and "Adele" not in m["baslik"] and "cover" not in m["baslik"].lower()
    assert m["sanatci"] == "Yeni Ses" and m["orijinal_yazarlar"] == ["Adele", "Dan Wilson"]
    assert m["yapay_zeka"]["kullanildi"] is True


def test_yukle_md_eksikleri_yazar(tmp_path):
    y = paket.yayin_ayarlari(_yayin(tmp_path))
    m = paket.metadata(_durum(), y, {"lufs": -14.0, "gercek_tepe_dbtp": -1.2}, 284.98)
    md = paket.yukle_md(m, y, {"ses": "a.wav", "kapak": "a.jpg"})
    assert "Eksik karar" in md and "sanatci_adi" in md and "dagitimci" in md
    assert "`Adele, Dan Wilson`" in md and "4:45" in md
    tam = paket.yukle_md(m | {"sanatci": "Yeni Ses"}, paket.yayin_ayarlari(_yayin(tmp_path, "Yeni Ses", "routenote")),
                         {"ses": "a.wav", "kapak": "a.jpg"})
    assert "Eksik karar" not in tam


@ffmpeg_gerekli
def test_paketle_uctan_uca(tmp_path):
    c = tmp_path / "c"
    k = c / "adele-someone-like-you"
    (k / "adaylar" / "1").mkdir(parents=True)
    _muzik(k / "adaylar" / "1" / "tam.flac")
    d = _durum()
    d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, {}, True)]
    d.secilen = 1
    d.gec("onaylandi")
    durum.yaz(c, d)
    sonuc = paket.paketle(c, _yayin(tmp_path))
    assert [x.kimlik for x in sonuc] == ["adele-someone-like-you"]
    p = k / "paket"
    assert (p / "SANATCI_-_Someone_Like_You.wav").exists() and (p / "SANATCI_-_Someone_Like_You.jpg").exists()
    meta = json.loads((p / "metadata.json").read_text(encoding="utf-8"))
    assert meta["master"]["lufs"] == pytest.approx(-14.0, abs=0.7)
    assert durum.oku(c, "adele-someone-like-you").asama == "paketlendi"
    assert paket.paketle(c, _yayin(tmp_path)) == []  # zaten paketli
