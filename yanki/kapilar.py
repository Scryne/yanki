"""Otomatik kapılar: yayınlanamayacak adayı eler. "İyi"yi seçmez — onu Scryne kulakla seçer.

Spike'ta otomatik kalite ölçüleri (Audiobox, perde, gürültülülük) Scryne'ın duyduğunu görmedi; burada yalnız kesin
"olmaz" durumları var. Eşikler spike ölçümlerinden (docs/arastirma/01):

| Kapı       | İyi cover        | Olmaz                                | Eşik    |
| parmak_izi | 0,59–0,66        | orijinali taşıyan 0,74–0,93          | < 0,72  |
| dalga      | 0,01–0,04        | orijinali taşıyan 0,41–0,90          | < 0,25  |
| soz_wer    | 0,01–0,33        | sözsüz/anlamsız vokal 0,94–0,98      | < 0,50  |
| sure_fark  | 0                | kesik/yanlış çıktı                   | ≤ 2 sn  |
"""

import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from yanki import ses

ESIK = {"parmak_izi": 0.72, "dalga": 0.25, "soz_wer": 0.50, "sure_fark": 2.0}


@dataclass(frozen=True)
class Olcum:
    deger: float
    esik: float
    gecti: bool


def parmak_izi(fpcalc: Path, yol: Path, uzunluk_sn: int = 600) -> np.ndarray:
    cikti = subprocess.run([str(fpcalc), "-raw", "-json", "-length", str(uzunluk_sn), str(yol)],
                           capture_output=True, check=True).stdout
    return np.array(json.loads(cikti)["fingerprint"], dtype=np.uint32)


def parmak_izi_benzerligi(a: np.ndarray, b: np.ndarray, kayma: int = 20) -> float:
    """En iyi kaymada eşleşen bit oranı. Aynı kayıt ≈ 0,95; ilgisiz ≈ 0,54."""
    en_iyi = 0.0
    for k in range(-kayma, kayma + 1):
        x, y = (a[k:], b) if k >= 0 else (a, b[-k:])
        n = min(len(x), len(y))
        if n < 50:
            continue
        farkli = np.unpackbits(np.bitwise_xor(x[:n], y[:n]).view(np.uint8)).sum()
        en_iyi = max(en_iyi, 1 - farkli / (n * 32))
    return float(en_iyi)


def mono(yol: Path, sr: int) -> np.ndarray:
    import soundfile as sf

    with tempfile.TemporaryDirectory() as t:
        gecici = Path(t) / "m.wav"
        subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(yol), "-ac", "1",
                        "-ar", str(sr), str(gecici)], check=True)
        return sf.read(str(gecici), dtype="float32")[0]


def dalga_korelasyonu(a: np.ndarray, b: np.ndarray, sr: int, en_fazla_kayma_sn: float = 0.5) -> float:
    """Normalize çapraz korelasyonun ±kayma içindeki en büyük mutlak değeri (FFT ile)."""
    n = min(len(a), len(b))
    a, b = a[:n] - a[:n].mean(), b[:n] - b[:n].mean()
    payda = np.sqrt((a**2).sum() * (b**2).sum())
    if payda == 0:
        return 0.0
    boy = 1 << (2 * n - 1).bit_length()
    xc = np.fft.irfft(np.fft.rfft(a, boy) * np.conj(np.fft.rfft(b, boy)), boy)
    k = int(en_fazla_kayma_sn * sr)
    pencere = np.concatenate([xc[: k + 1], xc[-k:]])
    return float(np.abs(pencere).max() / payda)


def normalle(s: str) -> str:
    s = re.sub(r"\[[^\]]*\]", " ", s.lower())
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9' ]+", " ", s)).strip()


_whisper = None


def dokum(yol: Path) -> str:
    global _whisper
    if _whisper is None:
        from faster_whisper import WhisperModel

        _whisper = WhisperModel("small.en", device="cpu", compute_type="int8")
    # dosya yolu değil dizi: faster-whisper 1.2.1, PyAV 19'da kaldırılan bir argümanı kullanıyor
    parcalar, _ = _whisper.transcribe(mono(yol, 16000), language="en", beam_size=5)
    return " ".join(p.text.strip() for p in parcalar)


def soz_wer(soz: str, dokum_metni: str) -> float:
    import jiwer

    ref, hyp = normalle(soz), normalle(dokum_metni)
    if not ref:
        raise ValueError("referans söz boş")
    return 1.0 if not hyp else float(jiwer.wer(ref, hyp))


def degerlendir(aday: Path, kaynak: Path, soz: str, fpcalc: Path, dokumcu=dokum) -> dict[str, dict]:
    sr = 8000
    olc = {
        "parmak_izi": parmak_izi_benzerligi(parmak_izi(fpcalc, kaynak), parmak_izi(fpcalc, aday)),
        "dalga": dalga_korelasyonu(mono(kaynak, sr), mono(aday, sr), sr),
        "soz_wer": soz_wer(soz, dokumcu(aday)),
        "sure_fark": abs(ses.sure(aday) - ses.sure(kaynak)),
    }
    return {ad: asdict(Olcum(round(d, 3), ESIK[ad], d < ESIK[ad] if ad != "sure_fark" else d <= ESIK[ad]))
            for ad, d in olc.items()}


def hepsi_gecti(kapilar: dict[str, dict]) -> bool:
    return all(k["gecti"] for k in kapilar.values())
