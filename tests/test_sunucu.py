import json

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from yanki import ayarlar, durum, sunucu


@pytest.fixture
def ortam(tmp_path):
    c = tmp_path / "calisma"
    k = c / "a-b"
    (k / "adaylar").mkdir(parents=True)
    sf.write(str(k / "kaynak.wav"), np.sin(np.linspace(0, 400, 48000)).astype("float32"), 48000)
    sf.write(str(k / "adaylar" / "1.flac"), np.sin(np.linspace(0, 300, 48000)).astype("float32"), 48000)
    d = durum.Durum("a-b", "A", "B", kaynak={"dosya": "kaynak.wav"})
    d.adaylar = [durum.Aday(1, "adaylar/1.flac", 42, {"parmak_izi": {"gecti": True, "deger": 0.58}}, True),
                 durum.Aday(2, "", 7, {"motor": {"gecti": False}}, False)]
    d.gec("uretildi")
    durum.yaz(c, d)
    (tmp_path / "gizli.txt").write_text("sır", encoding="utf-8")
    return TestClient(sunucu.uygulama(ayarlar.yukle(), c)), c


def test_liste_ve_ayrinti(ortam):
    istemci, _ = ortam
    assert istemci.get("/api/sarkilar").json()[0] == {"kimlik": "a-b", "sanatci": "A", "ad": "B", "asama": "uretildi",
                                                       "hata": None, "gecen_aday": 1, "bekleyen_onarim": 0}
    assert istemci.get("/api/sarki/a-b").json()["adaylar"][0]["tohum"] == 42
    assert istemci.get("/api/sarki/a-b").json()["kesitler"] == []  # söz zamanı yoksa kesit yok


def test_sarki_kesitleri_soz_zamanindan(ortam):
    istemci, c = ortam
    satirlar = [[10.0, "a"], [40.0, "n"], [45.0, "b"], [80.0, "n"], [120.0, "n"]]
    (c / "a-b" / "soz_zaman.json").write_text(json.dumps(satirlar), encoding="utf-8")
    k = istemci.get("/api/sarki/a-b").json()["kesitler"]
    assert [x["kimlik"] for x in k] == ["ilk_kita", "nakarat", "son_nakarat"] and k[1]["bas"] == 39.0
    assert istemci.get("/api/sarki/yok").status_code == 404


def test_ses_ve_dalga(ortam):
    istemci, c = ortam
    assert istemci.get("/ses/a-b/adaylar/1.flac").status_code == 200
    d = istemci.get("/api/dalga/a-b/adaylar/1.flac").json()
    assert d["sure"] == 1.0 and max(d["tepe"]) == 1.0 and len(d["tepe"]) <= sunucu.DALGA_NOKTA
    assert (c / "a-b" / "adaylar" / "1.flac.dalga.json").exists()


@pytest.mark.parametrize("yol", ["../../gizli.txt", "..%2F..%2Fgizli.txt", "yok.wav"])
def test_klasor_disina_cikilamaz(ortam, yol):
    istemci, _ = ortam
    assert istemci.get(f"/ses/a-b/{yol}").status_code == 404


def test_onar_kabul_onay_akisi(ortam):
    istemci, c = ortam
    r = istemci.post("/api/sarki/a-b/onar", json={"aday": 1, "bas": 58, "son": 62})
    assert r.status_code == 200 and r.json()["asama"] == "onarim" and r.json()["bekleyen_onarim"] == 2
    # bekleyen onarım varken onay yok
    assert istemci.post("/api/sarki/a-b/onayla", json={"aday": 1}).status_code == 409
    # motoru taklit et: sürümlerden biri hazır
    d = durum.oku(c, "a-b")
    for o in d.adaylar[0].onarimlar:
        o.update(durum="hazir", dosya="adaylar/1.flac", kapilar={"dalga": {"gecti": True, "deger": 0.02}})
    durum.yaz(c, d)
    kimlik = d.adaylar[0].onarimlar[0]["id"]
    assert istemci.post("/api/sarki/a-b/onarim-kabul", json={"aday": 1, "onarim": kimlik}).status_code == 200
    d = durum.oku(c, "a-b")
    assert [o["durum"] for o in d.adaylar[0].onarimlar] == ["kabul", "ret"]
    assert istemci.post("/api/sarki/a-b/onayla", json={"aday": 1}).json()["asama"] == "onaylandi"
    assert durum.oku(c, "a-b").secilen == 1


def test_kapidan_gecmeyen_onaylanamaz(ortam):
    istemci, _ = ortam
    assert istemci.post("/api/sarki/a-b/onayla", json={"aday": 2}).status_code == 409


def test_gecersiz_aralik(ortam):
    istemci, _ = ortam
    assert istemci.post("/api/sarki/a-b/onar", json={"aday": 1, "bas": 10, "son": 5}).status_code == 422


def test_reddet(ortam):
    istemci, c = ortam
    assert istemci.post("/api/sarki/a-b/reddet", json={"neden": "ses kötü"}).json()["asama"] == "reddedildi"
    assert durum.oku(c, "a-b").hata == "ses kötü"


def test_sayfa_sunulur(ortam):
    istemci, _ = ortam
    assert "Yanki" in istemci.get("/").text and istemci.get("/uygulama.js").status_code == 200


def test_stil_degisince_yeniden_uretime_doner(ortam):
    istemci, c = ortam
    d = durum.oku(c, "a-b")
    d.analiz = {"stil": "piano ballad", "bpm": 68, "ton": "A major"}
    durum.yaz(c, d)
    r = istemci.post("/api/sarki/a-b/stil", json={"stil": "  acoustic   guitar ballad ", "bpm": 70, "ton": "A major"})
    assert r.status_code == 200 and r.json()["asama"] == "analiz"
    d = durum.oku(c, "a-b")
    assert d.analiz["stil"] == "acoustic guitar ballad" and d.analiz["bpm"] == 70
    assert d.notlar[-1]["stil_degisti"]["eski"]["stil"] == "piano ballad"
    # analizdeyken ikinci istek ve onay yok
    assert istemci.post("/api/sarki/a-b/stil", json={"stil": "rock"}).status_code == 409
    assert istemci.post("/api/sarki/a-b/onar", json={"aday": 1, "bas": 1, "son": 2}).status_code == 409


@pytest.mark.parametrize("govde", [{"stil": ""}, {"stil": "ok stil", "bpm": 5}, {"stil": "x" * 501}])
def test_stil_gecersiz(ortam, govde):
    istemci, _ = ortam
    assert istemci.post("/api/sarki/a-b/stil", json=govde).status_code == 422


def test_bekleyen_onarim_varken_stil_degismez(ortam):
    istemci, c = ortam
    d = durum.oku(c, "a-b")
    d.analiz = {"stil": "piano ballad"}
    durum.yaz(c, d)
    istemci.post("/api/sarki/a-b/onar", json={"aday": 1, "bas": 0.2, "son": 0.5})
    assert istemci.post("/api/sarki/a-b/stil", json={"stil": "rock ballad"}).status_code == 409
