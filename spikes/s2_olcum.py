"""S2: Cover çıktısını nesnel ölç — melodi korunmuş mu, sözler anlaşılır mı, kaynağın kopyası mı?

  uv run --no-project --with librosa --with faster-whisper --with jiwer python spikes/s2_olcum.py \
      soz <kaynak.wav> <soz.txt>                 # kaynağın sözlerini Whisper ile çıkar
  uv run ... python spikes/s2_olcum.py olc <kaynak.wav> <soz.txt> <cover1> [<cover2> ...] [--kontrol x.wav]

Ölçüler:
- melodi: kaynak ve cover'ın kroma (CENS) dizileri arasında DTW hizalı ortalama kosinüs benzerliği.
  Aynı tondaki ilgisiz bir parça (--kontrol) taban çizgisini verir; cover tabandan belirgin yüksek olmalı.
- soz_wer: cover'ın Whisper dökümü ile kaynak sözleri arasındaki kelime hata oranı (düşük = anlaşılır).
- dalga_korelasyon: ham dalga biçimi benzerliği; yüksekse cover kaynağın kendisini taşıyor (yeni kayıt değil).
"""

import argparse
import json
import re
import sys

import jiwer
import librosa
import numpy as np

SR = 22050


def yukle(yol: str, sure: float | None = None) -> np.ndarray:
    y, _ = librosa.load(yol, sr=SR, mono=True, duration=sure)
    return y


def kroma(y: np.ndarray) -> np.ndarray:
    return librosa.feature.chroma_cens(y=y, sr=SR, hop_length=2048)


def melodi_benzerligi(a: np.ndarray, b: np.ndarray) -> float:
    ca, cb = kroma(a), kroma(b)
    _, yol = librosa.sequence.dtw(X=ca, Y=cb, metric="cosine", subseq=False)
    sim = [float(np.dot(ca[:, i], cb[:, j]) / (np.linalg.norm(ca[:, i]) * np.linalg.norm(cb[:, j]) + 1e-9)) for i, j in yol]
    return round(float(np.mean(sim)), 3)


def melodi_kare(a: np.ndarray, b: np.ndarray) -> float:
    """Hizasız, kare kare kroma benzerliği. Cover kaynağın zamanlamasını koruyorsa yüksek, ilgisiz parçada düşük."""
    ca = librosa.feature.chroma_cqt(y=a, sr=SR, hop_length=2048)
    cb = librosa.feature.chroma_cqt(y=b, sr=SR, hop_length=2048)
    n = min(ca.shape[1], cb.shape[1])
    ca, cb = ca[:, :n], cb[:, :n]
    sim = (ca * cb).sum(0) / (np.linalg.norm(ca, axis=0) * np.linalg.norm(cb, axis=0) + 1e-9)
    return round(float(np.mean(sim)), 3)


def dalga_korelasyonu(a: np.ndarray, b: np.ndarray) -> float:
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    # küçük kaymalara karşı en iyi gecikmeyi ara (±0,5 sn)
    en_iyi = 0.0
    for kayma in range(-SR // 2, SR // 2 + 1, SR // 50):
        x, y = (a[kayma:], b[: n - kayma]) if kayma >= 0 else (a[: n + kayma], b[-kayma:])
        r = float(np.corrcoef(x, y)[0, 1])
        en_iyi = max(en_iyi, abs(r))
    return round(en_iyi, 3)


_whisper = None


def dokum(yol: str) -> str:
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel

        _whisper = WhisperModel("small.en", device="cpu", compute_type="int8")
    # dosya yerine dizi: faster-whisper 1.2.1 PyAV 19'da kaldırılan bir argümanı kullanıyor
    ses, _ = librosa.load(yol, sr=16000, mono=True)
    parcalar, _ = _whisper.transcribe(ses, language="en", vad_filter=False, beam_size=5)
    return " ".join(p.text.strip() for p in parcalar)


def normalle(s: str) -> str:
    s = re.sub(r"\[[^\]]*\]", " ", s.lower())
    s = re.sub(r"[^a-z' ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("komut", choices=["soz", "olc"])
    ap.add_argument("kaynak")
    ap.add_argument("soz")
    ap.add_argument("coverlar", nargs="*")
    ap.add_argument("--kontrol", default=None)
    a = ap.parse_args()

    if a.komut == "soz":
        metin = dokum(a.kaynak)
        with open(a.soz, "w", encoding="utf-8") as f:
            f.write(metin)
        print(f"söz yazıldı: {len(metin.split())} kelime")
        return

    ref = normalle(open(a.soz, encoding="utf-8").read())
    k = yukle(a.kaynak)
    sure = len(k) / SR
    satirlar = []
    hedefler = list(a.coverlar) + ([a.kontrol] if a.kontrol else [])
    for yol in hedefler:
        c = yukle(yol, sure)
        hyp = normalle(dokum(yol))
        satirlar.append(
            {
                "dosya": yol.replace("\\", "/").split("/")[-2] + "/" + yol.replace("\\", "/").split("/")[-1][:12],
                "kontrol": yol == a.kontrol,
                "melodi": melodi_benzerligi(k, c),
                "melodi_kare": melodi_kare(k, c),
                "tempo": [round(float(librosa.beat.beat_track(y=x, sr=SR)[0][0]), 1) for x in (k, c)],
                "soz_wer": round(jiwer.wer(ref, hyp), 3) if hyp else 1.0,
                "dalga_korelasyon": dalga_korelasyonu(k, c),
                "dokum_kelime": len(hyp.split()),
            }
        )
        print(json.dumps(satirlar[-1], ensure_ascii=False), file=sys.stderr)
    print(json.dumps({"kaynak_kelime": len(ref.split()), "sonuclar": satirlar}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
