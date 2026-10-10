"""Denetim (2026-10-09) bulgularının testleri: eşzamanlı yazım, gece koşusunun adım yalıtımı, sunucu korumaları,
yükleme kaydı, yedek."""

import json
import subprocess
import sys
import time
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf
from fastapi.testclient import TestClient

from yanki import ayarlar, durum, kilit, motor, sunucu, uretim

# ── süreçler arası kilit ve taze oku-değiştir-yaz ───────────


def test_guncelle_taze_okur_ve_yazar(tmp_path):
    durum.yaz(tmp_path, durum.Durum("a-b", "A", "B"))
    with durum.guncelle(tmp_path, "a-b") as d:
        d.notlar.append({"x": 1})
    assert durum.oku(tmp_path, "a-b").notlar == [{"x": 1}]
    with pytest.raises(RuntimeError), durum.guncelle(tmp_path, "a-b") as d:
        d.notlar.append({"y": 2})
        raise RuntimeError  # blok düşerse yazılmaz
    assert durum.oku(tmp_path, "a-b").notlar == [{"x": 1}]
    with pytest.raises(durum.Yok), durum.guncelle(tmp_path, "yok"):
        pass
    with durum.guncelle(tmp_path, "yeni-sarki", yoksa=durum.Durum("yeni-sarki", "Y", "S")) as d:
        d.gec("hazir")
    assert durum.oku(tmp_path, "yeni-sarki").asama == "hazir"


def test_kilit_baska_surecteyken_bekler_sonra_mesgul(tmp_path):
    yol = tmp_path / "k.kilit"
    kod = ("import sys, time; from pathlib import Path; from yanki import kilit\n"
           "with kilit.bekleyerek(Path(sys.argv[1])):\n    print('aldi', flush=True); time.sleep(3)")
    surec = subprocess.Popen([sys.executable, "-c", kod, str(yol)], stdout=subprocess.PIPE, text=True)
    try:
        assert surec.stdout.readline().strip() == "aldi"
        with pytest.raises(kilit.KilitMesgul), kilit.bekleyerek(yol, zaman_asimi_sn=0.3):
            pass
        with kilit.bekleyerek(yol, zaman_asimi_sn=10):  # öbür süreç bırakınca alınır
            pass
    finally:
        surec.wait(10)


# ── üretim: uzun koşu sırasında verilen karar ezilmez ───────
def _ayar():
    a = ayarlar.yukle()
    return replace(a, cover=replace(a.cover, aday_sayisi=2, tohumlar=(42, 7)))


def _sarki(c: Path, kimlik: str, sure: float = 30.0) -> None:
    k = c / kimlik
    k.mkdir(parents=True)
    t = np.arange(int(sure * uretim.SR)) / uretim.SR
    sf.write(str(k / "kaynak.wav"), (0.3 * np.sin(2 * np.pi * 220 * t)).astype("float32"), uretim.SR)
    (k / "soz.txt").write_text("[verse]\nla la", encoding="utf-8")
    d = durum.Durum(kimlik, "A", "B", kaynak={"dosya": "kaynak.wav", "sure_sn": sure}, soz={"dosya": "soz.txt"},
                    analiz={"stil": "s"})
    d.gec("analiz")
    durum.yaz(c, d)


def _motor(sirasinda=None, bozuk=False):
    def calistir(a, isler, klasor, zaman_asimi_sn):
        if sirasinda:
            sirasinda()
        sonuc = []
        for i in isler:
            if bozuk:
                sonuc.append(motor.Sonuc(i.id, False, "RuntimeError: CUDA out of memory"))
                continue
            Path(i.cikti_klasor).mkdir(parents=True, exist_ok=True)
            yol = Path(i.cikti_klasor) / "out.flac"
            ses, sr = sf.read(i.kaynak, dtype="float32", always_2d=True)
            sf.write(str(yol), ses * 0.5, sr)
            sonuc.append(motor.Sonuc(i.id, True, cikti=str(yol)))
        return sonuc
    return calistir


GECER = lambda *_: {"dalga": {"gecti": True, "deger": 0.02, "esik": 0.25}}  # noqa: E731


