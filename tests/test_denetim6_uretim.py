"""Denetim 6 (üretim ve motor): kiralık GPU bütçe bildirimi, eğitim pod'u artık temizliği, harcama kaydının kırpılması,
yarım yoklama, işçinin öksüz kalmaması, üretimde şarkı yalıtımı, baştan almada kilitli klasör, onarım doğrulaması."""

import json
import sys
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest

from tests.test_uretim import GECER, SahteMotor, _ayar, _sarki
from yanki import ayarlar, durum, egitim, motor, olay, runpod, uretim, uzak


def _uzak_ayar(tmp_path, **k):
    return replace(ayarlar.yukle(), kok=tmp_path, uzak=ayarlar.Uzak(acik=True, **k))


# ── bütçe ────────────────────────────────────────────────
def test_bakiye_bitince_uretim_bekler_ve_gunde_bir_bildirilir(tmp_path, monkeypatch):
    """2026-10-16: bakiye 0,80 $'da kaldı, 50 şarkı bütün gün yalnız günlüğe yazılarak bekledi."""
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    a = _uzak_ayar(tmp_path, en_az_bakiye=1.0, yerel_yedek=False)
    for _ in range(3):  # sürekli koşu her 30 dk
        calistir, _, uzak_mi = uzak.motor_sec(a, kayit=lambda _m: None, stok=lambda k, g: "High",
                                              bakiye=lambda _k: 0.8, ssh_engeli=lambda: None)
        assert calistir is None and uzak_mi is False
    olaylar = olay.oku(tmp_path / "calisma")
    assert len(olaylar) == 1 and "bütçe" in olaylar[0]["baslik"] and "0.80" in olaylar[0]["metin"]


