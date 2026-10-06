"""S6: Ses kalitesi — Meta Audiobox Aesthetics (ACE-Step makalesinin kullandığı ölçüt).

  uv run --no-project --python 3.11 --with audiobox_aesthetics --with requests \
      --with torch==2.7.1+cu128 --with torchaudio==2.7.1+cu128 \
      --index https://download.pytorch.org/whl/cu128 --index-strategy unsafe-best-match \
      python spikes/s6_kalite.py <ses1> [<ses2> ...]

Eksenler (1–10): PQ üretim kalitesi (netlik, bozulma), PC üretim karmaşıklığı, CE içerik keyfi, CU içerik faydası.
Kulakla "kalite kötü" yargısının vekili PQ ve CE'dir; orijinal kayıt tavanı verir.
"""

import sys
from pathlib import Path

from audiobox_aesthetics.infer import initialize_predictor


def main() -> None:
    tahmin = initialize_predictor()
    yollar = sys.argv[1:]
    sonuc = tahmin.forward([{"path": str(Path(y).resolve())} for y in yollar])
    print(f"{'dosya':44} {'PQ':>5} {'CE':>5} {'CU':>5} {'PC':>5}")
    for y, s in zip(yollar, sonuc):
        ad = Path(y).parent.name + "/" + Path(y).name if Path(y).stem.startswith(("out_", "lego")) or len(Path(y).stem) > 30 else Path(y).name
        print(f"{ad[:44]:44} {s['PQ']:5.2f} {s['CE']:5.2f} {s['CU']:5.2f} {s['PC']:5.2f}")


if __name__ == "__main__":
    main()
