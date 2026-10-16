import subprocess

from yanki import ayarlar, saglik


def _evde_uretim(a):
    from dataclasses import replace

    return replace(a, uzak=replace(a.uzak, acik=False))


def test_gpu_okunamazsa_kontrol_basarisiz(monkeypatch):
    monkeypatch.setattr(saglik, "gpu_kullanilan_mib", lambda: None)
    k = {x.ad: x for x in saglik.kontroller(_evde_uretim(ayarlar.yukle()))}
    assert not k["GPU"].tamam


def test_evde_uretim_kapaliyken_dolu_gpu_hata_sayilmaz(monkeypatch):
    from dataclasses import replace

    a = ayarlar.yukle()
    a = replace(a, uzak=replace(a.uzak, acik=True, yerel_yedek=False))
    monkeypatch.setattr(saglik, "gpu_kullanilan_mib", lambda: a.gpu.bos_esik_mib + 1)
    k = {x.ad: x for x in saglik.kontroller(a)}["GPU boş"]
    assert k.tamam and "evde üretim kapalı" in k.ayrinti


def test_gpu_esigi(monkeypatch):
    a = _evde_uretim(ayarlar.yukle())
    monkeypatch.setattr(saglik, "gpu_kullanilan_mib", lambda: a.gpu.bos_esik_mib + 1)
    assert not {x.ad: x for x in saglik.kontroller(a)}["GPU boş"].tamam
    monkeypatch.setattr(saglik, "gpu_kullanilan_mib", lambda: a.gpu.bos_esik_mib - 1)
    assert {x.ad: x for x in saglik.kontroller(a)}["GPU boş"].tamam


def test_nvidia_smi_bozuk_cikti(monkeypatch):
    monkeypatch.setattr(saglik.shutil, "which", lambda _: "nvidia-smi")

    def sahte(*_a, **_k):
        return subprocess.CompletedProcess([], 0, stdout="N/A\n")

    monkeypatch.setattr(saglik.subprocess, "run", sahte)
    assert saglik.gpu_kullanilan_mib() is None
