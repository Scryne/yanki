import subprocess

from yanki import ayarlar, saglik


def test_gpu_okunamazsa_kontrol_basarisiz(monkeypatch):
    monkeypatch.setattr(saglik, "gpu_kullanilan_mib", lambda: None)
    k = {x.ad: x for x in saglik.kontroller(ayarlar.yukle())}
    assert not k["GPU"].tamam


def test_gpu_esigi(monkeypatch):
    a = ayarlar.yukle()
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
