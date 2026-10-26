"""DistributeMusic.AI (Denetim 7, 2026-10-26): panel kipi, API kipi (sahte istemciyle; canlı denenmedi), paket."""

import json
from datetime import date

import pytest

from yanki import dagitim, distributemusic, durum, paket, takip


class SahteApi:
    def __init__(self, durumlar=None, liste=None, post_hata=None):
        self.istekler, self.yuklenen = [], []
        self.durumlar = durumlar or {}
        self.liste = liste or []
        self.post_hata = post_hata

    def dosya_yukle(self, yol, tur, bekle_sn=600):
        self.yuklenen.append((yol.name, tur))
        return f"uploads/{tur}/{yol.name}"

    def post(self, yol, govde):
        self.istekler.append(("POST", yol, govde))
        if self.post_hata:
            raise self.post_hata
        return {"release_id": "r1", "display_id": "DM-1", "status": "pending"}

    def get(self, yol):
        self.istekler.append(("GET", yol, None))
        if yol == "/releases":
            return {"releases": self.liste}
        if yol.endswith("/links"):
            return {"upc": "123456789012", "tracks": [{"isrc": "QZ-ABC-26-00001"}],
                    "smartlink": {"spotify": "https://open.spotify.com/track/x"}}
        return self.durumlar.get(yol, {"status": "pending"})


AYAR = {"gece": True, "sozlesme_kabul": True, "surum_turu": "Cover", "ai_baglanti": distributemusic.AI_BAGLANTI,
        "api": True}


