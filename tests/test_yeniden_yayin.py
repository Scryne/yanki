"""Kendi kalkmış yayını → FreshTunes taslağı (Bulucu'dan): yalnız kayıtlı kendi sanatçı adlarına; künye parçanın
ayrıntısından, ses YouTube'da aynı süreli kayıttan (önce "- Topic"), kapak iTunes'tan 3000×3000."""

import io
import shutil
from dataclasses import replace
from datetime import date, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from yanki import ayarlar, bulucu, elle, kaynak, sanatci, sunucu, yeniden_yayin

KOK = Path(__file__).resolve().parents[1]
PID = "5l6tv2lFylSdCgkWyfHC0P"


@pytest.fixture
def kok(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(KOK / "config" / "yayin.toml", tmp_path / "config" / "yayin.toml")
    return tmp_path


def _parca(**ek) -> dict:
    """Bulucu'nun `parca` sonucu (calisma/bulucu/parca-*.json biçimi)."""
    return {"tur": "parca", "id": PID, "ad": "Gece Yürüyüşü", "sanatci": "Scryne, Konuk",
            "sanatcilar": [{"id": "4Z8W4fKeB5YxbusRsdQVPb", "name": "Scryne"}, {"id": "7AcV1lk8Zrgo1691PDWEle",
                                                                                 "name": "Konuk"}],
            "resim": "https://i.scdn.co/image/x", "isrc": "TRA1B2600001", "upc": "8680000000017",
            "label": "Kendi Plak", "cikis": "2024-03-15", "ilk_yayin": None, "acik_icerik": True,
            "sure_ms": 201500, "diller": ["tr"], "yazarlar": ["Ad Soyad", "Not Documented"],
            "yapimcilar": ["Not Documented", "Yapımcı Kişi"], "telif_p": "(P) 2024 Kendi Plak",
            "telif_c": "© 2024 Ad Soyad", "distributor": "DistroKid", **ek}


def test_kendi_sanatci_eslesmesi():
    adlar = yeniden_yayin.sanatci_adlari("Scryne, Konuk")
    assert adlar == ["Scryne", "Konuk"]
    assert yeniden_yayin.kendi_sanatci(adlar, ["scryne"]) == "scryne"  # kayıtlı yazılışı döner
    assert yeniden_yayin.kendi_sanatci(["IŞIK"], ["ışık"]) == "ışık"
    assert yeniden_yayin.kendi_sanatci(["Başkası"], ["Scryne"]) is None
    assert yeniden_yayin.sanatci_adlari(None, [{"id": "x", "name": "A"}, {"name": ""}]) == ["A"]


def test_taslak_parcanin_kunyesiyle_dolar(tmp_path, kok):
    c = tmp_path / "calisma"
    m = yeniden_yayin.taslak_kur(c, kok, _parca(), ["Scryne"])
    assert (m["baslik"], m["sanatci"], m["dagiticilar"], m["yapay_zeka"]) == \
        ("Gece Yürüyüşü", "Scryne", ["freshtunes"], False)
    assert (m["isrc"], m["upc"], m["orijinal_tarih"]) == ("TRA1B2600001", "8680000000017", "2024-03-15")
    assert m["spotify_sanatci_id"] == "4Z8W4fKeB5YxbusRsdQVPb"  # kendi profilin, konuğunki değil
    assert m["yazar_adlari"] == [["Ad", "Soyad"]] and m["uretici"] == "Yapımcı Kişi"  # "Not Documented" atlanır
    assert (m["p_yil"], m["p_sahibi"], m["c_yil"], m["c_sahibi"]) == (2024, "Kendi Plak", 2024, "Ad Soyad")
    assert m["dil"] == "Turkish" and m["acik_icerik"] is True and m["etiket"] == "Kendi Plak"
    assert m["yayin_tarihi"] == (date.today() + timedelta(days=elle.FRESHTUNES_YAYIN_ONERI_GUN)).isoformat()
    assert m["kaynak_parca"]["sure_sn"] == 201.5 and m["kaynak_parca"]["spotify_id"] == PID
    assert "spotify:track:" in m["notlar"]


def test_yalniz_kendi_katalogun(tmp_path, kok):
    c = tmp_path / "calisma"
    with pytest.raises(yeniden_yayin.Hata, match="önce kendi sanatçı adını"):
        yeniden_yayin.taslak_kur(c, kok, _parca(), [])
    with pytest.raises(yeniden_yayin.Hata, match="kendi sanatçı adların arasında değil"):
        yeniden_yayin.taslak_kur(c, kok, _parca(sanatci="Başkası", sanatcilar=[{"id": "x", "name": "Başkası"}]),
                                 ["Scryne"])
    with pytest.raises(yeniden_yayin.Hata, match="süresi"):
        yeniden_yayin.taslak_kur(c, kok, _parca(sure_ms=None), ["Scryne"])
    with pytest.raises(elle.Hata, match="AI cover"):
        elle.kendi_sanatcilar_yaz(c, ["Scryne", "orvane"], kok)
    assert elle.kendi_sanatcilar_yaz(c, [" Scryne ", "Scryne", ""], kok) == ["Scryne"]
    elle.freshtunes_girdim(c)  # giriş kaydı sanatçı adlarını silmez
    assert elle.kendi_sanatcilar(c) == ["Scryne"]


def test_telif_satiri_yoksa_yil_ilk_cikis_yili(tmp_path, kok):
    m = yeniden_yayin.taslak_kur(tmp_path / "calisma", kok, _parca(telif_c=None, telif_p=None, cikis="2021-06-01"),
                                 ["Scryne"])
    assert (m["c_yil"], m["p_yil"]) == (2021, 2021)


def test_bicimi_tutmayan_alan_taslagi_dusurmez(tmp_path, kok):
    m = yeniden_yayin.taslak_kur(tmp_path / "calisma", kok, _parca(isrc="BOZUK", upc="12"), ["Scryne"])
    assert m["isrc"] == "" and m["upc"] == "" and m["sanatci"] == "Scryne"


def test_ses_secimi_ayni_saniye_ve_topic():
    A = kaynak.Aday
    adaylar = [A("a", "Scryne - Gece Yürüyüşü (Official Video)", 209.0, "Scryne"),  # klip: 7 sn uzun
               A("b", "Gece Yürüyüşü (Live)", 201.5, "Scryne"),  # canlı: istenmeyen
               A("c", "Gece Yürüyüşü", 202.8, "Hayran Kanal"),
               A("d", "Gece Yürüyüşü", 203.0, "Scryne - Topic")]
    assert yeniden_yayin.ses_sec(adaylar, "Scryne", 201.5).id == "d"  # Topic, tolerans içinde
    assert yeniden_yayin.ses_sec(adaylar[:3], "Scryne", 201.5).id == "c"
    assert yeniden_yayin.ses_sec(adaylar[:2], "Scryne", 201.5) is None
    # canlı deneme (Mt. Eden, 292,9 sn): hayran yüklemesi en yakın süreydi, sanatçının kanalı ve "Orchestral" elenmeli
    mt = [A("e", "MT Eden - Sierra Leone (feat. Freshly Ground)", 293.0, "evanzo7music"),
          A("f", "Mt Eden - Sierra Leone feat. Freshly Ground", 294.0, "Mt Eden Official"),
          A("g", "Mt. Eden - Sierra Leone feat. Freshly Ground (Orchestral Version)", 292.0, "Mt Eden Official")]
    assert yeniden_yayin.ses_sec(mt, "Mt. Eden", 292.907, "Sierra Leone (feat. Freshly Ground)").id == "f"
    assert yeniden_yayin.ses_sec(mt[2:], "Mt. Eden", 292.907, "Sierra Leone (Orchestral Version)").id == "g"


def test_ses_ve_kapak_doldurulur(tmp_path, kok, monkeypatch):
    c = tmp_path / "calisma"
    k = yeniden_yayin.taslak_kur(c, kok, _parca(), ["Scryne"])["kimlik"]
    kaydedilen = {}

    def ses_kaydet(calisma, kimlik, ad, veri):  # ffmpeg'siz: dönüşüm ayrıca sınanıyor (test_elle)
        kaydedilen["veri"] = veri
        (elle.klasor(calisma, kimlik) / "ses.flac").write_bytes(b"flac")
        return {"ad": ad, "sure": 202.0, "kayipli": True}

    monkeypatch.setattr(elle, "ses_kaydet", ses_kaydet)
    sorgular = []

    def adaylar(sorgu):
        sorgular.append(sorgu)
        return [kaynak.Aday("d", "Gece Yürüyüşü", 202.0, "Scryne - Topic")]

    def indir(vid, hedef):
        hedef.write_bytes(b"opus" + vid.encode())
        return hedef

    satir = yeniden_yayin.ses_indir(c, k, adaylar=adaylar, indir=indir)
    assert "Scryne - Topic" in satir and "+0.5 sn" in satir and kaydedilen["veri"] == b"opusd"
    assert sorgular == ["Scryne Gece Yürüyüşü"] and not list(elle.klasor(c, k).glob(".youtube*"))
    assert elle.oku(c, k)["ses"]["youtube"] == "d"

    b = io.BytesIO()
    Image.new("RGB", (3000, 3000), (10, 20, 30)).save(b, "JPEG")
    istenen = []
    url = "https://is1-ssl.mzstatic.com/image/thumb/Music/x/3000x3000bb.jpg"
    yeniden_yayin.kapak_indir(c, k, bul=lambda *a: url, al=lambda u: istenen.append(u) or b.getvalue())
    assert istenen == [url] and (elle.klasor(c, k) / "kapak.jpg").exists()


def test_bulunamayan_ses_aciklanir_kapak_yine_denenir(tmp_path, kok):
    c = tmp_path / "calisma"
    k = yeniden_yayin.taslak_kur(c, kok, _parca(), ["Scryne"])["kimlik"]
    with pytest.raises(yeniden_yayin.Hata, match="3:21 süreli kayıt bulunamadı"):
        yeniden_yayin.ses_indir(c, k, adaylar=lambda s: [kaynak.Aday("a", "Gece Yürüyüşü", 240.0, "X")])
    sonuc = yeniden_yayin.kaynak_doldur(c, k, ses=lambda *a: (_ for _ in ()).throw(yeniden_yayin.Hata("yok")),
                                        kapak=lambda *a: "kapak: iTunes")
    assert sonuc == ["kapak: iTunes", "✗ ses: yok"]
    with pytest.raises(yeniden_yayin.Hata):
        yeniden_yayin.kaynak_doldur(c, k, ses=lambda *a: (_ for _ in ()).throw(OSError("ağ")),
                                    kapak=lambda *a: (_ for _ in ()).throw(yeniden_yayin.Hata("kapak yok")))


def test_itunes_kapagi_ayni_parca_ve_sureyle():
    sonuclar = {"results": [
        {"artistName": "Scryne", "trackName": "Gece Yürüyüşü", "trackTimeMillis": 240000,
         "artworkUrl100": "https://a/100x100bb.jpg"},  # başka sürüm (süre)
        {"artistName": "Scryne & Konuk", "trackName": "Gece Yürüyüşü (feat. Konuk)", "trackTimeMillis": 202000,
         "artworkUrl100": "https://a/b/100x100bb.jpg"}]}
    assert yeniden_yayin.kapak_bul("Scryne", "Gece Yürüyüşü", 201.5, ara=lambda p: sonuclar) == \
        "https://a/b/3000x3000bb.jpg"
    assert yeniden_yayin.kapak_bul("Başkası", "Gece Yürüyüşü", 201.5, ara=lambda p: sonuclar) is None


def test_oda_bulucudan_taslak_acar(tmp_path, kok, monkeypatch):
    c = tmp_path / "calisma"
    baslayan = []
    monkeypatch.setattr(sanatci.Isci, "baslat", lambda self, ad, kimlik=None: baslayan.append((ad, kimlik)) or
                        {"ad": ad, "kimlik": kimlik})
    oda = TestClient(sunucu.uygulama(replace(ayarlar.yukle(), kok=kok), c), base_url="http://127.0.0.1:8765")
    assert oda.post("/api/bulucu/freshtunes", json={"parca": PID}).status_code == 409  # ayrıntı yok
    bulucu.sonuc_yaz(c, _parca())
    bulucu.sonuc_yaz(c, {"tur": "playlist", "id": "1pXViTb7efviU11zRaVM2y", "ad": "Kalkanlarım", "toplam": 2,
                         "satirlar": [{"id": PID, "ad": "Gece Yürüyüşü", "sanatci": "Scryne", "kopyalar": []},
                                      {"id": "x" * 22, "ad": "Başka", "sanatci": "Başkası", "kopyalar": []}]})
    assert oda.post("/api/bulucu/freshtunes", json={"parca": PID}).status_code == 422  # kendi ad kayıtlı değil
    v = oda.get("/api/bulucu/sonuc/playlist-1pXViTb7efviU11zRaVM2y").json()
    assert v["kendi_ayarli"] is False and [s["kendi"] for s in v["satirlar"]] == [False, False]
    assert oda.post("/api/elle-freshtunes/sanatcilar", json={"adlar": ["Orvane"]}).status_code == 422
    assert oda.post("/api/elle-freshtunes/sanatcilar", json={"adlar": ["Scryne"]}).json()["sanatcilar"] == ["Scryne"]
    v = oda.get("/api/bulucu/sonuc/playlist-1pXViTb7efviU11zRaVM2y").json()
    assert [s["kendi"] for s in v["satirlar"]] == [True, False]
    r = oda.post("/api/bulucu/freshtunes", json={"parca": PID}).json()
    assert r["uyari"] is None and baslayan == [("elle_kaynak", r["kimlik"])]
    m = oda.get(f"/api/elle/{r['kimlik']}").json()
    assert m["isrc"] == "TRA1B2600001" and m["kaynak_parca"]["sure_sn"] == 201.5
    assert oda.get("/api/elle").json()["kendi_sanatcilar"] == ["Scryne"]
    assert oda.post(f"/api/elle/{r['kimlik']}/kaynak", json={}).status_code == 200
    assert oda.post("/api/bulucu/freshtunes", json={"parca": "../x"}).status_code == 422


try:  # kazanç düşürme ffmpeg ister (CI makinesinde yok)
    from yanki import ses as _ses

    _ses.arac("ffmpeg")
    FFMPEG = True
except FileNotFoundError:
    FFMPEG = False


@pytest.mark.skipif(not FFMPEG, reason="ffmpeg gerekli")
def test_youtube_sesinde_kirpilma_bir_db_dusurulur(tmp_path):
    """Canlı deneme: YouTube'dan çözülen ses 0 dBFS'e dayanıyordu (FreshTunes kırpılmış sesi reddediyor)."""
    import numpy as np
    import soundfile as sf

    yol = tmp_path / "ses.flac"
    t = np.arange(44100 * 2) / 44100
    sinyal = np.clip(np.sin(2 * np.pi * 220 * t) * 1.4, -1, 1)
    sf.write(str(yol), np.stack([sinyal, sinyal], 1), 44100, subtype="PCM_16")
    assert elle.ses_olcumu(yol)["kirpik"] > yeniden_yayin.KIRPIK_ESIGI
    o = yeniden_yayin._tepe_indir(yol)
    assert o["kirpik"] == 0 and -1.2 < o["tepe_db"] < -0.8 and o["kazanc_db"] == -1.0
