import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from yanki import ayarlar, durum, motor, uretim


def _ayar() -> ayarlar.Ayarlar:
    """Testler gerçek config'teki aday sayısından bağımsız: 2 aday, tohumlar 42 ve 7."""
    a = ayarlar.yukle()
    return replace(a, cover=replace(a.cover, aday_sayisi=2, tohumlar=(42, 7)))


def _sarki(c: Path, kimlik: str, sure: float, satirlar=None) -> durum.Durum:
    k = c / kimlik
    k.mkdir(parents=True)
    t = np.arange(int(sure * uretim.SR)) / uretim.SR
    sf.write(str(k / "kaynak.wav"), (0.3 * np.sin(2 * np.pi * 220 * t)).astype("float32"), uretim.SR)
    (k / "soz.txt").write_text("[verse]\nla la", encoding="utf-8")
    if satirlar is not None:
        (k / "soz_zaman.json").write_text(json.dumps(satirlar), encoding="utf-8")
    d = durum.Durum(kimlik, "A", "B", kaynak={"dosya": "kaynak.wav", "sure_sn": sure}, soz={"dosya": "soz.txt"},
                    analiz={"stil": "s", "bpm": 68, "ton": "A major"})
    d.gec("analiz")
    durum.yaz(c, d)
    return d


class SahteMotor:
    def __init__(self, bozuk: set[str] = frozenset()):
        self.turlar, self.bozuk = [], bozuk

    def __call__(self, a, isler, klasor, zaman_asimi_sn):
        self.turlar.append(isler)
        sonuc = []
        for i in isler:
            if i.id in self.bozuk:
                sonuc.append(motor.Sonuc(i.id, False, "RuntimeError: bozuk"))
                continue
            ses, sr = sf.read(i.kaynak, dtype="float32", always_2d=True)
            if i.gorev == "cover":
                t = np.arange(len(ses)) / sr
                dalga = (0.2 * np.sin(2 * np.pi * (300 + i.tohum) * t))[:, None]
                ses = np.repeat(dalga, ses.shape[1], 1).astype("float32")
            else:  # repaint: yalnız bölge değişir
                b, s = (int(x * sr) for x in i.bolge)
                ses = ses.copy()
                ses[b:s] = 0
            Path(i.cikti_klasor).mkdir(parents=True, exist_ok=True)
            yol = Path(i.cikti_klasor) / "out.flac"
            sf.write(str(yol), ses, sr)
            sonuc.append(motor.Sonuc(i.id, True, cikti=str(yol), sure_sn=1.0))
        return sonuc


GECER = lambda *_: {"dalga": {"gecti": True, "deger": 0.02, "esik": 0.25}}  # noqa: E731
DUSER = lambda *_: {"dalga": {"gecti": False, "deger": 0.9, "esik": 0.25}}  # noqa: E731


def test_kisa_sarki_tek_parca(tmp_path):
    c = tmp_path / "c"
    _sarki(c, "kisa", 60)
    m = SahteMotor()
    uretim.uret(_ayar(), c, calistir=m, degerlendir=GECER)
    d = durum.oku(c, "kisa")
    assert d.asama == "uretildi" and [x.gecti for x in d.adaylar] == [True, True]
    assert len(m.turlar) == 1 and len(m.turlar[0]) == 2  # tek tur, aday başına bir iş
    assert sf.info(str(c / "kisa" / d.adaylar[0].dosya)).duration == pytest.approx(60, abs=0.01)


def test_uzun_sarki_parcali_ve_referansli(tmp_path):
    c = tmp_path / "c"
    satirlar = [[t, f"satır {t}"] for t in range(5, 245, 10)]
    _sarki(c, "uzun", 250, satirlar)
    m = SahteMotor()
    uretim.uret(_ayar(), c, calistir=m, degerlendir=GECER)
    d = durum.oku(c, "uzun")
    assert d.asama == "uretildi"
    tur1, tur2 = m.turlar
    assert [i.id for i in tur1] == ["uzun|cover|1|1", "uzun|cover|2|1"]
    assert len(tur2) == 2 * 2  # 3 parça → aday başına 2 parça daha
    ilk1 = next(Path(i.cikti_klasor) for i in tur1 if i.id.endswith("|1|1"))
    assert all(Path(i.referans).parent == ilk1 for i in tur2 if "|cover|1|" in i.id)
    assert all("satır" in i.soz for i in tur1 + tur2)  # her parçaya kendi sözü
    assert sf.info(str(c / "uzun" / d.adaylar[0].dosya)).duration == pytest.approx(250, abs=0.05)


