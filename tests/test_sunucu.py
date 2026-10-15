import json

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from yanki import ayarlar, durum, sunucu

ODA = "http://127.0.0.1:8765"  # oda yalnız yerel Host kabul ediyor


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
    return TestClient(sunucu.uygulama(ayarlar.yukle(), c), base_url=ODA), c


def test_liste_ve_ayrinti(ortam):
    istemci, c = ortam
    assert istemci.get("/api/sarkilar").json()[0] == {"kimlik": "a-b", "sanatci": "A", "ad": "B", "asama": "uretildi",
                                                       "hata": None, "gecen_aday": 1, "bekleyen_onarim": 0,
                                                       "kapak": None, "guncel": durum.oku(c, "a-b").gecmis[-1]["zaman"],
                                                       "dil": None}
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


@pytest.fixture
def kesif_ortami(tmp_path):
    from yanki import kesif

    c = tmp_path / "calisma"
    c.mkdir()
    liste_yolu = tmp_path / "liste.toml"
    liste_yolu.write_text("# liste\n", encoding="utf-8")
    adaylar = [kesif.Aday("HAARPER", "Cadavers in My Cadillac", "playlist:p", youtube_izlenme=76938, geri_geldi=False,
                          sanatci_uyusuyor=True, soz_var=True, sure_sn=110, rakip_cover=0, youtube_id="HCHkoIfw8JA"),
               kesif.Aday("Del", "Put Me in a Movie", "playlist:p", youtube_izlenme=119125, sanatci_uyusuyor=False)]
    kesif.birlestir(c, adaylar)
    return TestClient(sunucu.uygulama(ayarlar.yukle(), c, liste_yolu), base_url=ODA), c, liste_yolu


def test_kesif_listesi_ekle_ele(kesif_ortami):
    from yanki import kesif, liste

    istemci, c, liste_yolu = kesif_ortami
    d = istemci.get("/api/kesif").json()
    assert [(x["sanatci"], x["hal"], x["listede"]) for x in d["adaylar"]] == [
        ("HAARPER", "kaldırılmış", False), ("Del", "sanatçı uymuyor", False)]
    assert d["adaylar"][0]["puan"] == 76938 and d["adaylar"][0]["youtube_id"] == "HCHkoIfw8JA"
    assert set(d["kota"]) == {"bagli", "kilit_sn", "neden", "bugun", "tavan"}
    r = istemci.post("/api/kesif/haarper-cadavers-in-my-cadillac/ekle")
    assert r.status_code == 200 and r.json()["listede"] is True
    assert liste.yukle(liste_yolu) == [liste.Sarki("HAARPER", "Cadavers in My Cadillac")]
    assert istemci.post("/api/kesif/haarper-cadavers-in-my-cadillac/ekle").status_code == 409  # iki kez eklenmez
    assert istemci.post("/api/kesif/del-put-me-in-a-movie/ele", json={"elendi": True}).json()["elendi"] is True
    assert kesif.oku(c)["del-put-me-in-a-movie"].elendi is True
    assert istemci.post("/api/kesif/del-put-me-in-a-movie/ele", json={"elendi": False}).json()["elendi"] is False
    assert istemci.post("/api/kesif/yok/ele", json={}).status_code == 404


def test_kesif_eklemesi_kosu_surerken_de_calisir(kesif_ortami):
    """Kiralık GPU'da üretim ~1 saat koşu kilidini tutuyor; liste kendi kilidiyle yazılır (önce 409 dönüyordu)."""
    from yanki import kilit, liste

    istemci, c, liste_yolu = kesif_ortami
    with kilit.tek_kosu(c / ".yanki.kilit") as alindi:
        assert alindi
        r = istemci.post("/api/kesif/haarper-cadavers-in-my-cadillac/ekle")
    assert r.status_code == 200 and [s.ad for s in liste.yukle(liste_yolu)] == ["Cadavers in My Cadillac"]