def test_stok_yoklugu_butce_bildirimi_degildir(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    a = _uzak_ayar(tmp_path, yerel_yedek=False)
    bildirilen = []
    uzak.motor_sec(a, kayit=lambda _m: None, stok=lambda k, g: None, bakiye=lambda _k: 10.0, ssh_engeli=lambda: None,
                   butce_bildir=lambda kok, neden: bildirilen.append(neden))
    assert bildirilen == []


def test_harcama_kaydi_bu_ayin_odemelerini_dusurmez():
    """Önce düz son 500 kayıt: stok yokken her koşunun 0 $'lık denemesi ayın başındaki ödemeleri silerdi."""
    simdi = datetime(2026, 11, 20)
    eski = [{"zaman": "2026-08-01T10:00:00", "usd": 5.0}] * 10
    gecen_ay = [{"zaman": "2026-10-02T10:00:00", "usd": 1.0}] * 3
    bu_ay = [{"zaman": "2026-11-01T10:00:00", "usd": 2.0}] + [{"zaman": "2026-11-15T10:00:00", "usd": 0}] * 600
    kalan = uzak._harcama_kirp(eski + gecen_ay + bu_ay, simdi)
    assert sum(x["usd"] for x in kalan if x["zaman"].startswith("2026-11")) == 2.0
    assert sum(x["usd"] for x in kalan if x["zaman"].startswith("2026-10")) == 3.0
    assert not any(x["zaman"].startswith("2026-08") for x in kalan)
    kisa = [{"zaman": "2025-01-01T00:00:00", "usd": 1.0}] * 5
    assert uzak._harcama_kirp(kisa, simdi) == kisa  # az kayıt: dokunulmaz


# ── artık pod ────────────────────────────────────────────
def test_her_kosu_egitim_podunun_artigini_da_temizler(tmp_path, monkeypatch):
    """Eğitim ortasında kapanan bilgisayarın pod'u yalnız bir sonraki `yanki egit`te siliniyordu."""
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    monkeypatch.delenv("RUNPOD_API_KEY_2", raising=False)
    cagri = []

    def kapat(k, klasor, kayit_adi="acik_pod", on_ek="yanki-", harcama=None):
        cagri.append((kayit_adi, on_ek, harcama is not None))
        return ["egitim-pod"] if on_ek == "egitim-" else []

    assert uzak.artik_temizle(tmp_path, kapat=kapat) == ["egitim-pod"]
    assert cagri == [("acik_pod", "yanki-", True), (egitim.POD_KAYIT, "egitim-", True)]


def test_artik_temizlik_sahibi_yasayan_egitim_poduna_dokunmaz(tmp_path, monkeypatch):
    klasor = tmp_path / "calisma" / ".runpod"
    runpod.sahip_yaz(klasor, "egt1", ad=egitim.POD_AD)  # bu süreç: yaşıyor (süren eğitim)
    silinen = []

    def gql(_k, sorgu, d=None, **_):
        if "pods" in sorgu:
            return {"myself": {"pods": [{"id": "egt1", "name": egitim.POD_AD, "costPerHr": 0.4,
                                         "runtime": {"uptimeInSeconds": 7200}}]}}
        silinen.append(d["id"])
        return {}

    monkeypatch.setattr(runpod, "gql", gql)
    assert runpod.kapat_artiklari("x", klasor, egitim.POD_KAYIT, "egitim-") == [] and silinen == []


def test_egitim_artik_podunun_suresi_butceye_yazilir(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    a = replace(ayarlar.yukle(), kok=tmp_path)
    alinan = {}

    def kapat(*x, **k):
        alinan.update(k)
        raise RuntimeError("dur")  # pod açılmadan önce

    with pytest.raises(RuntimeError, match="dur"):
        egitim.egit(a, egitim.Ayar(), tmp_path / "veri.tar", bildir=lambda *_: None, bakiye=lambda _k: 10.0,
                    kapat=kapat, commit="x")
    assert callable(alinan.get("harcama"))


# ── uzak işçi yoklaması ──────────────────────────────────
def test_isci_kos_yarim_yoklama_ciktisinda_dusmez():
    class Pod:
        def __init__(self):
            self.yokla = ['SURUYOR\n#SONUC#\n[{"id": "a", "basari": tr',
                          "BITTI\n#SONUC#\n" + json.dumps([{"id": "a", "basari": True}]) + "\n#GUNLUK#\n0\n"]

        def komut(self, betik, zaman_asimi=120, tekrar=True):
            if "motor_sonuc.json" not in betik or "cat " not in betik:
                return ""
            return self.yokla.pop(0)

    satirlar = []
    assert uzak.isci_kos(Pod(), "/root/ACE", 60, aralik_sn=0, toplam=1, bildir=satirlar.append) == [
        {"id": "a", "basari": True}]
    assert any("yarım" in s for s in satirlar)


# ── evdeki motor ─────────────────────────────────────────
def test_hat_duserse_evdeki_isci_oksuz_kalmaz(tmp_path, monkeypatch):
    class Surec:
        returncode = None
        oldu = False

        def __init__(self, *a, **k):
            Surec.son = self

        def poll(self):
            return None if not self.oldu else -9

        def wait(self, timeout=None):
            if self.oldu:
                return -9
            raise KeyboardInterrupt  # Ctrl+C ya da bekçide hata

        def kill(self):
            self.oldu = True

    monkeypatch.setattr(motor.subprocess, "Popen", Surec)
    a = ayarlar.yukle()
    i = motor.Is(id="x", gorev="cover", kaynak="k.wav", cikti_klasor=str(tmp_path / "o"), soz="la", adim=1)
    with pytest.raises(KeyboardInterrupt):
        motor.calistir(a, [i], tmp_path / "m", 60, python=tmp_path / "py.exe", bekle=lambda *_: 0)
    assert Surec.son.oldu


def test_suresi_dolmadan_biten_isci_zaman_asimi_sayilmaz(tmp_path):
    isci = tmp_path / "isci.py"
    isci.write_text("import sys; sys.exit(3)", encoding="utf-8")
    a = ayarlar.yukle()
    i = motor.Is(id="x", gorev="cover", kaynak="k.wav", cikti_klasor=str(tmp_path / "o"), soz="la", adim=1)
    r = motor.calistir(a, [i], tmp_path / "m", 60, python=Path(sys.executable), isci=isci,
                       bekle=lambda *_: 0)
    assert "3 koduyla" in r[0].hata


# ── üretim ───────────────────────────────────────────────
def test_bir_sarkinin_sonuc_islemesi_duserse_digerleri_kaydedilir(tmp_path, monkeypatch):
    c = tmp_path / "c"
    _sarki(c, "a1", 60)
    _sarki(c, "b2", 60)
    gercek = uretim._sonuclari_isle

    def bozuk(calisma, baslangic, yeni, onarimlar, kimlik, *k):
        if kimlik == "a1":
            raise OSError("disk dolu")
        return gercek(calisma, baslangic, yeni, onarimlar, kimlik, *k)

    monkeypatch.setattr(uretim, "_sonuclari_isle", bozuk)
    sonuc = uretim.uret(_ayar(), c, calistir=SahteMotor(), degerlendir=GECER)
    assert {d.kimlik: d.asama for d in sonuc} == {"a1": "hata", "b2": "uretildi"}
    assert durum.oku(c, "b2").asama == "uretildi"
    assert durum.oku(c, "a1").asama == "hata" and "disk dolu" in durum.oku(c, "a1").hata  # ücretli tekrar yok


def test_bastan_kilitli_klasorde_durumu_yine_sifirlar(tmp_path, monkeypatch):
    import shutil

    c = tmp_path / "c"
    d = durum.Durum("s", "X", "S", asama="paketlendi", analiz={"stil": "piano"}, secilen=1,
                    kaynak={"dosya": "kaynak.wav", "sure_sn": 200.0})
    d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, gecti=True)]
    durum.yaz(c, d)
    for yol in ("adaylar/1/tam.flac", "paket/X.wav"):
        (c / "s" / yol).parent.mkdir(parents=True, exist_ok=True)
        (c / "s" / yol).write_bytes(b"x")
    gercek = shutil.move

    def tasi(kaynak, hedef):
        if kaynak.endswith("paket"):
            raise PermissionError("dosya başka bir işlemde açık")
        return gercek(kaynak, hedef)

    monkeypatch.setattr(shutil, "move", tasi)
    d = uretim.bastan(c, "s", "deneme", arsiv=tmp_path / "arsiv")
    assert d.asama == "analiz" and d.adaylar == [] and durum.oku(c, "s").asama == "analiz"
    not_ = d.notlar[-1]["bastan"]
    assert not_["tasinan"] == ["adaylar"] and "paket" in not_["tasinamayan"][0]


