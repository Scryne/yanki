"""S33 kör test seti: ölçümde öne çıkan kollar (A taban, G CFG 10, H heun) üretimdeki mastering'den geçer (paket.master:
−14 LUFS, ton eşleme orijinale), aynı ses yüksekliğinde dinlenir. D (DCW, söz WER 1,0) ve S (sde, kapı 5/15) elendi.
Üç kolun da olduğu şarkılar (ilk tur kısmi: Last Last'te yalnız A/D, Doja yok).

  uv run --no-sync python spikes/s33_karisim.py
"""

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import kulak, paket  # noqa: E402

CALISMA = KOK / "calisma"
HAM = CALISMA / "dinleme" / "s33"
DINLEME = CALISMA / "dinleme" / "s33k"
KOLLAR = ("A", "G", "H")


def main() -> None:
    y = paket.yayin_ayarlari(KOK / "config" / "yayin.toml")
    set_ = kulak.setler()["egitim-5"]
    for sarki in sorted(p.name for p in HAM.iterdir() if p.is_dir()):
        if not all((HAM / sarki / f"{kol}.flac").exists() for kol in KOLLAR):
            continue
        orijinal = kulak.dosya_yolu(CALISMA, set_, sarki, "orijinal")
        for kol in KOLLAR:
            hedef = DINLEME / sarki / f"{kol}.flac"
            if not hedef.exists():
                paket.master(HAM / sarki / f"{kol}.flac", hedef, y, referans=orijinal)
        print(f"  {sarki}", flush=True)


if __name__ == "__main__":
    main()