def test_yayin_listesi(tmp_path):
    c = tmp_path / "calisma"
    d = durum.Durum("adele-x", "Adele", "X", asama="yayinda",
                    yayin={"son": {"canli": True, "siralar": {"GB": 2}, "sanatci_id": "orv"}, "gecmis": []})
    durum.yaz(c, d)
    (c / "adele-x" / "paket").mkdir()
    (c / "adele-x" / "paket" / "metadata.json").write_text(
        json.dumps({"yukleme": {"yayin_tarihi": "2026-10-28", "isrc": "GX1", "dagitimci": "routenote"}}),
        encoding="utf-8")
    durum.yaz(c, durum.Durum("b-c", "B", "C", asama="uretildi"))
    istemci = TestClient(sunucu.uygulama(ayarlar.yukle(), c, tmp_path / "liste.toml"), base_url=ODA)
    y = istemci.get("/api/yayin").json()
    assert [s["kimlik"] for s in y["sarkilar"]] == ["adele-x"] and y["sarkilar"][0]["yayin_tarihi"] == "2026-10-28"
    assert y["sarkilar"][0]["son"]["siralar"] == {"GB": 2} and y["profiller"] == ["orv"]


# ── pano, kapak, kazanç (2026-10-10) ────────────────────────
def _jpeg(yol, boyut=(900, 1200)):
    from PIL import Image

    Image.new("RGB", boyut, (40, 60, 80)).save(yol, "JPEG")


def test_kapak_kucuk_kare_onbellekli_ve_listede(ortam):
    istemci, c = ortam
    assert istemci.get("/kapak/a-b").status_code == 404  # kapak yok
    _jpeg(c / "a-b" / "kapak_pinterest.jpg")
    url = istemci.get("/api/sarkilar").json()[0]["kapak"]
    assert url.startswith("/kapak/a-b?v=")
    from io import BytesIO

    from PIL import Image

    r = istemci.get("/kapak/a-b?boyut=96")
    assert r.status_code == 200 and Image.open(BytesIO(r.content)).size == (96, 96)
    assert istemci.get("/kapak/a-b?boyut=4000").status_code == 404  # yalnız tanımlı boyutlar
    assert istemci.get("/kapak/..%2F..?boyut=96").status_code == 404
    (c / "a-b" / "paket").mkdir()
    _jpeg(c / "a-b" / "paket" / "Orvane_-_B.jpg", (3000, 3000))  # paketteki önce gelir
    assert sunucu.kapak_kaynagi(c, "a-b").parent.name == "paket"
    for _ in range(3):  # tekrar tekrar istense de küçük resim paketin dışında, kaynak hep aynı dosya
        assert istemci.get(istemci.get("/api/sarkilar").json()[0]["kapak"] + "&boyut=96").status_code == 200
    assert [x.name for x in (c / "a-b" / "paket").iterdir()] == ["Orvane_-_B.jpg"]
    assert sunucu.kapak_kaynagi(c, "a-b").name == "Orvane_-_B.jpg"
    (c / "a-b" / "paket" / ".kapak_eski_96.jpg").write_bytes(b"x")  # eski sürümün bıraktığı küçük resim sayılmaz
    assert sunucu.kapak_kaynagi(c, "a-b").name == "Orvane_-_B.jpg"


def test_baska_kapak_pinterestten_ve_yuklenmiste_yasak(ortam, monkeypatch):
    from yanki import pinterest

    istemci, c = ortam

    def sahte(calisma, d, yeni=False):
        _jpeg(calisma / d.kimlik / "kapak_pinterest.jpg")
        (calisma / d.kimlik / "kapak_kaynak.json").write_text(json.dumps({"pin_id": "1", "aciklama": "a lake",
                                                                          "yeni": yeni}), "utf-8")
        return calisma / d.kimlik / "kapak_pinterest.jpg"

    monkeypatch.setattr(pinterest, "getir", sahte)
    r = istemci.post("/api/sarki/a-b/kapak")
    assert r.status_code == 200 and r.json()["kapak_bilgi"]["aciklama"] == "a lake" and r.json()["kapak"]
    assert istemci.post("/api/sarki/a-b/kapak").json()["kapak_bilgi"]["yeni"] is True  # ikincisi başka pin
    with durum.guncelle(c, "a-b") as d:
        d.gec("yuklendi")
    assert istemci.post("/api/sarki/a-b/kapak").status_code == 409


