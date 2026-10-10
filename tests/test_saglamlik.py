"""Denetim (2026-10-10, Scryne: "projeyi baştan sona incele, eksikleri ve hataları çöz"): her düzeltmenin ve eklemenin
testi. Ağ yok (conftest); dış servisler sahte."""

import http.client
import io
import json
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest

from yanki import ag, dagitim, dosya, durum, kesif, olay, onay, pinterest, sozler, takip, temizlik, tunearo


# ── atomik yazım: okuyucu dosyayı tutarken (Windows) yerine koyma yeniden denenir ──
def test_atomik_yazim_okuyucu_varken_yeniden_dener(tmp_path, monkeypatch):
    yol = tmp_path / "durum.json"
    gercek, sayac = Path.replace, {"n": 0}

    def mesgul(self, hedef):
        sayac["n"] += 1
        if sayac["n"] < 3:
            raise PermissionError(5, "Erişim engellendi")
        return gercek(self, hedef)

    monkeypatch.setattr(Path, "replace", mesgul)
    monkeypatch.setattr(dosya.time, "sleep", lambda _: None)
    dosya.json_yaz(yol, {"a": 1})
    assert json.loads(yol.read_text(encoding="utf-8")) == {"a": 1} and sayac["n"] == 3
    assert not list(tmp_path.glob("*.tmp"))


def test_atomik_yazim_hep_mesgulse_gecici_dosya_kalmaz(tmp_path, monkeypatch):
    monkeypatch.setattr(Path, "replace", lambda self, h: (_ for _ in ()).throw(PermissionError(5, "x")))
    monkeypatch.setattr(dosya.time, "sleep", lambda _: None)
    with pytest.raises(PermissionError):
        dosya.yaz(tmp_path / "a.json", "{}")
    assert not list(tmp_path.glob("*.tmp"))


# ── ağ: yarıda kesilen cevap geçici sayılır ──
class _Cevap:
    def __init__(self, govde: bytes):
        self.govde = govde

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, *_):
        return self.govde


def test_kesik_cevap_yeniden_denenir(monkeypatch):
    sira = [http.client.IncompleteRead(b"{"), _Cevap(b'{"ok": true}')]

    def urlopen(*_a, **_k):
        x = sira.pop(0)
        if isinstance(x, Exception):
            raise x
        return x

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ag.time, "sleep", lambda _: None)
    assert ag.json_al("https://lrclib.net/api/get") == {"ok": True}


def test_yarim_json_sonunda_oserror(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: _Cevap(b'{"yarim'))
    monkeypatch.setattr(ag.time, "sleep", lambda _: None)
    with pytest.raises(OSError, match="yarım cevap"):
        ag.json_al("https://lrclib.net/api/get", deneme=2)


# ── Pinterest: indirilemeyen görselde sıradakine geçilir (odada "Başka kapak" 500 veriyordu) ──
def _pin(no, en=1500, boy=1500):
    return {"id": str(no), "type": "pin", "seo_alt_text": "a misty lake", "image_signature": f"imza{no}",
            "images": {"orig": {"url": f"https://i.pinimg.com/{no}.jpg", "width": en, "height": boy}}}


def _jpeg(boyut=(1200, 1200)):
    from PIL import Image

    b = io.BytesIO()
    Image.new("RGB", boyut, (20, 30, 40)).save(b, "JPEG")
    return b.getvalue()


def test_pinterest_indirilemeyen_gorselde_siradakine_gecer(tmp_path):
    c = tmp_path / "c"
    d = durum.Durum("a", "X", "A", asama="onaylandi", analiz={"stil": "piano ballad"})
    durum.yaz(c, d)
    indirilen = []

    def indirici(url):
        indirilen.append(url)
        if url.endswith("/1.jpg"):
            raise OSError("görsel indirilemedi: IncompleteRead")
        if url.endswith("/2.jpg"):
            return _jpeg((300, 300))  # açıklama 1500 diyor, gerçek görsel küçük
        return _jpeg()

    pinterest.getir(c, d, arayici=lambda q: [_pin(1, 2000, 2000), _pin(2, 1800, 1800), _pin(3)], indirici=indirici)
    assert json.loads((c / "a" / "kapak_kaynak.json").read_text(encoding="utf-8"))["pin_id"] == "3"
    assert [u[-5:] for u in indirilen] == ["1.jpg", "2.jpg", "3.jpg"]