def test_uretim_sirasinda_verilen_ret_ezilmez(tmp_path):
    c = tmp_path / "c"
    _sarki(c, "a-b")

    def scryne_reddeder():  # dinleme odası, motor çalışırken
        with durum.guncelle(c, "a-b") as d:
            d.gec("reddedildi", "beğenmedim")

    sonuc = uretim.uret(_ayar(), c, calistir=_motor(scryne_reddeder), degerlendir=GECER)
    d = durum.oku(c, "a-b")
    assert d.asama == "reddedildi" and d.hata == "beğenmedim"
    assert len(d.adaylar) == 2 and all(x.gecti for x in d.adaylar)  # sonuçlar yine de kayıtlı
    assert sonuc[0].asama == "reddedildi"


def test_onarim_uretilirken_eklenen_yeni_onarim_kaybolmaz(tmp_path):
    c, a = tmp_path / "c", _ayar()
    _sarki(c, "a-b")
    uretim.uret(a, c, calistir=_motor(), degerlendir=GECER)
    with durum.guncelle(c, "a-b") as d:
        uretim.onarim_iste(a, d, 1, 5.0, 8.0)

    def yeni_istek():
        with durum.guncelle(c, "a-b") as d:
            uretim.onarim_iste(a, d, 2, 10.0, 12.0)

    uretim.uret(a, c, calistir=_motor(yeni_istek), degerlendir=GECER)
    d = durum.oku(c, "a-b")
    assert [o["durum"] for o in d.adaylar[0].onarimlar] == ["hazir", "hazir"]
    assert [o["durum"] for o in d.adaylar[1].onarimlar] == ["bekliyor", "bekliyor"]
    assert d.asama == "onarim"  # sonraki koşu yeni isteği üretir


def test_kapi_olcumu_duserse_aday_duser_kosu_surer(tmp_path):
    c = tmp_path / "c"
    _sarki(c, "a-b")
    _sarki(c, "c-d")

    def bozuk_kapi(aday, *_):
        if "a-b" in str(aday):
            raise RuntimeError("Whisper çöktü")
        return GECER()

    uretim.uret(_ayar(), c, calistir=_motor(), degerlendir=bozuk_kapi)
    a, b = durum.oku(c, "a-b"), durum.oku(c, "c-d")
    assert a.asama == "hata" and "degerlendirme" in a.adaylar[0].kapilar
    assert "Whisper çöktü" in a.adaylar[0].kapilar["degerlendirme"]["hata"]
    assert b.asama == "uretildi"


def test_hazirligi_bozuk_sarki_digerlerini_durdurmaz(tmp_path):
    c = tmp_path / "c"
    _sarki(c, "a-b")
    _sarki(c, "c-d")
    (c / "a-b" / "kaynak.wav").unlink()  # uzun şarkıda kesim için kaynak okunamaz
    with durum.guncelle(c, "a-b") as d:
        d.kaynak["sure_sn"] = 300
        d.notlar.append({"x": 1})
    (c / "a-b" / "soz_zaman.json").write_text(json.dumps([[t, "s"] for t in range(5, 295, 10)]), encoding="utf-8")
    uretim.uret(_ayar(), c, calistir=_motor(), degerlendir=GECER)
    assert durum.oku(c, "a-b").asama == "hata" and "üretim hazırlığı" in durum.oku(c, "a-b").hata
    assert durum.oku(c, "c-d").asama == "uretildi"


def test_yalniz_motor_hatasi_iki_kez_kendiliginden_denenir(tmp_path):
    c, a = tmp_path / "c", _ayar()
    _sarki(c, "a-b")
    for _ in range(uretim.MOTOR_TEKRAR):
        uretim.uret(a, c, calistir=_motor(bozuk=True), degerlendir=GECER)
        assert durum.oku(c, "a-b").asama == "analiz"
    uretim.uret(a, c, calistir=_motor(bozuk=True), degerlendir=GECER)
    d = durum.oku(c, "a-b")
    assert d.asama == "hata" and sum("motor_tekrar" in n for n in d.notlar) == uretim.MOTOR_TEKRAR
    assert [x.no for x in d.adaylar] == [1, 2]  # başarısız denemeler aday numarası tüketmez


# ── sunucu korumaları ───────────────────────────────────────
@pytest.fixture
def oda(tmp_path):
    c = tmp_path / "calisma"
    k = c / "a-b"
    (k / "adaylar").mkdir(parents=True)
    sf.write(str(k / "adaylar" / "1.flac"), np.zeros(4800, "float32"), 48000)
    d = durum.Durum("a-b", "A", "B")
    d.adaylar = [durum.Aday(1, "adaylar/1.flac", 42, {"dalga": {"gecti": True}}, True)]
    d.gec("uretildi")
    durum.yaz(c, d)
    (tmp_path / ".env").write_text("SPOTIFY_CLIENT_SECRET=sir", encoding="utf-8")
    (k / "notlar.txt").write_text("ses değil", encoding="utf-8")
    return TestClient(sunucu.uygulama(ayarlar.yukle(), c)), c


