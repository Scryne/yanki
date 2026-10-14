"""S33 kollarını ölçer: kulak testinden önce eleme. İki adım, iki ortam:

  uv run --no-sync python spikes/s33_olcum.py kapilar          # üretimin kapıları (söz WER, parmak izi, dalga, süre)
  motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s33_olcum.py beat   # S22 beat + S32 parça ölçüleri (scipy)
  uv run --no-sync python spikes/s33_olcum.py ozet

Beat ölçüleri orijinale göre: groove (S22), döngüsellik farkı, bölüm değişimi; Demucs parça seviyeleri (vokale göre
bas/diğer/davul dB, davul crest) cover − orijinal. "Orijinale uzaklık" mutlak fark: ince beat bas ve diğer parçada
negatif fark olarak görünür (S32: ep20 bas −4,1 dB).
"""

import json
import sys
from pathlib import Path

import numpy as np

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "spikes"))

CALISMA = KOK / "calisma"
DINLEME = CALISMA / "dinleme" / "s33"
KLASOR = CALISMA / "_spike" / "s33"
KOLLAR = ("A", "D", "H", "S", "G", "J", "L", "K")


def sarkilar() -> list[str]:
    return sorted(p.name for p in DINLEME.iterdir() if p.is_dir())


def kapilar_olc() -> None:
    from yanki import ayarlar, durum, egitim, kapilar

    a = ayarlar.yukle()
    yol = KLASOR / "kapilar.json"
    sonuc = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    for sarki in sarkilar():
        kok = egitim.deneme_kok(CALISMA, sarki)
        d = durum.oku(kok, sarki)
        k = durum.klasor(kok, sarki)
        soz = (k / d.soz["dosya"]).read_text(encoding="utf-8")
        for kol in KOLLAR:
            dosya = DINLEME / sarki / f"{kol}.flac"
            if dosya.exists() and kol not in sonuc.get(sarki, {}):
                sonuc.setdefault(sarki, {})[kol] = kapilar.degerlendir(dosya, k / d.kaynak["dosya"], soz, a.fpcalc,
                                                                       dil=d.analiz.get("dil", "en"))
        print(sarki[:34], {kol: _gecti(r) for kol, r in sonuc.get(sarki, {}).items()}, flush=True)
        KLASOR.mkdir(parents=True, exist_ok=True)
        yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")


def _gecti(r: dict) -> bool:
    return all(v.get("gecti", True) for v in r.values() if isinstance(v, dict))


def beat_olc() -> None:
    import s22_beat
    import s32_beat_olcum as s32

    from yanki import kulak

    set_ = kulak.setler()["egitim-5"]
    yol = KLASOR / "beat.json"
    sonuc = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    for sarki in sarkilar():
        kaynak = kulak.dosya_yolu(CALISMA, set_, sarki, "orijinal")
        o = s22_beat.analiz(kaynak)
        orijinal_parca = s32.olc(s32.KLASOR / sarki / "orijinal")  # S32'de ayrılmıştı
        for kol in KOLLAR:
            dosya = DINLEME / sarki / f"{kol}.flac"
            if not dosya.exists() or kol in sonuc.get(sarki, {}):
                continue
            hedef = KLASOR / sarki / kol
            s32.ayir(dosya, hedef, "cuda")
            p = s32.olc(hedef)
            sonuc.setdefault(sarki, {})[kol] = {**s22_beat.karsilastir(s22_beat.analiz(dosya), o),
                                                **{f"{k}_fark": round(p[k] - orijinal_parca[k], 3) for k in p}}
        print(sarki[:34], {k: (v["groove"], v["bas_db_fark"]) for k, v in sonuc.get(sarki, {}).items()}, flush=True)
        KLASOR.mkdir(parents=True, exist_ok=True)
        yol.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")


def ozet() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    kap = json.loads((KLASOR / "kapilar.json").read_text(encoding="utf-8"))
    beat = json.loads((KLASOR / "beat.json").read_text(encoding="utf-8"))
    alanlar = ("groove", "dongusellik", "bolum_degisim", "perk_oran", "bas_db_fark", "diger_db_fark", "davul_db_fark",
               "davul_crest_fark", "alt_bant_fark")
    print(f"{'kol':4} {'kapı':>6} {'WER':>6} {'iz':>6} " + " ".join(f"{a[:13]:>13}" for a in alanlar))
    for kol in KOLLAR:
        k = [kap[s][kol] for s in kap if kol in kap[s]]
        b = [beat[s][kol] for s in beat if kol in beat[s]]
        if not k:
            continue
        wer = np.median([x["soz_wer"]["deger"] for x in k])
        iz = max(x["parmak_izi"]["deger"] for x in k)
        satir = f"{kol:4} {sum(map(_gecti, k)):>3}/{len(k):<2} {wer:6.3f} {iz:6.3f} "
        satir += " ".join(f"{np.median([x[a] for x in b]):13.3f}" for a in alanlar) if b else ""
        print(satir)


if __name__ == "__main__":
    adim = sys.argv[1] if len(sys.argv) > 1 else ""
    if adim not in ("kapilar", "beat", "ozet"):
        raise SystemExit(__doc__)
    {"kapilar": kapilar_olc, "beat": beat_olc, "ozet": ozet}[adim]()
