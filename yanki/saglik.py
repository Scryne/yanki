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
    sonuc += [*anahtar_kontrolleri(a), disk_kontrolu(a)]
    kullanilan = gpu_kullanilan_mib()
    if kullanilan is None:
        sonuc.append(Kontrol("GPU", False, "nvidia-smi okunamadı"))
    else:
        bos = kullanilan < a.gpu.bos_esik_mib
        sonuc.append(Kontrol("GPU boş", bos, f"{kullanilan} MiB kullanımda (eşik {a.gpu.bos_esik_mib})"))
    return sonuc


DISK_EN_AZ_GB = 20  # şarkı başı ~300–450 MB ara ses; gece iki şarkıyla haftada ~6 GB (temizlik 14 gün sonra siler)


def disk_kontrolu(a: Ayarlar) -> Kontrol:
    bos = shutil.disk_usage(a.kok).free / 1e9
    return Kontrol("disk", bos >= DISK_EN_AZ_GB, f"{bos:,.0f} GB boş (en az {DISK_EN_AZ_GB})")


def anahtar_kontrolleri(a: Ayarlar) -> list[Kontrol]:
    """Dış servis anahtarları yerinde mi (ağa çıkmaz; değer yazılmaz). Yoksa ilgili adım atlanır, hat yine çalışır."""
    import os

    from yanki import spotify

    # .env'nin tamamı (spotify.env_oku Spotify dışındakileri de okur) + ortam değişkenleri (Tunearo ve TypeSafe orada
    # da olabilir)
    e = {**spotify.env_oku(a.kok), **{k: v for k, v in os.environ.items() if k.startswith(("TUNEARO_", "TYPESAFE_"))}}
    var =lambda *adlar: all(e.get(x) for x in adlar)  # noqa: E731
    return [
        Kontrol("Tunearo anahtarı", var("TUNEARO_API_KEY"), "yükleme ve durum yoklaması" if var("TUNEARO_API_KEY")
                else ".env → TUNEARO_API_KEY yok: yükleme otomatik değil"),
        Kontrol("Spotify anahtarı", var("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"),
                "keşif doğrulaması ve takip" if var("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
                else ".env → SPOTIFY_CLIENT_ID/SECRET yok: keşif doğrulanmaz, takip yok"),
        Kontrol("TypeSafe anahtarı", var("TYPESAFE_API_KEY"), "keşif özgünlük kararı (Jev)" if var("TYPESAFE_API_KEY")
                else ".env → TYPESAFE_API_KEY yok: özgünlük regex yedeğiyle"),
    ]