def test_motor_hatasi_adayi_dusurur_digerini_birakir(tmp_path):
    c = tmp_path / "c"
    _sarki(c, "kisa", 60)
    uretim.uret(_ayar(), c, calistir=SahteMotor({"kisa|cover|2|1"}), degerlendir=GECER)
    d = durum.oku(c, "kisa")
    assert d.asama == "uretildi" and [x.gecti for x in d.adaylar] == [True, False]
    assert "bozuk" in d.adaylar[1].kapilar["motor"]["hata"]


def test_hicbir_aday_gecmezse_hata(tmp_path):
    c = tmp_path / "c"
    _sarki(c, "kisa", 60)
    uretim.uret(_ayar(), c, calistir=SahteMotor(), degerlendir=DUSER)
    d = durum.oku(c, "kisa")
    assert d.asama == "hata" and "aday 1: dalga" in d.hata


def test_pencereli_onarim_yalniz_bolgeyi_degistirir(tmp_path):
    c = tmp_path / "c"
    a = _ayar()
    _sarki(c, "uzun", 250, [[t, f"satır {t}"] for t in range(5, 245, 10)])
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    d = durum.oku(c, "uzun")
    uretim.onarim_iste(a, d, 1, 100.0, 104.0)
    durum.yaz(c, d)
    m = SahteMotor()
    uretim.uret(a, c, calistir=m, degerlendir=GECER)
    d = durum.oku(c, "uzun")
    assert d.asama == "uretildi"
    assert len(m.turlar) == 1 and all(i.gorev == "repaint" for i in m.turlar[0])
    pencere = sf.info(m.turlar[0][0].kaynak).duration
    assert pencere == pytest.approx(4 + 2 * uretim.PENCERE_PAYI, abs=0.05)  # tüm şarkı değil
    o = d.adaylar[0].onarimlar[0]
    assert o["durum"] == "hazir"
    temel, _ = sf.read(str(c / "uzun" / o["temel"]), dtype="float32", always_2d=True)
    onarilan, sr = sf.read(str(c / "uzun" / o["dosya"]), dtype="float32", always_2d=True)
    assert len(onarilan) == len(temel)
    assert np.allclose(onarilan[: 70 * sr], temel[: 70 * sr]) and np.allclose(onarilan[140 * sr:], temel[140 * sr:])
    bolge = onarilan[int((100 - a.onarim.pay_sn + 0.6) * sr): int((104 + a.onarim.pay_sn - 0.6) * sr)]
    assert np.abs(bolge).max() < 1e-3  # sahte repaint bölgeyi sıfırladı
    uretim.onarim_kabul(d, 1, o["id"])
    assert d.adaylar[0].dosya == o["dosya"] and d.adaylar[0].onarimlar[1]["durum"] == "ret"


def test_zaman_damgasi_eksikse_lrclibden_tamamlanir(tmp_path):
    from yanki import sozler

    c = tmp_path / "c"
    d = _sarki(c, "eski", 250)  # soz_zaman.json yok (eski hazırlık)
    d.soz["kaynak"] = "lrclib"
    satirlar = tuple((float(t), f"s{t}") for t in range(5, 245, 10))
    plan, sozler_ = uretim.parca_plani(c, d, lrclib=lambda *a: sozler.Soz("x", "lrclib", 250.0, satirlar))
    assert len(plan) == 3 and (c / "eski" / "soz_zaman.json").exists()
    assert not d.notlar


def test_zaman_damgasi_hic_yoksa_tek_parca_ve_uyari(tmp_path):
    c = tmp_path / "c"
    d = _sarki(c, "dosya", 250)
    d.soz["kaynak"] = "dosya"
    plan, _ = uretim.parca_plani(c, d)
    assert len(plan) == 1 and "tek parça" in d.notlar[-1]["uyari"]


