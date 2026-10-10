"""Faz 10: Tunearo API ile otomatik yükleme ve durum yoklama (sahte API; gerçek istek yok)."""

import io
import json
import urllib.error
import urllib.request
from datetime import date

import pytest

from yanki import ag, dagitim, durum, olay, takip, tunearo

AYAR = {"haric_bolgeler": ["US", "CA", "MX", "IN", "PK"], "haric_magazalar": ["amazon", "youtube_cid"]}


class SahteApi:
    """Tunearo'nun yalnız hattın kullandığı uçları; durum bellekte. Her çağrı `cagrilar`a yazılır."""

    def __init__(self, sanatcilar=({"id": "art-1", "artist_name": "Orvane"},)):
        self.sanatcilar = list(sanatcilar)
        self.yayinlar: dict[str, dict] = {}
        self.parcalar: dict[str, dict] = {}
        self.cagrilar: list[tuple] = []
        self.yuklenen: list[tuple] = []
        self._no = 0

    def _id(self, on):
        self._no += 1
        return f"{on}-{self._no}"

    def get(self, yol):
        self.cagrilar.append(("GET", yol))
        p = yol.strip("/").split("/")
        if p == ["artists"]:
            return {"data": self.sanatcilar}
        if p[0] == "releases" and p[-1] == "status":
            r = self.yayinlar.get(p[1])
            if r is None:
                raise ag.Bulunamadi(yol)
            return {k: r.get(k) for k in ("id", "status", "rejection_reason", "upc", "updated_at")}
        if p[0] == "releases" and p[-1] == "tracks":
            return {"data": [t for t in self.parcalar.values() if t["release_id"] == p[1]]}
        if p[0] == "releases" and len(p) == 4:
            return {"track": self.parcalar[p[3]]}
        raise AssertionError(yol)

    def post(self, yol, govde=None):
        self.cagrilar.append(("POST", yol, govde))
        p = yol.strip("/").split("/")
        if p == ["artists"]:
            a = {"id": self._id("art"), **govde}
            self.sanatcilar.append(a)
            return {"artist": a}
        if p == ["releases"]:
            r = {"id": self._id("rel"), "status": "draft", **govde}
            self.yayinlar[r["id"]] = r
            return {"release": r}
        if p[-1] == "artwork-upload-url":
            return {"upload_url": "https://depo/imza-kapak", "path": f"{p[1]}/kapak.jpg"}
        if p[-1] == "audio-upload-url":
            return {"upload_url": "https://depo/imza-ses", "path": f"{p[1]}/{p[3]}/ses.{govde['extension']}"}
        if p[-1] == "tracks":
            govde = {k: v for k, v in govde.items() if k != "lyrics"}  # gerçek API POST'ta sözü düşürüyor
            t = {"id": self._id("trk"), "release_id": p[1], "isrc": None, "audio_file_url": None, **govde}
            self.parcalar[t["id"]] = t
            return {"track": t}
        if p[-1] == "takedown":
            r = self.yayinlar[p[1]]
            if r["status"] != "live":
                raise tunearo.TunearoHatasi(409, f"Cannot takedown release in status '{r['status']}'")
            r["status"] = "takedown_requested"
            return {"release": {"id": p[1], "status": r["status"]}}
        if p[-1] == "submit":
            r = self.yayinlar[p[1]]
            assert r["status"] in ("draft", "rejected") and any(t["release_id"] == p[1] for t in self.parcalar.values())
            r["status"] = "pending"
            return {"release": {"id": p[1], "status": "pending"}}
        raise AssertionError(yol)

    def patch(self, yol, govde):
        self.cagrilar.append(("PATCH", yol, govde))
        p = yol.strip("/").split("/")
        if p[0] == "artists":
            hedef = next(x for x in self.sanatcilar if x["id"] == p[1])
        else:
            hedef = self.parcalar[p[3]] if len(p) == 4 else self.yayinlar[p[1]]
        hedef.update(govde)
        return {}

    def delete(self, yol):
        self.cagrilar.append(("DELETE", yol))
        p = yol.strip("/").split("/")
        assert self.yayinlar[p[1]]["status"] == "draft"  # gerçek API yalnız taslağı siler (409)
        del self.yayinlar[p[1]]
        return {}

    def dosya_yukle(self, adres, yol, tur):
        self.yuklenen.append((adres, yol.name, tur))