def test_pano_hat_ve_kulak_bekleyen(ortam):
    istemci, c = ortam
    with durum.guncelle(c, "a-b") as d:
        d.analiz = {"stil": "rap, hip hop song", "dil": "en"}
    p = istemci.get("/api/pano").json()
    assert [x["ad"] for x in p["hat"]] == ["Keşif", "Üretim", "Dinleme", "Paket", "İnceleme", "Yayında"]
    assert next(x for x in p["hat"] if x["ad"] == "Dinleme")["sayi"] == 1
    if p["ayarlar"].get("oto_onay"):  # gerçek config: otomatik onay açıksa rap şarkı kulak bekler
        assert p["kulak"][0]["kimlik"] == "a-b" and "rap" in p["kulak"][0]["neden"]
    assert "takvim" in p and "olaylar" in p and p["takvim"].get("yazarsiz", []) == []


def test_son_gece_gunlukten(tmp_path):
    g = tmp_path / "gunluk"
    g.mkdir()
    satirlar = ["\ufeff=== 2026-10-10T03:00:01 başladı", "── keşif (03:00:01)", "── üretim (03:01:54)",
                "── koşu bitti (05:00:00); sorunlu adım: keşif", "── dış servisler: x",
                "=== 2026-10-10T05:00:02 bitti (kod 1)"]
    (g / "2026-10-10.log").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    s = sunucu._son_gece(tmp_path)
    assert s == {"bas": "2026-10-10T03:00:01", "bit": "2026-10-10T05:00:02", "kod": 1, "suruyor": False,
                 "adim": "üretim", "sorunlu": "keşif"}
    (g / "2026-10-11.log").write_text("=== 2026-10-11T03:00:01 başladı\n── keşif (03:00:01)\n", encoding="utf-8")
    assert sunucu._son_gece(tmp_path)["suruyor"] is True


def _tunearo_secili(monkeypatch):
    from dataclasses import replace

    from yanki import paket

    gercek = paket.yayin_ayarlari
    monkeypatch.setattr(paket, "yayin_ayarlari", lambda yol: replace(gercek(yol), dagitimci="tunearo"))


def test_kazanc_baglanti_yoksa_bagli_degil(ortam, monkeypatch):
    from yanki import tunearo

    istemci, _ = ortam
    _tunearo_secili(monkeypatch)

    def yok(cls, kok):
        raise tunearo.AyarYok(None, "anahtar yok")

    monkeypatch.setattr(tunearo.Istemci, "kokten", classmethod(yok))
    assert istemci.get("/api/kazanc").json() == {"bagli": False}


def test_sarki_bolumleri_ve_hattin_onerisi(ortam):
    # sözler bölüm yapısıyla (söz rayı) ve öneri: söz WER'i en düşük iki aday arasından hizalaması yüksek olan
    istemci, c = ortam
    satirlar = [[10.0, "a1"], [14.0, "a2"], [40.0, "nakarat bir"], [44.0, "nakarat iki"], [60.0, "b1"], [64.0, "b2"],
                [90.0, "nakarat bir"], [94.0, "nakarat iki"]]
    (c / "a-b" / "soz_zaman.json").write_text(json.dumps(satirlar), encoding="utf-8")
    with durum.guncelle(c, "a-b") as d:
        wer = lambda w: {"soz_wer": {"gecti": True, "deger": w, "esik": 0.5}}  # noqa: E731
        d.adaylar = [durum.Aday(1, "adaylar/1.flac", 42, wer(0.10), True, hizalama=[{"dit": 0.10}]),
                     durum.Aday(2, "adaylar/1.flac", 7, wer(0.12), True, hizalama=[{"dit": 0.20}]),
                     durum.Aday(3, "adaylar/1.flac", 123, wer(0.30), True, hizalama=[{"dit": 0.90}])]
    r = istemci.get("/api/sarki/a-b").json()
    adlar = [b["ad"] for b in r["bolumler"]]
    assert "Chorus" in adlar and r["bolumler"][adlar.index("Chorus")]["satirlar"][0] == [40.0, "nakarat bir"]
    assert r["oneri"]["aday"] == 2 and "0,12" in r["oneri"]["neden"]


