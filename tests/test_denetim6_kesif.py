"""Denetim 6: keşif, takip, Bulucu, kazanç."""

import json
from datetime import date, datetime, timedelta

import pytest

from yanki import bulucu, durum, kazanc, kesif, performans, spotify, takip


# ── Spotify ─────────────────────────────────────────────────
def test_kimlik_ayikla_dil_ekli_ve_gomme_linki():
    kimlik = "37i9dQZF1DXcBWIGoYBM5M"
    for metin in (f"https://open.spotify.com/intl-tr/playlist/{kimlik}?si=abc",
                  f"https://open.spotify.com/embed/playlist/{kimlik}", f"spotify:playlist:{kimlik}", kimlik,
                  f"https://open.spotify.com/playlist/{kimlik}"):
        assert spotify.kimlik_ayikla(metin) == kimlik
    assert spotify.kimlik_ayikla(f"https://open.spotify.com/intl-pt-BR/track/{kimlik}", "track") == kimlik


class _Kayitli(spotify.Spotify):
    def __init__(self, kok, yanitlar):
        super().__init__(kok, "cid", "sec")
        self.yanitlar, self.istekler, self.aralik_sn = list(yanitlar), [], 0

    def _http(self, yontem, url, basliklar, veri=None):
        self.istekler.append(url)
        kod, govde, *bas = self.yanitlar.pop(0)
        return kod, (bas[0] if bas else {}), json.dumps(govde).encode()


def test_token_ucu_429_kilit_yazar(tmp_path):
    sp = _Kayitli(tmp_path, [(429, {}, {"Retry-After": "7200"})])
    with pytest.raises(spotify.Sinirli):
        sp.ara("q", "TR")
    sp2 = _Kayitli(tmp_path, [])
    with pytest.raises(spotify.Sinirli):
        sp2.ara("q", "TR")  # yeni süreç token ucunu da yoklamaz
    assert sp2.istekler == []


def test_504_bir_kez_yeniden_denenir(tmp_path, monkeypatch):
    monkeypatch.setattr(spotify.time, "sleep", lambda _s: None)
    sp = _Kayitli(tmp_path, [(200, {"access_token": "t", "expires_in": 3600}), (504, {}),
                             (200, {"tracks": {"items": [{"id": "x"}]}})])
    assert [t["id"] for t in sp.ara("q", "TR", adet=1)] == ["x"]


# ── Takip ───────────────────────────────────────────────────
def _parca(id_, ad, sanatci, isrc=None):
    t = {"id": id_, "name": ad, "is_playable": True, "artists": [{"id": f"art-{sanatci}", "name": sanatci}]}
    if isrc is not None:
        t["external_ids"] = {"isrc": isrc}
    return t


class _Web:
    def __init__(self, isrc_sonuc=None, hata=None, ara_hata=None):
        self.isrc_sonuc, self.hata, self.ara_hata, self.cagri = isrc_sonuc or [], hata, ara_hata, []

    def isrc_ara(self, isrc, market):
        self.cagri.append(("isrc", market))
        if self.hata:
            raise self.hata
        return self.isrc_sonuc

    def ara(self, sorgu, market, adet=20):
        self.cagri.append(("ara", market))
        if self.ara_hata:
            raise self.ara_hata
        return [_parca("bizim", "Fix You", "Orvane")]


class _Istemci:
    ulke = "TR"

    def __init__(self, isrc_sonuc):
        self.isrc_sonuc, self.cagri = isrc_sonuc, []

    def isrc_ara(self, isrc, market=None):
        return self.isrc_sonuc

    def ara(self, sorgu, market, adet=20):
        self.cagri.append(("ara", market))
        return [_parca("x", "Fix You", "Coldplay"), _parca("bizim", "Fix You", "Orvane")]


