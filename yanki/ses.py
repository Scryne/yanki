"""ffmpeg/ffprobe çağrıları."""

import os
import shutil
import subprocess
from functools import cache
from pathlib import Path


@cache
def arac(ad: str) -> str:
    """PATH'te yoksa winget kurulum yerine bakar (winget PATH'i yalnız yeni kabuklara yansıtır)."""
    if bulunan := shutil.which(ad):
        return bulunan
    paketler = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    for aday in sorted(paketler.glob(f"Gyan.FFmpeg*/*/bin/{ad}.exe"), reverse=True):
        return str(aday)
    raise FileNotFoundError(f"{ad} bulunamadı (winget install Gyan.FFmpeg.Shared)")


# ffmpeg/ffprobe/fpcalc tek çağrısının üst sınırı: 8 dk'lık şarkı saniyeler sürer; takılan bir araç (bozuk dosya,
# kilitli sürücü) koşuyu sonsuza kadar asmasın (TimeoutExpired adımın hatası olur)
ARAC_SURESI = 900


def sure(yol: Path) -> float:
    cikti = subprocess.run(
        [arac("ffprobe"), "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(yol)],
        capture_output=True, text=True, check=True, timeout=ARAC_SURESI,
    ).stdout
    return float(cikti.strip())


def wav48(girdi: Path, cikti: Path) -> Path:
    """ACE-Step'e verilecek biçim: 48 kHz stereo WAV (soundfile hızlı yolu; torchcodec'e düşmez)."""
    cikti.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(girdi), "-ar", "48000", "-ac", "2",
         "-c:a", "pcm_s16le", str(cikti)],
        check=True, timeout=ARAC_SURESI,
    )
    return cikti
