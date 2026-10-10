"""Faz 13 ve Faz 10'un API'den bağımsız kısmı: bildirimler, servis sayaçları, yayın takvimi, dağıtımcı reddi,
gündüz boşta üretim."""

import argparse
import json
from dataclasses import replace
from datetime import date, datetime

import pytest

from yanki import ayarlar, dagitim, durum, olay, sayac, takip


def _sarki(c, kimlik, asama, gecmis=(), **k):
    d = durum.Durum(kimlik, "A", kimlik.upper(), asama=asama, **k)
    d.gecmis = [{"zaman": z, "asama": a, "hata": None} for a, z in gecmis]
    durum.yaz(c, d)
    return d


# ── bildirim ────────────────────────────────────────────────
def test_olay_kaydedilir_ve_anahtarla_bir_kez_bildirilir(tmp_path):
    assert olay.bildir(tmp_path, "gecikme", "yayın tarihi geçti: B", "metin", "gecikme:a-b:2026-10-28")
    assert not olay.bildir(tmp_path, "gecikme", "yayın tarihi geçti: B", "metin", "gecikme:a-b:2026-10-28")
    assert olay.bildir(tmp_path, "dinleme", "hazır", "x")  # anahtarsız her seferinde
    (tmp_path / "olaylar.jsonl").open("a", encoding="utf-8").write('{"yarim')  # güç kesintisi
    assert [o["tur"] for o in olay.oku(tmp_path)] == ["gecikme", "dinleme"]


def test_takip_olaylari():
    d = durum.Durum("a-b", "Adele", "Someone Like You")
    son = {"zaman": "2026-10-29T03:10:00", "canli": True, "spotify_id": "x", "arama_sirasi": 3,
           "siralar": {"GB": 3, "TR": 5}, "kayip": False, "yayin_tarihi": "2026-10-28"}
    (tur, baslik, metin, _), = takip.olaylar(d, {}, son)
    assert tur == "yayinda" and "GB 3, TR 5" in metin
    assert takip.olaylar(d, son, {**son, "zaman": "2026-10-30T03:00:00"}) == []  # değişiklik yok
    (tur, _, metin, _), = takip.olaylar(d, son, {**son, "arama_sirasi": 1, "siralar": {"GB": 1, "TR": 5}})
    assert tur == "sira" and "3 → 1" in metin
    yok = {"zaman": "2026-10-31T03:00:00", "canli": False, "kayip": False, "yayin_tarihi": "2026-10-28"}
    assert takip.olaylar(d, {}, yok, bugun=date(2026, 10, 30)) == []  # 2 gün: henüz erken
    (tur, _, metin, anahtar), = takip.olaylar(d, {}, yok, bugun=date(2026, 10, 31))
    assert tur == "gecikme" and "dagitim-red a-b" in metin and anahtar == "gecikme:a-b:2026-10-28"
    assert [o[0] for o in takip.olaylar(d, son, {**yok, "kayip": True}, bugun=date(2026, 10, 29))] == ["kayip"]


# ── servis sayaçları ────────────────────────────────────────
def test_sayac_ozeti_ve_gunluk_toplam(tmp_path):
    sayac.sifirla()
    assert sayac.servis("https://lrclib.net/api/get?x=1") == "LRCLIB"
    for basari in (True, True, False, True):
        sayac.say("YouTube", basari)
    sayac.say("LRCLIB", True)
    assert sayac.ozet() == "LRCLIB 1 · YouTube 4 (1 hata, %25)"
    sayac.yaz(tmp_path, date(2026, 10, 9))
    sayac.yaz(tmp_path, date(2026, 10, 9))  # aynı gün ikinci koşu (gündüz) toplanır
    kayit = json.loads((tmp_path / "gunluk" / "servisler.json").read_text(encoding="utf-8"))
    assert kayit["2026-10-09"]["YouTube"] == {"istek": 8, "hata": 2}
    sayac.sifirla()


