"""Denetim 4 (2026-10-11): canlı günlükte bulunan hatalar. Her test düzeltmesiz kodda kırmızı."""

import io
import json
import socket
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta
from types import SimpleNamespace

import pytest

from tests.test_tunearo import SahteApi, _paket, _sinirsiz_ayar, _yukleme
from yanki import ag, dagitim, durum, olay, tunearo


# ── ad çözümleme: IPv6 sorgusu zaman aşımına düşen ad (dashboard.tunearo.com, her istek ~12 sn) ──
def test_ipv6_sorgusu_asili_kalsa_da_ipv4_adresiyle_hemen_doner(monkeypatch):
    cagrilar = []

    def sahte(host, port, family=0, type=0, proto=0, flags=0):
        cagrilar.append(family)
        if family == socket.AF_INET6:
            time.sleep(3)  # bu ağda AAAA zaman aşımı
            raise socket.gaierror(socket.EAI_NONAME, "yok")
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("185.158.133.1", port))]

    monkeypatch.setattr(ag, "_gercek_getaddrinfo", sahte)
    monkeypatch.setattr(ag, "_dns_onbellek", {})
    t = time.monotonic()
    sonuc = socket.getaddrinfo("ornek-yavas.test", 443, 0, socket.SOCK_STREAM)
    assert time.monotonic() - t < 1.5
    assert sonuc[0][4][0] == "185.158.133.1"
    n = len(cagrilar)
    assert socket.getaddrinfo("ornek-yavas.test", 443, 0, socket.SOCK_STREAM) == sonuc  # önbellek
    assert len(cagrilar) == n


def test_ad_cozulemezse_hata_cagirana_ulasir(monkeypatch):
    def sahte(host, port, family=0, type=0, proto=0, flags=0):
        raise socket.gaierror(socket.EAI_NONAME, "yok")

    monkeypatch.setattr(ag, "_gercek_getaddrinfo", sahte)
    monkeypatch.setattr(ag, "_dns_onbellek", {})
    with pytest.raises(socket.gaierror):
        socket.getaddrinfo("olmayan.test", 443)


def test_ip_adresi_ve_tek_aile_istegi_dogrudan_gecer(monkeypatch):
    cagrilar = []
    monkeypatch.setattr(ag, "_gercek_getaddrinfo", lambda *a: cagrilar.append(a) or [])
    socket.getaddrinfo("127.0.0.1", 80)
    socket.getaddrinfo("ornek.test", 80, socket.AF_INET)
    assert [c[2] for c in cagrilar] == [0, socket.AF_INET]


# ── Tunearo: hesap düzeyi erişim kapanması (2026-10-11 12:47, "API access not enabled for this user") ──
def _http_hatasi(kod: int, metin: str):
    def urlopen(*_a, **_k):
        raise urllib.error.HTTPError("https://x", kod, "Forbidden", {}, io.BytesIO(json.dumps({"error": metin})
                                                                                   .encode()))
    return urlopen


def test_hesap_duzeyi_403_erisim_yok_parca_kotasi_degil(monkeypatch):
    i = tunearo.Istemci("anahtar")
    monkeypatch.setattr(urllib.request, "urlopen", _http_hatasi(403, "API access not enabled for this user"))
    with pytest.raises(tunearo.ErisimYok):
        i.get("/artists")
    monkeypatch.setattr(urllib.request, "urlopen", _http_hatasi(403, "Track limit reached"))
    with pytest.raises(tunearo.TunearoHatasi) as e:
        i.post("/releases/r/tracks", {})
    assert not isinstance(e.value, tunearo.ErisimYok) and e.value.kod == 403
    monkeypatch.setattr(urllib.request, "urlopen", _http_hatasi(401, "Invalid API key"))
    with pytest.raises(tunearo.ErisimYok):
        i.get("/artists")


class KapaliApi(SahteApi):
    def get(self, yol):
        self.cagrilar.append(("GET", yol))
        raise tunearo.ErisimYok(403, f"GET {yol}: API access not enabled for this user")

    def post(self, yol, govde=None):
        self.cagrilar.append(("POST", yol, govde))
        raise tunearo.ErisimYok(403, f"POST {yol}: API access not enabled for this user")


def _yuklu_uc(c):
    for k in ("a", "b", "c"):
        _yukleme(c, k, "yuklendi", dagitimci="tunearo", dagitim_durumu="pending", release_id=f"rel-{k}")