@pytest.mark.parametrize("yol", ["/ses/%2E%2E/.env", "/api/dalga/%2E%2E/.env", "/ses/a-b/notlar.txt",
                                 "/ses/a-b/%2E%2E/%2E%2E/.env"])
def test_ses_ucu_klasor_ve_tur_disina_cikmaz(oda, yol):
    istemci, _ = oda
    r = istemci.get(yol)
    assert r.status_code == 404 and "sir" not in r.text


def test_yuklenmis_sarki_yeniden_onaylanamaz_reddedilemez(oda):
    istemci, c = oda
    with durum.guncelle(c, "a-b") as d:
        d.secilen = 1
        d.gec("yuklendi")
    assert istemci.post("/api/sarki/a-b/onayla", json={"aday": 1}).status_code == 409
    assert istemci.post("/api/sarki/a-b/reddet", json={"neden": ""}).status_code == 409
    assert istemci.post("/api/sarki/a-b/onar", json={"aday": 1, "bas": 1, "son": 2}).status_code == 409
    assert durum.oku(c, "a-b").asama == "yuklendi"


def test_ret_geri_alinir(oda):
    istemci, c = oda
    assert istemci.post("/api/sarki/a-b/geri-al").status_code == 409  # reddedilmemiş
    assert istemci.post("/api/sarki/a-b/reddet", json={"neden": "yanlış tık"}).json()["asama"] == "reddedildi"
    assert istemci.post("/api/sarki/a-b/geri-al").json()["asama"] == "uretildi"
    d = durum.oku(c, "a-b")
    assert d.hata is None and d.notlar[-1] == {"ret_geri_alindi": "uretildi"}


def test_kilit_doluysa_409(oda, monkeypatch):
    import contextlib

    istemci, _ = oda

    @contextlib.contextmanager
    def mesgul(*_a, **_k):
        raise kilit.KilitMesgul("dolu")
        yield

    monkeypatch.setattr(kilit, "bekleyerek", mesgul)
    assert istemci.post("/api/sarki/a-b/onayla", json={"aday": 1}).status_code == 409


# ── yükleme kaydı ───────────────────────────────────────────
def test_yukleme_dogrula():
    from yanki import takip

    b = takip.yukleme_dogrula("gx-m2x-26-26596", "5064150700802", "2026-10-28", "1:13")
    assert b == {"isrc": "GXM2X2626596", "upc": "5064150700802", "yayin_tarihi": "2026-10-28", "onizleme": "1:13"}
    for hatali in ({"isrc": "GXM2X26"}, {"upc": "12ab"}, {"yayin_tarihi": "28.10.2026"}, {"onizleme": "73"}):
        with pytest.raises(ValueError):
            takip.yukleme_dogrula(**hatali)


def _paketli(kok: Path, kimlik="a-b") -> Path:
    c = kok / "calisma"
    d = durum.Durum(kimlik, "A", "B", secilen=1)
    d.gec("paketlendi")
    durum.yaz(c, d)
    (c / kimlik / "paket").mkdir()
    (c / kimlik / "paket" / "metadata.json").write_text(json.dumps({"baslik": "B"}), encoding="utf-8")
    return c


def test_yuklendi_komutu_bilgiyi_kaydeder_sonra_gunceller(tmp_path, monkeypatch, capsys):
    from yanki import cli, takip

    c = _paketli(tmp_path)
    a = replace(ayarlar.yukle(), kok=tmp_path)
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: a)
    monkeypatch.setattr(cli.paket, "yayin_ayarlari", lambda _: replace(_yayin(), dagitimci="routenote"))
    assert cli.main(["yuklendi", "a-b", "--upc", "5064150700802"]) == 0
    assert durum.oku(c, "a-b").asama == "yuklendi" and "eksik: isrc" in capsys.readouterr().out
    y = takip.yukleme_bilgisi(c, "a-b")
    assert y["dagitimci"] == "routenote" and y["haric_bolgeler"] == ["US", "CA", "MX", "IN", "PK"]
    assert cli.main(["yuklendi", "a-b"]) == 1  # zaten yüklendi, bilgi yok
    assert cli.main(["yuklendi", "a-b", "--isrc", "BAD"]) == 1
    assert cli.main(["yuklendi", "a-b", "--isrc", "GXM2X2626596", "--yayin-tarihi", "2026-10-28"]) == 0
    y = takip.yukleme_bilgisi(c, "a-b")
    assert (y["isrc"], y["upc"], y["yayin_tarihi"]) == ("GXM2X2626596", "5064150700802", "2026-10-28")
    assert json.loads((c / "a-b" / "paket" / "metadata.json").read_text(encoding="utf-8"))["baslik"] == "B"


