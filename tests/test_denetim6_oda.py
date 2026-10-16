"""Denetim 6: dinleme odası — bozuk önbellek/ayar dosyası odayı düşürmez, gövde sınırı akışta da tutulur."""

import asyncio
import dataclasses
import json

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from yanki import ayarlar, durum, elle, sunucu

ODA = "http://127.0.0.1:8765"


@pytest.fixture
def ortam(tmp_path):
    c = tmp_path / "calisma"
    k = c / "a-b"
    (k / "adaylar").mkdir(parents=True)
    sf.write(str(k / "adaylar" / "1.flac"), np.sin(np.linspace(0, 300, 48000)).astype("float32"), 48000)
    d = durum.Durum("a-b", "A", "B")
    d.adaylar = [durum.Aday(1, "adaylar/1.flac", 42, {"parmak_izi": {"gecti": True, "deger": 0.58}}, True)]
    d.gec("uretildi")
    durum.yaz(c, d)
    return TestClient(sunucu.uygulama(ayarlar.yukle(), c), base_url=ODA), c


def test_bozuk_dalga_onbellegi_yeniden_hesaplanir(ortam):
    # yarım yazılmış önbellek (oda yazarken kapandı) ses dosyası değişene kadar her açılışta 422 veriyordu
    istemci, c = ortam
    onbellek = c / "a-b" / "adaylar" / "1.flac.dalga.json"
    onbellek.write_text('{"sure": 1.0, "tep', encoding="utf-8")
    r = istemci.get("/api/dalga/a-b/adaylar/1.flac")
    assert r.status_code == 200 and r.json()["sure"] == 1.0
    assert json.loads(onbellek.read_text(encoding="utf-8"))["sure"] == 1.0
    assert not list(onbellek.parent.glob("*.yaziliyor"))


def test_bozuk_soz_zamani_sarkiyi_acmayi_engellemez(ortam):
    istemci, c = ortam
    (c / "a-b" / "soz_zaman.json").write_text("[[10.0, ", encoding="utf-8")
    r = istemci.get("/api/sarki/a-b")
    assert r.status_code == 200 and r.json()["kesitler"] == [] and r.json()["bolumler"] == []


@pytest.fixture
def bozuk_yayin(tmp_path):
    """Scryne config/yayin.toml'u elle düzenlerken bıraktığı yazım hatası."""
    kok = tmp_path / "kok"
    (kok / "config").mkdir(parents=True)
    a = ayarlar.yukle()
    for ad in ("motor.toml", "kesif.toml", "operasyon.toml", "egitim.toml"):
        (kok / "config" / ad).write_bytes((a.kok / "config" / ad).read_bytes())
    (kok / "config" / "yayin.toml").write_text("[otomatik_onay\nacik = true\n", encoding="utf-8")
    a = dataclasses.replace(a, kok=kok)
    c = tmp_path / "calisma"
    k = c / "a-b"
    (k / "adaylar").mkdir(parents=True)
    d = durum.Durum("a-b", "A", "B")
    d.gec("uretildi")
    durum.yaz(c, d)
    return TestClient(sunucu.uygulama(a, c), base_url=ODA)


def test_bozuk_yayin_ayari_sarki_sayfasini_dusurmez(bozuk_yayin):
    r = bozuk_yayin.get("/api/sarki/a-b")
    assert r.status_code == 200 and r.json()["otomatik_onay"] is None


def test_bozuk_yayin_ayari_panoda_uyari(bozuk_yayin):
    r = bozuk_yayin.get("/api/pano")
    assert r.status_code == 200
    assert any("yayin.toml" in u["metin"] for u in r.json()["uyarilar"])


def test_bozuk_ayar_dosyasi_okunur_hata_verir(bozuk_yayin):
    r = bozuk_yayin.get("/api/sanatci")
    assert r.status_code == 503 and "config/" in r.json()["detail"]


def test_boyutsuz_govde_akista_sinirlanir(ortam, monkeypatch):
    # Content-Length'siz (parçalı) gövde önce bütünüyle belleğe okunup sonra ölçülüyordu. TestClient gövdeyi kendisi
    # baştan okuduğu için ASGI düzeyinde: sınır aşılınca sunucu gövdenin kalanını istemez.
    istemci, c = ortam
    kimlik = elle.yeni(c, ayarlar.yukle().kok, "Deneme")["kimlik"]
    monkeypatch.setattr(elle, "EN_BUYUK_YUKLEME", 1000)
    app = istemci.app
    okunan, giden = [], []

    async def al():
        okunan.append(1)
        return {"type": "http.request", "body": b"x" * 100, "more_body": len(okunan) < 50}

    async def gonder(m):
        giden.append(m)

    kapsam = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1", "method": "POST", "scheme": "http",
              "path": f"/api/elle/{kimlik}/ses", "raw_path": f"/api/elle/{kimlik}/ses".encode(),
              "query_string": b"ad=a.wav", "root_path": "", "headers": [(b"host", b"127.0.0.1:8765")],
              "server": ("127.0.0.1", 8765), "client": ("127.0.0.1", 5000)}
    asyncio.run(app(kapsam, al, gonder))
    assert next(m for m in giden if m["type"] == "http.response.start")["status"] == 413
    assert len(okunan) < 50
