"""S24: hangi ölçü Scryne'ın aday seçimini tutuyor? (22 şarkı, şarkı başı 3 aday, seçim Scryne'ın kulağıyla)

Önce (2026-10-09, 15 şarkı): en düşük söz WER 4/15 tuttu (rastgele ~%33). Şimdi S22'nin beat ölçüleri (groove,
döngüsellik, vurmalı payı, bölüm değişimi) her aday için hesaplanır; her ölçüde "en iyi" aday Scryne'ın seçtiğiyle kaç
şarkıda aynı ve seçilenin ortalama sırası. Ölçü kulağı tutuyorsa üretimde aday seçimine girer.

  motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s24_secim_dogrulama.py
"""

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK / "spikes"))

from s22_beat import analiz, karsilastir  # noqa: E402

# ölçü → (anahtar, büyük mü iyi)
OLCULER = {"groove": ("groove", True), "az_dongu": ("dongusellik", False), "egri": ("egri_kor", True),
           "perk_yakin": ("perk_sapma", False), "bolum_yakin": ("bolum_sapma", False), "soz_wer": ("wer", False),
           "parmak_izi": ("pi", False)}


def main() -> int:
    satirlar = []
    for yol in sorted((KOK / "calisma").glob("*/durum.json")):
        d = json.loads(yol.read_text(encoding="utf-8"))
        adaylar = [a for a in d.get("adaylar", []) if a.get("dosya") and a.get("gecti")
                   and (yol.parent / a["dosya"]).exists()]
        if not d.get("secilen") or len(adaylar) < 2 or any("otomatik_onay" in n for n in d.get("notlar", [])):
            continue
        o = analiz(yol.parent / d["kaynak"]["dosya"])
        olc = {}
        for a in adaylar:
            k = karsilastir(analiz(yol.parent / a["dosya"]), o)
            k["perk_sapma"] = abs(k["perk_oran"] - 1)
            k["bolum_sapma"] = abs(k["bolum_degisim"] - 1)
            k["wer"] = (a["kapilar"].get("soz_wer") or {}).get("deger", 1.0)
            k["pi"] = (a["kapilar"].get("parmak_izi") or {}).get("deger", 1.0)
            olc[a["no"]] = k
        satirlar.append({"kimlik": d["kimlik"], "secilen": d["secilen"], "olc": olc})
        print(d["kimlik"][:34], "seçilen", d["secilen"], {n: {k: v[k] for k in ("groove", "dongusellik")}
                                                          for n, v in olc.items()}, flush=True)
    print(f"\n{len(satirlar)} şarkı; rastgele isabet ≈ {sum(1 / len(s['olc']) for s in satirlar):.1f}")
    for ad, (anahtar, buyuk) in OLCULER.items():
        isabet, sira = 0, []
        for s in satirlar:
            dizi = sorted(s["olc"], key=lambda n: s["olc"][n][anahtar], reverse=buyuk)
            isabet += dizi[0] == s["secilen"]
            sira.append(dizi.index(s["secilen"]) + 1)
        print(f"  {ad:12} isabet {isabet}/{len(satirlar)}  seçilenin ort. sırası {sum(sira) / len(sira):.2f}")
    (KOK / "calisma" / "_spike" / "s24.json").write_text(json.dumps(satirlar, ensure_ascii=False, indent=1),
                                                         encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
