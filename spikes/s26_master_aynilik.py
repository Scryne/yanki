"""S26: yeni mastering (ton eşleme: her şarkı kendi orijinalinin dengesine) şarkılar arası aynılığı düşürüyor mu.

S22: seçilmiş adaylar birbirine 0,941, orijinaller 0,891 benziyor. Seçilmiş adaylar yeni zincirle (yanki/paket.py →
master, referans = orijinal) `calisma/_spike/s26/<kimlik>.wav`'a masterlanır; sonra:
  motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s22_beat.py calisma/_spike/s26

  uv run --no-sync python spikes/s26_master_aynilik.py
"""

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import paket  # noqa: E402


def main() -> int:
    y = paket.yayin_ayarlari(KOK / "config" / "yayin.toml")
    hedef = KOK / "calisma" / "_spike" / "s26"
    for yol in sorted((KOK / "calisma").glob("*/durum.json")):
        d = json.loads(yol.read_text(encoding="utf-8"))
        if not d.get("secilen") or d.get("asama") not in ("yuklendi", "paketlendi"):
            continue
        a = next((x for x in d["adaylar"] if x["no"] == d["secilen"]), None)
        if not (a and a.get("dosya")):
            continue
        cikti = hedef / d["kimlik"] / "master.wav"
        cikti.parent.mkdir(parents=True, exist_ok=True)
        if not cikti.exists():
            o = paket.master(yol.parent / a["dosya"], cikti, y, referans=yol.parent / d["kaynak"]["dosya"])
            print(d["kimlik"], o.get("ton_sapma_once_db"), "→", o.get("ton_sapma_sonra_db"), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