def _yayin():
    from yanki import paket

    return paket.Yayin("Orvane", "", "", -14.0, -1.2, 44100)


# ── yedek ───────────────────────────────────────────────────
def test_yedek_durumu_alir_ses_ve_sir_almaz_eskileri_budar(tmp_path):
    import zipfile

    from yanki import yedek

    c = tmp_path / "calisma"
    for yol, icerik in {"calisma/a-b/durum.json": "{}", "calisma/a-b/kaynak.wav": "ses", "calisma/.spotify.json": "t",
                        ".env": "sir", "calisma/kesif/adaylar.json": "{}", "girdi/liste.toml": "",
                        "config/motor.toml": "", "calisma/a-b/paket/metadata.json": "{}",
                        "calisma/a-b/paket/x.flac": "ses"}.items():
        (tmp_path / yol).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / yol).write_text(icerik, encoding="utf-8")
    op = ayarlar.Operasyon(c / "yedek", yedek_gun=7, yedek_sakla=2)
    assert yedek.gerekli_mi(op)
    yol, n = yedek.yedekle(tmp_path, op, datetime(2026, 10, 1, 3))
    with zipfile.ZipFile(yol) as z:
        assert sorted(z.namelist()) == ["calisma/a-b/durum.json", "calisma/a-b/paket/metadata.json",
                                        "calisma/kesif/adaylar.json", "config/motor.toml", "girdi/liste.toml"]
    assert not yedek.gerekli_mi(op, datetime(2026, 10, 5)) and yedek.gerekli_mi(op, datetime(2026, 10, 8, 4))
    yedek.yedekle(tmp_path, op, datetime(2026, 10, 8, 3))
    yedek.yedekle(tmp_path, op, datetime(2026, 10, 15, 3))
    assert [p.name for p in yedek.yedekler(op.yedek_klasor)] == ["yanki-2026-10-08-030000.zip",
                                                                 "yanki-2026-10-15-030000.zip"]


def test_operasyon_ayari_varsayilan_ve_dosya(tmp_path):
    op = ayarlar.operasyon_oku(tmp_path)
    assert op.yedek_klasor == tmp_path / "calisma" / "yedek" and op.temizlik_gun == 14
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "operasyon.toml").write_text('[yedek]\nklasor = "D:/Y"\nsakla = 0\n[temizlik]\ngun = 3\n',
                                                        encoding="utf-8")
    op = ayarlar.operasyon_oku(tmp_path)
    assert op.yedek_klasor == Path("D:/Y") and op.yedek_sakla == 1 and op.temizlik_gun == 3
    assert ayarlar.operasyon_oku().yedek_klasor.name == "yedek"  # depodaki config okunur


# ── gece koşusu: adım yalıtımı ──────────────────────────────
def test_calistir_dusen_adimdan_sonra_surer_ve_1_doner(tmp_path, monkeypatch, capsys):
    from yanki import cli

    sira = []
    a = replace(ayarlar.yukle(), kok=tmp_path)
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: a)
    monkeypatch.setattr(cli, "_kesif_ayarlari", lambda _k: {"kesif": {"gece_ekle": 0}})
    for ad in ("_hazirla", "_otomatik_onay", "_paketle", "_dagitim_durum", "_takvim_hatirlat", "_temizle",
               "_yedekle"):
        monkeypatch.setattr(cli, ad, lambda *_a, ad=ad: sira.append(ad) or 0)

    def uret_duser(*_):
        sira.append("_uret")
        raise RuntimeError("GPU 6 saat boşalmadı")

    monkeypatch.setattr(cli, "_uret_surekli", uret_duser)
    assert cli._calistir(cli.argparse.Namespace(liste=None, analizsiz=False)) == 1
    assert sira == ["_hazirla", "_uret", "_otomatik_onay", "_paketle", "_dagitim_durum", "_takvim_hatirlat",
                    "_temizle", "_yedekle"]
    cikti = capsys.readouterr().out
    assert "GPU 6 saat boşalmadı" in cikti and "sorunlu adım: üretim" in cikti