def test_pinterest_indirme_kesilirse_oserror(monkeypatch):
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(http.client.IncompleteRead(b"x", 10)))
    monkeypatch.setattr("time.sleep", lambda _: None)
    with pytest.raises(OSError, match="IncompleteRead"):
        pinterest._indir("https://i.pinimg.com/x.jpg")


# ── söz: elle bırakılan dosya varken bozuk LRCLIB cevabı şarkıyı düşürmez ──
def test_soz_dosyasi_varken_bozuk_lrclib_cevabi_dusurmez(tmp_path):
    yol = tmp_path / "a.txt"
    yol.write_text("Hello darkness\nmy old friend\n", encoding="utf-8")

    def bozuk(*_a, **_k):
        raise ValueError("Expecting value")

    s = sozler.bul("X", "A", yol, json_al=bozuk)
    assert s.kaynak == "dosya" and "Hello darkness" in s.metin


# ── temizlik: süre son yüklemeden sayılır ──
def test_temizlik_son_yuklemeye_bakar():
    d = durum.Durum("a", "X", "A", asama="yuklendi")
    d.gecmis = [{"zaman": "2026-09-01T00:00:00", "asama": "yuklendi"},
                {"zaman": "2026-09-02T00:00:00", "asama": "onaylandi"},
                {"zaman": "2026-10-09T00:00:00", "asama": "yuklendi"}]
    assert temizlik.yuklenme(d) == datetime(2026, 10, 9)


# ── takip: gecikme mesajı dağıtımcıya göre; sanatçı hesabı adımları bir kez ──
def test_tunearoda_gecikme_elle_red_komutu_onermez():
    d = durum.Durum("a", "X", "A")
    son = {"zaman": "2026-10-20T03:00:00", "canli": False, "yayin_tarihi": "2026-10-12", "dagitimci": "tunearo",
           "dagitim_durumu": "approved"}
    ((tur, _, metin, _),) = takip.olaylar(d, {}, son, bugun=date(2026, 10, 20))
    assert tur == "gecikme" and "approved" in metin and "dagitim-red" not in metin
    ((_, _, metin, _),) = takip.olaylar(d, {}, {**son, "dagitimci": "routenote"}, bugun=date(2026, 10, 20))
    assert "dagitim-red" in metin


def test_ilk_canli_sarkida_profil_sahiplen_ikincide_oac(tmp_path):
    c = tmp_path / "c"
    for i, canli in enumerate((True, False), 1):
        d = durum.Durum(f"s{i}", "X", f"S{i}", asama="yayinda" if canli else "yuklendi")
        d.yayin = {"son": {"canli": canli, "sanatci_id": "art123" if canli else None}}
        durum.yaz(c, d)
    (o,) = takip.profil_olaylari(c, "Orvane")
    assert o[3] == "profil:spotify_for_artists" and "artist/art123" in o[2] and takip.S4A in o[2]
    with durum.guncelle(c, "s2") as d:
        d.yayin = {"son": {"canli": True, "sanatci_id": "art123"}}
    assert [x[3] for x in takip.profil_olaylari(c, "Orvane")] == ["profil:spotify_for_artists", "profil:oac"]
    for x in takip.profil_olaylari(c, "Orvane") * 2:  # bildirim tekrar anahtarıyla bir kez
        olay.bildir(c, *x)
    assert len(olay.oku(c)) == 2