def test_pano_su_an_ve_uretim_tarifi(ortam):
    istemci, c = ortam
    p = istemci.get("/api/pano").json()
    assert p["simdi"]["suruyor"] is False and p["simdi"]["pod"] is None and p["simdi"]["uretimde"] == []
    (c / ".runpod").mkdir()
    (c / ".runpod" / "acik_pod").write_text("pod", encoding="utf-8")
    from yanki import kilit

    with kilit.tek_kosu(c / ".yanki.kilit"):  # koşu sürerken kilit dosyası okunamaz
        s = istemci.get("/api/pano").json()["simdi"]
    assert s["suruyor"] is True and s["pod"]["dakika"] == 0
    assert {"model", "lora", "betim", "aday"} <= set(p["ayarlar"]["tarif"])


def test_kazanc_ulasilamayinca_hata_degil_bilgi(ortam, monkeypatch):
    # erişim kapalıyken her pano açılışı konsola 502 düşürüyordu
    from yanki import tunearo

    istemci, _ = ortam
    _tunearo_secili(monkeypatch)
    monkeypatch.setattr(tunearo.Istemci, "kokten", classmethod(lambda cls, kok: object()))

    def kapali(*_a, **_k):
        raise tunearo.TunearoHatasi(403, "API access not enabled")

    monkeypatch.setattr(tunearo, "kazanc", kapali)
    r = istemci.get("/api/kazanc")
    assert r.status_code == 200 and r.json()["ulasilamadi"] and r.json()["erisim_kapali"]


def test_kazanc_dagitimci_yokken_istek_atmaz(ortam, monkeypatch):
    # Tunearo kapandı (2026-10-12): dağıtımcı seçilmemişken kazanç sorulmaz
    from dataclasses import replace

    from yanki import paket, tunearo

    istemci, _ = ortam
    gercek = paket.yayin_ayarlari
    monkeypatch.setattr(paket, "yayin_ayarlari", lambda yol: replace(gercek(yol), dagitimci=""))
    monkeypatch.setattr(tunearo, "kazanc", lambda *_a, **_k: pytest.fail("Tunearo'ya istek atıldı"))
    assert istemci.get("/api/kazanc").json()["bagli"] is False


def test_yazan_istek_yalniz_odanin_kendi_kokeninden(ortam):
    """Yerelde çalışan başka bir sayfa (başka port) da onay/gönderim uçlarına ulaşamamalı; tarayıcısız istek geçer."""
    istemci, _ = ortam
    yol = "/api/sarki/yok-boyle/reddet"
    for basliklar in ({"Origin": "http://localhost:3000"}, {"Origin": "http://evil.example"}, {"Origin": "null"},
                      {"Sec-Fetch-Site": "same-site"}, {"Sec-Fetch-Site": "cross-site"}):
        assert istemci.post(yol, json={"neden": ""}, headers=basliklar).status_code == 403, basliklar
    kendi = {"Origin": ODA, "Sec-Fetch-Site": "same-origin"}
    assert istemci.post(yol, json={"neden": ""}, headers=kendi).status_code == 404  # korumadan geçti, şarkı yok
    assert istemci.post(yol, json={"neden": ""}).status_code == 404


def test_pano_kapali_otomatik_kosuyu_soyler(tmp_path):
    """2026-10-13'ten beri Yanki/Surekli ve Yanki/Gece görevleri kapalıydı; pano hiçbir şey söylemiyordu (son koşu
    "sorunsuz")."""
    c = tmp_path / "calisma"
    c.mkdir()
    oda = TestClient(sunucu.uygulama(ayarlar.yukle(), c, gorev_oku=lambda: {"Surekli": "Disabled", "Gece": "Ready"}),
                     base_url=ODA)
    p = oda.get("/api/pano").json()
    assert [u["baslik"] for u in p["uyarilar"]] == ["Otomatik koşu kapalı"]
    assert "Yanki\\Surekli" in p["uyarilar"][0]["metin"] and "Gece" not in p["uyarilar"][0]["metin"]
    assert p["simdi"]["otomatik_kapali"] is True
    acik = TestClient(sunucu.uygulama(ayarlar.yukle(), c, gorev_oku=lambda: {"Surekli": "Ready"}), base_url=ODA)
    assert acik.get("/api/pano").json()["uyarilar"] == []