def test_dosyasiz_adaya_onarim_istenemez_olmayan_onarim_kabul_edilemez():
    a = _ayar()
    d = durum.Durum("s", "X", "S", asama="uretildi")
    d.adaylar = [durum.Aday(1, "", 42), durum.Aday(2, "adaylar/2/tam.flac", 7, gecti=True)]
    with pytest.raises(ValueError, match="sesi yok"):
        uretim.onarim_iste(a, d, 1, 10, 20)
    with pytest.raises(ValueError, match="yok"):
        uretim.onarim_iste(a, d, 9, 10, 20)
    with pytest.raises(ValueError, match="onarım yok"):
        uretim.onarim_kabul(d, 2, "2-1")
    uretim.onarim_iste(a, d, 2, 10, 20)
    assert d.asama == "onarim" and len(d.adaylar[1].onarimlar) == len(a.onarim.tohumlar)


def test_aday_sonundan_sonraki_onarim_araligi_yalniz_onarimi_dusurur(tmp_path):
    """Denetim 7: önce bütün şarkı `hata`ya düşüyordu (tek çıkış `bastan`, iyi adaylar arşive). Şimdi yalnız o onarım
    `hata`, şarkı dinlemeye döner."""
    c = tmp_path / "c"
    _sarki(c, "k", 30)
    uretim.uret(_ayar(), c, calistir=SahteMotor(), degerlendir=GECER)
    with durum.guncelle(c, "k") as d:
        uretim.onarim_iste(_ayar(), d, 1, 40, 45)
    d = uretim.uret(_ayar(), c, calistir=SahteMotor(), degerlendir=GECER)[0]
    onarimlar = next(x for x in d.adaylar if x.no == 1).onarimlar
    assert d.asama == "uretildi" and onarimlar and all(o["durum"] == "hata" and "sonundan" in o["hata"]
                                                       for o in onarimlar)


