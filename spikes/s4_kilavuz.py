"""S4: Besteden kılavuz ses — orijinal kayıttan tek örnek taşımayan, notalardan sentezlenmiş ses.

Demucs çıktısı (vocals.wav + no_vocals.wav) → basic-pitch ile MIDI → katkılı (additive) sentez → kilavuz.wav
Vokal melodisi önde, eşlik (akorlar, bas) arkada. ACE-Step'e src_audio olarak bu verilir.

  uv run --no-project --python 3.11 --with "basic-pitch[onnx]" --with "setuptools<72" --with soundfile \
      python spikes/s4_kilavuz.py <ayrik_klasor> <cikti.wav>
"""

import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import Model, predict

SR = 48000


def notalar(yol: Path, model, **ayar):
    _, midi, _ = predict(str(yol), model, **ayar)
    return [(n.start, n.end, n.pitch, n.velocity) for ins in midi.instruments for n in ins.notes]


def sentez(nota_listesi, sure: float, kazanc: float, harmonik: int) -> np.ndarray:
    cikti = np.zeros(int(sure * SR) + SR, dtype=np.float32)
    for bas, son, perde, hiz in nota_listesi:
        n = int((son - bas) * SR)
        if n <= 0:
            continue
        t = np.arange(n) / SR
        f0 = 440.0 * 2 ** ((perde - 69) / 12)
        dalga = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, harmonik + 1) if f0 * k < SR / 2)
        zarf = np.minimum(1.0, t / 0.01) * np.exp(-t * 1.5) * np.minimum(1.0, (n - np.arange(n)) / (0.02 * SR))
        i = int(bas * SR)
        cikti[i : i + n] += (kazanc * hiz / 127.0 * dalga * zarf).astype(np.float32)
    return cikti


def main() -> None:
    klasor, hedef = Path(sys.argv[1]), Path(sys.argv[2])
    model = Model(ICASSP_2022_MODEL_PATH)
    vokal = notalar(klasor / "vocals.wav", model, onset_threshold=0.6, frame_threshold=0.4, minimum_note_length=80)
    eslik = notalar(klasor / "no_vocals.wav", model, onset_threshold=0.5, frame_threshold=0.3, minimum_note_length=60)
    sure = sf.info(str(klasor / "vocals.wav")).duration
    karisim = sentez(vokal, sure, 1.0, 6) + sentez(eslik, sure, 0.35, 4)
    karisim = karisim[: int(sure * SR)]
    karisim /= np.abs(karisim).max() + 1e-9
    sf.write(str(hedef), np.stack([karisim, karisim], axis=1) * 0.9, SR)
    print(f"vokal notası={len(vokal)} eşlik notası={len(eslik)} süre={sure:.1f}s → {hedef}")


if __name__ == "__main__":
    main()