def test_istemci_bulamayinca_onceden_canli_parca_web_apiyle_dogrulanir():
    d = durum.Durum("fix", "Coldplay", "Fix You")
    onceki = {"canli": True, "siralar": {"TR": 1}, "web_kontrol": datetime.now().isoformat()}
    web = _Web([_parca("bizim", "Fix You", "Orvane", isrc="QZABC2600001")])
    son = takip.kontrol_et(web, d, "QZABC2600001", "Orvane", ("TR",), onceki=onceki, istemci=_Istemci([]))
    assert son["canli"] and son["spotify_id"] == "bizim" and ("isrc", "TR") in web.cagri
    # Web API de bulamazsa gerçekten kalkmış
    son = takip.kontrol_et(_Web([]), d, "QZABC2600001", "Orvane", ("TR",), onceki=onceki, istemci=_Istemci([]))
    assert son["canli"] is False
    # kota kilitliyken istemcinin sonucu geçerli, hata yükselmez
    son = takip.kontrol_et(_Web(hata=spotify.Sinirli(100)), d, "QZABC2600001", "Orvane", ("TR",), onceki=onceki,
                           istemci=_Istemci([]))
    assert son["canli"] is False
    # önceden canlı değilse Web API'ye sorulmaz (yayına çıkmamış şarkıda her gece istek olmasın)
    web = _Web([_parca("bizim", "Fix You", "Orvane", isrc="QZABC2600001")])
    takip.kontrol_et(web, d, "QZABC2600001", "Orvane", ("TR",), onceki=None, istemci=_Istemci([]))
    assert web.cagri == []


def test_kota_pazar_dongusunde_dolunca_istemci_pazari_yine_olculur():
    d = durum.Durum("fix", "Coldplay", "Fix You")
    ist = _Istemci([_parca("bizim", "Fix You", "Orvane")])
    web = _Web(ara_hata=spotify.Sinirli(100))
    onceki = {"canli": True, "siralar": {"GB": 4, "DE": 5, "TR": 9}}
    son = takip.kontrol_et(web, d, "QZABC2600001", "Orvane", ("GB", "DE", "TR"), onceki=onceki, istemci=ist)
    assert son["siralar"] == {"GB": 4, "DE": 5, "TR": 2}  # GB/DE önceki, TR istemciden taze
    assert web.cagri == [("ara", "GB")] and ist.cagri == [("ara", "TR")]
    assert son["web_kontrol"] is None  # Web API ölçümü yapılmadı: ertesi gece yeniden denenir


def _yuklenmis(c, kimlik, ad, isrc):
    d = durum.Durum(kimlik, "Adele", ad, asama="yuklendi")
    durum.yaz(c, d)
    (c / kimlik / "paket").mkdir(parents=True)
    (c / kimlik / "paket" / "metadata.json").write_text(json.dumps({"yukleme": {"isrc": isrc}}), encoding="utf-8")


def test_tek_sarkinin_spotify_hatasi_kalanlari_dusurmez(tmp_path):
    _yuklenmis(tmp_path, "a-bir", "Bir", "GXM2X2600001")
    _yuklenmis(tmp_path, "a-iki", "Iki", "GXM2X2600002")

    class Web:
        def isrc_ara(self, isrc, market):
            if isrc.endswith("1"):
                raise spotify.SpotifyHatasi("Spotify'a ulaşılamadı: bağlantı sıfırlandı")
            return [_parca("p2", "Iki", "Orvane", isrc=isrc)]

        def ara(self, sorgu, market, adet=20):
            return []

    sonuc = {d.kimlik: u for d, u in takip.takip_et(Web(), tmp_path, "Orvane", "TR")}
    assert "sorulamadı" in sonuc["a-bir"][0]
    assert durum.oku(tmp_path, "a-iki").asama == "yayinda"

    class Agsiz(Web):
        def isrc_ara(self, isrc, market):
            raise spotify.SpotifyHatasi("Spotify'a ulaşılamadı")

    _yuklenmis(tmp_path, "a-uc", "Uc", "GXM2X2600003")
    with pytest.raises(spotify.SpotifyHatasi):  # hiçbiri sorulamadıysa koşu hatası
        takip.takip_et(Agsiz(), tmp_path, "Orvane", "TR", kimlikler=["a-bir", "a-uc"])