def test_hazirlanacak_mi(tmp_path):
    from yanki.cli import _hazirlanacak_mi

    d = durum.Durum("a", "A", "B")
    assert _hazirlanacak_mi(None, False) and _hazirlanacak_mi(d, False)
    d.gec("hata", "söz bulunamadı")
    # hazırlık hatası yeniden denenir, ama gündüz görevi her 30 dk'da bir aynı istekleri atmasın
    assert not _hazirlanacak_mi(d, False, tmp_path)
    (tmp_path / "sozler").mkdir()
    (tmp_path / "sozler" / "a.txt").write_text("söz", encoding="utf-8")
    d.gecmis[-1]["zaman"] = "2026-01-01T00:00:00"
    assert _hazirlanacak_mi(d, False)  # süre doldu
    d.gecmis[-1]["zaman"] = datetime.now().isoformat(timespec="seconds")
    import os
    os.utime(tmp_path / "sozler" / "a.txt", (time.time() + 5, time.time() + 5))
    assert _hazirlanacak_mi(d, False, tmp_path)  # Scryne söz dosyasını bıraktı: hemen
    d.analiz = {"stil": "s"}
    assert not _hazirlanacak_mi(d, False)  # üretim hatası: yeniden indirmek çözmez
    for asama in ("onaylandi", "paketlendi", "yuklendi", "yayinda", "onarim"):
        d.gec(asama)
        assert not _hazirlanacak_mi(d, True)  # --yeniden onaylı/yüklenmiş şarkıyı geri almaz
    d.gec("uretildi")
    assert _hazirlanacak_mi(d, True)


# ── dış servisler ───────────────────────────────────────────
def test_spotify_ag_hatasi_spotify_hatasina_doner(tmp_path):
    from yanki import spotify

    sp = spotify.Spotify(tmp_path, "id", "gizli")
    with pytest.raises(spotify.SpotifyHatasi, match="ulaşılamadı"):
        sp.uygulama_token()  # conftest ağı kapatıyor: URLError
    assert spotify._retry_after("Wed, 21 Oct 2026 07:28:00 GMT") == 60 and spotify._retry_after("7") == 7


def test_stillmore_hazir_olmazsa_spotify_eski_haline_doner(monkeypatch):
    from yanki import stillmore

    olaylar = []
    monkeypatch.setattr(stillmore, "cdp_acik", lambda port=9222: False)
    monkeypatch.setattr(stillmore, "calisiyor_mu", lambda: True)
    monkeypatch.setattr(stillmore, "caliyor_mu", lambda: False)
    monkeypatch.setattr(stillmore, "kapat", lambda: olaylar.append("kapat"))
    monkeypatch.setattr(stillmore, "ac", lambda cdp, port=9222: olaylar.append(f"ac cdp={cdp}"))

    class Kirik:
        def __init__(self, port):
            raise stillmore.StillmoreYok("eklenti yüklenmedi")

    monkeypatch.setattr(stillmore, "Kopru", Kirik)
    monkeypatch.setattr(stillmore.time, "sleep", lambda _: None)  # arayüz sayfası beklemesi (kopru_bekle)
    with pytest.raises(stillmore.StillmoreYok), stillmore.Oturum(yeniden_baslat=True):
        pass
    # Scryne'ın açık Spotify'ı kapatıldı, CDP'li açıldı; hata sonrası kapatılıp bayraksız geri açıldı
    assert olaylar == ["kapat", "ac cdp=True", "kapat", "ac cdp=False"]


def test_kesif_birlestir_odadaki_eleme_kararini_korur(tmp_path):
    from yanki import kesif

    kesif.kaydet(tmp_path, {})
    gelen = kesif.Aday("A", "Şarkı", "playlist:x", elendi=True)  # koşunun başında okunan eski karar
    kesif.kaydet(tmp_path, {gelen.kimlik: kesif.Aday("A", "Şarkı", "playlist:x", elendi=False)})  # odada "Geri al"
    assert kesif.birlestir(tmp_path, [gelen])[gelen.kimlik].elendi is False