# ── Tunearo: Apple Music profili UPC'yle bulunur ve bağlanır; OAC talebi ──
class _Api:
    def __init__(self, sanatci=None, oac=None):
        self.sanatci = sanatci or {"id": "art-1", "artist_name": "Orvane", "apple_id": None}
        self.oac, self.cagrilar = oac, []

    def get(self, yol):
        self.cagrilar.append(("GET", yol))
        if yol == "/artists":
            return {"data": [self.sanatci]}
        if yol.endswith("/oac-request"):
            if self.oac is None:
                raise ag.Bulunamadi(yol)
            return self.oac
        raise AssertionError(yol)

    def patch(self, yol, govde):
        self.cagrilar.append(("PATCH", yol, govde))
        self.sanatci.update(govde)
        return {}

    def post(self, yol, govde=None):
        self.cagrilar.append(("POST", yol, govde))
        return {"id": "oac-1", "status": "pending", **(govde or {})}


def _yuklu(c, kimlik, **yukleme):
    d = durum.Durum(kimlik, "X", kimlik.upper(), asama="yuklendi")
    durum.yaz(c, d)
    (c / kimlik / "paket").mkdir(parents=True)
    (c / kimlik / "paket" / "metadata.json").write_text(json.dumps({"yukleme": yukleme}), encoding="utf-8")


def test_apple_profili_upc_ile_baglanir(tmp_path):
    c = tmp_path / "c"
    _yuklu(c, "a", dagitimci="tunearo", upc="5063720454459", dagitim_durumu="live")
    _yuklu(c, "b", dagitimci="tunearo", upc="5063720454460", dagitim_durumu="pending")  # henüz değil
    sorulan = []

    def itunes(url, parametre):
        sorulan.append(parametre["upc"])
        assert url == tunearo.ITUNES and parametre["country"] == "GB"
        return {"results": [{"wrapperType": "collection", "artistName": "Orvane", "artistId": 1789}]}

    api = _Api()
    assert tunearo.apple_bagla(c, api, "Orvane", json_al=itunes) == "1789"
    assert sorulan == ["5063720454459"] and api.sanatci["apple_id"] == "1789"
    assert tunearo.apple_bagla(c, api, "Orvane", json_al=itunes) is None  # bağlı: ezmez, sormaz
    assert sorulan == ["5063720454459"]


def test_apple_baska_sanatci_adiyla_eslesmez(tmp_path):
    c = tmp_path / "c"
    _yuklu(c, "a", dagitimci="tunearo", upc="1", dagitim_durumu="approved")
    api = _Api()
    sonuc = tunearo.apple_bagla(c, api, "Orvane",
                                json_al=lambda u, p: {"results": [{"artistName": "Orvane North", "artistId": 5}]})
    assert sonuc is None and not any(x[0] == "PATCH" for x in api.cagrilar)


def test_oac_talebi_varsa_yenisi_acilmaz():
    api = _Api()
    t = tunearo.oac_iste(api, "Orvane", "https://www.youtube.com/@orvane", "https://www.youtube.com/channel/UCx")
    assert t["status"] == "pending" and api.cagrilar[-1][0] == "POST"
    api2 = _Api(oac={"status": "approved"})
    assert tunearo.oac_iste(api2, "Orvane", "https://www.youtube.com/@o", "https://www.youtube.com/c/x")["status"] \
        == "approved" and not any(x[0] == "POST" for x in api2.cagrilar)
    with pytest.raises(ValueError):
        tunearo.oac_iste(api, "Orvane", "http://kotu", "https://www.youtube.com/c/x")


# ── keşif: hattın yapamadığı tür kendiliğinden listeye girmez ──
def _aday(**k):
    temel = dict(sanatci="Menor Teteu", ad="Ai Ai Ai Bebe", kaynak="stillmore:x", youtube_izlenme=97_967,
                 spotify_dinlenme=35_740_051, sanatci_uyusuyor=True, soz_var=True, sure_sn=180, geri_geldi=False,
                 rakip_cover=0)
    return kesif.Aday(**{**temel, **k})