def test_ilk_canli_gun_gecmis_kirpilinca_kaymaz():
    d = durum.Durum("a-b", "A", "B", asama="yuklendi")
    bas = datetime(2026, 8, 1, 3, 0)
    for i in range(takip.GECMIS_SINIRI + 10):  # her gece sıra değişiyor: geçmiş sınırda kırpılır
        z = bas + timedelta(days=i)
        takip.kaydet(d, {"canli": True, "spotify_id": "x", "sanatci_id": "y", "siralar": {"TR": i % 7 + 1},
                         "zaman": z.isoformat()})
    assert len(d.yayin["gecmis"]) == takip.GECMIS_SINIRI
    assert performans.yayin_gunu(d) == date(2026, 8, 1)


# ── Kazanç ──────────────────────────────────────────────────
def test_para_tam_kismi_sifir_virgullu_ondalik():
    assert kazanc._para("0,003")[0] == pytest.approx(0.003)
    assert kazanc._para("0,123")[0] == pytest.approx(0.123)
    assert kazanc._para("1,234")[0] == 1234
    assert kazanc._para("1,50")[0] == 1.5


def test_kucuk_satirlar_toplamda_kaybolmaz_ve_dosya_ici_ayni_satir_sayilir(tmp_path):
    c = tmp_path / "calisma"
    d = durum.Durum("numb", "Linkin Park", "Numb", asama="yuklendi")
    durum.yaz(c, d)
    (c / "numb" / "paket").mkdir(parents=True)
    (c / "numb" / "paket" / "metadata.json").write_text(json.dumps({"yukleme": {"isrc": "GBXYZ2600001"}}),
                                                        encoding="utf-8")
    satirlar = ["Sale Month,Store,Country,ISRC,Quantity,Earnings (USD)"]
    satirlar += [f"2026-09,Spotify,C{i},GBXYZ2600001,1,0.00004" for i in range(100)]
    satirlar += ["2026-09,Deezer,FR,GBXYZ2600001,2,0.0100", "2026-09,Deezer,FR,GBXYZ2600001,2,0.0100"]
    k = kazanc.klasor(tmp_path)
    k.mkdir(parents=True)
    (k / "eylul.csv").write_text("\n".join(satirlar), encoding="utf-8")
    (k / "tum-gecmis.csv").write_text("\n".join(satirlar), encoding="utf-8")  # aynı satırlar: bir kez
    r = kazanc.sarki_kazanclari(tmp_path, c)
    assert r["sarkilar"]["numb"]["tutar"] == pytest.approx(0.024)  # 100 × 0,00004 + 2 × 0,01
    assert r["sarkilar"]["numb"]["akis"] == 104


# ── Bulucu ──────────────────────────────────────────────────
def test_zaman_asiminda_sayfadaki_is_birakilir(monkeypatch, tmp_path):
    monkeypatch.setattr(bulucu, "IS_ZAMAN_ASIMI", 0)
    monkeypatch.setattr(bulucu.stillmore, "cdp_acik", lambda port=9222: True)

    class Kopru:
        def __init__(self):
            self.ifadeler = []

        def degerlendir(self, ifade, zaman_asimi=120):
            self.ifadeler.append(ifade)
            return 7 if ifade.startswith("window.__yanki.baslat") else True

    k = Kopru()
    b = bulucu.Bulucu(tmp_path, kopru_ac=lambda: k, uyku=lambda _s: None)
    with pytest.raises(TimeoutError):
        b._ara({"tur": "parca", "kimlik": "4uLU6hMCjMI75M1A2tKUQC"})
    assert k.ifadeler[-1] == "window.__yanki && window.__yanki.birak(7)"
    assert "birak(no)" in bulucu.YARDIMCI and "sinirMs" in bulucu.YARDIMCI


def test_listedekiler_calisma_klasoru_yokken(tmp_path):
    lyol = tmp_path / "liste.toml"
    lyol.write_text('[[sarki]]\nsanatci = "A"\nad = "B"\n', encoding="utf-8")
    assert kesif.listedekiler(lyol, tmp_path / "yok") == {"a-b"}


def test_bulucu_buyuk_harfli_dil_eki():
    assert bulucu.coz("https://open.spotify.com/intl-pt-BR/track/4uLU6hMCjMI75M1A2tKUQC?si=1") == (
        "parca", "4uLU6hMCjMI75M1A2tKUQC")
