"""S32: beat neden zayıf, sayıyla. Scryne (2026-10-14, ek eğitim kör testinden sonra): "vokal şu anlık okey, beat
tarafı hâlâ eksik ve kötü"; kulağa batan: ince/güçsüz, basslar zayıf, enstrüman eksik, ritim yanlış, hepsi aynı.

Aynı 17 şarkı (S30/S31 seti): orijinal kayıt ve üretimdeki model (ep20) çıktısı Demucs htdemucs ile dört parçaya
ayrılır (vokal, davul, bas, diğer). Ölçüler:
- parça seviyesi vokale göre (dB): davul, bas, diğer; cover − orijinal farkı "ince / bas zayıf"ı gösterir
- alt bant payı (< 120 Hz, karışımın enerjisinde): "bas zayıf"
- davul tepe/RMS oranı (crest, dB): vuruşun keskinliği, "güçsüz"
- diğer parçanın spektral düzlüğü ve bant genişliği: "enstrüman eksik" (ince, dar bir yatak)
Ayrılmış parçalar `calisma/_spike/s32/<şarkı>/{orijinal,ep20}/` altında kalır (sonraki kollar karışımı buradan kurar).

  uv run --no-sync python spikes/s32_beat_olcum.py [--cpu]
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import kulak  # noqa: E402

CALISMA = KOK / "calisma"
KLASOR = CALISMA / "_spike" / "s32"
# torch sabit + CUDA dizini: sabitsiz `--with demucs` PyPI'dan CPU torch çekiyor ("Torch not compiled with CUDA")
DEMUCS = ["uv", "run", "--no-project", "--python", "3.11", "--with", "demucs", "--with", "soundfile",
          "--with", "torch==2.7.1+cu128", "--with", "torchaudio==2.7.1+cu128",
          "--index", "https://download.pytorch.org/whl/cu128", "--index-strategy", "unsafe-best-match",
          "python", "-m", "demucs"]
PARCALAR = ("vocals", "drums", "bass", "other")


def ayir(girdi: Path, hedef: Path, cihaz: str) -> None:
    if all((hedef / f"{p}.wav").exists() for p in PARCALAR):
        return
    gecici = hedef.parent / "_demucs"
    subprocess.run([*DEMUCS, "-n", "htdemucs", "-d", cihaz, "-o", str(gecici), str(girdi)], check=True)
    cikti = gecici / "htdemucs" / girdi.stem
    hedef.mkdir(parents=True, exist_ok=True)
    for p in PARCALAR:
        (cikti / f"{p}.wav").replace(hedef / f"{p}.wav")


def _oku(yol: Path) -> tuple[np.ndarray, int]:
    x, sr = sf.read(str(yol), dtype="float32", always_2d=True)
    return x.mean(1), sr


def _db(x: np.ndarray) -> float:
    return float(10 * np.log10(np.mean(x ** 2) + 1e-12))


def _crest(x: np.ndarray, sr: int) -> float:
    """Davulun tepe/RMS oranı, 50 ms pencerelerde (sessiz pencereler hariç) medyan: vuruşun keskinliği."""
    n = int(0.05 * sr)
    p = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt((p ** 2).mean(1)) + 1e-9
    tepe = np.abs(p).max(1)
    canli = rms > rms.max() * 0.05
    return float(np.median(20 * np.log10(tepe[canli] / rms[canli]))) if canli.any() else 0.0


def _spektrum(x: np.ndarray, sr: int) -> tuple[np.ndarray, np.ndarray]:
    n = 8192
    p = x[: len(x) // n * n].reshape(-1, n) * np.hanning(n)
    g = (np.abs(np.fft.rfft(p, axis=1)) ** 2).mean(0)
    return np.fft.rfftfreq(n, 1 / sr), g


def olc(klasor: Path) -> dict:
    s = {p: _oku(klasor / f"{p}.wav") for p in PARCALAR}
    sr = s["vocals"][1]
    karisim = sum(x for x, _ in s.values())
    f, g = _spektrum(karisim, sr)
    alt = float(g[f < 120].sum() / g.sum())
    fo, go = _spektrum(s["other"][0], sr)
    bant = go[(fo > 60) & (fo < 16000)]
    duzluk = float(np.exp(np.mean(np.log(bant + 1e-20))) / (np.mean(bant) + 1e-20))
    merkez = float((fo * go).sum() / go.sum())
    yayilim = float(np.sqrt((((fo - merkez) ** 2) * go).sum() / go.sum()))
    v = _db(s["vocals"][0])
    return {"davul_db": round(_db(s["drums"][0]) - v, 2), "bas_db": round(_db(s["bass"][0]) - v, 2),
            "diger_db": round(_db(s["other"][0]) - v, 2), "alt_bant": round(alt, 4),
            "davul_crest": round(_crest(s["drums"][0], sr), 2), "diger_duzluk": round(duzluk, 4),
            "diger_yayilim_hz": round(yayilim)}


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    cihaz = "cpu" if "--cpu" in sys.argv else "cuda"
    set_ = kulak.setler()["egitim-5"]
    sonuc = {}
    for sarki in kulak.sarki_listesi(CALISMA, set_):
        kaynak = kulak.dosya_yolu(CALISMA, set_, sarki, "orijinal")
        ep20 = kulak.dosya_yolu(CALISMA, set_, sarki, "ep20")
        if not kaynak or not ep20:
            print(f"  ✗ {sarki}: dosya yok")
            continue
        for ad, yol in (("orijinal", kaynak), ("ep20", ep20)):
            ayir(yol, KLASOR / sarki / ad, cihaz)
        sonuc[sarki] = {ad: olc(KLASOR / sarki / ad) for ad in ("orijinal", "ep20")}
        o, c = sonuc[sarki]["orijinal"], sonuc[sarki]["ep20"]
        print(f"  {sarki[:34]:34} " + " ".join(f"{k} {c[k] - o[k]:+.2f}" for k in o), flush=True)
    (KLASOR / "olcum.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
    if sonuc:
        print("── ortalama fark (ep20 − orijinal)")
        for k in next(iter(sonuc.values()))["orijinal"]:
            fark = [v["ep20"][k] - v["orijinal"][k] for v in sonuc.values()]
            print(f"  {k:18} {np.mean(fark):+.3f}  (ep20 küçük: {sum(x < 0 for x in fark)}/{len(fark)})")


if __name__ == "__main__":
    main()