@pytest.mark.parametrize("turler, uygun", [
    (["brazilian music"], False), (["rap, hip hop"], False), (["electro"], False), (["films, games"], False),
    (["metal"], False), (["pop"], True), (["rock", "alternative"], True), (["soul & funk"], True), ([], True),
])
def test_tur_uygunlugu(turler, uygun):
    a = _aday(turler=turler)
    assert a.uygun is uygun
    assert (a.puan > 0) is uygun and kesif.spotifya_sorulur(a) is uygun
    assert (kesif.hal(a) == "tür uymuyor") is (not uygun)


def test_turu_bilinmeyen_aday_elenmez_ve_listeye_uygun_olan_girer(tmp_path):
    bilinmeyen, uymayan, uygun = _aday(), _aday(sanatci="A", turler=["reggaeton"]), _aday(sanatci="B", turler=["pop"])
    assert bilinmeyen.uygun is None and bilinmeyen.puan > 0
    liste = tmp_path / "liste.toml"
    liste.write_text("", encoding="utf-8")
    (tmp_path / "calisma").mkdir()
    eklenen = kesif.listeye_ekle(kesif.sirala({x.kimlik: x for x in (uymayan, uygun)}), liste,
                                 tmp_path / "calisma", 5)
    assert [x.sanatci for x in eklenen] == ["B"]


def test_denenmemis_kalibi_otomatik_onayda_da_gecerli():
    for stil in ("brazilian music, latin song", "electro, dance song"):
        assert onay.DENENMEMIS.search(stil)
    assert not onay.DENENMEMIS.search("pop, soul song, female lead vocal, clean modern studio recording")


# ── takvim: plan kendi gününe göre ──
def test_bugun_yuklenecek_planin_gunune_gore(tmp_path):
    c = tmp_path / "c"
    d = durum.Durum("a", "X", "A", asama="paketlendi")
    durum.yaz(c, d)
    gelecek = date.today() + timedelta(days=10)
    p = dagitim.plan(c, dagitim.Takvim(baslangic="hemen"), gelecek, {})
    assert p.bugun_yuklenecek is not None and p.sira[0].yukleme == gelecek


# ── gündüz: dağıtım durumu seyrek yoklanır ──
def test_gunduz_dagitim_yoklamasi_seyrek(tmp_path, monkeypatch):
    from yanki import cli

    c = tmp_path / "calisma"
    _yuklu(c, "a", dagitimci="tunearo", release_id="rel-1", dagitim_durumu="pending")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "yayin.toml").write_text(
        '[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "tunearo"\n[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.2\n'
        'ornekleme = 44100\n', encoding="utf-8")
    yoklanan = []

    class Sahte:
        ad, otomatik = "tunearo", True

        def yokla(self, calisma, bildir=None):
            yoklanan.append(calisma)
            return []

    monkeypatch.setattr(dagitim, "sec", lambda ad, kok=None: Sahte())
    simdi = datetime.now()
    cli._seyrek_yokla(tmp_path, simdi)
    cli._seyrek_yokla(tmp_path, simdi + timedelta(hours=1))  # 3 saat dolmadı
    assert len(yoklanan) == 1
    cli._seyrek_yokla(tmp_path, simdi + timedelta(hours=4))
    assert len(yoklanan) == 2


def test_gunduz_yuklu_sarki_yoksa_yoklamaz(tmp_path, monkeypatch):
    from yanki import cli

    monkeypatch.setattr(dagitim, "sec", lambda *a, **k: (_ for _ in ()).throw(AssertionError("sorulmamalı")))
    cli._seyrek_yokla(tmp_path)  # yüklü şarkı yok, ayar dosyası da yok: sessizce çıkar