def test_ag_istekleri_sayilir(monkeypatch):
    import urllib.error

    from yanki import ag

    sayac.sifirla()
    monkeypatch.setattr(ag.time, "sleep", lambda _: None)
    with pytest.raises(urllib.error.URLError):
        ag.json_al("https://musicbrainz.org/ws/2/recording/", deneme=2)  # conftest: ağ yok
    assert (sayac.ISTEK["MusicBrainz"], sayac.HATA["MusicBrainz"]) == (2, 2)
    sayac.sifirla()


# ── yayın takvimi ───────────────────────────────────────────
def test_takvim_sirasi_kesif_puani_sonra_onay_sirasi(tmp_path):
    _sarki(tmp_path, "yuklu", "yayinda", [("yuklendi", "2026-10-08T12:00:00")])
    _sarki(tmp_path, "eski-onay", "paketlendi", [("onaylandi", "2026-10-01T10:00:00")])
    _sarki(tmp_path, "yeni-onay", "paketlendi", [("onaylandi", "2026-10-05T10:00:00")])
    _sarki(tmp_path, "kesif-sarkisi", "paketlendi", [("onaylandi", "2026-10-07T10:00:00")])
    p = dagitim.plan(tmp_path, dagitim.Takvim(), date(2026, 10, 9), {"kesif-sarkisi": 5e6})
    assert [x.kimlik for x in p.sira] == ["kesif-sarkisi", "eski-onay", "yeni-onay"]
    # son yüklemeden bir hafta sonra, haftada bir; yayın tarihi yüklemeden 21 gün sonra
    assert [x.yukleme for x in p.sira] == [date(2026, 10, 15), date(2026, 10, 22), date(2026, 10, 29)]
    assert p.sira[0].yayin_tarihi == date(2026, 11, 5) and p.beklemede is None
    iki = dagitim.plan(tmp_path, dagitim.Takvim(haftada=2), date(2026, 10, 9), {})
    assert [x.yukleme for x in iki.sira[:2]] == [date(2026, 10, 12), date(2026, 10, 16)]  # 4 günde bir


def test_takvim_ilk_kabulu_bekler_ve_reddedileni_atlar(tmp_path):
    _sarki(tmp_path, "yuklu", "yuklendi", [("yuklendi", "2026-10-08T12:00:00")])
    _sarki(tmp_path, "paket", "paketlendi")
    p = dagitim.plan(tmp_path, dagitim.Takvim(), date(2026, 10, 20), {})
    assert p.beklemede and p.bugun_yuklenecek is None and [x.kimlik for x in p.sira] == ["paket"]
    assert dagitim.plan(tmp_path, dagitim.Takvim(baslangic="hemen"), date(2026, 10, 20), {}).beklemede is None
    (tmp_path / "yuklu" / "paket").mkdir()
    (tmp_path / "yuklu" / "paket" / "metadata.json").write_text(json.dumps({"yukleme": {"isrc": "X"}}), "utf-8")
    d = dagitim.red_kaydet(tmp_path, "yuklu", "kapak telifli")
    assert d.asama == "paketlendi" and d.hata == "dağıtımcı reddi: kapak telifli"
    meta = json.loads((tmp_path / "yuklu" / "paket" / "metadata.json").read_text(encoding="utf-8"))
    assert "yukleme" not in meta and meta["yukleme_gecmisi"][0]["red"] == "kapak telifli"
    p = dagitim.plan(tmp_path, dagitim.Takvim(baslangic="hemen"), date(2026, 10, 20), {})
    assert p.duzeltme == ["yuklu"] and [x.kimlik for x in p.sira] == ["paket"]
    with pytest.raises(ValueError):
        dagitim.red_kaydet(tmp_path, "paket", "x")  # yüklenmemiş


def test_takvim_hatirlatmasi_bir_kez(tmp_path, monkeypatch):
    from yanki import cli

    c = tmp_path / "calisma"
    _sarki(c, "yuklu", "yayinda", [("yuklendi", "2026-09-01T12:00:00")])
    _sarki(c, "paket", "paketlendi")
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "yayin.toml").write_text(
        '[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "routenote"\n[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.2\n'
        "ornekleme = 44100\n[takvim]\nacik = true\n", encoding="utf-8")
    assert cli._takvim_hatirlat(tmp_path) == 0
    assert cli._takvim_hatirlat(tmp_path) == 0
    olaylar = olay.oku(c)
    assert len(olaylar) == 1 and olaylar[0]["tur"] == "takvim" and "paket/YUKLE.md" in olaylar[0]["metin"]
    assert cli.ozet(tmp_path)["yuklenecek"] == "A — PAKET"


