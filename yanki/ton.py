"""Ton eşleme: cover'ın frekans dengesini orijinal kaydınkine yaklaştıran düzeltme eğrisi (mastering, `paket.master`).

Ölçüm (2026-10-11, yayına giden 22 şarkı, 1/3 oktav, 200 Hz–2 kHz'e göre): ACE-Step çıktısı orijinale göre 40–63 Hz'te
ortalama +5…+8 dB fazla (şarkıdan şarkıya ±11 dB), 3–8 kHz'te −2…−4 dB eksik (vokal varlığı ve parlaklık; ±4 dB).
Sapma şarkıya göre değiştiği için sabit bir EQ değil, her şarkıda kendi orijinaline göre eğri: referans mastering.

Temkin: düzenleme orijinalden farklı olabilir (organ yerine piyano) → farkın yalnız `ORAN`'ı uygulanır, kesme en çok
`EN_COK_KESME`, yükseltme en çok `EN_COK_YUKSELTME` dB (yükseltme yapay ürünleri de büyütür), komşu bantlarla
yumuşatılır; 40 Hz altı ve 12 kHz üstü dokunulmaz (kaynak YouTube AAC'si 16 kHz'te kesiyor). Seviye farkını eğri
taşımaz (200 Hz–4 kHz ortancası sıfıra çekilir): ses yüksekliği sonra ayarlanır.
"""

from pathlib import Path

import numpy as np

MERKEZLER = tuple(round(31.5 * 2 ** (i / 3), 1) for i in range(26))  # 31,5 Hz … ~10 kHz, 1/3 oktav
ALT_HZ, UST_HZ = 40.0, 12000.0
ORAN = 0.7
EN_COK_KESME, EN_COK_YUKSELTME = 8.0, 3.0
PENCERE = 16384


def bant_spektrumu(yol: Path, merkezler=MERKEZLER) -> np.ndarray:
    """1/3 oktav bant gücü (dB), sesli pencerelerin ortalaması (sessiz giriş/çıkış dengeyi çarpıtmasın)."""
    import soundfile as sf

    x, sr = sf.read(str(yol), dtype="float32", always_2d=True)
    m = x.mean(1)
    if len(m) < PENCERE:
        raise ValueError(f"ses çok kısa: {yol}")
    seg = np.lib.stride_tricks.sliding_window_view(m, PENCERE)[:: PENCERE // 2]
    enerji = (seg ** 2).mean(1)
    seg = seg[enerji > enerji.max() * 1e-3]
    if not len(seg):  # tamamen sessiz: bant ortalamaları NaN olur, ffmpeg eğrisi bozulurdu
        raise ValueError(f"ses sessiz: {yol}")
    guc = (np.abs(np.fft.rfft(seg * np.hanning(PENCERE), axis=1)) ** 2).mean(0)
    f = np.fft.rfftfreq(PENCERE, 1 / sr)
    return np.array([10 * np.log10(guc[(f >= c / 2 ** (1 / 6)) & (f < c * 2 ** (1 / 6))].mean() + 1e-20)
                     for c in merkezler])


def egri(cover: np.ndarray, orijinal: np.ndarray, merkezler=MERKEZLER) -> list[tuple[float, float]]:
    """(Hz, dB) düzeltme noktaları: orijinal − cover, seviyesi ortalanmış, yumuşatılmış, sınırlanmış, kısmi."""
    c = np.asarray(merkezler)
    fark = np.asarray(orijinal) - np.asarray(cover)
    orta = (c >= 200) & (c <= 4000)
    fark = fark - np.median(fark[orta])
    yumusak = np.convolve(np.pad(fark, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    duzeltme = np.clip(yumusak * ORAN, -EN_COK_KESME, EN_COK_YUKSELTME)
    duzeltme[(c < ALT_HZ) | (c > UST_HZ)] = 0.0
    return [(float(hz), round(float(db), 2)) for hz, db in zip(c, duzeltme, strict=True)]


def ffmpeg_filtresi(noktalar: list[tuple[float, float]]) -> str:
    """Doğrusal fazlı FIR eşitleyici (`firequalizer`); uç noktalar 0 dB'ye bağlanır."""
    girdiler = [(20.0, 0.0), *noktalar, (16000.0, 0.0), (24000.0, 0.0)]
    return "firequalizer=gain_entry='" + ";".join(f"entry({hz:g},{db:g})" for hz, db in girdiler) + "'"


def sapma(cover: np.ndarray, orijinal: np.ndarray, merkezler=MERKEZLER) -> float:
    """40 Hz–12 kHz'te seviyesi ortalanmış ortalama mutlak fark (dB): eşlemenin işe yarayıp yaramadığı."""
    c = np.asarray(merkezler)
    fark = np.asarray(orijinal) - np.asarray(cover)
    fark = fark - np.median(fark[(c >= 200) & (c <= 4000)])
    return float(np.abs(fark[(c >= ALT_HZ) & (c <= UST_HZ)]).mean())
