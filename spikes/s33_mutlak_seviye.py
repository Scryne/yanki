"""S33 ek ölçü: parça seviyeleri miksin toplamına göre (dB), cover (G, CFG 10) − orijinal.

S32/S33'ün "bas −4 dB" ölçüsü vokale göreydi; vokal öne çıktıysa eşlik olduğundan ince görünür. Burada her parça
dört parçanın toplamının RMS'ine göre ölçülür: vokalin önde mi, eşliğin eksik mi olduğu ayrılır. Demucs çalışmaz;
S32'nin orijinal parçaları ve S33'ün G parçaları kullanılır.

  uv run --no-sync python spikes/s33_mutlak_seviye.py
"""

from pathlib import Path

import numpy as np
import soundfile as sf

KOK = Path(__file__).resolve().parents[1]
SPIKE = KOK / "calisma" / "_spike"
PARCALAR = ("vocals", "bass", "other", "drums")


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)) + 1e-12))


def olc(klasor: Path) -> dict[str, float]:
    p = {n: sf.read(klasor / f"{n}.wav", dtype="float32")[0] for n in PARCALAR}
    m = min(len(v) for v in p.values())
    toplam = _rms(sum(v[:m] for v in p.values()))
    return {n: 20 * np.log10(_rms(v[:m]) / toplam) for n, v in p.items()}


def main() -> None:
    farklar = {}
    for g in sorted((SPIKE / "s33").glob("*/G")):
        orijinal = SPIKE / "s32" / g.parent.name / "orijinal"
        if orijinal.is_dir():
            a, b = olc(orijinal), olc(g)
            farklar[g.parent.name] = {n: b[n] - a[n] for n in PARCALAR}
    for s, f in farklar.items():
        print(f"{s[:34]:34} " + "  ".join(f"{n[:3]} {f[n]:+5.1f}" for n in PARCALAR))
    print(f"{'medyan':34} " + "  ".join(f"{n[:3]} {np.median([f[n] for f in farklar.values()]):+5.1f}"
                                         for n in PARCALAR))


if __name__ == "__main__":
    main()
