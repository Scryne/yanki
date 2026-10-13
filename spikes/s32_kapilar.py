"""S32 kollarını üretimin kapılarından geçirir (söz WER, parmak izi, dalga, süre): E orijinalin eşliğinden üretildiği
için orijinal kaydı taşıyor mu (S23'te orijinal tını referansı kaydı sızdırmıştı). Çıktı `_spike/s32/kapilar.json`.

  uv run --no-sync python spikes/s32_kapilar.py [kol …]
"""

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import ayarlar, durum, egitim, kapilar, kulak  # noqa: E402

CALISMA = KOK / "calisma"
KLASOR = CALISMA / "_spike" / "s32"


def main(kollar: list[str]) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    a = ayarlar.yukle()
    yol = KLASOR / "kapilar.json"
    sonuc = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    for sarki in kulak.sarki_listesi(CALISMA, kulak.setler()["beat-1"]):
        kok = egitim.deneme_kok(CALISMA, sarki)
        d = durum.oku(kok, sarki)
        k = durum.klasor(kok, sarki)
        soz = (k / d.soz["dosya"]).read_text(encoding="utf-8")
        satir = []
        for kol in kollar:
            dosya = CALISMA / "dinleme" / "s32" / sarki / f"{kol}.flac"
            if not dosya.exists():
                continue
            r = kapilar.degerlendir(dosya, k / d.kaynak["dosya"], soz, a.fpcalc, dil=d.analiz.get("dil", "en"))
            sonuc.setdefault(sarki, {})[kol] = r
            gecti = all(v.get("gecti", True) for v in r.values() if isinstance(v, dict))
            satir.append(f"{kol} {'✓' if gecti else '✗'} iz {r['parmak_izi']['deger']:.3f} "
                         f"dalga {r['dalga']['deger']:.3f} wer {r['soz_wer']['deger']:.2f}")
        print(f"  {sarki[:34]:34} " + " | ".join(satir), flush=True)
        yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(sys.argv[1:] or ["A", "B", "E"])