def _paket(c, kimlik="keane-sowk", asama="paketlendi", **meta_ek):
    d = durum.Durum(kimlik, "Keane", "Somewhere Only We Know", asama=asama,
                    analiz={"stil": "piano rock, male lead vocal", "dil": "en"},
                    kunye={"sanatci_turleri": ["rock", "pop"]})
    durum.yaz(c, d)
    p = c / kimlik / "paket"
    p.mkdir(parents=True)
    (p / "Orvane_-_Somewhere_Only_We_Know.flac").write_bytes(b"fLaC" + b"\0" * 64)
    (p / "Orvane_-_Somewhere_Only_We_Know.jpg").write_bytes(b"\xff\xd8\xff" + b"\0" * 64)
    meta = {"baslik": "Somewhere Only We Know", "sanatci": "Orvane", "etiket": "Orvane", "tur": "cover",
            "orijinal_sanatci": "Keane", "orijinal_yazarlar": ["Tom Chaplin", "Richard Hughes", "Tim Rice-Oxley"],
            "orijinal_yazar_adlari": [["Tom", "Chaplin"], ["Richard", "Hughes"], ["Tim", "Rice-Oxley"]],
            "orijinal_yil": "2004", "dil": "en", "sure_sn": 236.5, "onizleme_sn": 46.91, "acik_icerik": False,
            "master": {"lufs": -14.0, "gercek_tepe_dbtp": -2.98}, **meta_ek}
    (p / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    (c / kimlik / "soz.txt").write_text("[verse]\nI walked across an empty land\n[00:30.37] I knew the pathway\n\n"
                                        "[chorus]\n[00:46.91] Oh, simple thing\n", encoding="utf-8")
    return d


def _meta(c, kimlik="keane-sowk"):
    return json.loads((c / kimlik / "paket" / "metadata.json").read_text(encoding="utf-8"))


def _dagitimci(tmp_path, api):
    return tunearo.Tunearo(tmp_path, istemci=api, ayar=AYAR)


@pytest.fixture(autouse=True)
def _ffmpegsiz(monkeypatch):
    """FLAC → WAV açma ffmpeg ister (CI'da yok); burada yalnız doğru dosyanın yüklendiği sınanır."""
    def sahte(ses, klasor):
        hedef = klasor / f"{ses.stem}.wav"
        hedef.write_bytes(b"RIFF" + ses.read_bytes())
        return hedef

    monkeypatch.setattr(tunearo, "wav_hazirla", sahte)


# ── eşleme ──────────────────────────────────────────────────
def test_tur_secimi_stilden_sonra_sanatci_turunden_yoksa_pop():
    assert tunearo.tur_sec("alternative rock, pop song") == "Alternative"
    assert tunearo.tur_sec("rap, hip hop song, clean modern studio recording") == "Hip Hop/Rap"
    assert tunearo.tur_sec("emotional piano ballad, female lead vocal") == "Pop"
    assert tunearo.tur_sec("emotional, male lead vocal", ["rock"]) == "Rock"  # stilde tür yoksa sanatçınınki
    assert tunearo.tur_sec("soulful piano ballad") == "Pop"  # "soulful" R&B sayılmaz
    # sanatçı türleri kendi sırasıyla: Adele "pop, soul, …, r&b" → Pop (birleşik metinde R&B/Soul çıkıyordu, canlı)
    assert tunearo.tur_sec("soulful, female lead vocal", ["pop", "soul", "neo soul", "r&b"]) == "Pop"
    assert tunearo.tur_sec("", ["neo soul", "pop"]) == "R&B/Soul" and tunearo.tur_sec("", []) == "Pop"


def test_duz_soz_etiket_ve_zaman_damgasi_yok():
    soz = "[verse]\nI walked\n[00:30.37] I knew\n\n\n\n[chorus]\n[01:02.5] Oh simple\n"
    assert tunearo.duz_soz(soz) == "I walked\nI knew\n\nOh simple"


def test_magaza_ayari_bilinmeyen_kodu_reddeder(tmp_path):
    (tmp_path / "yayin.toml").write_text('[tunearo]\nharic_magazalar = ["amazon", "amazonn"]\n', encoding="utf-8")
    with pytest.raises(ValueError, match="amazonn"):
        tunearo.ayar_oku(tmp_path / "yayin.toml")
    assert tunearo.ayar_oku(tmp_path / "yok.toml") == {"haric_bolgeler": [], "haric_magazalar": []}


# ── yükleme ─────────────────────────────────────────────────
def test_yukleme_uctan_uca_ve_kayit(tmp_path):
    c = tmp_path / "calisma"
    _paket(c)
    api = SahteApi()
    bilgi = dagitim.otomatik_yukle(c, _dagitimci(tmp_path, api), "keane-sowk", date(2026, 11, 5))

    r = api.yayinlar[bilgi["release_id"]]
    assert r["status"] == "pending" and r["artist_ids"] == ["art-1"] and r["release_type"] == "Single"
    assert r["primary_genre"] == "Rock" and r["release_date"] == "2026-11-05" and r["label_name"] == "Orvane"
    assert r["licensed_territories_exclude"] == "US|CA|MX|IN|PK"
    magazalar = r["services"].split("|")
    assert "spotify" in magazalar and "amazon" not in magazalar and "youtube_cid" not in magazalar
    assert len(magazalar) == len(tunearo.MAGAZALAR) - 2
    assert r["copyright_year"] == 2004 and r["copyright_holder"] == "Tom Chaplin, Richard Hughes, Tim Rice-Oxley"
    assert r["producer_copyright_holder"] == "Orvane" and r["cover_artwork_url"].endswith("kapak.jpg")
    (t,) = api.parcalar.values()
    assert t["lyrics"] == "I walked across an empty land\nI knew the pathway\n\nOh, simple thing"
    assert "preview_start_time" not in t and t["producer"] == "Orvane" and t["lyricist"] == t["composer"]
    assert t["audio_file_url"].endswith("ses.wav")  # yükleme ucu yolu bağlamadıysa PATCH ile bağlandı
    # FLAC paket WAV'a açılıp yüklenir (Tunearo deposu hep .wav adıyla saklıyor)
    assert [(y[1], y[2]) for y in api.yuklenen] == [("Orvane_-_Somewhere_Only_We_Know.jpg", "image/jpeg"),
                                                     ("Orvane_-_Somewhere_Only_We_Know.wav", "audio/wav")]
    assert not any(c_[0] == "POST" and c_[1] == "/artists" for c_ in api.cagrilar)  # sanatçı vardı, açılmadı

    d = durum.oku(c, "keane-sowk")
    assert d.asama == "yuklendi"
    y = takip.yukleme_bilgisi(c, "keane-sowk")
    assert y["dagitimci"] == "tunearo" and y["dagitim_durumu"] == "pending" and y["yayin_tarihi"] == "2026-11-05"
    assert y["haric_magazalar"] == ["amazon", "youtube_cid"] and "mekanik_lisans" not in y  # RouteNote varsayılanı yok
    assert _meta(c)["tunearo"]["track_id"] == t["id"]


def test_sanatci_yoksa_bir_kez_acilir(tmp_path):
    c = tmp_path / "calisma"
    _paket(c)
    api = SahteApi(sanatcilar=[{"id": "baska", "artist_name": "Niall"}])
    dagitim.otomatik_yukle(c, _dagitimci(tmp_path, api), "keane-sowk", date(2026, 11, 5))
    acilan = [x for x in api.cagrilar if x[:2] == ("POST", "/artists")]
    assert len(acilan) == 1 and acilan[0][2] == {"artist_name": "Orvane"}


def test_taslak_gonderilmez_sonraki_cagri_ayni_yayini_tamamlar(tmp_path):
    c = tmp_path / "calisma"
    _paket(c)
    api = SahteApi()
    t = _dagitimci(tmp_path, api)
    assert dagitim.otomatik_yukle(c, t, "keane-sowk", date(2026, 11, 5), gonder=False) == {}
    assert durum.oku(c, "keane-sowk").asama == "paketlendi" and "yukleme" not in _meta(c)
    (rid,) = api.yayinlar
    assert api.yayinlar[rid]["status"] == "draft" and _meta(c)["tunearo"]["durum"] == "draft"

    bilgi = dagitim.otomatik_yukle(c, t, "keane-sowk", date(2026, 11, 6))
    assert bilgi["release_id"] == rid and len(api.yayinlar) == 1 and len(api.parcalar) == 1  # kota yanmadı
    assert api.yayinlar[rid]["status"] == "pending" and api.yayinlar[rid]["release_date"] == "2026-11-06"


def test_gonderilmis_ama_kaydedilememis_yayin_yeniden_gonderilmez(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, tunearo={"release_id": "rel-9", "track_id": "trk-9"})
    api = SahteApi()
    api.yayinlar["rel-9"] = {"id": "rel-9", "status": "pending", "upc": None}
    bilgi = dagitim.otomatik_yukle(c, _dagitimci(tmp_path, api), "keane-sowk", date(2026, 11, 5))
    assert bilgi["release_id"] == "rel-9" and bilgi["dagitim_durumu"] == "pending"
    assert not api.yuklenen and all(x[0] == "GET" for x in api.cagrilar)
    assert durum.oku(c, "keane-sowk").asama == "yuklendi"


def test_panelden_silinen_taslak_bastan_acilir(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, tunearo={"release_id": "silindi", "track_id": "x"})
    api = SahteApi()
    bilgi = dagitim.otomatik_yukle(c, _dagitimci(tmp_path, api), "keane-sowk", date(2026, 11, 5))
    assert bilgi["release_id"] != "silindi" and _meta(c)["tunearo"]["release_id"] == bilgi["release_id"]


def test_reddedilen_paket_duzeltilmeden_yuklenmez(tmp_path):
    c = tmp_path / "calisma"
    _paket(c)
    with durum.guncelle(c, "keane-sowk") as d:
        d.gec("paketlendi", f"{dagitim.RED_ONEKI}kapak")
    with pytest.raises(ValueError, match="reddetti"):
        dagitim.otomatik_yukle(c, _dagitimci(tmp_path, SahteApi()), "keane-sowk", date(2026, 11, 5))


# ── durum yoklama ───────────────────────────────────────────
def _yuklenmis(tmp_path):
    c = tmp_path / "calisma"
    _paket(c)
    api = SahteApi()
    t = _dagitimci(tmp_path, api)
    bilgi = dagitim.otomatik_yukle(c, t, "keane-sowk", date(2026, 11, 5))
    return c, api, t, bilgi["release_id"]


def test_yoklama_kabulde_isrc_ve_upc_yazar_bir_kez_bildirir(tmp_path):
    c, api, t, rid = _yuklenmis(tmp_path)
    bildir = lambda *a: olay.bildir(c, *a)  # noqa: E731
    api.yayinlar[rid].update(status="approved", upc="5063720454459")
    (trk,) = api.parcalar.values()
    trk["isrc"] = "GB-GXK-26-00059"
    ((d, yeni, eski),) = t.yokla(c, bildir)
    assert (yeni, eski) == ("approved", "pending")
    y = takip.yukleme_bilgisi(c, "keane-sowk")
    assert y["isrc"] == "GBGXK2600059" and y["upc"] == "5063720454459" and y["dagitim_durumu"] == "approved"
    t.yokla(c, bildir)  # değişiklik yok → yeni bildirim yok
    api.yayinlar[rid]["status"] = "live"
    t.yokla(c, bildir)
    turler = [(o["tur"], o["metin"].split(" ")[0]) for o in olay.oku(c)]
    assert [x[0] for x in turler] == ["dagitim", "dagitim"] and durum.oku(c, "keane-sowk").asama == "yuklendi"
    # Spotify'da görülünce yayinda'ya `yanki takip` geçirir; ISRC artık orada


def test_yoklama_redde_paketlendiye_doner_neden_kaydedilir(tmp_path):
    c, api, t, rid = _yuklenmis(tmp_path)
    neden = "Your uploaded release has been flagged as a potential derivative work.\n\nPlease ensure you hold rights."
    api.yayinlar[rid].update(status="rejected", rejection_reason=neden, updated_at="2026-10-20T10:00:00")
    t.yokla(c, lambda *a: olay.bildir(c, *a))
    d = durum.oku(c, "keane-sowk")
    assert d.asama == "paketlendi" and d.hata.startswith(dagitim.RED_ONEKI + "Tunearo: Your uploaded")
    assert "Please ensure" not in d.hata  # ilk paragraf
    meta = _meta(c)
    assert "yukleme" not in meta and meta["yukleme_gecmisi"][0]["red_metni"] == neden
    assert meta["tunearo"]["release_id"] == rid  # yeniden gönderimde aynı yayın düzeltilir
    (o,) = olay.oku(c)
    assert o["tur"] == "red" and "Tunearo reddetti" in o["baslik"]

    # düzeltilip yeniden paketlenince aynı yayın ve parça yeniden gönderilir (kota yanmaz)
    with durum.guncelle(c, "keane-sowk") as x:
        x.gec("paketlendi")
    dagitim.otomatik_yukle(c, t, "keane-sowk", date(2026, 11, 12))
    assert len(api.yayinlar) == 1 and len(api.parcalar) == 1 and api.yayinlar[rid]["status"] == "pending"


def test_yoklama_baska_dagitimciya_ve_kayitsiz_yayina_dokunmaz(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, kimlik="rn", asama="yuklendi", yukleme={"dagitimci": "routenote", "isrc": "GXM2X2626596"})
    api = SahteApi()
    assert _dagitimci(tmp_path, api).yokla(c) == [] and api.cagrilar == []


# ── takvim kapısı (etkin dağıtımcıya göre) ──────────────────
def _yukleme(c, kimlik, asama, **yukleme):
    _paket(c, kimlik=kimlik, asama=asama, **({"yukleme": yukleme} if yukleme else {}))
    with durum.guncelle(c, kimlik) as d:
        d.gecmis.append({"zaman": "2026-10-08T12:00:00", "asama": "yuklendi", "hata": None})


def test_ilk_kabul_kapisi_etkin_dagitimciya_bakar(tmp_path):
    c = tmp_path / "calisma"
    t = dagitim.Takvim()
    _yukleme(c, "rn", "yuklendi", dagitimci="routenote")
    _paket(c, kimlik="kuyruk")
    # RouteNote incelemesi Tunearo'yu bekletmez; eski kural (dağıtımcısız) bekletir
    assert dagitim.plan(c, t, date(2026, 10, 20), {}).beklemede
    p = dagitim.plan(c, t, date(2026, 10, 20), {}, dagitimci="tunearo")
    assert p.beklemede is None and p.sira[0].kimlik == "kuyruk"
    # ilk Tunearo yüklemesi incelemede → ikinci yok
    _yukleme(c, "tn", "yuklendi", dagitimci="tunearo", dagitim_durumu="pending")
    p = dagitim.plan(c, t, date(2026, 10, 20), {}, dagitimci="tunearo")
    assert "ilk kabul bekleniyor" in p.beklemede
    # kabul → takvim açılır
    meta = _meta(c, "tn")
    meta["yukleme"]["dagitim_durumu"] = "approved"
    (c / "tn" / "paket" / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    assert dagitim.plan(c, t, date(2026, 10, 20), {}, dagitimci="tunearo").beklemede is None


def test_ilk_kabul_kapisi_redden_sonra_yeni_yukleme_yapmaz(tmp_path):
    c = tmp_path / "calisma"
    _yukleme(c, "tn", "yuklendi", dagitimci="tunearo", dagitim_durumu="pending")
    _paket(c, kimlik="kuyruk")
    dagitim.red_kaydet(c, "tn", "Tunearo: derivative work")
    p = dagitim.plan(c, dagitim.Takvim(), date(2026, 10, 20), {}, dagitimci="tunearo")
    assert "reddetti" in p.beklemede and "yanki yukle" in p.beklemede and p.duzeltme == ["tn"]
    assert dagitim.plan(c, dagitim.Takvim(baslangic="hemen"), date(2026, 10, 20), {},
                        dagitimci="tunearo").sira[0].kimlik == "kuyruk"


def test_takvim_sirasi_gelince_gece_kosusu_yukler(tmp_path, monkeypatch):
    from yanki import cli

    c = tmp_path / "calisma"
    _paket(c, kimlik="kuyruk")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "yayin.toml").write_text(
        '[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "tunearo"\n[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.2\n'
        'ornekleme = 44100\n[takvim]\nacik = true\n[tunearo]\nharic_magazalar = ["amazon"]\n', encoding="utf-8")
    api = SahteApi()
    monkeypatch.setattr(tunearo.Istemci, "kokten", classmethod(lambda cls, kok: api))
    assert cli._takvim_hatirlat(tmp_path) == 0
    assert durum.oku(c, "kuyruk").asama == "yuklendi" and len(api.yayinlar) == 1
    (o,) = olay.oku(c)
    assert o["tur"] == "dagitim" and "Tunearo incelemesine" in o["metin"]
    assert cli._takvim_hatirlat(tmp_path) == 0 and len(api.yayinlar) == 1  # kuyruk boş, ikinci yükleme yok


# ── istemci ─────────────────────────────────────────────────
def test_istemci_postu_yeniden_denemez_get_i_dener_dogrulama_hatasini_okur(monkeypatch):
    cagri = []

    def sahte(istek, timeout):
        cagri.append(istek.get_method())
        if istek.get_method() == "PATCH":
            govde = json.dumps({"error": "validation", "issues": [{"field": "release_type", "message": "Expected"}]})
            raise urllib.error.HTTPError(istek.full_url, 422, "x", {}, io.BytesIO(govde.encode()))
        raise urllib.error.HTTPError(istek.full_url, 502, "x", {}, io.BytesIO(b"{}"))

    monkeypatch.setattr(urllib.request, "urlopen", sahte)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    api = tunearo.Istemci("tn_test")
    with pytest.raises(tunearo.TunearoHatasi):
        api.post("/releases", {"title": "x"})
    assert cagri == ["POST"]
    with pytest.raises(tunearo.TunearoHatasi):
        api.get("/artists")
    assert cagri[1:] == ["GET"] * 3
    with pytest.raises(tunearo.TunearoHatasi, match="release_type: Expected"):
        api.patch("/releases/x", {})
    with pytest.raises(tunearo.AyarYok):
        tunearo.Istemci("")


def test_yazarsiz_cover_gonderilmez(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, orijinal_yazarlar=[], orijinal_yazar_adlari=[])
    api = SahteApi()
    with pytest.raises(ValueError, match="orijinal yazarlar"):
        dagitim.otomatik_yukle(c, _dagitimci(tmp_path, api), "keane-sowk", date(2026, 11, 5))
    assert api.cagrilar == [] and durum.oku(c, "keane-sowk").asama == "paketlendi"


def test_takip_tunearo_isrc_beklerken_elle_komut_onermez(tmp_path):
    c, _api, _t, _rid = _yuklenmis(tmp_path)
    ((_d, uyarilar),) = takip.takip_et(None, c, "Orvane", ["GB"])
    assert "incelemesi sürüyor (pending)" in uyarilar[0] and "yanki yuklendi" not in uyarilar[0]


# ── gözden geçirme bulguları (2026-10-10): kaydedilemeyen gönderim, tek yayının yoklama hatası, yarım yükleme sırası
class GonderimDuser(SahteApi):
    """Gönderim sunucuda gerçekleşir ama cevap gelmez (zaman aşımı, süreç düştü)."""

    def post(self, yol, govde=None):
        sonuc = super().post(yol, govde)
        if yol.endswith("/submit") and not getattr(self, "bir_kez", False):
            self.bir_kez = True
            raise tunearo.TunearoHatasi(None, "zaman aşımı")
        return sonuc


def test_kaydedilemeyen_gonderim_kapiyi_tutar_yeniden_gonderilmez(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, kimlik="a")
    _paket(c, kimlik="b")
    api = GonderimDuser()
    t = _dagitimci(tmp_path, api)
    with pytest.raises(tunearo.TunearoHatasi):
        dagitim.otomatik_yukle(c, t, "a", date(2026, 11, 5))
    assert durum.oku(c, "a").asama == "paketlendi" and _meta(c, "a")["tunearo"]["durum"] == "gonderiliyor"
    # b daha yüksek puanlı olsa da: a incelemede sayılır (ikinci gönderim yok) ve kuyruğun başında
    p = dagitim.plan(c, dagitim.Takvim(), date(2026, 10, 20), {"b": 9e9}, dagitimci="tunearo")
    assert "incelemede" in p.beklemede and p.sira[0].kimlik == "a"
    # sonraki koşu: yayın pending → yeniden gönderilmez, ilk tarihle kaydedilir
    bilgi = dagitim.otomatik_yukle(c, t, "a", date(2026, 11, 20))
    assert bilgi["yayin_tarihi"] == "2026-11-05" and durum.oku(c, "a").asama == "yuklendi"
    assert sum(x[1].endswith("/submit") for x in api.cagrilar if x[0] == "POST") == 1


def test_kaydedilemeyen_gonderim_reddedildiyse_once_red_kaydedilir(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, kimlik="a")
    api = GonderimDuser()
    t = _dagitimci(tmp_path, api)
    with pytest.raises(tunearo.TunearoHatasi):
        dagitim.otomatik_yukle(c, t, "a", date(2026, 11, 5))
    (rid,) = api.yayinlar
    api.yayinlar[rid].update(status="rejected", rejection_reason="Artwork", updated_at="x")
    bilgi = dagitim.otomatik_yukle(c, t, "a", date(2026, 11, 5))  # sessizce yeniden göndermez
    assert bilgi["dagitim_durumu"] == "rejected" and api.yayinlar[rid]["status"] == "rejected"
    t.yokla(c, lambda *a: olay.bildir(c, *a))
    assert durum.oku(c, "a").hata.startswith(dagitim.RED_ONEKI) and olay.oku(c)[0]["tur"] == "red"
    with durum.guncelle(c, "a") as x:  # düzeltildi, yeniden paketlendi
        x.gec("paketlendi")
    dagitim.otomatik_yukle(c, t, "a", date(2026, 11, 12))
    assert api.yayinlar[rid]["status"] == "pending" and len(api.yayinlar) == 1


def test_bir_yayinin_yoklama_hatasi_digerlerini_durdurmaz(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, kimlik="a")
    _paket(c, kimlik="b")
    api = SahteApi()
    t = _dagitimci(tmp_path, api)
    dagitim.otomatik_yukle(c, t, "a", date(2026, 11, 5))
    dagitim.otomatik_yukle(c, t, "b", date(2026, 11, 12))
    ra, rb = api.yayinlar
    del api.yayinlar[ra]  # panelden silinmiş
    api.yayinlar[rb]["status"] = "approved"
    sonuc = {d.kimlik: yeni for d, yeni, _ in t.yokla(c, lambda *a: olay.bildir(c, *a))}
    assert sonuc == {"a": "bulunamadi", "b": "approved"}
    assert takip.yukleme_bilgisi(c, "b")["dagitim_durumu"] == "approved"
    assert any(o["tur"] == "kayip" and "bulunamadı" in o["metin"] for o in olay.oku(c))


def test_yarim_kalan_taslak_kuyrugun_basina_gecer(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, kimlik="taslak", tunearo={"release_id": "rel-1", "durum": "draft"})
    _paket(c, kimlik="populer")
    p = dagitim.plan(c, dagitim.Takvim(), date(2026, 10, 20), {"populer": 9e9}, dagitimci="tunearo")
    assert [x.kimlik for x in p.sira] == ["taslak", "populer"]


def test_spotify_profili_tunearo_sanatcisina_baglanir(tmp_path):
    c = tmp_path / "calisma"
    api = SahteApi()
    assert tunearo.profil_bagla(c, api, "Orvane") is None  # henüz Spotify'da yok
    for kimlik, profil in (("a", "sp-1"), ("b", "sp-1"), ("c", "sp-2")):
        d = durum.Durum(kimlik, "X", kimlik, asama="yayinda", yayin={"son": {"canli": True, "sanatci_id": profil}})
        durum.yaz(c, d)
    bildirilen = []
    assert tunearo.profil_bagla(c, api, "Orvane", lambda *a: bildirilen.append(a)) == "sp-1"
    assert api.sanatcilar[0]["spotify_id"] == "sp-1"
    assert [b[1] for b in bildirilen] == ["Spotify profili bölünmüş", "Spotify profili bağlandı"]
    assert tunearo.profil_bagla(c, api, "Orvane") is None  # zaten bağlı: istek yok
    api.sanatcilar[0]["spotify_id"] = "elle"
    bildirilen.clear()
    assert tunearo.profil_bagla(c, api, "Orvane", lambda *a: bildirilen.append(a)) is None
    assert api.sanatcilar[0]["spotify_id"] == "elle" and "başka profile" in bildirilen[-1][1]


def test_kazanc_yalniz_bizim_yayinlar_ve_onbellek(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, kimlik="a", yukleme={"dagitimci": "tunearo", "release_id": "rel-a"},
           yukleme_gecmisi=[{"dagitimci": "tunearo", "release_id": "rel-eski", "red": "x"}])
    _paket(c, kimlik="b", yukleme={"dagitimci": "routenote", "isrc": "X"})

    class Kazanc:
        cagri = 0

        def get(self, yol):
            Kazanc.cagri += 1
            rid = yol.split("/")[2]
            return {"lifetime_earnings": {"rel-a": 1.5, "rel-eski": 0.25}[rid], "this_month_earnings": 0.5,
                    "by_source": [{"source": "Spotify - Stream", "amount": 1.0}]}

    v = tunearo.kazanc(c, Kazanc())
    assert v["toplam"] == 1.75 and v["kaynaklar"] == [{"kaynak": "Spotify - Stream", "tutar": 2.0}]
    assert sorted(v["yayinlar"]) == ["rel-a", "rel-eski"] and Kazanc.cagri == 2
    tunearo.kazanc(c, Kazanc())
    assert Kazanc.cagri == 2  # önbellekten


# ── geri çekme ve sürekli takvim (Scryne, 2026-10-10: "hepsini kaldıralım, sürekli şarkı atalım") ──
def test_incelemedeki_yayin_isaretlenir_red_gelince_ayni_yayin_kuyruga_doner(tmp_path):
    c, api, t, rid = _yuklenmis(tmp_path)
    monkey_sec = dagitim.sec
    try:
        dagitim.sec = lambda ad, kok=None: t  # noqa: E731
        assert dagitim.geri_cek(c, "keane-sowk", "baştan yayın") == "bekliyor"
    finally:
        dagitim.sec = monkey_sec
    assert durum.oku(c, "keane-sowk").asama == "yuklendi" and takip.yukleme_bilgisi(c, "keane-sowk")["geri_cek"]
    ((_, s, _),) = t.yokla(c)  # hâlâ incelemede: dokunulmaz
    assert s == "geri çekilecek (pending)" and api.yayinlar[rid]["status"] == "pending"
    # arkadaş panelden reddetti → red sayılmaz, aynı yayın düzeltilip yeniden gönderilir (kota yanmaz)
    api.yayinlar[rid].update(status="rejected", rejection_reason="geri çekildi")
    ((d, s, _),) = t.yokla(c, lambda *a: olay.bildir(c, *a))
    assert s == "geri_cekildi" and d.asama == "onaylandi" and not d.hata
    with durum.guncelle(c, "keane-sowk") as x:  # gece koşusu güncel ayarlarla yeniden paketler
        x.gec("paketlendi")
    meta = _meta(c)
    assert "yukleme" not in meta and meta["yukleme_gecmisi"][-1]["geri_cekildi"] == "baştan yayın"
    assert "red" not in meta["yukleme_gecmisi"][-1] and meta["tunearo"]["release_id"] == rid
    assert dagitim.plan(c, dagitim.Takvim(baslangic="surekli"), date.today(), {},
                        dagitimci="tunearo").bugun_yuklenecek.kimlik == "keane-sowk"
    dagitim.otomatik_yukle(c, t, "keane-sowk", date(2026, 10, 12))
    assert len(api.yayinlar) == 1 and len(api.parcalar) == 1
    assert api.yayinlar[rid]["status"] == "pending" and api.yayinlar[rid]["release_date"] == "2026-10-12"


def test_canli_yayina_takedown_istenir_sonraki_yukleme_yeni_yayin_acar(tmp_path):
    c, api, t, rid = _yuklenmis(tmp_path)
    api.yayinlar[rid]["status"] = "live"
    assert t.geri_cek(c, durum.oku(c, "keane-sowk"), "baştan yayın") == "tamam"
    assert api.yayinlar[rid]["status"] == "takedown_requested"
    meta = _meta(c)
    assert "tunearo" not in meta and meta["tunearo_gecmisi"][0]["release_id"] == rid
    with durum.guncelle(c, "keane-sowk") as x:
        x.gec("paketlendi")
    dagitim.otomatik_yukle(c, t, "keane-sowk", date(2026, 10, 12))
    assert len(api.yayinlar) == 2


def test_onaylanmis_yayin_canliya_cikinca_yoklama_takedown_ister(tmp_path):
    c, api, t, rid = _yuklenmis(tmp_path)
    api.yayinlar[rid]["status"] = "approved"
    assert t.geri_cek(c, durum.oku(c, "keane-sowk"), "baştan") == "bekliyor"  # takedown yalnız canlıda (409)
    api.yayinlar[rid]["status"] = "live"
    ((d, s, _),) = t.yokla(c)
    assert s == "geri_cekildi" and d.asama == "onaylandi" and api.yayinlar[rid]["status"] == "takedown_requested"


def test_taslak_silinir(tmp_path):
    c = tmp_path / "calisma"
    _paket(c, asama="yuklendi")
    api = SahteApi()
    api.yayinlar["rel-9"] = {"id": "rel-9", "status": "draft"}
    takip.yukleme_kaydet(c, "keane-sowk", {"release_id": "rel-9"}, "tunearo")
    assert _dagitimci(tmp_path, api).geri_cek(c, durum.oku(c, "keane-sowk"), "x") == "tamam"
    assert "rel-9" not in api.yayinlar and durum.oku(c, "keane-sowk").asama == "onaylandi"


def test_elle_dagitimcida_panelden_kaldirilmadan_kaydedilmez(tmp_path):
    c = tmp_path / "calisma"
    _yukleme(c, "rn", "yuklendi", dagitimci="routenote", isrc="GXM2X2626596")
    with pytest.raises(ValueError, match="--kaldirildi"):
        dagitim.geri_cek(c, "rn", "baştan")
    assert durum.oku(c, "rn").asama == "yuklendi"
    assert dagitim.geri_cek(c, "rn", "baştan", kaldirildi=True) == "tamam"
    d, meta = durum.oku(c, "rn"), _meta(c, "rn")
    assert d.asama == "onaylandi" and not d.hata and meta["yukleme_gecmisi"][0]["isrc"] == "GXM2X2626596"


def test_surekli_takvim_kabul_beklemez_red_varken_durur(tmp_path):
    c = tmp_path / "calisma"
    t = dagitim.Takvim(haftada=7, yayin_on_gun=1, baslangic="surekli")
    _yukleme(c, "tn", "yuklendi", dagitimci="tunearo", dagitim_durumu="pending")
    _paket(c, kimlik="kuyruk")
    p = dagitim.plan(c, t, date(2026, 10, 20), {}, dagitimci="tunearo")
    assert p.beklemede is None
    assert (p.sira[0].yukleme, p.sira[0].yayin_tarihi) == (date(2026, 10, 20), date(2026, 10, 21))
    dagitim.red_kaydet(c, "tn", "Tunearo: derivative work")
    p = dagitim.plan(c, t, date(2026, 10, 20), {}, dagitimci="tunearo")
    assert "reddetti" in p.beklemede and p.bugun_yuklenecek is None
