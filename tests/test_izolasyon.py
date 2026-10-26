"""conftest'teki gerçek veri kapısı her yazma yolunu tutuyor mu: kapı kendisi sınanmazsa yeşil test bir şey
kanıtlamaz."""

import os
import shutil

import pytest

from yanki import ayarlar, dosya

HEDEF = ayarlar.KOK / "calisma" / "_izolasyon_testi.txt"


@pytest.mark.parametrize("yaz", [
    lambda: HEDEF.write_text("x", encoding="utf-8"),
    lambda: HEDEF.write_bytes(b"x"),
    lambda: open(HEDEF, "w", encoding="utf-8"),
    lambda: HEDEF.open("a", encoding="utf-8"),
    lambda: dosya.yaz(HEDEF, "x"),
    lambda: HEDEF.unlink(missing_ok=True),
    lambda: os.remove(HEDEF),
    lambda: (ayarlar.KOK / "girdi" / "_yeni").mkdir(),
    lambda: shutil.rmtree(ayarlar.KOK / "config" / "_yok"),
], ids=["write_text", "write_bytes", "open", "Path.open", "dosya.yaz", "unlink", "os.remove", "mkdir", "rmtree"])
def test_gercek_veriye_yazma_dusurulur(yaz):
    with pytest.raises(AssertionError, match="gerçek veriye"):
        yaz()
    assert not HEDEF.exists()


def test_tasima_ve_kopyalama_hedefi_denetlenir(tmp_path):
    kaynak = tmp_path / "a.txt"
    kaynak.write_text("x", encoding="utf-8")
    for islem in (lambda: shutil.copy(kaynak, HEDEF), lambda: os.replace(kaynak, HEDEF), lambda: kaynak.rename(HEDEF)):
        with pytest.raises(AssertionError, match="gerçek veriye"):
            islem()
    assert kaynak.exists() and not HEDEF.exists()


def test_okuma_ve_gecici_klasor_serbest(tmp_path):
    (tmp_path / "b.txt").write_text("y", encoding="utf-8")
    assert (tmp_path / "b.txt").read_text(encoding="utf-8") == "y"
    with open(ayarlar.KOK / "config" / "yayin.toml", encoding="utf-8") as f:
        assert f.read(1)
