"""S10: parçalı tam şarkı cover'ı — süre, dikişler ve tını tutarlılığı (referanslı A / referanssız B).

  uv run python spikes/s10_parcali.py <kaynak.wav> "<sanatçı>" "<şarkı>" "<stil>" <bpm> "<ton>" <cikti_klasor>
"""

import json
import sys
import time
from pathlib import Path

import soundfile as sf

from yanki import ayarlar, motor, parcalama, sozler


def main() -> None:
    kaynak, sanatci, sarki, stil, bpm, ton, cikti = sys.argv[1:8]
    cikti = Path(cikti).resolve()
    a = ayarlar.yukle()
    soz = sozler.lrclib(sanatci, sarki)
    ses, sr = sf.read(kaynak, dtype="float32")
    sure = len(ses) / sr
    plan = parcalama.plan(sure, [t for t, _ in soz.satirlar])
    sozler_ = parcalama.soz_dagit(plan, list(soz.satirlar))
    print("plan:", [(p.no, p.bas, p.son) for p in plan])
    for p in plan:
        sf.write(str(cikti / f"kaynak_{p.no}.wav"), ses[int(p.bas * sr): int(p.son * sr)], sr)

    def is_(p, ek, ref=None):
        return motor.Is(id=f"{ek}{p.no}", gorev="cover", kaynak=str(cikti / f"kaynak_{p.no}.wav"),
                        cikti_klasor=str(cikti / f"{ek}{p.no}"), stil=stil, soz=sozler_[p.no - 1], adim=a.cover.adim,
                        tohum=a.cover.tohumlar[0], guc=a.cover.guc, bpm=int(bpm), ton=ton, referans=ref)

    t = time.time()
    ilk = motor.calistir(a, [is_(plan[0], "p")], cikti / "_m1", zaman_asimi_sn=3600)[0]
    assert ilk.basari, ilk.hata
    kalan = [is_(p, "A", ilk.cikti) for p in plan[1:]] + [is_(p, "B") for p in plan[1:]]
    sonuc = {r.id: r for r in motor.calistir(a, kalan, cikti / "_m2", zaman_asimi_sn=3 * 3600)}
    toplam = time.time() - t
    for ek in "AB":
        dosyalar = [ilk.cikti] + [sonuc[f"{ek}{p.no}"].cikti for p in plan[1:]]
        sesler = [sf.read(d, dtype="float32", always_2d=True)[0] for d in dosyalar]
        birlesik = parcalama.birlestir(sesler, plan, 48000)
        sf.write(str(cikti / f"tam_{ek}.flac"), birlesik, 48000)
    print(json.dumps({"toplam_sn": round(toplam), "ilk_parca_sn": ilk.sure_sn,
                      "parcalar": {k: (v.basari, v.sure_sn, v.hata) for k, v in sonuc.items()}}, ensure_ascii=False))


if __name__ == "__main__":
    main()
