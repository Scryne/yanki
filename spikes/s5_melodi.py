"""S5: Vokal melodisi korunmuş mu? Demucs vokal izlerinin perde eğrileri DTW ile karşılaştırılır.

  uv run --no-project --with librosa python spikes/s5_melodi.py <kaynak_vocals.wav> <cover_vocals.wav> [...]

Ölçü: DTW hizasından sonra iki eğrinin de seslendirildiği karelerde perde sınıfı farkı ≤ 1 yarım ton olan karelerin
oranı (transpozisyon serbest: 12 kaydırmanın en iyisi). Negatif kontrol: kaynak eğrisinin kendisi zamanda 1/3 kaydırılmış
(aynı ses, aynı ton, farklı melodi anı). Pozitif kontrol: kaynak eğrisi + küçük perde gürültüsü.
"""

import sys

import librosa
import numpy as np

SR = 16000
HOP = 320  # 20 ms


def egri(yol: str) -> np.ndarray:
    y = librosa.load(yol, sr=SR, mono=True)[0]
    f0, sesli, _ = librosa.pyin(y, fmin=70, fmax=1000, sr=SR, hop_length=HOP, frame_length=1024)
    midi = librosa.hz_to_midi(f0)
    midi[~sesli] = np.nan
    return midi


def benzerlik(a: np.ndarray, b: np.ndarray) -> float:
    # yalnız seslendirilmiş kareler; DTW maliyeti perde sınıfı mesafesi
    a = a[~np.isnan(a)][::2]
    b = b[~np.isnan(b)][::2]
    if len(a) < 20 or len(b) < 20:
        return 0.0
    en_iyi = 0.0
    for k in range(12):
        bb = b + k
        fark = np.abs(((a[:, None] - bb[None, :]) + 6) % 12 - 6)
        _, yol = librosa.sequence.dtw(C=fark, subseq=False)
        oran = float(np.mean([fark[i, j] <= 1.0 for i, j in yol]))
        en_iyi = max(en_iyi, oran)
    return round(en_iyi, 3)


def main() -> None:
    kaynak = egri(sys.argv[1])
    rng = np.random.default_rng(0)
    print(f"{'POZ kaynak+perde gürültüsü':34} melodi={benzerlik(kaynak, kaynak + rng.normal(0, 0.3, len(kaynak))):.3f}")
    print(f"{'NEG kaynak, zamanda 1/3 kaydırılmış':34} melodi={benzerlik(kaynak, np.roll(kaynak, len(kaynak) // 3)):.3f}")
    for yol in sys.argv[2:]:
        c = egri(yol)
        sesli = float(np.mean(~np.isnan(c)))
        ad = yol.replace("\\", "/").split("/")[-2]
        print(f"{ad[:34]:34} melodi={benzerlik(kaynak, c):.3f} sesli_kare={sesli:.2f}")


if __name__ == "__main__":
    main()
