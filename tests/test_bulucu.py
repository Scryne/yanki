import json
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yanki import ayarlar, bulucu, kesif, stillmore, sunucu

ODA = "http://127.0.0.1:8765"
PID = "3vAnSIcOBOBbzAQElt7cSq"


def test_girdi_cozumu():
    assert bulucu.coz("https://open.spotify.com/intl-tr/track/4uLU6hMCjMI75M1A2tKUQC?si=abc") == \
        ("parca", "4uLU6hMCjMI75M1A2tKUQC")
    assert bulucu.coz(f"https://open.spotify.com/playlist/{PID}") == ("playlist", PID)
    assert bulucu.coz("spotify:artist:0gxyHStUsqpMadRV0Di1Qt") == ("sanatci", "0gxyHStUsqpMadRV0Di1Qt")
    assert bulucu.coz("https://open.spotify.com/embed/album/6N9PS4QXF1D0OWPk0Sxtb4") == \
        ("album", "6N9PS4QXF1D0OWPk0Sxtb4")
    assert bulucu.coz(" gb-arl-93-00135 ") == ("isrc", "GBARL9300135")
    assert bulucu.coz("5064150239784") == ("upc", "5064150239784")
    for bozuk, ne in [("", "yapıştır"), ("4uLU6hMCjMI75M1A2tKUQC", "Linkin tamamını"),
                      ("https://open.spotify.com/show/4uLU6hMCjMI75M1A2tKUQC", "tanınmadı"), ("merhaba", "olmalı")]:
        with pytest.raises(bulucu.GirdiHatasi, match=ne):
            bulucu.coz(bozuk)
    assert bulucu.gecerli("parca", "4uLU6hMCjMI75M1A2tKUQC") and not bulucu.gecerli("parca", "x'); alert(1); //")
    assert not bulucu.gecerli("isrc", "GBARL93001") and bulucu.gecerli("upc", "035627515026")


def _satir(id_, ad, sanatci="DJ Delacroix", **ek):
    return {"id": id_, "ad": ad, "sanatci": sanatci, "neden": "removed", "dinlenme": 22661260, "isrc": "BX4IU2351779",
            "cikis": "2023-10-14", "kopyalar": [], **ek}


def test_kesfe_gonderilen_satirlar_kesif_csvsi_olarak_okunur(tmp_path):
    satirlar = [_satir("3Lnrri5QqhZrpkPIwZawKc", "AUTOMOTIVO DAS GALÁXIAS"),
                _satir("0ZOwLTQEVU0N027rEEmNRC", "Magia", kopyalar=[{"id": "3WMQn1hpTK30AfGF7wbroe"}]),  # boşluk yok
                _satir("1111111111111111111111", "Kapali", "Earth, Wind & Fire, Someone", neden="country",
                       dinlenme=None)]
    assert bulucu.kesfe_gonder(tmp_path, satirlar, "bulucu:playlist-x") == (2, 1)
    assert bulucu.kesfe_gonder(tmp_path, satirlar[:1], "bulucu:playlist-x") == (0, 1)  # aynı kimlik iki kez yazılmaz
    adaylar = kesif.stillmore_csv(bulucu.csv_yolu(tmp_path))
    assert [(a.sanatci, a.ad, a.neden, a.spotify_dinlenme, a.isrc) for a in adaylar] == [
        ("DJ Delacroix", "AUTOMOTIVO DAS GALÁXIAS", "kaldirildi", 22661260, "BX4IU2351779"),
        ("Earth, Wind & Fire", "Kapali", "kismi", None, "BX4IU2351779")]
    assert bulucu.gonderilenler(tmp_path) == {"3Lnrri5QqhZrpkPIwZawKc", "1111111111111111111111"}


def test_parca_kaydinda_yalniz_calinan_kopya_engeller(tmp_path):
    kalkmis = {"tur": "parca", "calinir": False, **_satir("2222222222222222222222", "A")}
    olu_kopya = {**kalkmis, "kopyalar": [{"id": "3333333333333333333333", "calinir": False}]}
    canli_kopya = {**kalkmis, "id": "4444444444444444444444",
                   "kopyalar": [{"id": "5555555555555555555555", "calinir": True}]}
    calinan = {**kalkmis, "id": "6666666666666666666666", "calinir": True}
    assert bulucu.kesfe_gonder(tmp_path, [olu_kopya, canli_kopya, calinan], "bulucu:parca") == (1, 2)


def test_izlenen_playlist_gece_havuzuna_girer_birakilan_cikar(tmp_path):
    havuz = {"cfg": {"kaynak": "config"}, "eski": {"kaynak": "bulucu", "ad": "Eski"}}
    izlenen = bulucu.izle(tmp_path, PID, "akil", 37, True)
    assert bulucu.havuza_isle(havuz, izlenen) == 2  # biri eklendi, bırakılan "eski" çıktı
    assert set(havuz) == {"cfg", PID} and havuz[PID]["kaynak"] == "bulucu" and havuz[PID]["toplam"] == 37
    assert bulucu.havuza_isle(havuz, bulucu.izle(tmp_path, PID, "akil", 37, False)) == 1 and set(havuz) == {"cfg"}
    with pytest.raises(bulucu.GirdiHatasi):
        bulucu.izle(tmp_path, "../x", "", None, True)


