"""S14 (Faz 7): Whisper'ın kelime güveni, Scryne'ın kulakla işaretlediği bozuk aralığı gösterir mi?

Tek etiket: Adele aday 1, 58–62 sn (Scryne işaretledi; onarım 1-1 kabul, 1-2 ret). Soru: onarım öncesi sürümde düşük
güvenli kelimeler ya da sözün beklendiği yerde kelime boşluğu bu aralıkta toplanıyor mu, şarkının geri kalanından
ayrışıyor mu; kabul edilen onarımda düzeliyor mu. Tek örnek bir dedektörü doğrulamaz; yalnız yönü gösterir.

  uv run python spikes/s14_supheli_aralik.py
"""

import json
from pathlib import Path

from yanki import kapilar

K = Path("calisma/adele-someone-like-you")
SURUMLER = {"once": K / "adaylar/1/tam.flac", "onarim_kabul": K / "onarimlar/1-1/tam.flac",
            "onarim_ret": K / "onarimlar/1-2/tam.flac"}
ETIKET = (58.0, 62.0)
PENCERE = 4.0  # sn; şarkı boyunca kayan pencere


def kelimeler(yol: Path) -> list[tuple[float, float, str, float]]:
    from faster_whisper import WhisperModel

    m = WhisperModel("small.en", device="cpu", compute_type="int8")
    parcalar, _ = m.transcribe(kapilar.mono(yol, 16000), language="en", beam_size=5, word_timestamps=True)
    return [(w.start, w.end, w.word.strip(), w.probability) for p in parcalar for w in p.words]


def pencereler(ks: list, sure: float) -> list[tuple[float, float, int]]:
    """Her 1 sn'de [t, t+PENCERE): ortalama kelime güveni, kelime sayısı."""
    sonuc = []
    t = 0.0
    while t + PENCERE <= sure:
        icinde = [p for b, s, _, p in ks if b < t + PENCERE and s > t]
        sonuc.append((t, sum(icinde) / len(icinde) if icinde else None, len(icinde)))
        t += 1.0
    return sonuc


def main() -> None:
    satirlar = json.loads((K / "soz_zaman.json").read_text(encoding="utf-8"))
    sozlu = [float(t) for t, s in satirlar if s.strip() and s.strip() != "♪"]
    cikti = {}
    for ad, yol in SURUMLER.items():
        ks = kelimeler(yol)
        sure = max(s for _, s, _, _ in ks) + 1
        pn = [(t, g, n) for t, g, n in pencereler(ks, sure) if any(t <= x < t + PENCERE + 4 for x in sozlu) or n]
        etikette = [(b, s, w, round(p, 2)) for b, s, w, p in ks if b < ETIKET[1] + 1 and s > ETIKET[0] - 1]
        # en düşük güvenli 8 pencere (sözün beklendiği yerlerde)
        dusuk = sorted((x for x in pn if x[1] is not None), key=lambda x: x[1])[:8]
        cikti[ad] = {"kelime": len(ks), "ortalama": round(sum(p for *_, p in ks) / len(ks), 3),
                     "etiket_kelimeleri": etikette, "en_dusuk_pencereler": [(t, round(g, 3), n) for t, g, n in dusuk]}
        print(f"\n== {ad}: {len(ks)} kelime, ortalama güven {cikti[ad]['ortalama']}")
        print("  58–62 sn:", " ".join(f"{w}({p})" for _, _, w, p in etikette))
        print("  en düşük pencereler:", ", ".join(f"{t:.0f}s={g:.2f}/{n}" for t, g, n in cikti[ad]["en_dusuk_pencereler"]))
    Path("calisma/dinleme").mkdir(parents=True, exist_ok=True)
    Path("calisma/dinleme/s14.json").write_text(json.dumps(cikti, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
