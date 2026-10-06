import json
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from yanki import ayarlar, durum, motor, uretim


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
    uretim.uret(ayarlar.yukle(), c, calistir=m, degerlendir=GECER)
    d = durum.oku(c, "kisa")
    assert d.asama == "uretildi" and [x.gecti for x in d.adaylar] == [True, True]
    assert len(m.turlar) == 1 and len(m.turlar[0]) == 2  # tek tur, aday başına bir iş
    assert sf.info(str(c / "kisa" / d.adaylar[0].dosya)).duration == pytest.approx(60, abs=0.01)


def test_uzun_sarki_parcali_ve_referansli(tmp_path):
    c = tmp_path / "c"
    satirlar = [[t, f"satır {t}"] for t in range(5, 245, 10)]
    _sarki(c, "uzun", 250, satirlar)
    m = SahteMotor()
    uretim.uret(ayarlar.yukle(), c, calistir=m, degerlendir=GECER)
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
    uretim.uret(ayarlar.yukle(), c, calistir=SahteMotor({"kisa|cover|2|1"}), degerlendir=GECER)
    d = durum.oku(c, "kisa")
    assert d.asama == "uretildi" and [x.gecti for x in d.adaylar] == [True, False]
    assert "bozuk" in d.adaylar[1].kapilar["motor"]["hata"]


def test_hicbir_aday_gecmezse_hata(tmp_path):
    c = tmp_path / "c"
    _sarki(c, "kisa", 60)
    uretim.uret(ayarlar.yukle(), c, calistir=SahteMotor(), degerlendir=DUSER)
    d = durum.oku(c, "kisa")
    assert d.asama == "hata" and "aday 1: dalga" in d.hata


def test_pencereli_onarim_yalniz_bolgeyi_degistirir(tmp_path):
    c = tmp_path / "c"
    a = ayarlar.yukle()
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
