"""`yanki durum`: hattın çalışması için gerekenler yerinde mi."""

import shutil
import subprocess
from dataclasses import dataclass

from yanki.ayarlar import Ayarlar


@dataclass(frozen=True)
class Kontrol:
    ad: str
    tamam: bool
    ayrinti: str


def gpu_kullanilan_mib() -> int | None:
    """nvidia-smi'den kullanılan VRAM; GPU ya da sürücü yoksa None."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        cikti = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
        return int(cikti.strip().splitlines()[0])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None


def _arac_kontrol(ad: str) -> Kontrol:
    """Hattın kullandığı yolla (`ses.arac`: PATH, yoksa winget kurulum yeri); yalnız PATH'e bakınca winget'le
    kurulmuş ffmpeg yeni kabuk açılana kadar ✗ görünüyordu, oysa hat onu buluyordu."""
    from yanki import ses

    try:
        return Kontrol(ad, True, ses.arac(ad))
    except FileNotFoundError as e:
        return Kontrol(ad, False, str(e))


def kontroller(a: Ayarlar) -> list[Kontrol]:
    sonuc = [
        Kontrol("motor venv", a.motor.python.exists(), str(a.motor.python)),
        Kontrol(f"model {a.motor.model}", (a.motor.checkpoints / a.motor.model).is_dir(),
                str(a.motor.checkpoints / a.motor.model)),
        Kontrol("VAE", (a.motor.checkpoints / "vae").is_dir(), str(a.motor.checkpoints / "vae")),
        _arac_kontrol("ffmpeg"),
        _arac_kontrol("ffprobe"),
        Kontrol("fpcalc", a.fpcalc.exists(), str(a.fpcalc)),
    ]
    kullanilan = gpu_kullanilan_mib()
    if kullanilan is None:
        sonuc.append(Kontrol("GPU", False, "nvidia-smi okunamadı"))
    else:
        bos = kullanilan < a.gpu.bos_esik_mib
        sonuc.append(Kontrol("GPU boş", bos, f"{kullanilan} MiB kullanımda (eşik {a.gpu.bos_esik_mib})"))
    return sonuc
