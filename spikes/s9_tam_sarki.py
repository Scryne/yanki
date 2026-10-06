"""S9 (Faz 2 ölçümü): tam şarkı cover'ı gerçek işçiyle — süre ve VRAM.

  uv run python spikes/s9_tam_sarki.py <kaynak.wav> "<sanatçı>" "<şarkı>" <cikti_klasor>
"""

import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from yanki import ayarlar, motor


def lrclib(sanatci: str, sarki: str) -> str:
    q = urllib.parse.urlencode({"artist_name": sanatci, "track_name": sarki})
    with urllib.request.urlopen(f"https://lrclib.net/api/get?{q}", timeout=30) as r:
        return json.load(r)["plainLyrics"]


def etiketle(duz: str) -> str:
    kitalar = [k.strip() for k in duz.replace("\r", "").split("\n\n") if k.strip()]
    tekrar = {k for k in kitalar if kitalar.count(k) > 1}
    return "\n\n".join(("[chorus]" if k in tekrar else "[verse]") + "\n" + k for k in kitalar)


def main() -> None:
    kaynak, sanatci, sarki, cikti = sys.argv[1:5]
    soz = etiketle(lrclib(sanatci, sarki))
    Path(cikti).mkdir(parents=True, exist_ok=True)
    Path(cikti, "soz.txt").write_text(soz, encoding="utf-8")
    a = ayarlar.yukle()
    is_ = motor.Is(id="tam", gorev="cover", kaynak=str(Path(kaynak).resolve()), cikti_klasor=str(Path(cikti).resolve()),
                   stil="emotional piano ballad, female lead vocal, soulful and powerful, solo grand piano accompaniment, "
                        "intimate, clean modern studio recording",
                   soz=soz, adim=a.cover.adim, tohum=a.cover.tohumlar[0], guc=a.cover.guc, bpm=68, ton="A major")
    s = motor.calistir(a, [is_], Path(cikti), zaman_asimi_sn=3600, gpu_bekleme_sn=1800)[0]
    print(json.dumps({k: v for k, v in s.__dict__.items() if k != "iz"}, ensure_ascii=False, indent=2))
    if s.iz:
        print(s.iz)


if __name__ == "__main__":
    main()
