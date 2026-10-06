from pathlib import Path

import pytest

from yanki import ayarlar


def test_proje_ayarlari_yuklenir():
    a = ayarlar.yukle()
    assert a.motor.model == "acestep-v15-xl-sft"
    assert a.motor.niceleme == "int8_weight_only"
    assert a.cover.gorev == "cover"
    assert 0 < a.cover.guc <= 1
    assert len(a.cover.tohumlar) >= a.cover.aday_sayisi
    assert a.motor.python.name == "python.exe"


def _yaz(tmp_path: Path, guc: float = 0.7, tohumlar: str = "[1, 2]", aday: int = 2) -> Path:
    yol = tmp_path / "motor.toml"
    yol.write_text(
        f"""
[motor]
klasor = "m"
model = "x"
niceleme = ""
cpu_offload = true
lm_model = "lm"
analiz_model = "t"
[cover]
gorev = "cover"
guc = {guc}
adim = 10
aday_sayisi = {aday}
tohumlar = {tohumlar}
[onarim]
gorev = "repaint"
adim = 10
pay_sn = 1.0
tohumlar = [3]
[gpu]
bos_esik_mib = 2000
bekleme_sn = 1
[araclar]
fpcalc = "f.exe"
""",
        encoding="utf-8",
    )
    return yol


def test_bos_niceleme_none_olur(tmp_path):
    a = ayarlar.yukle(_yaz(tmp_path), kok=tmp_path)
    assert a.motor.niceleme is None
    assert a.motor.klasor == tmp_path / "m"


def test_tohum_sayisi_aday_sayisindan_az_olamaz(tmp_path):
    with pytest.raises(ValueError, match="tohumlar"):
        ayarlar.yukle(_yaz(tmp_path, tohumlar="[1]", aday=2), kok=tmp_path)


@pytest.mark.parametrize("guc", [0.0, 1.5])
def test_guc_araligi(tmp_path, guc):
    with pytest.raises(ValueError, match="guc"):
        ayarlar.yukle(_yaz(tmp_path, guc=guc), kok=tmp_path)
