import json
from datetime import date, datetime, timedelta
from email.message import EmailMessage
from pathlib import Path

import pytest

from yanki import bulucu, dagitim, durum, eposta, kazanc, kesif, performans, stillmore, takip

ASAMALAR = ("uretildi", "onaylandi", "paketlendi", "yuklendi", "yayinda")


def _sarki(c: Path, kimlik: str, ad: str, asama: str = "yayinda", sanatci: str = "Orijinal", **meta_ek):
    d = durum.Durum(kimlik, sanatci, ad, kaynak={"dosya": "kaynak.wav"})
    for a in ASAMALAR[: ASAMALAR.index(asama) + 1]:
        d.gec(a)
    durum.yaz(c, d)
    p = durum.klasor(c, kimlik) / "paket"
    p.mkdir(parents=True, exist_ok=True)
    (p / "metadata.json").write_text(json.dumps({"baslik": ad, **meta_ek}), encoding="utf-8")
    return d


def _yayinda(c: Path, kimlik: str, ad: str, gunluk: int, gun_once: int = 30, sanatci: str = "Orijinal"):
    d = _sarki(c, kimlik, ad, sanatci=sanatci)
    bas = date.today() - timedelta(days=gun_once)
    d.yayin = {"gecmis": [{"zaman": datetime.combine(bas, datetime.min.time()).isoformat(), "canli": True}]}
    for i in range(0, gun_once + 1, 7):
        performans.dinlenme_ekle(d, 1000 + gunluk * i, bas + timedelta(days=i))
    durum.yaz(c, d)
    return d


def test_dinlenme_serisi_ve_gunluk():
    d = durum.Durum("a-b", "A", "B")
    assert performans.gunluk(d) is None
    performans.dinlenme_ekle(d, 100, date(2026, 10, 1))
    performans.dinlenme_ekle(d, 110, date(2026, 10, 1))  # aynı gün üstüne yazar
    performans.dinlenme_ekle(d, 410, date(2026, 10, 11))
    assert d.yayin["dinlenme"] == [["2026-10-01", 110], ["2026-10-11", 410]]
    assert performans.gunluk(d) == 30.0
    d.yayin["son"] = {"canli": True}
    takip.kaydet(d, {"canli": True, "spotify_id": "x", "sanatci_id": "y", "siralar": {}, "zaman": "2026-10-12T03:00"})
    assert d.yayin["dinlenme"]  # takip kaydı dinlenme serisini silmez


def test_tur_carpani_yeterli_veriyle_kesif_puanina_girer(tmp_path):
    c = tmp_path / "calisma"
    kayit = {}
    for i, (tur, gunluk) in enumerate([("pop", 400), ("pop", 300), ("metal", 25), ("metal", 30), ("rock", 100)]):
        d = _yayinda(c, f"s{i}-x", f"Şarkı {i}", gunluk, sanatci=f"S{i}")
        kayit[d.kimlik] = kesif.Aday(sanatci=f"S{i}", ad=f"Şarkı {i}", kaynak="t", turler=[tur])
    yeni = _yayinda(c, "taze-x", "Taze", 999, gun_once=7, sanatci="T")  # 14 günden az: tür hesabına girmez
    kayit[yeni.kimlik] = kesif.Aday(sanatci="T", ad="Taze", kaynak="t", turler=["jazz"])
    t = performans.tur_tablosu(c, kayit)
    assert t["yeterli"] and t["sarki"] == 5 and "jazz" not in t["turler"]
    assert t["turler"]["pop"]["carpan"] > 1 > t["turler"]["metal"]["carpan"] >= performans.CARPAN_ALT
    assert t["turler"]["rock"]["carpan"] == 1.0  # tek şarkı: çarpan yok
    aday = kesif.Aday(sanatci="Z", ad="Yeni", kaynak="t", turler=["metal"], youtube_izlenme=1_000_000,
                      sanatci_uyusuyor=True, soz_var=True, geri_geldi=False)
    once = aday.puan
    performans.uygula({**kayit, "z": aday}, c)  # keşif kaydı şarkılarımızın kendi adaylarını da taşır
    assert aday.performans == t["turler"]["metal"]["carpan"] and aday.puan == pytest.approx(once * aday.performans)