# ── gündüz boşta üretim ─────────────────────────────────────
def test_operasyon_gunduz_saat_penceresi():
    op = ayarlar.Operasyon(ayarlar.KOK, gunduz_saatler=(8, 1))
    assert [op.gunduz_saatinde(h) for h in (7, 8, 23, 0, 1, 3)] == [False, True, True, True, False, False]
    assert replace(op, gunduz_saatler=(9, 17)).gunduz_saatinde(12) and not replace(
        op, gunduz_saatler=(9, 17)).gunduz_saatinde(18)


@pytest.fixture
def gunduz(tmp_path, monkeypatch):
    from yanki import cli, saglik, sistem, uretim

    a = replace(ayarlar.yukle(), kok=tmp_path, uzak=ayarlar.Uzak())  # evdeki motor yolu
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: a)
    monkeypatch.setattr(cli.ayarlar, "operasyon_oku", lambda _k: ayarlar.Operasyon(tmp_path, gunduz_saatler=(0, 0)))
    monkeypatch.setattr(sistem, "bosta_sn", lambda: 3600)
    monkeypatch.setattr(sistem, "prizde_mi", lambda: True)
    monkeypatch.setattr(saglik, "gpu_kullanilan_mib", lambda: 500)
    monkeypatch.setattr(cli, "_hazirla", lambda _a: 0)
    monkeypatch.setattr(cli, "_paketle", lambda _a: 0)
    uretilen = []

    def sahte_uret(_a, c, kimlikler):
        uretilen.extend(kimlikler)
        sonuc = []
        for k in kimlikler:
            with durum.guncelle(c, k) as d:
                d.gec("uretildi")
            sonuc.append(d)
        return sonuc

    monkeypatch.setattr(uretim, "uret", sahte_uret)
    c = tmp_path / "calisma"
    _sarki(c, "analizde", "analiz", [("analiz", "2026-10-09T01:00:00")])
    _sarki(c, "onarimda", "onarim", [("onarim", "2026-10-09T12:00:00")])
    return cli, c, uretilen, monkeypatch


def test_gunduz_once_onarimi_uretir_ve_bildirir(gunduz):
    cli, c, uretilen, _ = gunduz
    ns = argparse.Namespace(zorla=False, liste=None)
    assert cli._gunduz(ns) == 0 and uretilen == ["onarimda"]  # Scryne'ın beklediği onarım önce, tek şarkı
    assert olay.oku(c)[-1]["tur"] == "dinleme"
    assert cli._gunduz(ns) == 0 and uretilen == ["onarimda", "analizde"]


@pytest.mark.parametrize("bozuk", ["etkin", "pil", "gpu", "saat"])
def test_gunduz_kosul_tutmazsa_uretmez(gunduz, bozuk, capsys):
    from yanki import saglik, sistem

    cli, _, uretilen, mp = gunduz
    if bozuk == "etkin":
        mp.setattr(sistem, "bosta_sn", lambda: 60)
    elif bozuk == "pil":
        mp.setattr(sistem, "prizde_mi", lambda: False)
    elif bozuk == "gpu":
        mp.setattr(saglik, "gpu_kullanilan_mib", lambda: 7000)
    else:
        saat = datetime.now().hour
        mp.setattr(cli.ayarlar, "operasyon_oku",
                   lambda _k: ayarlar.Operasyon(ayarlar.KOK, gunduz_saatler=((saat + 1) % 24, (saat + 2) % 24)))
    assert cli._gunduz(argparse.Namespace(zorla=False, liste=None)) == 0
    assert uretilen == [] and capsys.readouterr().out.strip()  # tek satır neden