def test_dagitim_yoklamasi_erisim_kapaninca_ilk_istekte_durur_bir_kez_bildirir(tmp_path, monkeypatch):
    """Önce 21 yayının her biri ayrı 403 yazıyor (her biri 12 sn), adım "sorunlu" bitip koşu kod 1 dönüyordu."""
    from yanki import cli

    c = tmp_path / "calisma"
    _yuklu_uc(c)
    _sinirsiz_ayar(tmp_path)
    api = KapaliApi()
    monkeypatch.setattr(tunearo.Istemci, "kokten", classmethod(lambda cls, kok: api))
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: SimpleNamespace(kok=tmp_path))
    assert cli._dagitim_durum(SimpleNamespace()) == 0
    assert len(api.cagrilar) == 1
    assert tunearo.erisim_durumu(c)["mesaj"].endswith("API access not enabled for this user")
    assert cli._dagitim_durum(SimpleNamespace()) == 0
    assert [o["baslik"] for o in olay.oku(c)] == ["Tunearo API erişimi kapalı"]  # günde bir
    assert all(durum.oku(c, k).asama == "yuklendi" for k in "abc")  # yerel kayıtlara dokunulmaz
    assert "Tunearo API erişimi kapalı" in " ".join(str(v) for v in cli.ozet(tmp_path).values() if v) or \
        cli.ozet(tmp_path)["tunearo_erisim_yok"]


def test_erisim_acilinca_kayit_silinir(tmp_path, monkeypatch):
    from yanki import cli

    c = tmp_path / "calisma"
    _yuklu_uc(c)
    _sinirsiz_ayar(tmp_path)
    tunearo.erisim_kaydet(c, tunearo.ErisimYok(403, "API access not enabled"))
    api = SahteApi()
    for k in "abc":
        api.yayinlar[f"rel-{k}"] = {"id": f"rel-{k}", "status": "pending"}
    monkeypatch.setattr(tunearo.Istemci, "kokten", classmethod(lambda cls, kok: api))
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: SimpleNamespace(kok=tmp_path))
    assert cli._dagitim_durum(SimpleNamespace()) == 0
    assert tunearo.erisim_durumu(c) is None


def test_takvim_yuklemesi_erisim_kapaninca_durur_kuyruk_bekler(tmp_path, monkeypatch):
    from yanki import cli

    c = tmp_path / "calisma"
    for k in ("a", "b", "c"):
        _paket(c, kimlik=k)
    _sinirsiz_ayar(tmp_path)
    api = KapaliApi()
    monkeypatch.setattr(tunearo.Istemci, "kokten", classmethod(lambda cls, kok: api))
    assert cli._takvim_hatirlat(tmp_path) == 0
    assert len(api.cagrilar) == 1 and all(durum.oku(c, k).asama == "paketlendi" for k in "abc")
    # erişim kapalı görüldü: sonraki koşular yüklemeyi denemez, takvim bekler
    t = dagitim.takvim_oku(tmp_path / "config" / "yayin.toml")
    assert "erişimi kapalı" in dagitim.plan(c, t, dagitimci="tunearo").beklemede
    assert cli._takvim_hatirlat(tmp_path) == 0 and len(api.cagrilar) == 1
    # 6 saat sonra bir kez yeniden dener (yüklenmiş şarkı yoksa yoklama yok, kayıt başka türlü kalkmazdı)
    sonra = datetime.now() + timedelta(hours=dagitim.ERISIM_DENEME_SAAT + 1)
    assert dagitim.erisim_kapali(c, sonra) is None


# ── yazarsız paket sıraya girmez (özet her oturumda "yükleme sırası geldi: Heaven Knows" diyordu) ──
def test_yazarsiz_paket_sirada_ve_ozette_gorunmez(tmp_path):
    from yanki import cli

    c = tmp_path / "calisma"
    _paket(c, kimlik="yazarsiz", orijinal_yazarlar=[], orijinal_yazar_adlari=[])
    _paket(c, kimlik="tam")
    _sinirsiz_ayar(tmp_path)
    p = dagitim.plan(c, dagitim.takvim_oku(tmp_path / "config" / "yayin.toml"), date(2026, 10, 20), {},
                     dagitimci="tunearo")
    assert [x.kimlik for x in p.sira] == ["tam"] and p.yazarsiz == ("yazarsiz",)
    with durum.guncelle(c, "tam") as d:
        d.gec("yuklendi")
    assert cli.ozet(tmp_path)["yuklenecek"] is None


# ── ikinci tarama (kalan modüller) ──
def test_odada_listeye_ekle_post_atar():
    """`api(yol, null)` GET atıyordu, uç yalnız POST: "Listeye ekle" hiç çalışmamıştı (404)."""
    from pathlib import Path

    js = (Path(__file__).parents[1] / "yanki" / "sayfa" / "uygulama.js").read_text(encoding="utf-8")
    assert 'islem("ekle", null' not in js
    assert "govde !== undefined && govde !== null" in js


def test_izlenmesi_olculmemis_aday_listeye_yazilir(tmp_path):
    from yanki import kesif, liste

    x = kesif.Aday("Sanatçı", "Şarkı", "stillmore:p")
    yol = tmp_path / "liste.toml"
    kesif.listeye_yaz([x], yol, "dinleme odasından eklendi")
    assert [s.ad for s in liste.yukle(yol)] == ["Şarkı"] and "YouTube ölçülmedi" in yol.read_text(encoding="utf-8")