def test_az_veriyle_carpan_yok(tmp_path):
    c = tmp_path / "calisma"
    d = _yayinda(c, "a-x", "A", 500)
    kayit = {d.kimlik: kesif.Aday(sanatci="Orijinal", ad="A", kaynak="t", turler=["pop"])}
    assert performans.tur_tablosu(c, kayit)["yeterli"] is False
    aday = kesif.Aday(sanatci="Z", ad="Y", kaynak="t", turler=["pop"])
    performans.uygula({"z": aday}, c)
    assert aday.performans is None


def test_sayaci_duran_kalkmis_sarki_onde(tmp_path):
    ortak = dict(kaynak="t", youtube_izlenme=1_000_000, sanatci_uyusuyor=True, soz_var=True, geri_geldi=False)
    eski, taze = kesif.Aday(sanatci="A", ad="Eski", **ortak), kesif.Aday(sanatci="A", ad="Taze", sayac_duruyor=True,
                                                                         **ortak)
    assert taze.puan == pytest.approx(eski.puan * kesif.TAZELIK_CARPANI)
    satir = {"id": "3Lnrri5QqhZrpkPIwZawKc", "ad": "Taze", "sanatci": "A", "neden": "removed", "kopyalar": [],
             "pencere": {"sayi_duruyor": True}}
    bulucu.kesfe_gonder(tmp_path, [satir], "bulucu:x")
    assert kesif.stillmore_csv(bulucu.csv_yolu(tmp_path))[0].sayac_duruyor is True
    a = stillmore.adaylara([{"trackId": "x", "name": "N", "artist": "A", "counter": True, "plays": 5}], "p")[0]
    assert a.sayac_duruyor is True
    yeni = kesif.Aday(sanatci="A", ad="Taze", kaynak="playlist:x")  # Web API taraması sayacı bilmez: kayıttaki kalır
    assert kesif.tasi(yeni, taze).sayac_duruyor is True


class _Kopru:
    def __init__(self):
        self.listeler = {"art1": [{"id": "p1", "name": "Sad", "owner": "ali"},
                                  {"id": "p2", "name": "Ed", "owner": "Spotify"},
                                  {"id": "p5", "name": "ADELE Greatest Hits", "owner": "x"},  # tek sanatçılık
                                  {"id": "p3", "name": "Mix", "owner": "veli"}],
                         "art2": [{"id": "p4", "name": "B", "owner": "x"}]}

    def ara(self, terim, adet=20):
        ad = terim.split(" ")[0]
        return [{"id": "t", "name": "x", "artists": [{"id": "art1" if ad == "Adele" else "art2", "name": ad}]}]

    def sanatci_listeleri(self, sanatci_id):
        return self.listeler[sanatci_id]


def test_havuz_iyi_sarkilarin_sanatci_listeleriyle_buyur(tmp_path):
    havuz = {"var": {"kaynak": "config"}}
    k = _Kopru()
    n = stillmore.havuz_genislet(k, tmp_path, havuz, [("Adele", "Hello"), ("adele", "Skyfall"), ("Numb", "Numb")],
                                 gece=1, liste_basina=5, en_cok=10)
    assert n == 2 and set(havuz) == {"var", "p1", "p3"} and havuz["p1"]["kaynak"] == "sanatci:Adele"  # editoryal yok
    n = stillmore.havuz_genislet(k, tmp_path, havuz, [("Adele", "Hello"), ("Numb", "Numb")], gece=5, liste_basina=5,
                                 en_cok=10)
    assert n == 1 and "p4" in havuz  # Adele 30 gün geçmeden yeniden genişletilmez
    assert stillmore.havuz_genislet(k, tmp_path, havuz, [("Yeni", "Y")], gece=5, liste_basina=5, en_cok=4) == 0


