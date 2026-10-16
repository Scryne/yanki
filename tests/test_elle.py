import io
import json
import shutil
import zipfile
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient
from PIL import Image

from yanki import ayarlar, elle, routenote, sanatci, sunucu

KOK = Path(__file__).resolve().parents[1]


@pytest.fixture
def kok(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(KOK / "config" / "yayin.toml", tmp_path / "config" / "yayin.toml")
    return tmp_path


def _wav(saniye: float = 2.0) -> bytes:
    t = np.linspace(0, saniye, int(48000 * saniye), endpoint=False)
    b = io.BytesIO()
    sf.write(b, np.stack([np.sin(2 * np.pi * 440 * t)] * 2, axis=1) * 0.3, 48000, format="WAV", subtype="PCM_24")
    return b.getvalue()


def _png(en: int, boy: int) -> bytes:
    b = io.BytesIO()
    Image.new("RGBA", (en, boy), (200, 30, 30, 255)).save(b, "PNG")
    return b.getvalue()


def _tam(c: Path, kok: Path) -> str:
    k = elle.yeni(c, kok, "Benim Şarkım")["kimlik"]
    elle.guncelle(c, k, {"yazar_adlari": [["Deniz", "Yazar"]], "spotify_sanatci_id": "4Z8W4fKeB5YxbusRsdQVPb"})
    elle.ses_kaydet(c, k, "demo.wav", _wav())
    elle.kapak_kaydet(c, k, "kapak.png", _png(2000, 1600))
    return k


def test_yeni_taslak_varsayilanlari_ve_dogrulama(tmp_path, kok):
    c = tmp_path / "calisma"
    m = elle.yeni(c, kok, "Benim Şarkım")
    assert m["sanatci"] == "Orvane" and m["dagiticilar"] == ["routenote"]
    assert m["kimlik"].startswith("orvane-benim-sarkim")
    assert elle.yeni(c, kok, "Benim Şarkım")["kimlik"] != m["kimlik"]  # aynı ad: ayrı taslak
    k = m["kimlik"]
    m = elle.guncelle(c, k, {"isrc": "tr-a1b-26-00001", "upc": "5 064149 827466",
                             "spotify_sanatci_id": "https://open.spotify.com/artist/4Z8W4fKeB5YxbusRsdQVPb?si=x"})
    assert (m["isrc"], m["upc"], m["spotify_sanatci_id"]) == ("TRA1B2600001", "5064149827466", "4Z8W4fKeB5YxbusRsdQVPb")
    for bozuk, ne in [({"isrc": "TR12"}, "ISRC"), ({"upc": "123"}, "UPC"), ({"dil": "Klingon"}, "dil"),
                      ({"tur": "Polka"}, "tür"), ({"gizli": 1}, "bilinmeyen"), ({"acik_icerik": "evet"}, "evet/hayır"),
                      ({"dagiticilar": ["distrokid"]}, "dağıtıcı"), ({"yazar_adlari": [["tek"]]}, "kişi"),
                      ({"yayin_tarihi": "yarın"}, "tarih")]:
        with pytest.raises(elle.Hata, match=ne):
            elle.guncelle(c, k, bozuk)
    with pytest.raises(elle.Hata):
        elle.oku(c, "../../etc")


def test_ses_ve_kapak_dagitici_bicimine_cevrilir(tmp_path, kok):
    c = tmp_path / "calisma"
    k = elle.yeni(c, kok, "X")["kimlik"]
    bilgi = elle.ses_kaydet(c, k, "demo.wav", _wav(2.0))
    yol = elle.klasor(c, k) / "ses.flac"
    i = sf.info(yol)
    assert (i.samplerate, i.channels, i.subtype) == (44100, 2, "PCM_16") and abs(bilgi["sure"] - 2.0) < 0.05
    assert not bilgi["kayipli"]
    with pytest.raises(elle.Hata, match="WAV"):
        elle.ses_kaydet(c, k, "demo.txt", b"x")
    with pytest.raises(elle.Hata, match="okunamadı"):
        elle.ses_kaydet(c, k, "bozuk.wav", b"RIFF0000WAVEnot really")
    b = elle.kapak_kaydet(c, k, "k.png", _png(2000, 1600))
    with Image.open(elle.klasor(c, k) / "kapak.jpg") as im:
        assert im.size == (3000, 3000) and im.mode == "RGB"
    assert b["kirpildi"] and b["buyutuldu"]
    with pytest.raises(elle.Hata, match="1400"):
        elle.kapak_kaydet(c, k, "k.png", _png(800, 800))


def test_kontrol_eksikleri_ve_hazir(tmp_path, kok):
    c = tmp_path / "calisma"
    k = elle.yeni(c, kok, "")["kimlik"]
    elle.guncelle(c, k, {"spotify_sanatci_id": ""})
    eksik = elle.kontrol(c, k)["eksik"]
    assert {"Şarkının adı", "Ses dosyası", "Kapak görseli", "En az bir besteci (ad + soyad)"} <= set(eksik)
    assert any("Spotify profil kimliği yok" in u for u in elle.kontrol(c, k)["uyari"])  # eksik değil, uyarı
    k = _tam(c, kok)
    assert elle.hazir_mi(c, k, "routenote") == []
    assert any("büyütüldü" in u for u in elle.kontrol(c, k)["uyari"])
    elle.guncelle(c, k, {"yayin_tarihi": (date.today() + timedelta(days=3)).isoformat()})
    assert "en erken" in elle.hazir_mi(c, k, "routenote")[0]
    elle.guncelle(c, k, {"yayin_tarihi": "", "cover": True, "yazar_adlari": [["Adele", ""]]})
    eksik = elle.hazir_mi(c, k, "routenote")
    assert any("orijinal sanatçı" in x for x in eksik) and any("soyadı" in x for x in eksik)
    assert elle.hazir_mi(c, k, "elle") == [*eksik, "bu dağıtıcı seçili değil"]  # genel eksikler her dağıtıcıda
    elle.guncelle(c, k, {"dagiticilar": ["elle"]})
    assert "bu dağıtıcı seçili değil" in elle.hazir_mi(c, k, "routenote")


def test_routenote_alanlari_secimlerden(tmp_path, kok):
    taban = {"yazar_adlari": [["A", "B"], ["", ""]], "soz_ayni": True, "tur": "Rock"}
    m = elle.routenote_meta({**taban, "cover": True, "mekanik_lisans": False, "yapay_zeka": True, "content_id": False})
    assert m["haric_bolgeler"] == list(routenote.HARIC_BOLGELER) and m["rn_tur"] == "Rock"
    assert set(m["kapali_magazalar"]) == {"Amazon", "Melon", "Bugs!", "FLO", "Genie Music", "YouTube Content ID"}
    assert m["yazar_adlari"] == [["A", "B"]] == m["soz_yazari_adlari"]
    m = elle.routenote_meta({**taban, "cover": False, "yapay_zeka": False, "content_id": True, "soz_ayni": False,
                             "sanatci": "Başka", "varsayilan_sanatci": "Orvane",
                             "soz_yazari_adlari": [["C", "D"]]})
    assert m["haric_bolgeler"] == [] and m["kapali_magazalar"] == [] and m["soz_yazari_adlari"] == [["C", "D"]]
    assert m["yeni_profil"] is True  # varsayılan sanatçı değil: kayıtlı (Orvane) profili bağlanmaz
    assert elle.routenote_meta({**taban, "sanatci": "Orvane", "varsayilan_sanatci": "Orvane"})["yeni_profil"] is False
    rm = {"sanatci": "Orvane", "baslik": "X", "dil": "Turkish", "acik_icerik": False, **m, "rn_tur": "Rock"}
    assert routenote.rn_dil(rm) == "Turkish" and routenote.rn_dil({"dil": "en"}) == "English"
    assert routenote.yazarlar(rm) == [("A", "B")] and routenote.soz_yazarlari(rm) == [("C", "D")]


def test_routenote_on_kontrolu_elle_paketi_gecer(tmp_path, kok):
    c = tmp_path / "calisma"
    k = _tam(c, kok)
    p = elle.routenote_hazirla(c, k)
    meta = elle.oku(c, k)
    routenote.on_kontrol(meta, p / "ses.flac", p / "kapak.jpg")
    with pytest.raises(ValueError, match="tür"):
        routenote.on_kontrol({**meta, "rn_tur": "Polka"}, p / "ses.flac", p / "kapak.jpg")


def test_gonderilen_taslak_kilitlenir_zip_ve_silme(tmp_path, kok):
    c = tmp_path / "calisma"
    k = _tam(c, kok)
    data, ad = elle.paket_zip(c, k)
    z = zipfile.ZipFile(io.BytesIO(data))
    assert ad == "Orvane - Benim Şarkım.zip"
    adlar = set(z.namelist())
    assert {"Orvane - Benim Şarkım/audio.flac", "Orvane - Benim Şarkım/artwork.jpg",
            "Orvane - Benim Şarkım/BILGILER.txt"} <= adlar
    metin = z.read("Orvane - Benim Şarkım/BILGILER.txt").decode()
    assert "Composers:" in metin and "Deniz Yazar" in metin and "as soon as approved" in metin
    meta = elle.oku(c, k)
    meta["routenote"] = {"upc": "5064150000000", "adim": "gonderiliyor"}
    elle._yaz(c, k, meta)
    with pytest.raises(elle.Hata, match="gönderildi"):
        elle.guncelle(c, k, {"baslik": "Y"})
    with pytest.raises(elle.Hata):
        elle.sil(c, k)
    assert "gönderildi" in elle.gonderim_sonucu(c, k, True)
    assert elle.hal(elle.oku(c, k)) == "gonderildi"
    with pytest.raises(elle.Hata):
        elle.sifirla(c, k)


@pytest.fixture
def oda(tmp_path, kok, monkeypatch):
    c = tmp_path / "calisma"
    baslayan = []
    monkeypatch.setattr(sanatci.Isci, "baslat", lambda self, ad, kimlik=None: baslayan.append((ad, kimlik)) or
                        {"ad": ad, "kimlik": kimlik})
    a = replace(ayarlar.yukle(), kok=kok)
    return TestClient(sunucu.uygulama(a, c), base_url="http://127.0.0.1:8765"), baslayan, c


def test_odadan_taslak_doldurulur_ve_gonderilir(oda, kok):
    istemci, baslayan, c = oda
    d = istemci.get("/api/elle").json()
    assert "Pop" in d["secenek"]["turler"] and "Turkish" in d["secenek"]["diller"] and d["liste"] == []
    m = istemci.post("/api/elle", json={"baslik": "Gece"}).json()
    k = m["kimlik"]
    assert m["hal"] == "taslak" and "Ses dosyası" in m["kontrol"]["eksik"]
    assert istemci.post(f"/api/elle/{k}", json={"isrc": "XX"}).status_code == 422
    m = istemci.post(f"/api/elle/{k}", json={"yazar_adlari": [["Deniz", "Yazar"]], "acik_icerik": True,
                                                  "yeni_profil": True}).json()
    assert m["acik_icerik"] is True
    r = istemci.post(f"/api/elle/{k}/ses?ad=demo.wav", content=_wav(),
                     headers={"Content-Type": "application/octet-stream"})
    assert r.status_code == 200 and r.json()["dosya"]["ses"]
    r = istemci.post(f"/api/elle/{k}/kapak?ad=k.png", content=_png(3000, 3000))
    assert r.status_code == 200 and r.json()["kontrol"]["eksik"] == []
    assert istemci.get(f"/elle/{k}/kapak?boyut=96").headers["content-type"] == "image/jpeg"
    assert istemci.get(f"/elle/{k}/ses").status_code == 200
    assert istemci.post(f"/api/elle/{k}/gonder", json={"gonder": True, "onay": "başka"}).status_code == 422
    assert istemci.post(f"/api/elle/{k}/gonder", json={"gonder": True, "onay": "gece"}).status_code == 200
    assert istemci.post(f"/api/elle/{k}/gonder", json={"gonder": False}).status_code == 200
    assert baslayan == [("elle_gonder", k), ("elle_taslak", k)]
    z = istemci.get(f"/elle/{k}/paket.zip")
    assert z.headers["content-type"] == "application/zip" and "attachment" in z.headers["content-disposition"]
    assert istemci.get("/api/elle").json()["liste"][0]["kimlik"] == k
    assert istemci.post(f"/api/elle/{k}/sil", json={}).status_code == 200
    assert istemci.get(f"/api/elle/{k}").status_code == 404
    assert json.loads(json.dumps(istemci.get("/api/elle").json()))["liste"] == []
