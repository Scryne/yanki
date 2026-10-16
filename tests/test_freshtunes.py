"""FreshTunes: Scryne'ın kendi şarkıları için ikinci dağıtıcı (2026-10-16: "normal şarkıları da paylaşabileceğim bir
dağıtıcı, para vermeden"). Şartları botu ve yapay zekâ kaydını yasaklıyor: hat paketi hazırlar, gönderim elle."""

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

from yanki import ayarlar, elle, olay, sunucu

KOK = Path(__file__).resolve().parents[1]


@pytest.fixture
def kok(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(KOK / "config" / "yayin.toml", tmp_path / "config" / "yayin.toml")
    return tmp_path


def _ses(yol: Path, bas_sn=0.5, ton_sn=3.0, son_sn=0.5, genlik=0.3, sr=44100) -> None:
    t = np.arange(int(ton_sn * sr)) / sr
    ton = np.sin(2 * np.pi * 440 * t) * genlik
    mono = np.concatenate([np.zeros(int(bas_sn * sr)), ton, np.zeros(int(son_sn * sr))])
    sf.write(str(yol), np.stack([mono, mono], axis=1), sr, format="FLAC", subtype="PCM_16")


def _hazir(c: Path, kok: Path, **alanlar) -> str:
    """Ses ve kapak ffmpeg'siz yazılır (dosyalar zaten hattın biçiminde): kontrol ve paket ffmpeg istemez."""
    k = elle.yeni(c, kok, "Kendi Şarkım", sablon="freshtunes")["kimlik"]
    elle.guncelle(c, k, {"sanatci": "Scryne", "yazar_adlari": [["Ad", "Soyad"]], **alanlar})
    kl = elle.klasor(c, k)
    _ses(kl / "ses.flac")
    Image.new("RGB", (3000, 3000), (20, 40, 60)).save(kl / "kapak.jpg", "JPEG")
    meta = elle.oku(c, k)
    meta["ses"] = {"sure": 4.0, "flac_boyut": (kl / "ses.flac").stat().st_size, **elle.ses_olcumu(kl / "ses.flac")}
    elle._yaz(c, k, meta)
    return k


def test_kendi_sarkim_taslagi_orvane_degil_yapay_zekasiz(tmp_path, kok):
    c = tmp_path / "calisma"
    m = elle.yeni(c, kok, "İlk", sablon="freshtunes")
    assert m["dagiticilar"] == ["freshtunes"] and m["yapay_zeka"] is False and m["cover"] is False
    assert m["sanatci"] == "" and m["varsayilan_sanatci"] == "Orvane"
    assert m["yayin_tarihi"] == (date.today() + timedelta(days=elle.FRESHTUNES_YAYIN_ONERI_GUN)).isoformat()
    # sonraki taslak sanatçıyı, profili ve yazarları son FreshTunes taslağından alır (ücretsiz planda tek sanatçı)
    elle.guncelle(c, m["kimlik"], {"sanatci": "Scryne", "spotify_sanatci_id": "4Z8W4fKeB5YxbusRsdQVPb",
                                   "yazar_adlari": [["Ad", "Soyad"]]})
    ikinci = elle.yeni(c, kok, "İkinci", sablon="freshtunes")
    assert (ikinci["sanatci"], ikinci["spotify_sanatci_id"], ikinci["yazar_adlari"]) == \
        ("Scryne", "4Z8W4fKeB5YxbusRsdQVPb", [["Ad", "Soyad"]])
    assert elle.yeni(c, kok, "Cover")["sanatci"] == "Orvane"  # şablonsuz taslak değişmedi
    with pytest.raises(elle.Hata):
        elle.yeni(c, kok, "x", sablon="distrokid")


def test_freshtunes_denetimi(tmp_path, kok):
    c = tmp_path / "calisma"
    k = _hazir(c, kok)
    assert elle.hazir_mi(c, k, "freshtunes") == []
    elle.guncelle(c, k, {"yapay_zeka": True})
    assert any("yapay zekâ" in x for x in elle.hazir_mi(c, k, "freshtunes"))
    elle.guncelle(c, k, {"yapay_zeka": False, "sanatci": "Orvane"})
    assert any("AI cover sanatçısı" in x for x in elle.hazir_mi(c, k, "freshtunes"))
    elle.guncelle(c, k, {"sanatci": "Scryne", "yayin_tarihi": (date.today() + timedelta(days=3)).isoformat()})
    assert any("en erken" in x for x in elle.hazir_mi(c, k, "freshtunes"))
    elle.guncelle(c, k, {"yayin_tarihi": ""})  # "onaylanınca" FreshTunes'ta yok
    assert any("en erken" in x for x in elle.hazir_mi(c, k, "freshtunes"))
    elle.guncelle(c, k, {"yayin_tarihi": (date.today() + timedelta(days=7)).isoformat(),
                         "dagiticilar": ["freshtunes", "routenote"]})
    assert any("iki dağıtıcıya" in x for x in elle.kontrol(c, k)["eksik"])
    elle.guncelle(c, k, {"dagiticilar": ["freshtunes", "elle"]})  # elle ZIP'le birlikte serbest
    assert elle.hazir_mi(c, k, "freshtunes") == []


def test_ses_olcumu_sessizlik_ve_kirpilma(tmp_path, kok):
    yol = tmp_path / "a.flac"
    _ses(yol, bas_sn=6.2, son_sn=1.0)
    o = elle.ses_olcumu(yol)
    assert abs(o["bas_sessizlik"] - 6.2) < 0.1 and abs(o["son_sessizlik"] - 1.0) < 0.1
    assert -11 < o["tepe_db"] < -10 and o["kirpik"] == 0
    _ses(yol, genlik=1.5)  # sinüs ±1'in üstünde: tam ölçekte kırpılır
    assert elle.ses_olcumu(yol)["kirpik"] > 0.1
    # uzun sessizlik FreshTunes'ta eksik, kırpılma uyarı
    c = tmp_path / "calisma"
    k = _hazir(c, kok)
    kl = elle.klasor(c, k)
    _ses(kl / "ses.flac", bas_sn=6.0, genlik=1.5)
    meta = elle.oku(c, k)
    meta["ses"].update(elle.ses_olcumu(kl / "ses.flac"))
    elle._yaz(c, k, meta)
    assert any("Başta 6.0 sn sessizlik" in x for x in elle.hazir_mi(c, k, "freshtunes"))
    assert any("0 dBFS" in x for x in elle.kontrol(c, k)["uyari"])


def test_freshtunes_paketi_ve_gonderim_kaydi(tmp_path, kok):
    c = tmp_path / "calisma"
    k = _hazir(c, kok, uretici="Scryne", content_id=True)
    veri, ad = elle.paket_zip(c, k, "freshtunes")
    assert ad == "Scryne - Kendi Şarkım (FreshTunes).zip"
    with zipfile.ZipFile(io.BytesIO(veri)) as z:
        adlar = set(z.namelist())
        metin = z.read("Scryne - Kendi Şarkım/FRESHTUNES.txt").decode("utf-8")
    assert {"Scryne - Kendi Şarkım/audio.flac", "Scryne - Kendi Şarkım/artwork.jpg"} <= adlar
    assert "Release title:" in metin and "Kendi Şarkım" in metin and "First name: Ad   Last name: Soyad" in metin
    assert "FreshTunes ücretsiz atar" in metin and "Payoneer" in metin and "FreshTunes %20" in metin
    assert "AI-generated" not in metin
    # eksik varken paket inmez
    elle.guncelle(c, k, {"yapay_zeka": True})
    with pytest.raises(elle.Hata, match="yapay zekâ"):
        elle.paket_zip(c, k, "freshtunes")
    with pytest.raises(elle.Hata, match="eksik"):
        elle.freshtunes_gonderildi(c, k)
    elle.guncelle(c, k, {"yapay_zeka": False})
    assert "kaydedildi" in elle.freshtunes_gonderildi(c, k)
    m = elle.oku(c, k)
    assert elle.hal(m) == "gonderildi" and "FreshTunes" in elle.kilitli(m)
    with pytest.raises(elle.Hata):  # gönderilmiş kayıt değişmez, silinmez
        elle.guncelle(c, k, {"baslik": "Başka"})
    with pytest.raises(elle.Hata):
        elle.sil(c, k)
    assert "sıfırlandı" in elle.sifirla(c, k, "freshtunes")
    m = elle.oku(c, k)
    assert elle.kilitli(m) is None and m["freshtunes_gecmisi"][0]["adim"] == "gonderildi"


def test_freshtunes_giris_hatirlatmasi(tmp_path, kok):
    """ToS §4: 3 ayda bir giriş yoksa askı, açmak 50 $. Hatırlatma 75. günden itibaren haftada bir."""
    c = tmp_path / "calisma"
    assert elle.freshtunes_durumu(c) is None  # hiç gönderilmemiş: hatırlatma yok
    k = _hazir(c, kok)
    elle.freshtunes_gonderildi(c, k)
    gonderim = date.today()
    olaylar = lambda: [o["baslik"] for o in olay.oku(c)]  # noqa: E731

    def bildir(*a):
        olay.bildir(c, *a)

    elle.freshtunes_hatirlatma(c, bildir, gonderim + timedelta(days=74))
    assert olaylar() == []
    for gun in (75, 76, 81, 82):  # aynı hafta bir kez, yeni hafta yeniden
        elle.freshtunes_hatirlatma(c, bildir, gonderim + timedelta(days=gun))
    assert olaylar() == ["FreshTunes'a giriş yap"] * 2
    d = elle.freshtunes_durumu(c, gonderim + timedelta(days=95))
    assert d["kalan"] == -5 and d["hatirlat"]
    elle.freshtunes_girdim(c, gonderim + timedelta(days=95))
    assert elle.freshtunes_durumu(c, gonderim + timedelta(days=100))["gun"] == 5


def test_odadan_freshtunes_akisi(tmp_path, kok):
    c = tmp_path / "calisma"
    oda = TestClient(sunucu.uygulama(replace(ayarlar.yukle(), kok=kok), c), base_url="http://127.0.0.1:8765")
    m = oda.post("/api/elle", json={"baslik": "Oda", "sablon": "freshtunes"}).json()
    assert m["dagiticilar"] == ["freshtunes"] and "freshtunes" in m["kontrol"]["dagitici"]
    assert oda.post("/api/elle", json={"sablon": "baska"}).status_code == 422
    k = _hazir(c, kok)
    d = oda.get("/api/elle").json()
    assert d["secenek"]["dagiticilar"]["freshtunes"]["otomatik"] is False and d["freshtunes"] is None
    r = oda.get(f"/elle/{k}/paket.zip?dagitici=freshtunes")
    assert r.status_code == 200 and "FreshTunes" in r.headers["content-disposition"]
    assert oda.get(f"/elle/{k}/paket.zip?dagitici=routenote").status_code == 422
    assert oda.post(f"/api/elle/{k}/freshtunes-gonderildi", json={}).status_code == 200
    assert oda.post(f"/api/elle/{k}/freshtunes-gonderildi", json={}).status_code == 409  # iki kez değil
    assert oda.get("/api/elle").json()["freshtunes"]["gun"] == 0
    r = oda.post("/api/elle-freshtunes/girdim", json={})
    assert r.status_code == 200 and r.json()["freshtunes"]["kalan"] == elle.FRESHTUNES_GIRIS_GUN
    assert oda.post(f"/api/elle/{k}/sifirla?dagitici=freshtunes", json={}).status_code == 200
    assert json.loads((elle.klasor(c, k) / "metadata.json").read_text(encoding="utf-8")).get("freshtunes") is None


def test_bos_taslaklar_temizlenir(tmp_path, kok):
    c = tmp_path / "calisma"
    bos = [elle.yeni(c, kok)["kimlik"] for _ in range(3)]
    adli = elle.yeni(c, kok, "Adı Var")["kimlik"]
    kapakli = elle.yeni(c, kok)["kimlik"]
    Image.new("RGB", (1500, 1500)).save(elle.klasor(c, kapakli) / "kapak.jpg", "JPEG")
    assert elle.bos_taslaklar(c) == sorted(bos)
    oda = TestClient(sunucu.uygulama(replace(ayarlar.yukle(), kok=kok), c), base_url="http://127.0.0.1:8765")
    assert oda.get("/api/elle").json()["bos"] == 3
    assert oda.post("/api/elle-bos-temizle", json={}).json()["silinen"] == 3
    assert {x["kimlik"] for x in elle.liste(c)} == {adli, kapakli}