def test_iyi_sarkilar_dinlenmeye_gore(tmp_path):
    c = tmp_path / "calisma"
    _yayinda(c, "az-x", "Az", 10, sanatci="Az")
    _yayinda(c, "cok-x", "Cok", 500, sanatci="Cok")
    _sarki(c, "paket-x", "Paket", asama="paketlendi", sanatci="Paket")
    _sarki(c, "uretim-x", "Uretim", asama="uretildi", sanatci="Uretim")
    assert stillmore.iyi_sarkilar(c) == [("Cok", "Cok"), ("Az", "Az"), ("Paket", "Paket")]


RAPOR = """RouteNote Monthly Sales Report
Period,September 2026
Sale Month,Store,Country,Artist,Track Title,ISRC,UPC,Quantity,Earnings (USD)
2026-09,Spotify,GB,Orvane,Numb,GBXYZ2600001,5064149827466,1200,"3.6000"
2026-09,Apple Music,DE,Orvane,Numb,GBXYZ2600001,5064149827466,100,0.5500
2026-09,Spotify,TR,Başkası,Other,USABC1234567,,50,0.1000
"""


def test_kazanc_raporu_isrc_ile_sarkiya_baglanir(tmp_path):
    c = tmp_path / "calisma"
    _sarki(c, "numb", "Numb", yukleme={"isrc": "GBXYZ2600001", "upc": "5064149827466", "dagitimci": "routenote"})
    k = kazanc.klasor(tmp_path)
    k.mkdir(parents=True)
    (k / "eylul.csv").write_text(RAPOR, encoding="utf-8")
    (k / "eylul-kopya.csv").write_text(RAPOR, encoding="utf-8")  # aynı rapor iki kez: bir kez sayılır
    r = kazanc.sarki_kazanclari(tmp_path, c)
    assert r["sarkilar"]["numb"] == {"tutar": 4.15, "akis": 1300, "para": "USD"}
    assert r["ozet"]["toplam"] == {"USD": 4.25} and r["ozet"]["aylar"] == ["2026-09"] and r["ozet"]["eslesmeyen"] == 1
    assert r["ozet"]["magazalar"]["Spotify"] == 3.7


