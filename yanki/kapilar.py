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
    """Bölüm etiketleri ve noktalama çıkar; kesme işareti silinir ("don't"/"don’t" → "dont", "'cause" → "cause"):
    LRCLIB kıvrık kesme kullanıyor, Whisper düz — ikisi eşleşmeyince söz WER'i boşuna artıyordu (2026-10-07)."""
    # Unicode harfler korunur (Türkçe/Fransızca sözler; önce yalnız a-z kalıyordu, İngilizce dışı söz boş çıkardı)
    s = re.sub(r"\[[^\]]*\]", " ", s.replace("İ", "i").lower())
    s = re.sub(r"['’‘`]", "", s)
    return re.sub(r"\s+", " ", re.sub(r"[^\w ]+|_", " ", s)).strip()


# ACE-Step'in kabul ettiği dil kodları (motor/ACE-Step-1.5/acestep/constants.py → VALID_LANGUAGES)
ACESTEP_DILLERI = {
    "ar", "az", "bg", "bn", "ca", "cs", "da", "de", "el", "en", "es", "fa", "fi", "fr", "he", "hi", "hr", "ht", "hu",
    "id", "is", "it", "ja", "ko", "la", "lt", "ms", "ne", "nl", "no", "pa", "pl", "pt", "ro", "ru", "sa", "sk", "sr",
    "sv", "sw", "ta", "te", "th", "tl", "tr", "uk", "ur", "vi", "yue", "zh",
}
_modeller: dict[str, object] = {}


def _model(ad: str):
    """İngilizce için kalibre edilmiş `small.en` (kapı eşikleri onunla ölçüldü), diğer diller için çok dilli `small`."""
    if ad not in _modeller:
        from faster_whisper import WhisperModel

        _modeller[ad] = WhisperModel(ad, device="cpu", compute_type="int8")
    return _modeller[ad]


def dokum(yol: Path, dil: str = "en") -> str:
    # dosya yolu değil dizi: faster-whisper 1.2.1, PyAV 19'da kaldırılan bir argümanı kullanıyor
    model = _model("small.en" if dil == "en" else "small")
    parcalar, _ = model.transcribe(mono(yol, 16000), language=dil if dil in ACESTEP_DILLERI else None, beam_size=5)
    return " ".join(p.text.strip() for p in parcalar)


def dil_tespit(yol: Path, bas_orani: float = 0.4, sure_sn: float = 30.0) -> tuple[str, float]:
    """Kaynak sesin söz dili (Whisper çok dilli `small`, şarkının ~%40'ından 30 sn: çoğunlukla vokalli bölge).
    Dönen kod ACE-Step'in listesinde yoksa "unknown"."""
    ses_ = mono(yol, 16000)
    bas = int(min(len(ses_) * bas_orani, max(0, len(ses_) - sure_sn * 16000)))
    dil, olasilik, _ = _model("small").detect_language(ses_[bas: bas + int(sure_sn * 16000)])
    return (dil if dil in ACESTEP_DILLERI else "unknown"), float(olasilik)


_INGILIZCE_SIK = frozenset("the a an and or but i you me my your we our it is are was be to of in on at for with "
                           "that this what when all so no not do don't can i'm just like love oh".split())


def ingilizce_orani(soz: str) -> float | None:
    """Söz kelimelerinin İngilizcenin en sık kelimelerinden olanlarının payı (etiket satırları hariç). Kelime yoksa
    None."""
    kelimeler = [w for satir in soz.splitlines() if not satir.strip().startswith("[")
                 for w in re.findall(r"[a-z']+", satir.casefold())]
    return sum(w in _INGILIZCE_SIK for w in kelimeler) / len(kelimeler) if kelimeler else None


def soz_wer(soz: str, dokum_metni: str) -> float:
    import jiwer

    ref, hyp = normalle(soz), normalle(dokum_metni)
    if not ref:
        raise ValueError("referans söz boş")
    return 1.0 if not hyp else float(jiwer.wer(ref, hyp))


def degerlendir(aday: Path, kaynak: Path, soz: str, fpcalc: Path, dokumcu=dokum, dil: str = "en"
                ) -> dict[str, dict]:
    sr = 8000
    olc = {
        "parmak_izi": parmak_izi_benzerligi(parmak_izi(fpcalc, kaynak), parmak_izi(fpcalc, aday)),
        "dalga": dalga_korelasyonu(mono(kaynak, sr), mono(aday, sr), sr),
        "soz_wer": soz_wer(soz, dokumcu(aday, dil)),
        "sure_fark": abs(ses.sure(aday) - ses.sure(kaynak)),
    }
    return {ad: asdict(Olcum(round(d, 3), ESIK[ad], d < ESIK[ad] if ad != "sure_fark" else d <= ESIK[ad]))
            for ad, d in olc.items()}


def hepsi_gecti(kapilar: dict[str, dict]) -> bool:
    return all(k["gecti"] for k in kapilar.values())
