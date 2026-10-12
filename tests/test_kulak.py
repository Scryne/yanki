import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from yanki import ayarlar, kulak, sunucu

ODA = "http://127.0.0.1:8765"


@pytest.fixture
def ortam(tmp_path, monkeypatch):
    c = tmp_path / "calisma"
    s = kulak.Set("deneme", "Deneme", "açıklama", "dinleme/x", {"eski": "eski model", "yeni": "yeni model"})
    monkeypatch.setattr(kulak, "SETLER", (s,))
    ses = np.zeros(4800, dtype="float32")
    for sarki in ("a-b", "c-d"):
        for kol in ("eski", "yeni"):
            (c / "dinleme" / "x" / sarki).mkdir(parents=True, exist_ok=True)
            sf.write(str(c / "dinleme" / "x" / sarki / f"{kol}.flac"), ses, 48000)
    (c / "_referans" / "a-b").mkdir(parents=True)
    sf.write(str(c / "_referans" / "a-b" / "kaynak.wav"), ses, 48000)
    (tmp_path / "gizli.txt").write_text("sır", encoding="utf-8")
    return TestClient(sunucu.uygulama(ayarlar.yukle(), c), base_url=ODA), c


def test_kor_sira_oy_verilince_acilir(ortam):
    istemci, c = ortam
    g = istemci.get("/api/kulak").json()[0]
    x = next(s for s in g["sarkilar"] if s["kimlik"] == "a-b")
    assert [k["harf"] for k in x["kollar"]] == ["A", "B"] and all(k["ad"] is None for k in x["kollar"])
    assert x["orijinal"] and not next(s for s in g["sarkilar"] if s["kimlik"] == "c-d")["orijinal"]
    # aynı şarkıda sıra kararlı (sayfa yenilenince A yine A)
    assert kulak.sira("deneme", "a-b", ["eski", "yeni"]) == kulak.sira("deneme", "a-b", ["yeni", "eski"])
    # yalnız not yazmak körlüğü bozmaz
    g = istemci.post("/api/kulak/deneme/a-b", json={"not": "vokal metalik"}).json()[0]
    assert all(k["ad"] is None for k in next(s for s in g["sarkilar"] if s["kimlik"] == "a-b")["kollar"])
    g = istemci.post("/api/kulak/deneme/a-b", json={"en_iyi": "yeni"}).json()[0]
    x = next(s for s in g["sarkilar"] if s["kimlik"] == "a-b")
    assert {k["ad"] for k in x["kollar"]} == {"eski model", "yeni model"} and x["oy"]["not"] == "vokal metalik"
    istemci.post("/api/kulak/deneme/a-b", json={"yayinlanir": True})
    o = istemci.get("/api/kulak").json()[0]["ozet"]
    assert o["oylanan"] == 1 and o["sayim"]["yeni"] == 1 and o["yayinlanir"] == 1
    # "hepsi kötü" yayınlanabilir cevabını siler
    o = istemci.post("/api/kulak/deneme/a-b", json={"en_iyi": "hepsi_kotu"}).json()[0]["ozet"]
    assert o["sayim"]["hepsi_kotu"] == 1 and o["yayinlanir"] == 0


def test_gecersiz_oy_ve_ses_yolu(ortam):
    istemci, _ = ortam
    assert istemci.post("/api/kulak/deneme/a-b", json={"en_iyi": "baska"}).status_code == 422
    assert istemci.post("/api/kulak/deneme/yok", json={"en_iyi": "yeni"}).status_code == 404
    assert istemci.post("/api/kulak/yok/a-b", json={"en_iyi": "yeni"}).status_code == 404
    assert istemci.get("/kulak-ses/deneme/a-b/yeni").status_code == 200
    assert istemci.get("/kulak-ses/deneme/a-b/orijinal").status_code == 200
    for yol in ("/kulak-ses/deneme/a-b/..%2F..%2F..%2Fgizli.txt", "/kulak-ses/deneme/..%2F..%2Fx/yeni",
                "/kulak-ses/deneme/c-d/orijinal", "/kulak-ses/yok/a-b/yeni"):
        assert istemci.get(yol).status_code == 404, yol