def test_kazanc_okuyucu_baska_basliklari_tanir(tmp_path):
    yol = tmp_path / "r.csv"
    yol.write_text("Reporting Period;DSP;Territory;Track;ISRC;Streams;Net Revenue;Currency\n"
                   "10/2026;Deezer;FR;Numb;GBXYZ2600001;1.234;1,50;EUR\n", encoding="utf-8")
    assert kazanc.oku_dosya(yol) == [{"isrc": "GBXYZ2600001", "upc": None, "parca": "Numb", "magaza": "Deezer",
                                      "ulke": "FR", "ay": "2026-10", "adet": 1234, "tutar": 1.5, "para": "EUR"}]
    (tmp_path / "bos.csv").write_text("a,b\n1,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="bulunamadı"):
        kazanc.oku_dosya(tmp_path / "bos.csv")


def _ileti(konu, govde, html=False, kimden="RouteNote <noreply@routenote.com>", mid="<1@rn>"):
    m = EmailMessage()
    m["From"], m["Subject"], m["Message-ID"], m["Date"] = kimden, konu, mid, "Fri, 16 Oct 2026 10:00:00 +0000"
    m.set_content(govde, subtype="html" if html else "plain")
    return m.as_bytes()


def test_eposta_siniflandirma_ve_eslesme():
    onay = eposta.ayristir(_ileti("Your release has been approved", "<p>Good news! <b>Numb</b> was approved.</p>",
                                  html=True))
    assert onay.metin.startswith("Good news!") and eposta.sinif(onay) == "onay"
    assert eposta.sinif(eposta.ayristir(_ileti("Release update", "Unfortunately your release has not been approved "
                                                "because of the artwork."))) == "red"
    assert eposta.sinif(eposta.ayristir(_ileti("Action Needed: Numb", "Our moderation team sent it back"))) == "aksiyon"
    assert eposta.sinif(eposta.ayristir(_ileti("Newsletter", "Check our new features"))) is None
    liste = [{"kimlik": "numb", "ad": "Numb", "upc": "5064149827466", "asama": "yuklendi"},
             {"kimlik": "numb-akustik", "ad": "Numb (Acoustic)", "upc": "", "asama": "yuklendi"},
             {"kimlik": "lovely", "ad": "lovely", "upc": "5064149247325", "asama": "yuklendi"}]
    assert eposta.eslestir(eposta.ayristir(_ileti("x", "UPC 5064149247325 approved")), liste)["kimlik"] == "lovely"
    assert eposta.eslestir(onay, liste)["kimlik"] == "numb"
    assert eposta.eslestir(eposta.ayristir(_ileti("Numb (Acoustic) approved", "")), liste)["kimlik"] == "numb-akustik"
    assert eposta.eslestir(eposta.ayristir(_ileti("Your release", "approved")), liste) is None


def test_eposta_hatta_islenir_bir_kez(tmp_path):
    c = tmp_path / "calisma"
    rn = {"upc": "5064149827466", "adim": "gonderildi"}
    _sarki(c, "numb", "Numb", asama="yuklendi", routenote=rn,
           yukleme={"isrc": "GBXYZ2600001", "upc": "5064149827466", "dagitimci": "routenote"})
    _sarki(c, "lovely", "lovely", asama="yuklendi", routenote={"upc": "5064149247325", "adim": "gonderildi"},
           yukleme={"upc": "5064149247325", "dagitimci": "routenote"})
    _sarki(c, "elle", "Elle Gonderilen", asama="paketlendi", routenote={"upc": "5064150000000", "adim": "hazir"})
    bildirimler = []
    iletiler = [eposta.ayristir(_ileti("Release approved", "Numb has been approved", mid="<a>")),
                eposta.ayristir(_ileti("Release declined", "lovely was declined: misleading artist name", mid="<b>")),
                eposta.ayristir(_ileti("Approved", "Elle Gonderilen is approved", mid="<c>")),
                eposta.ayristir(_ileti("Profile Code", "Here is your access code: abc123", mid="<d>")),
                eposta.ayristir(_ileti("Update", "We have news about your release", mid="<e>"))]
    sonuc = eposta.isle(c, iletiler, bildir=lambda *a: bildirimler.append(a))
    assert [(x["sinif"], x["kimlik"]) for x in sonuc] == [("onay", "numb"), ("red", "lovely"), ("onay", "elle"),
                                                          (None, None), (None, None)]
    assert sonuc[3]["eylem"].startswith("ilgisiz")
    assert takip.yukleme_bilgisi(c, "numb")["dagitim_durumu"] == "approved"
    lovely = durum.oku(c, "lovely")
    assert lovely.asama == "paketlendi" and dagitim.RED_ONEKI in (lovely.gecmis[-1].get("hata") or "")
    meta = json.loads((durum.klasor(c, "lovely") / "paket" / "metadata.json").read_text(encoding="utf-8"))
    assert "routenote" not in meta and meta["routenote_gecmisi"][0]["upc"] == "5064149247325"
    assert durum.oku(c, "elle").asama == "yuklendi"  # elle gönderilmiş, onay e-postasıyla kaydedildi
    assert [b[1] for b in bildirimler][-1].startswith("RouteNote e-postası")  # yayınla ilgili, tanınmadı
    assert not any("Profile Code" in b[2] for b in bildirimler)  # hesap iletisi bildirilmez
    assert eposta.isle(c, iletiler, bildir=lambda *a: bildirimler.append(a)) == []  # ikinci kez işlenmez
    ornekler = [p.read_text(encoding="utf-8") for p in (c / "eposta" / "ornek").glob("*.txt")]
    assert len(ornekler) == 4 and not any("abc123" in o for o in ornekler)  # giriş kodu diske yazılmaz


class _Imap:
    def __init__(self, sunucu):
        self.sunucu, self.komutlar = sunucu, []

    def login(self, k, s):
        self.komutlar.append(("login", k))

    def select(self, kutu, readonly=False):
        assert readonly
        self.komutlar.append(("select", kutu))

    def search(self, _, *ölçüt):
        self.komutlar.append(("search", ölçüt))
        return "OK", [b"1 2"]

    def fetch(self, no, ne):
        assert ne == "(BODY.PEEK[])"  # okunmadı işareti bozulmaz
        return "OK", [(b"1", _ileti("Approved", f"release {no.decode()}", mid=f"<{no.decode()}>")), b")"]

    def logout(self):
        pass


def test_imap_yalniz_routenote_salt_okunur(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("EPOSTA_KULLANICI=a@b.c\nEPOSTA_SIFRE=abcd efgh ijkl mnop\n", encoding="utf-8")
    for k in ("EPOSTA_KULLANICI", "EPOSTA_SIFRE", "EPOSTA_SUNUCU"):
        monkeypatch.delenv(k, raising=False)
    a = eposta.ayar(tmp_path)
    assert a == {"kullanici": "a@b.c", "sifre": "abcdefghijklmnop", "sunucu": "imap.gmail.com"}
    iletiler = eposta.getir(a, imap=_Imap)
    assert [i.metin for i in iletiler] == ["release 1", "release 2"]
    assert eposta.ayar(tmp_path / "yok") is None


def test_odada_performans_ve_kazanc(tmp_path, monkeypatch):
    import shutil
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from yanki import ayarlar, sunucu

    kok = tmp_path / "kok"
    (kok / "config").mkdir(parents=True)
    shutil.copy(Path(__file__).resolve().parents[1] / "config" / "yayin.toml", kok / "config" / "yayin.toml")
    for k in ("EPOSTA_KULLANICI", "EPOSTA_SIFRE"):
        monkeypatch.delenv(k, raising=False)
    c = tmp_path / "calisma"
    d = _yayinda(c, "numb", "Numb", 120)
    takip.yukleme_kaydet(c, d.kimlik, {"isrc": "GBXYZ2600001", "upc": "5064149827466"}, "routenote")
    istemci = TestClient(sunucu.uygulama(replace(ayarlar.yukle(), kok=kok), c), base_url="http://127.0.0.1:8765")
    k = istemci.get("/api/kazanc").json()
    assert k["bagli"] is False and "girdi/kazanc" in k["mesaj"]
    kazanc.klasor(kok).mkdir(parents=True)
    (kazanc.klasor(kok) / "eylul.csv").write_text(RAPOR, encoding="utf-8")
    k = istemci.get("/api/kazanc").json()
    assert k["bagli"] and k["toplam"] == 4.25 and k["para"] == "USD" and k["son_ay"] == "2026-09"
    assert k["yayinlar"] == ["numb"] and k["kaynaklar"][0] == {"kaynak": "Spotify", "tutar": 3.7}
    p = istemci.get("/api/performans").json()
    assert p["sarkilar"][0]["kazanc"] == 4.15 and p["sarkilar"][0]["gunluk"] == 120.0
    assert p["eposta"] == {"ayarli": False, "son": []}
    y = istemci.get("/api/yayin").json()["sarkilar"][0]
    assert y["dinlenme"] == 1000 + 120 * 28 and y["gunluk"] == 120.0


def test_eposta_metni_temizlenir():
    for charset in ("", "; charset=iso-8859-1"):  # charset yok ya da yanlış: UTF-8 baytlar latin-1 çözülür
        ham = (f"From: noreply@routenote.com\r\nSubject: Welcome\r\nContent-Type: text/html{charset}\r\n\r\n"
               .encode() + "<!-- tag needs inline styles --><p>we’ll help</p>".encode())
        assert eposta.ayristir(ham).metin == "we’ll help"