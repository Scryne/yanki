import json
import sys
from pathlib import Path

import pytest

from yanki import ayarlar, motor

SAHTE_ISCI = '''
import json, sys
from pathlib import Path
is_ = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
davranis = is_["isler"][0]["stil"]
if davranis == "cokme":
    sys.exit(3)
if davranis == "model_yok":
    Path(sys.argv[2]).write_text(json.dumps([{"id": None, "basari": False, "hata": "model yüklenemedi: x"}]))
    sys.exit(2)
if davranis == "uyu":
    import time; time.sleep(30)
sonuc = []
for i in is_["isler"]:
    if i["tohum"] == 13:
        sonuc.append({"id": i["id"], "basari": False, "hata": "RuntimeError: kötü tohum"})
    else:
        out = Path(i["cikti_klasor"]) / (i["id"] + ".flac")
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(b"x")
        sonuc.append({"id": i["id"], "basari": True, "cikti": str(out), "sure_sn": 1.0, "cikti_sure_sn": 90.0})
Path(sys.argv[2]).write_text(json.dumps(sonuc), encoding="utf-8")
sys.exit(0 if all(s["basari"] for s in sonuc) else 1)
'''


@pytest.fixture
def isci(tmp_path):
    yol = tmp_path / "sahte_isci.py"
    yol.write_text(SAHTE_ISCI, encoding="utf-8")
    return yol


def _is(id_="a", tohum=1, stil="normal", **k):
    return motor.Is(id=id_, gorev="cover", kaynak="k.wav", cikti_klasor=k.pop("cikti", "c"), stil=stil, soz="la la",
                    adim=8, tohum=tohum, **k)


def _calistir(tmp_path, isci, isler, **k):
    return motor.calistir(ayarlar.yukle(), isler, tmp_path / "is", zaman_asimi_sn=k.pop("zaman", 20),
                          python=Path(sys.executable), isci=isci, bekle=lambda *_: 0, **k)


def test_basarili_ve_basarisiz_is_ayri_doner(tmp_path, isci):
    s = _calistir(tmp_path, isci, [_is("a", cikti=str(tmp_path / "c")), _is("b", tohum=13, cikti=str(tmp_path / "c"))])
    assert [x.basari for x in s] == [True, False]
    assert Path(s[0].cikti).exists()
    assert "kötü tohum" in s[1].hata
    yazilan = json.loads((tmp_path / "is" / "motor_is.json").read_text(encoding="utf-8"))
    assert yazilan["motor"]["niceleme"] == "int8_weight_only"
    assert yazilan["isler"][0]["soz"] == "la la"


def test_goreli_klasor_isciye_mutlak_gider(tmp_path, isci, monkeypatch):
    # işçi motor klasöründe (cwd) başlar; göreli iş yolu orada bulunamazdı (Faz 2 gerçek koşusu)
    monkeypatch.chdir(tmp_path)
    s = motor.calistir(ayarlar.yukle(), [_is("a", cikti=str(tmp_path / "c"))], Path("goreli/is"), zaman_asimi_sn=20,
                       python=Path(sys.executable), isci=isci, bekle=lambda *_: 0)
    assert s[0].basari, s[0].hata


def test_isci_cokerse_her_is_hata_alir(tmp_path, isci):
    s = _calistir(tmp_path, isci, [_is(stil="cokme"), _is("b", stil="cokme")])
    assert not any(x.basari for x in s)
    assert all("3 koduyla" in x.hata for x in s)


def test_model_yuklenemezse_hata_isleri_tasir(tmp_path, isci):
    s = _calistir(tmp_path, isci, [_is(stil="model_yok")])
    assert "model yüklenemedi" in s[0].hata


def test_zaman_asimi(tmp_path, isci):
    s = _calistir(tmp_path, isci, [_is(stil="uyu")], zaman=2)
    assert "zaman aşımı" in s[0].hata


def test_sozsuz_is_reddedilir():
    with pytest.raises(ValueError, match="söz"):
        motor.Is(id="a", gorev="cover", kaynak="k", cikti_klasor="c", stil="s", soz="  ", adim=8, tohum=1)