def test_latin_disi_ad_bos_ya_da_cakisan_kimlik_uretmez():
    from yanki import liste

    k1, k2, k3 = liste.kimlik("Ёлка", "Прованс"), liste.kimlik("米津玄師", "Lemon"), liste.kimlik("Başka", "Lemon")
    assert k1 and k1 != liste.kimlik("Ёлка", "Другая") and k2 != "lemon" and k2.startswith("lemon-")
    assert k3 == "baska-lemon" and liste.kimlik("Adele", "Someone Like You") == "adele-someone-like-you"


def test_katalog_taramasi_spotify_hatasinda_onbellegi_yazar(tmp_path):
    from datetime import datetime

    from tests.test_kesif import DEEZER, SahteSpotify, _deezer, _parca
    from yanki import katalog, spotify

    class Bozuk(SahteSpotify):
        def ara(self, sorgu, market, adet=10):
            if "Glory Box" in sorgu:
                raise spotify.SpotifyHatasi("Spotify 502")
            return super().ara(sorgu, market, adet)

    sp = Bozuk(arama={'track:"Teardrop" artist:"Massive Attack"': [_parca("t1", "Teardrop", "Massive Attack",
                                                                            oynar=False)]})
    sp.istek_sayisi, sp.baska_yerde_acik = 0, set()
    ayar = katalog.Ayar(tohumlar=("Massive Attack",), liste_turleri=(0,), benzer_adet=1, butce=100, min_rank=500000)
    adaylar = katalog.tara(sp, tmp_path, ("US", "GB"), ayar, json_al=_deezer(DEEZER), bildir=lambda *_: None,
                           simdi=datetime(2026, 10, 9))
    assert "Teardrop" in [a.ad for a in adaylar] and katalog.onbellek_oku(tmp_path)


def test_cdp_baglantisi_koparsa_stillmore_yok(monkeypatch):
    import websockets.sync.client

    from yanki import stillmore

    k = stillmore.Kopru.__new__(stillmore.Kopru)
    k.ws_adres, k._id = "ws://127.0.0.1:9/x", 0

    def kapali(*_a, **_k):
        raise ConnectionRefusedError("Spotify kapandı")

    monkeypatch.setattr(websockets.sync.client, "connect", kapali)
    with pytest.raises(stillmore.StillmoreYok):
        k.degerlendir("1")


def test_yarim_yuklemeli_paket_odadan_reddedilemez(tmp_path):
    from fastapi.testclient import TestClient

    from yanki import ayarlar, sunucu

    c = tmp_path / "calisma"
    _paket(c, kimlik="yarim", tunearo={"release_id": "rel-1", "durum": "draft"})
    _paket(c, kimlik="temiz")
    oda = TestClient(sunucu.uygulama(ayarlar.yukle(), c), base_url="http://127.0.0.1:8765")
    r = oda.post("/api/sarki/yarim/reddet", json={"neden": "beğenmedim"})
    assert r.status_code == 409 and "geri-cek" in r.json()["detail"]
    assert oda.post("/api/sarki/temiz/reddet", json={"neden": "x"}).status_code == 200


def test_kunye_yazarsiz_eserde_durmaz_sonraki_kayda_bakar():
    from yanki import kunye

    yanitlar = {
        "/recording/": {"recordings": [{"id": "r1", "title": "Song", "score": 100},
                                       {"id": "r2", "title": "Song", "score": 98}]},
        "/recording/r1": {"relations": [{"type": "performance", "work": {"id": "w1", "title": "Song"}}]},
        "/work/w1": {"relations": []},
        "/recording/r2": {"relations": [{"type": "performance", "work": {"id": "w2", "title": "Song"}}]},
        "/work/w2": {"relations": [{"type": "composer", "artist": {"name": "Ana Yazar"}}]},
    }
    k = kunye.bul("A", "Song", json_al=lambda url, *a, **_k: yanitlar[url.split("/ws/2", 1)[1]],
                  uyku=lambda _: None)
    assert k.yazarlar == ("Ana Yazar",) and k.eser_mbid == "w2"


def test_kisa_ara_parca_birlestirmede_duser():
    import numpy as np

    from yanki import parcalama

    p = parcalama.plan(200.0, [0.0, 50.0, 95.0, 140.0, 185.0])
    sr = 100
    sesler = [np.ones((int((x.son - x.bas) * sr), 2), np.float32) for x in p]
    sesler[0] = sesler[0][: len(sesler[0]) // 2]  # ilk parça yarım çıktı
    with pytest.raises(ValueError, match="kısa"):
        parcalama.birlestir(sesler, p, sr)
    sesler = [np.ones((int((x.son - x.bas) * sr), 2), np.float32) for x in p]
    sesler[-1] = sesler[-1][:-50]  # son parçanın kuyruğu kısa olabilir
    assert len(parcalama.birlestir(sesler, p, sr)) == int(round(p[-1].son * sr))