def _paketli(c, kimlik="adele-hello", adlar=(("Adele", "Adkins"), ("Greg", "Kurstin"))):
    k = c / kimlik / "paket"
    k.mkdir(parents=True)
    (k / "Orvane_-_Hello.wav").write_bytes(b"RIFF....WAVE")
    (k / "Orvane_-_Hello.jpg").write_bytes(b"\xff\xd8jpg")
    meta = {"baslik": "Hello", "sanatci": "Orvane", "orijinal_sanatci": "Adele", "dil": "en", "acik_icerik": False,
            "orijinal_yazar_adlari": [list(x) for x in adlar], "orijinal_yazarlar": [" ".join(x) for x in adlar],
            "paket_dagitimci": "distributemusic"}
    (k / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    d = durum.Durum(kimlik, "Adele", "Hello", analiz={"stil": "soul, pop ballad"})
    d.gec("paketlendi")
    durum.yaz(c, d)
    return d


def test_api_kipi_dosyalari_yukler_ve_yayini_beyanla_acar(tmp_path):
    c = tmp_path / "calisma"
    d = _paketli(c)
    api = SahteApi()
    dm = distributemusic.DistributeMusic(tmp_path, api, AYAR)
    assert dm.otomatik and dm.gece
    bilgi = dagitim.otomatik_yukle(c, dm, d.kimlik, date(2026, 10, 28))
    assert bilgi["release_id"] == "r1" and bilgi["dagitim_durumu"] == "pending"
    assert api.yuklenen == [("Orvane_-_Hello.wav", "audio"), ("Orvane_-_Hello.jpg", "cover")]
    _, yol, govde = api.istekler[-1]
    assert yol == "/releases"
    assert govde["title"] == "Hello" and govde["artist_name"] == "Orvane" and govde["release_type"] == "single"
    assert govde["is_ai_generated"] is True and govde["ai_music_link"] and govde["version_type"] == "Cover"
    assert govde["composer"] == govde["lyricist"] == "Adele Adkins, Greg Kurstin"
    assert govde["release_date"] == "2026-10-28" and govde["song_language"] == "en"
    assert govde["tracks"] == [{"title": "Hello", "audio_path": "uploads/audio/Orvane_-_Hello.wav", "explicit": False}]
    assert "Adele" not in govde["title"] and govde["artist_name"] != "Adele"
    assert durum.oku(c, d.kimlik).asama == "yuklendi"
    assert takip.yukleme_bilgisi(c, d.kimlik)["dagitimci"] == "distributemusic"


def test_sozlesme_kabulu_yoksa_hic_istek_atmaz(tmp_path):
    c = tmp_path / "calisma"
    d = _paketli(c)
    api = SahteApi()
    dm = distributemusic.DistributeMusic(tmp_path, api, {**AYAR, "sozlesme_kabul": False})
    assert not dm.gece
    with pytest.raises(ValueError, match="sozlesme_kabul"):
        dm.yukle(c, d, date(2026, 10, 28))
    assert api.istekler == [] and api.yuklenen == []


def test_soyadi_bilinmeyen_yazarla_gonderilmez(tmp_path):
    c = tmp_path / "calisma"
    d = _paketli(c, adlar=(("Sia", ""),))
    with pytest.raises(ValueError, match="soyad"):
        distributemusic.DistributeMusic(tmp_path, SahteApi(), AYAR).yukle(c, d, date(2026, 10, 28))


def test_cevabi_kaybolan_gonderim_ikinci_yayin_acmaz(tmp_path):
    c = tmp_path / "calisma"
    d = _paketli(c)
    meta_yolu = c / d.kimlik / "paket" / "metadata.json"
    meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
    meta["distributemusic"] = {"durum": "gonderiliyor", "yayin_tarihi": "2026-10-28"}
    meta_yolu.write_text(json.dumps(meta), encoding="utf-8")
    api = SahteApi(liste=[{"release_id": "r9", "title": "Hello", "artist_name": "Orvane", "status": "pending"}])
    bilgi = distributemusic.DistributeMusic(tmp_path, api, AYAR).yukle(c, d, date(2026, 10, 29))
    assert bilgi["release_id"] == "r9" and not any(m == "POST" for m, _, _ in api.istekler)


def test_reddedilen_istek_yeniden_denenebilir_kalir(tmp_path):
    c = tmp_path / "calisma"
    d = _paketli(c)
    api = SahteApi(post_hata=distributemusic.Hata(400, "genre: invalid"))
    with pytest.raises(distributemusic.Hata):
        distributemusic.DistributeMusic(tmp_path, api, AYAR).yukle(c, d, date(2026, 10, 28))
    kayit = json.loads((c / d.kimlik / "paket" / "metadata.json").read_text(encoding="utf-8"))["distributemusic"]
    assert kayit["durum"] == "hata" and "genre" in kayit["son_hata"] and kayit["ses_yolu"]
    api.post_hata = None
    distributemusic.DistributeMusic(tmp_path, api, AYAR).yukle(c, d, date(2026, 10, 28))
    assert len(api.yuklenen) == 2  # dosyalar ikinci kez yüklenmedi


def test_yoklama_kabulde_kodlari_reddi_kuyruga_doner(tmp_path):
    c = tmp_path / "calisma"
    a, b = _paketli(c, "a"), _paketli(c, "b")
    for x in (a, b):
        dagitim.otomatik_yukle(c, distributemusic.DistributeMusic(tmp_path, SahteApi(), AYAR), x.kimlik,
                               date(2026, 10, 28))
    takip.yukleme_kaydet(c, "b", {"release_id": "r2"})
    api = SahteApi(durumlar={"/releases/r1": {"status": "live"},
                             "/releases/r2": {"status": "changes_requested", "feedback": "Cover art has text"}})
    olaylar = []
    sonuc = distributemusic.DistributeMusic(tmp_path, api, AYAR).yokla(c, lambda *x: olaylar.append(x))
    assert {s.kimlik: y for s, y, _ in sonuc} == {"a": "live", "b": "changes_requested"}
    ya = takip.yukleme_bilgisi(c, "a")
    assert ya["upc"] == "123456789012" and ya["isrc"] == "QZABC2600001"
    bd = durum.oku(c, "b")
    assert bd.asama == "paketlendi" and "Cover art has text" in bd.hata
    assert any(o[0] == "red" for o in olaylar)


def test_panel_kipi_anahtarsiz_yoklamaz(tmp_path, monkeypatch):
    monkeypatch.delenv("DISTRIBUTEMUSIC_API_KEY", raising=False)
    dm = distributemusic.DistributeMusic(tmp_path, None, AYAR)
    assert not dm.otomatik and not dm.gece and dm.yokla(tmp_path / "calisma") == []


def test_paket_wav_ve_panel_alanlari(tmp_path):
    yol = tmp_path / "yayin.toml"
    yol.write_text('[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "distributemusic"\n'
                   '[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.2\nornekleme = 44100\n', encoding="utf-8")
    y = paket.yayin_ayarlari(yol)
    assert paket.SES_BICIMI[y.dagitimci] == "wav"
    d = durum.Durum("k", "Adele", "Hello", kunye={"yazarlar": ["Adele Adkins"], "yazar_adlari": [["Adele", "Adkins"]]},
                    analiz={"dil": "en", "stil": "soul ballad"})
    m = paket.metadata(d, y, {"lufs": -14.0, "gercek_tepe_dbtp": -1.2}, 295.0)
    assert m["paket_dagitimci"] == "distributemusic"
    md = paket.yukle_md(m, y, {"ses": "a.wav", "kapak": "a.jpg"})
    assert "DistributeMusic.AI" in md and "Version type:** Cover" in md and "AI-generated:** Yes" in md
    assert "`Adele Adkins`" in md and "16 bit / 44,1 kHz WAV" in md and "Eksik karar" not in md


def test_baska_dagitimci_paketi_bayat(tmp_path):
    c = tmp_path / "calisma"
    d = _paketli(c)
    yol = tmp_path / "yayin.toml"
    yol.write_text('[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "distributemusic"\n'
                   '[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.2\nornekleme = 44100\n', encoding="utf-8")
    y = paket.yayin_ayarlari(yol)
    assert not paket.bayat_mi(c, d, y)
    meta_yolu = c / d.kimlik / "paket" / "metadata.json"
    meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
    del meta["paket_dagitimci"]  # damgasız: RouteNote dönemi (FLAC)
    meta_yolu.write_text(json.dumps(meta), encoding="utf-8")
    assert paket.bayat_mi(c, d, y)


def test_gece_alani_olmayan_dagitimci_gondermez():
    assert dagitim.Elle("distrokid").gece is False


def test_istemci_429da_bekler_401de_erisim_yok(monkeypatch):
    import io
    import urllib.error
    import urllib.request

    cevaplar = [urllib.error.HTTPError("u", 429, "Too Many", {"Retry-After": "1"}, io.BytesIO(b"{}")),
                io.BytesIO(json.dumps({"user_id": "u1"}).encode())]
    gonderilen = []

    class Cevap:
        def __init__(self, b):
            self.b = b

        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

        def read(self):
            return self.b.read()

    def ac(istek, timeout=0):
        gonderilen.append(istek)
        x = cevaplar.pop(0)
        if isinstance(x, Exception):
            raise x
        return Cevap(x)

    monkeypatch.setattr(urllib.request, "urlopen", ac)
    uyunan = []
    api = distributemusic.Istemci("dm_live_x", uyu=uyunan.append)
    assert api.get("/me") == {"user_id": "u1"} and uyunan == [1.0]
    assert gonderilen[0].get_header("Authorization") == "Bearer dm_live_x"
    cevaplar.append(urllib.error.HTTPError("u", 401, "no", {}, io.BytesIO(b'{"detail": "Invalid key"}')))
    with pytest.raises(distributemusic.ErisimYok, match="Invalid key"):
        api.get("/me")
    cevaplar.append(urllib.error.HTTPError("u", 429, "Too Many", {}, io.BytesIO(b"{}")))
    with pytest.raises(distributemusic.Hata):  # POST denenmez (ikinci yayın açılmasın)
        api.post("/releases", {})


def test_cok_parcali_govde():
    govde, tur = distributemusic._cok_parcali({"kind": "audio"}, "a.wav", b"RIFF", "audio/wav")
    sinir = tur.split("boundary=")[1]
    assert govde.startswith(f"--{sinir}\r\n".encode()) and govde.endswith(f"--{sinir}--\r\n".encode())
    assert b'name="kind"\r\n\r\naudio' in govde and b'filename="a.wav"' in govde and b"\r\n\r\nRIFF\r\n" in govde


def test_oda_panel_kipinde_yuklendi_kaydi(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from yanki import ayarlar, sunucu

    monkeypatch.delenv("DISTRIBUTEMUSIC_API_KEY", raising=False)
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "yayin.toml").write_text(
        '[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "distributemusic"\n'
        '[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.2\nornekleme = 44100\n', encoding="utf-8")
    from dataclasses import replace

    a = replace(ayarlar.yukle(), kok=tmp_path)
    c = tmp_path / "calisma"
    _paketli(c)
    istemci = TestClient(sunucu.uygulama(a, c, tmp_path / "liste.toml"), base_url="http://127.0.0.1:8765")
    assert istemci.get("/api/saglik").json() == {"tamam": True}
    assert istemci.post("/api/sanatci/adele-hello/yuklendi", json={"onay": "Başka"}).status_code == 422
    r = istemci.post("/api/sanatci/adele-hello/yuklendi", json={"onay": "hello"})
    assert r.status_code == 200 and durum.oku(c, "adele-hello").asama == "yuklendi"
    assert takip.yukleme_bilgisi(c, "adele-hello")["dagitimci"] == "distributemusic"
    assert istemci.post("/api/sanatci/adele-hello/yuklendi", json={"onay": "hello"}).status_code == 409