def test_onarim_istegi_aday_suresini_asamaz(tmp_path):
    a = replace(_ayar(), kok=tmp_path)  # gerçek calisma/'ya dokunulmaz
    c = tmp_path / "calisma"
    _sarki(c, "k", 30)
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    with durum.guncelle(c, "k") as d, pytest.raises(ValueError, match="sonundan"):
        uretim.onarim_iste(a, d, 1, 40, 45)



def test_gecersiz_anahtarli_hesap_obur_hesabi_engellemez(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "iptal")
    monkeypatch.setenv("RUNPOD_API_KEY_2", "ikinci")

    def bakiye(k):
        if k == "iptal":
            raise runpod.RunPodHatasi("RunPod 401: unauthorized")
        return 5.0

    assert runpod.anahtar(tmp_path, 1.0, bakiye) == "ikinci"
    assert runpod.anahtar(tmp_path, 9.0, bakiye) == "ikinci"  # ikisinde de yok: okunabilen hesap (bütçe yazar)
    monkeypatch.setenv("RUNPOD_API_KEY_2", "iptal")
    with pytest.raises(runpod.RunPodHatasi, match="401"):
        runpod.anahtar(tmp_path, 1.0, bakiye)


def test_isci_genel_hatasi_sonucsuz_islere_yazilir(tmp_path):
    isci = tmp_path / "isci.py"
    isci.write_text("import json, sys; json.dump([{'id': None, 'basari': False, 'hata': 'betimleyici yok'}, "
                    "{'id': None, 'basari': False, 'hata': 'LoRA yüklenemedi'}], open(sys.argv[2], 'w')); "
                    "sys.exit(2)", encoding="utf-8")
    i = motor.Is(id="x", gorev="cover", kaynak="k.wav", cikti_klasor=str(tmp_path / "o"), soz="la", adim=1)
    r = motor.calistir(ayarlar.yukle(), [i], tmp_path / "m", 60, python=Path(sys.executable), isci=isci,
                       bekle=lambda *_: 0)
    assert r[0].hata == "LoRA yüklenemedi"


def test_uretim_engeli_kaydedilir_ve_sunucu_acilinca_silinir(tmp_path, monkeypatch):
    """Bakiye bitince üretim bekliyordu ama pano, `yanki durum` ve oturum özeti bunu hiç söylemiyordu."""
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    a = _uzak_ayar(tmp_path, en_az_bakiye=1.0, yerel_yedek=False)
    c = tmp_path / "calisma"
    uzak.motor_sec(a, kayit=lambda _m: None, stok=lambda k, g: "High", bakiye=lambda _k: 0.8,
                   ssh_engeli=lambda: None, butce_bildir=lambda *_a: None)
    e = uzak.uretim_engeli(c)
    assert e["tur"] == "butce" and "0.80" in e["neden"]
    uzak.motor_sec(a, kayit=lambda _m: None, stok=lambda k, g: None, bakiye=lambda _k: 10.0,
                   ssh_engeli=lambda: None)
    assert uzak.uretim_engeli(c)["tur"] == "sunucu"  # stok yok
    calistir, _, uzak_mi = uzak.motor_sec(a, kayit=lambda _m: None, stok=lambda k, g: "High",
                                          bakiye=lambda _k: 10.0, ssh_engeli=lambda: None)
    assert uzak_mi and uzak.uretim_engeli(c) is None