def test_stil_degisince_yeni_adaylar_eskilerin_ardindan(tmp_path):
    c, a = tmp_path / "c", _ayar()
    _sarki(c, "s", 60)
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    d = durum.oku(c, "s")
    eski_dosya = d.adaylar[0].dosya
    uretim.stil_degistir(d, "acoustic guitar ballad", 70, "A major")
    durum.yaz(c, d)
    m = SahteMotor()
    uretim.uret(a, c, calistir=m, degerlendir=DUSER)  # yeni stil kötü çıksa da eski adaylar şarkıyı taşır
    d = durum.oku(c, "s")
    assert [x.no for x in d.adaylar] == [1, 2, 3, 4]
    assert [x.stil for x in d.adaylar] == ["s", "s", "acoustic guitar ballad", "acoustic guitar ballad"]
    assert [i.stil for i in m.turlar[0]] == ["acoustic guitar ballad"] * 2 and [i.bpm for i in m.turlar[0]] == [70, 70]
    assert d.adaylar[0].dosya == eski_dosya and (c / "s" / eski_dosya).exists()
    assert d.asama == "uretildi" and [x.gecti for x in d.adaylar] == [True, True, False, False]


def test_stil_degisimi_onarim_beklerken_reddedilir(tmp_path):
    c, a = tmp_path / "c", _ayar()
    _sarki(c, "s", 60)
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    d = durum.oku(c, "s")
    uretim.onarim_iste(a, d, 1, 10, 12)
    with pytest.raises(ValueError):
        uretim.stil_degistir(d, "rock", None, "")


def test_gercek_configteki_aday_sayisi_kadar_aday(tmp_path):
    c, a = tmp_path / "c", ayarlar.yukle()
    _sarki(c, "s", 60)
    m = SahteMotor()
    uretim.uret(a, c, calistir=m, degerlendir=GECER)
    d = durum.oku(c, "s")
    assert [x.no for x in d.adaylar] == list(range(1, a.cover.aday_sayisi + 1))
    assert [x.tohum for x in d.adaylar] == list(a.cover.tohumlar[: a.cover.aday_sayisi])


def test_onayli_sarki_yeniden_uretimde_eskileri_korur(tmp_path):
    c, a = tmp_path / "c", _ayar()
    _sarki(c, "s", 60)
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    d = durum.oku(c, "s")
    d.secilen = 1
    d.gec("paketlendi")
    uretim.yeniden_uretime_al(d)
    assert d.asama == "analiz" and d.secilen is None
    assert d.notlar[-1]["yeniden_uretim"] == {"onceki_asama": "paketlendi", "onceki_secilen": 1}
    durum.yaz(c, d)
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    d = durum.oku(c, "s")
    assert [x.no for x in d.adaylar] == [1, 2, 3, 4] and d.asama == "uretildi"


def test_yuklenmis_sarki_yeniden_uretilmez(tmp_path):
    c, a = tmp_path / "c", _ayar()
    _sarki(c, "s", 60)
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    d = durum.oku(c, "s")
    d.gec("yuklendi")
    with pytest.raises(ValueError):
        uretim.yeniden_uretime_al(d)


def test_yeniden_komutu_eski_paketi_kenara_alir(tmp_path, monkeypatch):
    from yanki import cli

    c, a = tmp_path / "calisma", _ayar()
    _sarki(c, "s", 60)
    uretim.uret(a, c, calistir=SahteMotor(), degerlendir=GECER)
    d = durum.oku(c, "s")
    d.secilen = 1
    d.gec("paketlendi")
    durum.yaz(c, d)
    (c / "s" / "paket").mkdir()
    (c / "s" / "paket" / "YUKLE.md").write_text("eski", encoding="utf-8")
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: replace(a, kok=tmp_path))
    assert cli.main(["yeniden", "s"]) == 0
    assert not (c / "s" / "paket").exists() and (c / "s" / "paket_onceki" / "YUKLE.md").exists()
    assert durum.oku(c, "s").asama == "analiz"