class _Kopru:
    """Spotify sayfasının yerine: yardımcı yüklenir, iş başlar, iki yoklamada biter."""

    def __init__(self, sonuc, adimlar=None, hata=None):
        self.sonuc, self.hata, self.ifadeler = sonuc, hata, []
        self.adimlar = adimlar or [{"no": 1, "durum": "suruyor", "ilerleme": {"bitti": 1, "toplam": 2, "etiket": "x"}},
                                   {"no": 1, "durum": "hata" if hata else "bitti", "ilerleme": None, "hata": hata}]

    def degerlendir(self, ifade, zaman_asimi=120):
        self.ifadeler.append(ifade)
        if ifade.startswith("window.__yanki.baslat"):
            return 1
        if "durum()" in ifade:
            return self.adimlar.pop(0) if len(self.adimlar) > 1 else self.adimlar[0]
        if ifade.startswith("window.__yanki.sonuc"):
            return self.sonuc
        return True

    def ulke(self):
        return "TR"


def _bekle(b):
    import time

    for _ in range(200):
        if not b.suruyor():
            return b.durum()
        time.sleep(0.01)
    raise AssertionError("iş bitmedi")


def test_is_ilerler_sonucu_kaydeder(tmp_path, monkeypatch):
    monkeypatch.setattr(stillmore, "cdp_acik", lambda port=9222: True)
    k = _Kopru({"tur": "playlist", "id": PID, "ad": "akil", "toplam": 37,
                "satirlar": [_satir("3Lnrri5QqhZrpkPIwZawKc", "A")]})
    b = bulucu.Bulucu(tmp_path, kopru_ac=lambda: k, uyku=lambda s: None)
    assert b.baslat("playlist", PID)["durum"] == "suruyor"
    d = _bekle(b)
    assert d["durum"] == "bitti" and d["anahtar"] == f"playlist-{PID}"
    assert k.ifadeler[0] == bulucu.YARDIMCI  # yardımcı önce yüklendi
    assert f'baslat("playlist", "{PID}", {bulucu.IS_ZAMAN_ASIMI * 1000})' in k.ifadeler[1]
    kayit = bulucu.sonuc_oku(tmp_path, f"playlist-{PID}")
    assert kayit["ad"] == "akil" and kayit["zaman"]
    assert bulucu.gecmis(tmp_path)[0] | {"zaman": None} == {
        "anahtar": f"playlist-{PID}", "tur": "playlist", "ad": "akil", "alt": "Playlist", "zaman": None,
        "sayi": "1 kalkmış / 37", "resim": None}
    with pytest.raises(bulucu.GirdiHatasi):
        b.baslat("parca", "kisa")


def test_is_hatasi_ve_sayfa_yenilenmesi_gosterilir(tmp_path, monkeypatch):
    monkeypatch.setattr(stillmore, "cdp_acik", lambda port=9222: True)
    b = bulucu.Bulucu(tmp_path, kopru_ac=lambda: _Kopru(None, hata="Playlist API kullanılamıyor."), uyku=lambda s: None)
    b.baslat("playlist", PID)
    assert _bekle(b) | {"baslangic": None, "bitis": None} == {
        "tur": "playlist", "kimlik": PID, "durum": "hata", "ilerleme": None, "hata": "Playlist API kullanılamıyor.",
        "anahtar": None, "baslangic": None, "bitis": None}
    yenilenen = _Kopru(None, adimlar=[{"no": 7, "durum": "bos"}])  # Spotify sayfası yenilendi: iş numarası tutmuyor
    b = bulucu.Bulucu(tmp_path, kopru_ac=lambda: yenilenen, uyku=lambda s: None)
    b.baslat("parca", "4uLU6hMCjMI75M1A2tKUQC")
    assert "yenilendi" in _bekle(b)["hata"]


def test_yardimci_sayfada_bir_kez_tanimlanir():
    assert "(() => {" in bulucu.YARDIMCI and "__SURUM__" not in bulucu.YARDIMCI
    assert f"window.__yanki.surum === {bulucu.YARDIMCI_SURUM}) return true" in bulucu.YARDIMCI


class _Isci:
    def __init__(self):
        self.baslayan = []

    def baglanti(self, taze=False):
        return {"cdp": True, "spotify": True, "stillmore": "12.13.0", "ulke": "TR", "hata": None}

    def durum(self):
        return None

    def baslat(self, tur, kimlik=None):
        self.baslayan.append((tur, kimlik))
        return {"tur": tur, "kimlik": kimlik, "durum": "suruyor"}