# ── sağlık: anahtarlar ve disk ──
def test_saglik_anahtar_ve_disk(tmp_path, monkeypatch):
    from dataclasses import replace

    from yanki import ayarlar, saglik

    for k in ("TUNEARO_API_KEY", "TYPESAFE_API_KEY", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"):
        monkeypatch.delenv(k, raising=False)
    a = replace(ayarlar.yukle(), kok=tmp_path)
    (tmp_path / ".env").write_text("TUNEARO_API_KEY=tn_live_x\nSPOTIFY_CLIENT_ID=a\n", encoding="utf-8")
    k = {x.ad: x for x in saglik.anahtar_kontrolleri(a)}
    assert k["Tunearo anahtarı"].tamam and not k["Spotify anahtarı"].tamam and not k["TypeSafe anahtarı"].tamam
    assert "tn_live" not in " ".join(x.ayrinti for x in k.values())  # değer yazılmaz
    assert saglik.disk_kontrolu(a).ad == "disk"


# ── yedek: olay kaydı da yedekte ──
def test_yedek_olay_kaydini_alir(tmp_path):
    from yanki import yedek

    (tmp_path / "calisma").mkdir()
    (tmp_path / "calisma" / "olaylar.jsonl").write_text("{}\n", encoding="utf-8")
    assert tmp_path / "calisma" / "olaylar.jsonl" in yedek.dosyalar(tmp_path)


# ── YouTube: boyutu bilinmeyen videoda boş indirme hata sayılır ──
def test_youtube_bos_indirme_hata(tmp_path, monkeypatch):
    import sys
    import types

    from yanki import kaynak

    class Ydl:
        def __init__(self, *_a, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def extract_info(self, *_a, **_k):
            return {"url": "https://googlevideo/x", "filesize": None}

    class Oturum:
        def __init__(self, **_k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def get(self, *_a, **_k):
            return types.SimpleNamespace(status_code=403, content=b"")

    monkeypatch.setitem(sys.modules, "yt_dlp", types.SimpleNamespace(YoutubeDL=Ydl))
    import curl_cffi.requests as cr

    monkeypatch.setattr(cr, "Session", Oturum)
    with pytest.raises(OSError, match="boş indirme"):
        kaynak._indir_bir("v", tmp_path / "a.m4a")


def test_ag_gecici_hata_sinifi_url_hatasini_kapsar():
    assert issubclass(urllib.error.URLError, ag.GECICI) and issubclass(http.client.IncompleteRead, ag.GECICI)


def test_istekler_ingilizce_ister(monkeypatch):
    """Deezer tür adlarını IP'nin diline çeviriyordu ("brezilya müziği"): tür süzgeci ve stil tanımı İngilizce ister."""
    gorulen = {}

    def urlopen(istek, **_k):
        gorulen.update(istek.headers)
        return _Cevap(b"{}")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    ag.json_al("https://api.deezer.com/genre")
    assert gorulen.get("Accept-language") == "en"


# ── takip: Spotify uygulamasının kendi araması (kotasız) + haftalık Web API ──
def _parca(id_, ad, sanatci, playable=True, isrc=None):
    t = {"id": id_, "name": ad, "is_playable": playable, "artists": [{"id": f"art-{sanatci}", "name": sanatci}]}
    if isrc is not None:
        t["external_ids"] = {"isrc": isrc}
    return t


class _SahteSp:
    """Web API: her çağrı sayılır."""

    def __init__(self):
        self.cagri = []

    def isrc_ara(self, isrc, market):
        self.cagri.append(("isrc", market))
        return [_parca("bizim", "Fix You", "Orvane", isrc=isrc)]

    def ara(self, sorgu, market, adet=20):
        self.cagri.append(("ara", market))
        return [_parca("x", "Fix You", "Coldplay"), _parca("bizim", "Fix You", "Orvane")]


class _SahteIstemci:
    ulke = "TR"

    def __init__(self, isrc_sonuc):
        self.isrc_sonuc, self.cagri = isrc_sonuc, []

    def isrc_ara(self, isrc, market=None):
        self.cagri.append("isrc")
        return self.isrc_sonuc

    def ara(self, sorgu, market, adet=20):
        self.cagri.append(("ara", market))
        return [_parca("bizim", "Fix You", "Orvane")]


def test_takip_istemciyle_kotasiz_web_api_haftalik():
    d = durum.Durum("fix", "Coldplay", "Fix You")
    sp, ist = _SahteSp(), _SahteIstemci([_parca("bizim", "Fix You", "Orvane")])
    pazar = ("GB", "DE", "TR")
    t0 = datetime(2026, 10, 20, 3, 0)
    son = takip.kontrol_et(sp, d, "QZABC2600001", "Orvane", pazar, onceki=None, istemci=ist, simdi=t0)
    assert son["canli"] and son["siralar"] == {"GB": 2, "DE": 2, "TR": 1} and son["arama_sirasi"] == 1
    assert ("isrc", "GB") not in sp.cagri and [c for c in sp.cagri] == [("ara", "GB"), ("ara", "DE")]
    # ertesi gece: Web API'ye hiç gidilmez, TR istemciden, GB/DE önceki ölçüm
    sp.cagri.clear()
    son2 = takip.kontrol_et(sp, d, "QZABC2600001", "Orvane", pazar, onceki=son, istemci=ist,
                            simdi=t0 + timedelta(days=1))
    assert sp.cagri == [] and son2["siralar"] == {"GB": 2, "DE": 2, "TR": 1}
    assert son2["web_kontrol"] == son["web_kontrol"]
    son3 = takip.kontrol_et(sp, d, "QZABC2600001", "Orvane", pazar, onceki=son2, istemci=ist,
                            simdi=t0 + timedelta(days=7))
    assert sp.cagri == [("ara", "GB"), ("ara", "DE")] and son3["web_kontrol"] > son["web_kontrol"]


def test_takip_istemcinin_bulanik_isrc_sonucu_bizim_sayilmaz():
    d = durum.Durum("fix", "Coldplay", "Fix You")
    # ISRC araması yayında olmayan parçada başka şarkılar döndürebiliyor (canlı: GBAYE… → 20 farklı albüm)
    ist = _SahteIstemci([_parca("a", "Fix You", "Coldplay"), _parca("b", "Spinning Around", "Orvane")])
    son = takip.kontrol_et(_SahteSp(), d, "QZABC2600001", "Orvane", ("TR",), istemci=ist)
    assert son["canli"] is False and ist.cagri == ["isrc"]  # canlı değilken ad araması yapılmaz


def test_istemci_aramasi_dusunce_web_apiye_gecer():
    from yanki import stillmore

    class Kopru:
        def ulke(self):
            return "tr"

        def isrc_ara(self, isrc):
            raise stillmore.StillmoreYok("CDP koptu")

        def ara(self, terim, adet=20, islem="searchDesktop"):
            raise stillmore.StillmoreYok("CDP koptu")

    sp = _SahteSp()
    ist = stillmore.IstemciArama(Kopru(), sp)
    assert ist.ulke == "TR"
    assert ist.isrc_ara("QZ")[0]["id"] == "bizim" and ist.ara("Fix You", "TR")[1]["id"] == "bizim"
    assert sp.cagri == [("isrc", "TR"), ("ara", "TR")]
    ist.ara("Fix You", "GB")  # başka pazar doğrudan Web API
    assert sp.cagri[-1] == ("ara", "GB")
    with pytest.raises(stillmore.StillmoreYok):
        stillmore.IstemciArama(Kopru(), None).ara("x", "GB")


def test_kopru_arayuz_sayfasini_bekler(monkeypatch):
    from yanki import stillmore

    deneme = {"n": 0}

    class Gec:
        def __init__(self, port):
            deneme["n"] += 1
            if deneme["n"] < 3:
                raise stillmore.StillmoreYok("Spotify arayüz sayfası bulunamadı")

    monkeypatch.setattr(stillmore, "Kopru", Gec)
    assert isinstance(stillmore.kopru_bekle(uyku=lambda _: None), Gec) and deneme["n"] == 3


def test_takip_uygulama_acilamazsa_web_apiyle(monkeypatch):
    from yanki import cli, stillmore

    class Acilmaz:
        def __init__(self, **_k):
            pass

        def __enter__(self):
            raise stillmore.StillmoreYok("Spotify şu an çalıyor")

    monkeypatch.setattr(stillmore, "Oturum", Acilmaz)
    gelen = []
    assert cli._istemciyle(_SahteSp(), lambda ist: gelen.append(ist) or "tamam", True) == "tamam"
    assert gelen == [None]


# ── sürekli koşu (Scryne: "gece 3'ü beklemeye gerek yok, bilgisayar açıkken hep çalışsın") ──
@pytest.fixture
def surekli(tmp_path, monkeypatch):
    from dataclasses import replace

    from yanki import ayarlar, cli

    a = replace(ayarlar.yukle(), kok=tmp_path)
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: a)
    monkeypatch.setattr(cli.ayarlar, "operasyon_oku", lambda _k: ayarlar.Operasyon(tmp_path))
    monkeypatch.setattr(cli, "_kesif_ayarlari", lambda _k: {"kesif": {"gece_ekle": 2}})
    monkeypatch.setattr(cli, "_spotify_serbest", lambda _op: True)
    import yanki.spotify as sp

    monkeypatch.setattr(sp.Spotify, "__init__", lambda self, kok, *x, **k: setattr(self, "client_id", "x"))
    monkeypatch.setattr(sp.Spotify, "kota", lambda self: {"kilit": 0})
    kosan = []
    for ad, cikti in (("_kesif", "listeye eklendi: X"), ("_hazirla", ""), ("_uret_surekli", "üretilecek bir şey yok"),
                      ("_otomatik_onay", ""), ("_paketle", "paketlenecek onaylı şarkı yok"),
                      ("_dagitim_durum", "tunearo: izlenen yükleme yok"), ("_takip", ""),
                      ("_takvim_hatirlat", "takvim: kuyruk boş"), ("_temizle", ""),
                      ("_yedekle", "yedek güncel (son: …)")):
        monkeypatch.setattr(cli, ad, lambda *_a, ad=ad, cikti=cikti: kosan.append(ad) or print(cikti) or 0)
    (tmp_path / "calisma").mkdir()
    return cli, kosan, tmp_path


def test_surekli_kosu_gunluk_adimlari_zamani_gelince_koşturur(surekli, capsys):
    cli, kosan, kok = surekli
    ns = cli.argparse.Namespace(liste=None, analizsiz=False)
    assert cli._calistir(ns) == 0
    assert {"_kesif", "_dagitim_durum", "_takip", "_temizle"} <= set(kosan)
    assert "── keşif" in capsys.readouterr().out  # iş yapan adım yazılır
    kosan.clear()
    assert cli._calistir(ns) == 0  # 30 dk sonra: günlük/3 saatlik adımlar atlanır
    assert kosan == ["_hazirla", "_uret_surekli", "_otomatik_onay", "_paketle", "_takvim_hatirlat", "_yedekle"]
    assert capsys.readouterr().out == ""  # hiçbir adım iş yapmadı: günlüğe hiçbir şey
    kosan.clear()
    cli._calistir(cli.argparse.Namespace(liste=None, analizsiz=False, hepsi=True))
    assert {"_kesif", "_dagitim_durum", "_takip", "_temizle"} <= set(kosan)


def test_surekli_kosu_spotify_serbest_degilse_kesif_ve_takip_bekler(surekli, monkeypatch):
    cli, kosan, _ = surekli
    monkeypatch.setattr(cli, "_spotify_serbest", lambda _op: False)
    cli._calistir(cli.argparse.Namespace(liste=None, analizsiz=False))
    assert "_kesif" not in kosan and "_takip" not in kosan and "_dagitim_durum" in kosan


@pytest.fixture
def uretim_ortami(tmp_path, monkeypatch):
    from dataclasses import replace

    from yanki import ayarlar, cli, saglik, sistem, uretim

    a = replace(ayarlar.yukle(), kok=tmp_path)
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: a)
    monkeypatch.setattr(sistem, "prizde_mi", lambda: True)
    monkeypatch.setattr(sistem, "bosta_sn", lambda: 0)  # kullanıcı etkin
    monkeypatch.setattr(saglik, "gpu_kullanilan_mib", lambda: 500)
    c = tmp_path / "calisma"
    for i, asama in enumerate(("analiz", "analiz", "onarim", "analiz")):
        d = durum.Durum(f"s{i}", "X", f"S{i}", asama=asama)
        d.gecmis = [{"zaman": f"2026-10-10T0{i}:00:00", "asama": asama}]
        durum.yaz(c, d)
    uretilen = []

    def sahte(_a, calisma, kimlikler, calistir=None):
        uretilen.append(kimlikler)
        return [durum.oku(calisma, k) for k in kimlikler]

    monkeypatch.setattr(uretim, "uret", sahte)
    return cli, ayarlar.Operasyon(tmp_path), uretilen, monkeypatch


def test_surekli_uretim_kullanici_etkinken_de_onarim_once_sinirli(uretim_ortami):
    cli, op, uretilen, _ = uretim_ortami
    assert cli._uret_surekli(None, op) == 0
    assert uretilen == [["s2", "s0"]]  # onarım önce, koşu başına 2 şarkı


@pytest.mark.parametrize("engel", ["gpu", "pil", "bosta"])
def test_surekli_uretim_bekler(uretim_ortami, engel, capsys):
    from dataclasses import replace

    from yanki import saglik, sistem

    cli, op, uretilen, mp = uretim_ortami
    if engel == "gpu":
        mp.setattr(saglik, "gpu_kullanilan_mib", lambda: 7000)
    elif engel == "pil":
        mp.setattr(sistem, "prizde_mi", lambda: False)
    else:
        op = replace(op, surekli_bosta_bekle=True)
    assert cli._uret_surekli(None, op) == 0 and uretilen == []
    assert "üretim bekliyor" in capsys.readouterr().out


def test_spotify_serbest(monkeypatch):
    from yanki import ayarlar, cli, sistem, stillmore

    op = ayarlar.Operasyon(ayarlar.KOK)
    monkeypatch.setattr(stillmore, "cdp_acik", lambda: False)
    monkeypatch.setattr(stillmore, "calisiyor_mu", lambda: False)
    assert cli._spotify_serbest(op)  # kapalı: açılabilir
    monkeypatch.setattr(stillmore, "calisiyor_mu", lambda: True)
    monkeypatch.setattr(sistem, "bosta_sn", lambda: 60)
    assert not cli._spotify_serbest(op)  # Scryne Spotify'ı kullanıyor olabilir
    monkeypatch.setattr(sistem, "bosta_sn", lambda: 3600)
    assert cli._spotify_serbest(op)


def test_surekli_kosu_spotify_kilitliyken_kesfi_ertelir(surekli, monkeypatch):
    """Kilit varken keşif koşsa doğrulayamaz ve günlük hakkı yanardı; kilit kalkınca ilk koşuda yapılır."""
    import time

    import yanki.spotify as sp

    cli, kosan, kok = surekli
    monkeypatch.setattr(sp.Spotify, "kota", lambda self: {"kilit": time.time() + 3600})
    cli._calistir(cli.argparse.Namespace(liste=None, analizsiz=False))
    assert "_kesif" not in kosan
    monkeypatch.setattr(sp.Spotify, "kota", lambda self: {"kilit": 0})
    kosan.clear()
    cli._calistir(cli.argparse.Namespace(liste=None, analizsiz=False))
    assert "_kesif" in kosan
