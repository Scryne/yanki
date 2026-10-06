"""S7: Scryne'ın kulakla bulduğu dört kusurun ölçülebilir vekilleri (2026-10-06: "kalite çok kötü").

  uv run --no-project --python 3.11 --with demucs --with librosa --with faster-whisper --with jiwer --with soundfile \
      --with torch==2.7.1+cu128 --with torchaudio==2.7.1+cu128 \
      --index https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match \
      python spikes/s7_kusur.py --soz soz.txt <orijinal.wav> <aday1> [<aday2> ...]

Her ölçü orijinale göre basılır (orijinal = insan performansı, tavan):
- soz_wer          sözler yutuluyor   → Whisper dökümü ile kaynak sözleri arası WER
- perde_sapma_sent detone             → vokal (Demucs) perdesinin en yakın yarım tona ortalama uzaklığı, sent;
                                         vibrato yüzünden orijinal de sıfır değildir, karşılaştır
- perde_titreme    metalik/robotik    → ardışık karelerde perde sıçraması (sent/kare, medyan); yapay vokalde yüksek
- vurus_kararsiz   ritim kayıyor      → vuruşlar arası sürenin değişim katsayısı
- tiz_oran         bulanık/çamurlu    → 4 kHz üstü enerjinin toplam enerjiye oranı (orijinale göre düşükse boğuk)
"""

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import jiwer
import librosa
import numpy as np

SR = 22050


def vokal_ayir(yol: Path, kok: Path) -> Path:
    hedef = kok / "htdemucs" / yol.stem / "vocals.wav"
    if not hedef.exists():
        subprocess.run([sys.executable, "-m", "demucs", "--two-stems=vocals", "-n", "htdemucs", "-o", str(kok), str(yol)],
                       check=True, capture_output=True)
    return hedef


def perde(vokal: Path):
    y = librosa.load(str(vokal), sr=16000, mono=True)[0]
    f0, sesli, _ = librosa.pyin(y, fmin=70, fmax=1000, sr=16000, hop_length=320, frame_length=1024)
    m = librosa.hz_to_midi(f0[sesli])
    if len(m) < 20:
        return float("nan"), float("nan")
    sapma = np.abs(m - np.round(m)) * 100
    sicrama = np.abs(np.diff(m)) * 100
    sicrama = sicrama[sicrama < 150]  # nota geçişlerini değil, nota içi titremeyi say
    return float(np.mean(sapma)), float(np.median(sicrama))


def ritim(y) -> float:
    _, vuruslar = librosa.beat.beat_track(y=y, sr=SR, units="time")
    aralik = np.diff(vuruslar)
    return float(np.std(aralik) / np.mean(aralik)) if len(aralik) > 4 else float("nan")


def tiz(y) -> float:
    S = np.abs(librosa.stft(y, n_fft=2048)) ** 2
    f = librosa.fft_frequencies(sr=SR, n_fft=2048)
    return float(S[f >= 4000].sum() / (S.sum() + 1e-12))


_w = None


def wer(yol: Path, ref: str) -> float:
    global _w
    if _w is None:
        from faster_whisper import WhisperModel

        _w = WhisperModel("small.en", device="cpu", compute_type="int8")
    ses = librosa.load(str(yol), sr=16000, mono=True)[0]
    hyp = " ".join(p.text for p in _w.transcribe(ses, language="en", beam_size=5)[0])
    norm = lambda s: re.sub(r"\s+", " ", re.sub(r"[^a-z' ]+", " ", re.sub(r"\[[^\]]*\]", " ", s.lower()))).strip()  # noqa: E731
    return jiwer.wer(norm(ref), norm(hyp)) if norm(hyp) else 1.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--soz", required=True)
    ap.add_argument("dosyalar", nargs="+")
    a = ap.parse_args()
    ref = Path(a.soz).read_text(encoding="utf-8")
    kok = Path(tempfile.gettempdir()) / "yanki_s7"
    print(f"{'dosya':36} {'wer':>5} {'sapma¢':>7} {'titreme¢':>8} {'vuruşCV':>7} {'tiz%':>6}")
    for i, d in enumerate(a.dosyalar):
        p = Path(d).resolve()
        # demucs çıktı adı dosya kökünden gelir; aynı adlı dosyalar çakışmasın
        kopya = kok / "girdi" / f"{i:02d}_{p.parent.name}_{p.stem}"[:60]
        kopya = kopya.with_suffix(p.suffix)
        kopya.parent.mkdir(parents=True, exist_ok=True)
        if not kopya.exists():
            kopya.write_bytes(p.read_bytes())
        y = librosa.load(str(p), sr=SR, mono=True)[0]
        sapma, titreme = perde(vokal_ayir(kopya, kok))
        ad = ("ORİJİNAL " if i == 0 else "") + p.parent.name + "/" + p.name
        print(f"{ad[:36]:36} {wer(p, ref):5.2f} {sapma:7.1f} {titreme:8.1f} {ritim(y):7.3f} {100 * tiz(y):6.2f}", flush=True)


if __name__ == "__main__":
    main()