def test_bayat_uretim_engeli_gosterilmez(tmp_path):
    import os
    import time

    c = tmp_path / "calisma"
    c.mkdir()
    yol = c / ".uretim_engeli.json"
    yol.write_text(json.dumps({"tur": "butce", "neden": "x"}), encoding="utf-8")
    assert uzak.uretim_engeli(c)["neden"] == "x"
    eski = time.time() - (uzak.ENGEL_GECERLI_SAAT + 1) * 3600
    os.utime(yol, (eski, eski))
    assert uzak.uretim_engeli(c) is None


def test_pano_ve_ozet_uretim_engelini_soyler(tmp_path):
    from fastapi.testclient import TestClient

    from tests.test_sunucu import ODA
    from yanki import cli, sunucu

    c = tmp_path / "calisma"
    durum.yaz(c, durum.Durum("a-b", "A", "B"))  # sırada bir şarkı
    (c / ".uretim_engeli.json").write_text(json.dumps({"tur": "butce", "neden": "RunPod bakiyesi 0.80 $ (en az "
                                                       "1.00 $): kredi yükle", "zaman": "2026-10-16T13:30:01"}),
                                           encoding="utf-8")
    a = replace(ayarlar.yukle(), uzak=ayarlar.Uzak(acik=True))
    p = TestClient(sunucu.uygulama(a, c, gorev_oku=lambda: {}), base_url=ODA).get("/api/pano").json()
    u = next(x for x in p["uyarilar"] if x["baslik"] == "Üretim bekliyor")
    assert "0.80" in u["metin"] and "aşamasındaki 1 şarkı" in u["metin"] and "13:30" in u["metin"]
    assert "kredi yükle" in p["simdi"]["engel"]  # "Şu an" şarkıları "üretiliyor" değil "sırada" gösterir
    assert "kredi yükle" in cli.ozet(tmp_path)["uretim_engeli"]


def _ffmpeg_var() -> bool:
    from yanki import ses

    try:
        ses.arac("ffmpeg")
        return True
    except FileNotFoundError:
        return False


@pytest.mark.skipif(not _ffmpeg_var(), reason="ffmpeg gerekli")
def test_silinmis_kaynak_kayitli_videodan_geri_gelir(tmp_path):
    """Denetim 7: dondurmada kuyruktaki bütün `kaynak.wav`'lar silinmişti; üretim hepsini `hata`ya düşürürdü."""
    import soundfile as sf

    from yanki import hazirlik

    c = tmp_path / "calisma"
    d = _sarki(c, "k", 30)
    asil = c / "k" / "kaynak.wav"
    yedek = tmp_path / "yedek.wav"
    asil.replace(yedek)
    d.kaynak["nereden"] = "youtube:abc"
    istenen = []

    def indir(vid, hedef):
        istenen.append(vid)
        hedef.write_bytes(yedek.read_bytes())
        return hedef

    assert hazirlik.kaynak_onar(c, d, tmp_path / "girdi", indir=indir) == asil and istenen == ["abc"]
    assert abs(sf.info(str(asil)).duration - 30) < 0.1 and not (c / "k" / "kaynak_ham.indirilen").exists()
    assert hazirlik.kaynak_onar(c, d, tmp_path / "girdi", indir=indir) is None  # yerindeyse dokunulmaz
    asil.unlink()
    d.kaynak["sure_sn"] = 200  # başka sürüm inerse kabul edilmez
    with pytest.raises(hazirlik.kaynak.KaynakYok, match="kayıtta"):
        hazirlik.kaynak_onar(c, d, tmp_path / "girdi", indir=indir)
    assert not asil.exists()
