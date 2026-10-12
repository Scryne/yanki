"""Otomatik kapılar: yayınlanamayacak adayı eler. "İyi"yi seçmez — onu Scryne kulakla seçer.

Spike'ta otomatik kalite ölçüleri (Audiobox, perde, gürültülülük) Scryne'ın duyduğunu görmedi; burada yalnız kesin
"olmaz" durumları var. Eşikler spike ölçümlerinden (docs/arastirma/01):

| Kapı       | İyi cover        | Olmaz                                | Eşik    |
| parmak_izi | 0,59–0,66        | orijinali taşıyan 0,74–0,93          | < 0,72  |
| dalga      | 0,01–0,06        | orijinali taşıyan 0,41–0,90          | < 0,20  |
| soz_wer    | 0,01–0,33        | sözsüz/anlamsız vokal 0,94–0,98      | < 0,50  |
| sure_fark  | 0                | kesik/yanlış çıktı                   | ≤ 2 sn  |

Dalga 300 Hz üstünde ölçülür (2026-10-12): cover kaynağın zamanlamasını izlediği için dört vuruşlu türde (EDM) kick
ve bas orijinalinkiyle üst üste biniyor; tam bantta temiz bir cover 0,25–0,26 çıkıp düşüyordu (Avicii "Wake Me Up",
300 Hz üstünde 0,03). Orijinali taşıyan çıktı her bantta yüksek: spike'taki referans örneği tam bant 0,445, 300 Hz
üstü 0,449; orijinal + gürültü 0,95; temiz cover'lar 0,03–0,06.
"""

import json
import re
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from yanki import ses

ESIK = {"parmak_izi": 0.72, "dalga": 0.20, "soz_wer": 0.50, "sure_fark": 2.0}
DALGA_ALT_HZ = 300.0
# Söz kapısı orijinal kayda göre (2026-10-12): Whisper orijinal kaydın kendisini de her türde aynı anlamıyor
# (balad 0,06–0,16; Kendrick Lamar "HUMBLE." 0,49, Despacito 0,31). Rap cover'ı orijinal kadar anlaşılır (0,52) olduğu
# halde mutlak 0,50 eşiğinden düşüyordu. Aday orijinalden en çok SOZ_PAYI kötü olabilir; anlamsız vokal (0,94–0,98)
# her durumda düşer (SOZ_TAVAN).
SOZ_PAYI, SOZ_TAVAN = 0.10, 0.80


def soz_esigi(orijinal_wer: float | None) -> float:
    if orijinal_wer is None:
        return ESIK["soz_wer"]
    return max(ESIK["soz_wer"], min(orijinal_wer + SOZ_PAYI, SOZ_TAVAN))


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


def alcak_kes(x: np.ndarray, sr: int, hz: float = DALGA_ALT_HZ) -> np.ndarray:
    """`hz` altını atar (FFT): kick ve bas zamanlaması dalga kapısına girmesin."""
    X = np.fft.rfft(x)
    X[np.fft.rfftfreq(len(x), 1 / sr) < hz] = 0
    return np.fft.irfft(X, len(x)).astype(np.float32)


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
    """Söz kelimelerinin İngilizcenin en sık kelimelerinden olanlarının payı (etiket satırları hariç). Bütün yazılar
    sayılır (Hangul/Kana dahil: önce yalnız Latin harfli kelimeler sayılıyordu, İngilizce parçalı Korece söz
    "İngilizce" çıkardı). Kelime yoksa None."""
    kelimeler = [w for satir in soz.splitlines() if not satir.strip().startswith("[")
                 for w in re.findall(r"[^\W\d_][\w']*", satir.casefold())]
    return sum(w in _INGILIZCE_SIK for w in kelimeler) / len(kelimeler) if kelimeler else None


# Kelimeler arasında boşluk olmayan diller: kelime hata oranı her satırı tek "kelime" sayıp hep ~1 çıkıyordu (YOASOBI
# "Idol" orijinal kaydın kendisi 0,998, 2026-10-12). Bu dillerde karakter hata oranı.
KARAKTER_DILLERI = frozenset({"ja", "zh", "yue", "th"})


# Latin alfabesi dışında yazılan diller (Whisper kodları): söz bu yazıyı hiç taşımıyorsa çeviri/romaji sürümüdür
LATIN_DISI_DILLER = frozenset({"ja", "ko", "zh", "yue", "th", "ru", "uk", "bg", "sr", "el", "ar", "fa", "he", "hi",
                               "bn", "ta", "te", "pa", "ne", "ur", "sa"})


def yerli_yazi_payi(soz: str) -> float | None:
    """Söz harflerinin Latin alfabesi (genişletilmişleri dahil) dışında kalan payı; harf yoksa None."""
    harfler = [c for satir in soz.splitlines() if not satir.strip().startswith("[") for c in satir if c.isalpha()]
    return sum(ord(c) > 0x24F for c in harfler) / len(harfler) if harfler else None


def soz_wer(soz: str, dokum_metni: str, dil: str = "en") -> float:
    import jiwer

    ref, hyp = normalle(soz), normalle(dokum_metni)
    if not ref:
        raise ValueError("referans söz boş")
    if not hyp:
        return 1.0
    if dil in KARAKTER_DILLERI:
        return float(jiwer.cer(ref.replace(" ", ""), hyp.replace(" ", "")))
    return float(jiwer.wer(ref, hyp))


def degerlendir(aday: Path, kaynak: Path, soz: str, fpcalc: Path, dokumcu=dokum, dil: str = "en",
                orijinal_wer: float | None = None) -> dict[str, dict]:
    """`orijinal_wer`: orijinal kaydın söz WER'i (aynı söz, aynı Whisper); söz eşiği ona göre (`soz_esigi`)."""
    sr = 8000
    olc = {
        "parmak_izi": parmak_izi_benzerligi(parmak_izi(fpcalc, kaynak), parmak_izi(fpcalc, aday)),
        "dalga": dalga_korelasyonu(alcak_kes(mono(kaynak, sr), sr), alcak_kes(mono(aday, sr), sr), sr),
        "soz_wer": soz_wer(soz, dokumcu(aday, dil), dil),
        "sure_fark": abs(ses.sure(aday) - ses.sure(kaynak)),
    }
    esik = {**ESIK, "soz_wer": round(soz_esigi(orijinal_wer), 3)}
    return {ad: asdict(Olcum(round(d, 3), esik[ad], d < esik[ad] if ad != "sure_fark" else d <= esik[ad]))
            for ad, d in olc.items()}


def orijinal_wer(kaynak: Path, soz: str, dil: str = "en", dokumcu=dokum) -> float | None:
    """Orijinal kaydın söz WER'i (göreli söz kapısı için; şarkı başı bir kez, CPU'da ~1 dk). Ölçülemezse None."""
    try:
        return round(soz_wer(soz, dokumcu(kaynak, dil), dil), 3)
    except Exception:  # noqa: BLE001 — ölçülemezse mutlak eşik
        return None


def hepsi_gecti(kapilar: dict[str, dict]) -> bool:
    return all(k["gecti"] for k in kapilar.values())