@pytest.fixture
def oda(tmp_path, monkeypatch):
    import shutil

    kok = tmp_path / "kok"
    (kok / "config").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "config" / "yayin.toml", kok / "config" / "yayin.toml")
    c = tmp_path / "calisma"
    (c / "kesif").mkdir(parents=True)
    liste = tmp_path / "liste.toml"
    liste.write_text('[[sarki]]\nsanatci = "Numb Artist"\nad = "Listede"\n', encoding="utf-8")
    monkeypatch.setattr(stillmore, "cdp_acik", lambda port=9222: True)
    isci = _Isci()
    a = replace(ayarlar.yukle(), kok=kok)
    return TestClient(sunucu.uygulama(a, c, liste_yolu=liste, bulucu_isci=isci), base_url=ODA), isci, c, kok


def test_odadan_arama_baslar(oda, monkeypatch):
    istemci, isci, _, _ = oda
    assert istemci.get("/api/bulucu").json()["baglanti"]["stillmore"] == "12.13.0"
    link = f"https://open.spotify.com/playlist/{PID}"
    assert istemci.post("/api/bulucu/ara", json={"girdi": link}).status_code == 200
    assert istemci.post("/api/bulucu/ara", json={"girdi": "merhaba"}).status_code == 422
    assert istemci.post("/api/bulucu/ac/parca/4uLU6hMCjMI75M1A2tKUQC", json={}).status_code == 200
    assert istemci.post("/api/bulucu/ac/parca/kisa", json={}).status_code == 422
    assert istemci.post("/api/bulucu/ac/sanatci/x');alert(1);aaaaaaaaaaaa", json={}).status_code == 422
    assert isci.baslayan == [("playlist", PID), ("parca", "4uLU6hMCjMI75M1A2tKUQC")]
    monkeypatch.setattr(stillmore, "cdp_acik", lambda port=9222: False)
    r = istemci.post("/api/bulucu/ara", json={"girdi": f"https://open.spotify.com/playlist/{PID}"})
    assert r.status_code == 409 and "bağlan" in r.json()["detail"]


def test_baglanirken_calan_spotify_sorulmadan_kesilmez(oda, monkeypatch):
    istemci, isci, _, _ = oda
    monkeypatch.setattr(stillmore, "cdp_acik", lambda port=9222: False)
    monkeypatch.setattr(stillmore, "calisiyor_mu", lambda: True)
    monkeypatch.setattr(stillmore, "caliyor_mu", lambda: True)
    assert istemci.post("/api/bulucu/baglan", json={}).status_code == 409 and isci.baslayan == []
    assert istemci.post("/api/bulucu/baglan", json={"zorla": True}).status_code == 200
    assert isci.baslayan == [("baglan", None)]


def test_sonuc_hattaki_yeriyle_doner_ve_keşfe_gider(oda):
    istemci, _, c, kok = oda
    kayit = {"tur": "playlist", "id": PID, "ad": "akil", "toplam": 37, "satirlar": [
        _satir("3Lnrri5QqhZrpkPIwZawKc", "Yeni Şarkı"), _satir("0ZOwLTQEVU0N027rEEmNRC", "Listede", "Numb Artist"),
        _satir("1111111111111111111111", "Elenmiş", "X")]}
    anahtar = bulucu.sonuc_yaz(c, kayit)
    elenmis = kesif.Aday(sanatci="X", ad="Elenmiş", kaynak="t", elendi=True)
    (c / "kesif" / "adaylar.json").write_text(json.dumps({elenmis.kimlik: elenmis.__dict__}), encoding="utf-8")
    v = istemci.get(f"/api/bulucu/sonuc/{anahtar}").json()
    durumlar = [(s["yanki"]["listede"], s["yanki"]["hal"], s["yanki"]["gonderildi"]) for s in v["satirlar"]]
    assert durumlar == [(False, None, False), (True, None, False), (False, "elendi", False)] and v["izleniyor"] is False
    r = istemci.post("/api/bulucu/kesfe", json={"anahtar": anahtar, "parcalar": ["3Lnrri5QqhZrpkPIwZawKc"]})
    assert r.json() == {"eklenen": 1, "atlanan": 0}
    assert istemci.get(f"/api/bulucu/sonuc/{anahtar}").json()["satirlar"][0]["yanki"]["gonderildi"] is True
    assert istemci.post("/api/bulucu/kesfe", json={"anahtar": anahtar, "parcalar": ["yok"]}).status_code == 404
    assert istemci.get("/api/bulucu/sonuc/..%2F..%2Fsecret").status_code == 404
    assert istemci.post("/api/bulucu/izle", json={"playlist": PID, "izle": True}).json()["izlenen"][0] == {
        "id": PID, "ad": "akil", "toplam": 37, "son_tarama": None, "calinamayan": None, "aday": None,
        "kaynak": "bulucu", "izleniyor": True}
    assert istemci.get(f"/api/bulucu/sonuc/{anahtar}").json()["izleniyor"] is True