def test_complete_parcalarla_talimat():
    sys.path.insert(0, str(Path(motor.ISCI).parent))
    from motor_isci import talimat

    t = {"complete": "Complete the input track with {TRACK_CLASSES}:", "complete_default": "Complete the input track:",
         "cover": "Generate audio semantic tokens based on the given conditions:"}
    assert talimat(t, "complete", ["drums", "bass"]) == "Complete the input track with DRUMS | BASS:"
    assert talimat(t, "complete", []) == "Complete the input track:"
    assert talimat(t, "cover") == t["cover"]
    i = motor.Is(id="a", gorev="complete", kaynak="v.wav", cikti_klasor="c", stil="s", soz="x", adim=64, tohum=1,
                 parcalar=("drums", "bass"))
    assert i.parcalar == ("drums", "bass")


@pytest.mark.parametrize("bolge", [None, (5.0, 5.0), (-1.0, 3.0)])
def test_repaint_bolge_ister(bolge):
    with pytest.raises(ValueError, match="bölge"):
        motor.Is(id="a", gorev="repaint", kaynak="k", cikti_klasor="c", stil="s", soz="x", adim=8, tohum=1, bolge=bolge)


def test_gpu_bekle_bosalinca_doner():
    a = ayarlar.yukle()
    okumalar = iter([a.gpu.bos_esik_mib + 500, a.gpu.bos_esik_mib + 10, 700])
    uykular = []
    assert motor.gpu_bekle(a, 3600, okuyucu=lambda: next(okumalar), uyku=uykular.append, saat=lambda: 0.0) == 700
    assert len(uykular) == 2


def test_gpu_bekle_zaman_asimi():
    a = ayarlar.yukle()
    zaman = iter(range(0, 10000, 100))
    with pytest.raises(motor.GpuMesgul):
        motor.gpu_bekle(a, 250, okuyucu=lambda: 7000, uyku=lambda _: None, saat=lambda: next(zaman))


def test_gpu_okunamazsa_hata():
    with pytest.raises(RuntimeError, match="okunamadı"):
        motor.gpu_bekle(ayarlar.yukle(), 10, okuyucu=lambda: None)


def test_motor_kurulu_degilse_acik_hata(tmp_path, monkeypatch):
    a = ayarlar.yukle()
    from dataclasses import replace

    a = replace(a, motor=replace(a.motor, klasor=tmp_path / "olmayan"))
    s = motor.calistir(a, [_is()], tmp_path / "is", zaman_asimi_sn=5, bekle=lambda *_: 0)
    assert "motor bulunamadı" in s[0].hata


def test_motor_klasoru_yoksa_is_klasorunde_baslar(tmp_path, isci):
    # CI'da motor klasörü yok: işçi orada başlatılamazdı (NotADirectoryError)
    from dataclasses import replace

    a = ayarlar.yukle()
    a = replace(a, motor=replace(a.motor, klasor=tmp_path / "olmayan"))
    s = motor.calistir(a, [_is("a", cikti=str(tmp_path / "c"))], tmp_path / "is", zaman_asimi_sn=20,
                       python=Path(sys.executable), isci=isci, bekle=lambda *_: 0)
    assert s[0].basari, s[0].hata


def test_ilerlemeyen_isci_bekci_ile_durdurulur(tmp_path, isci):
    """2026-10-10: VAE çözme paylaşımlı belleğe taşıp bir saat ilerlemedi, koşu toplam zaman aşımına (3 sa 45 dk)
    kadar bekleyecekti. Günlüğe yazmayan işçi `hareketsiz_sn` sonra durdurulur."""
    import time

    t = time.monotonic()
    (s,) = _calistir(tmp_path, isci, [_is(stil="uyu")], zaman=60, hareketsiz_sn=1, bekci_aralik_sn=0.2)
    assert not s.basari and "ilerlemedi" in s.hata and time.monotonic() - t < 15