# ── veto penceresi ve temizlik ──────────────────────────────
def _uretilmis(c, gecmis_zaman="2026-10-01T03:00:00"):
    from yanki import durum

    d = durum.Durum("a-b", "A", "B", asama="uretildi")
    d.gecmis = [{"zaman": gecmis_zaman, "asama": "uretildi", "hata": None}]
    d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, {"soz_wer": {"deger": 0.2, "gecti": True}}, True),
                 durum.Aday(2, "adaylar/2/tam.flac", 7, {"soz_wer": {"deger": 0.05, "gecti": True}}, True),
                 durum.Aday(3, "", 123, {"motor": {"gecti": False}}, False)]
    durum.yaz(c, d)
    return d


def test_otomatik_onay_kapali_iken_dokunmaz(tmp_path):
    from datetime import datetime

    from yanki import durum, onay

    _uretilmis(tmp_path)
    assert onay.uygula(tmp_path, onay.Ayar(acik=False), datetime(2026, 10, 9)) == []
    assert durum.oku(tmp_path, "a-b").asama == "uretildi"


def test_otomatik_onay_sure_dolunca_en_dusuk_wer(tmp_path):
    from datetime import datetime

    from yanki import durum, onay

    _uretilmis(tmp_path)
    ayar = onay.Ayar(acik=True, sure_saat=72)
    assert onay.uygula(tmp_path, ayar, datetime(2026, 10, 3, 12)) == []  # 57 saat: pencere açık
    assert [d.kimlik for d in onay.yaklasan(tmp_path, ayar, 24, datetime(2026, 10, 3, 12))] == ["a-b"]
    (d, a), = onay.uygula(tmp_path, ayar, datetime(2026, 10, 4, 4))
    d = durum.oku(tmp_path, "a-b")
    assert (d.asama, d.secilen, a.no) == ("onaylandi", 2, 2) and d.notlar[-1]["otomatik_onay"]["aday"] == 2


def test_otomatik_onay_bekleyen_onarimli_adayi_onermez(tmp_path):
    from yanki import onay

    d = _uretilmis(tmp_path)
    d.adaylar[1].onarimlar = [{"id": "x", "durum": "bekliyor"}]
    assert onay.oneri(d).no == 1


def test_temizlik_yalniz_yuklenmis_ve_eski(tmp_path):
    from datetime import datetime

    from yanki import durum, temizlik

    d = durum.Durum("a-b", "A", "B", asama="yuklendi", secilen=2)
    d.gecmis = [{"zaman": "2026-10-01T10:00:00", "asama": "yuklendi", "hata": None}]
    d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, {}, True), durum.Aday(2, "adaylar/2/tam.flac", 7, {}, True)]
    durum.yaz(tmp_path, d)
    k = tmp_path / "a-b"
    for yol in ("adaylar/1/tam.flac", "adaylar/2/tam.flac", "adaylar/2/tam.flac.dalga.json", "parcalar/p1.flac",
                "paket/x.flac", "kaynak.wav"):
        (k / yol).parent.mkdir(parents=True, exist_ok=True)
        (k / yol).write_bytes(b"x" * 10)
    assert temizlik.plan(tmp_path, d, 14, datetime(2026, 10, 9)) is None  # 8 gün: erken
    p = temizlik.plan(tmp_path, d, 14, datetime(2026, 10, 20))
    assert sorted(f.relative_to(k).as_posix() for f in p.dosyalar) == ["adaylar/1/tam.flac", "parcalar/p1.flac"]
    temizlik.uygula(tmp_path, d, p)
    d = durum.oku(tmp_path, "a-b")
    assert (k / "adaylar/2/tam.flac").exists() and (k / "paket/x.flac").exists() and (k / "kaynak.wav").exists()
    assert not (k / "parcalar").exists() and d.adaylar[0].dosya == "" and d.adaylar[1].dosya == "adaylar/2/tam.flac"
    d.asama = "paketlendi"
    assert temizlik.plan(tmp_path, d, 0, datetime(2026, 10, 20)) is None  # yüklenmemiş şarkıya dokunmaz
