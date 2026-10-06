"""S3: cover-nofsq güç taraması — armoni korunuyor mu, kaynak kaydın kopyası mı, sözler anlaşılır mı?

  uv run --no-project --with librosa --with faster-whisper --with jiwer python spikes/s3_benzerlik.py \
      --fpcalc <fpcalc.exe> --kaynak k.wav --soz k_soz.txt --kontrol ilgisiz.wav <cover1.flac> [...]

Ölçüler (her biri pozitif ve negatif kontrolle birlikte basılır, eşik tablodan okunur):
- armoni: hizasız kare kare kroma kosinüsü (en iyi transpozisyon). Kaynak+gürültü ≈ 0,98, ilgisiz şarkı ≈ 0,63.
- parmak_izi: Chromaprint ham parmak izlerinin en iyi kaymadaki eşleşen bit oranı. Aynı kayıt ≈ 0,9+,
  ilgisiz kayıt ≈ 0,5 (rastgele). Dağıtımcının parmak izi kontrolüne en yakın vekil.
- dalga: ham dalga biçimi korelasyonu (±0,5 sn kayma).
- wer: Whisper dökümü ile kaynak sözleri arasındaki kelime hata oranı.
"""

import argparse
import json
import re
import subprocess
import sys

import jiwer
import librosa
import numpy as np

SR = 22050


def yukle(yol, sure=None):
    return librosa.load(yol, sr=SR, mono=True, duration=sure)[0]


def armoni(a, b):
    ca = librosa.feature.chroma_cqt(y=a, sr=SR, hop_length=2048)
    cb = librosa.feature.chroma_cqt(y=b, sr=SR, hop_length=2048)
    n = min(ca.shape[1], cb.shape[1])
    ca, cb = ca[:, :n], cb[:, :n]
    en_iyi = 0.0
    for k in range(12):
        r = np.roll(cb, k, axis=0)
        en_iyi = max(en_iyi, float(np.mean((ca * r).sum(0) / (np.linalg.norm(ca, axis=0) * np.linalg.norm(r, axis=0) + 1e-9))))
    return round(en_iyi, 3)


def parmak_izi(fpcalc, yol):
    cikti = subprocess.run([fpcalc, "-raw", "-json", "-length", "120", yol], capture_output=True, check=True).stdout
    return np.array(json.loads(cikti)["fingerprint"], dtype=np.uint32)


def parmak_izi_benzerligi(fa, fb):
    en_iyi = 0.0
    for kayma in range(-20, 21):
        x, y = (fa[kayma:], fb) if kayma >= 0 else (fa, fb[-kayma:])
        n = min(len(x), len(y))
        if n < 50:
            continue
        xor = np.bitwise_xor(x[:n], y[:n])
        farkli = np.unpackbits(xor.view(np.uint8)).sum()
        en_iyi = max(en_iyi, 1 - farkli / (n * 32))
    return round(float(en_iyi), 3)


def dalga(a, b):
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    en_iyi = 0.0
    for kayma in range(-SR // 2, SR // 2 + 1, SR // 50):
        x, y = (a[kayma:], b[: n - kayma]) if kayma >= 0 else (a[: n + kayma], b[-kayma:])
        en_iyi = max(en_iyi, abs(float(np.corrcoef(x, y)[0, 1])))
    return round(en_iyi, 3)


_w = None


def dokum(yol):
    global _w
    if _w is None:
        from faster_whisper import WhisperModel

        _w = WhisperModel("small.en", device="cpu", compute_type="int8")
    ses = librosa.load(yol, sr=16000, mono=True)[0]
    return " ".join(p.text.strip() for p in _w.transcribe(ses, language="en", beam_size=5)[0])


def normalle(s):
    s = re.sub(r"\[[^\]]*\]", " ", s.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z' ]+", " ", s)).strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--fpcalc", required=True)
    ap.add_argument("--kaynak", required=True)
    ap.add_argument("--soz", required=True)
    ap.add_argument("--kontrol", required=True)
    ap.add_argument("coverlar", nargs="+")
    a = ap.parse_args()

    k = yukle(a.kaynak)
    sure = len(k) / SR
    fk = parmak_izi(a.fpcalc, a.kaynak)
    ref = normalle(open(a.soz, encoding="utf-8").read())

    gurultulu = a.kaynak.rsplit(".", 1)[0] + "_gurultu.wav"
    import soundfile as sf

    sf.write(gurultulu, k + 0.05 * np.abs(k).max() * np.random.default_rng(0).standard_normal(len(k)).astype(np.float32), SR)

    satirlar = []
    for etiket, yol in [("POZ kaynak+gürültü", gurultulu), ("NEG ilgisiz şarkı", a.kontrol)] + [
        (y.replace("\\", "/").split("/")[-2], y) for y in a.coverlar
    ]:
        c = yukle(yol, sure)
        hyp = normalle(dokum(yol))
        satir = {
            "etiket": etiket,
            "armoni": armoni(k, c),
            "parmak_izi": parmak_izi_benzerligi(fk, parmak_izi(a.fpcalc, yol)),
            "dalga": dalga(k, c),
            "wer": round(jiwer.wer(ref, hyp), 2) if hyp else 1.0,
        }
        satirlar.append(satir)
        print(f"{etiket[:26]:28} armoni={satir['armoni']:.3f} parmak_izi={satir['parmak_izi']:.3f} "
              f"dalga={satir['dalga']:.3f} wer={satir['wer']:.2f}", file=sys.stderr)
    print(json.dumps(satirlar, ensure_ascii=False))


if __name__ == "__main__":
    main()
