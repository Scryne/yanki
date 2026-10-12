"""S22: beat (eşlik) teşhisi. Scryne (2026-10-12): "üretilmiş tüm şarkıların beatleri çok kötü ve aynıydı".

Seçilmiş aday ile orijinal kayıt, vurmalı/armonik ayrıştırma (HPSS, medyan süzgeç) üzerinden karşılaştırılır:
  perk_oran     cover'ın vurmalı enerji payı / orijinalinki (1'in altı: davul/vurmalı zayıf ya da yok)
  groove        vurmalı vuruş zarfı korelasyonu (±2 kare kayma; cover orijinalin ritmini izliyor mu)
  bolum_degisim vurmalı enerji eğrisinin (4 sn) standart sapması, orijinale oran (1'in altı: bölümler arası düz)
  dongusellik   vurmalı zarfın 1,5–6 sn gecikmedeki en yüksek öz-korelasyonu, cover − orijinal (+: daha döngü gibi)
Şarkılar arası aynılık: vurmalı ve armonik bileşenin 1/3 oktav ortalama tayfı (seviyesi ortalanmış); cover'ların
birbirine ortalama kosinüs benzerliği, orijinallerin birbirine benzerliğiyle karşılaştırılır.

Motorun venv'iyle (scipy):  motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s22_beat.py [klasör ...]
Klasör verilirse (ör. calisma/dinleme/s20) oradaki <kimlik>/…/<kol>.flac dosyaları kol kol ölçülür.
"""

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import median_filter
from scipy.signal import resample_poly, stft

KOK = Path(__file__).resolve().parents[1]
SR, NFFT, HOP = 22050, 2048, 512
# 63 Hz–~8 kHz: altında STFT çözünürlüğü, üstünde 22 kHz örnekleme bandı boş bırakıyor
MERKEZLER = [63.0 * 2 ** (i / 3) for i in range(22)]


def yukle(yol: Path) -> np.ndarray:
    x, sr = sf.read(str(yol), dtype="float32", always_2d=True)
    m = x.mean(1)
    return resample_poly(m, SR, sr).astype("float32") if sr != SR else m


def hpss(m: np.ndarray):
    f, _, z = stft(m, SR, nperseg=NFFT, noverlap=NFFT - HOP)
    s = np.abs(z)
    h = median_filter(s, size=(1, 31))
    p = median_filter(s, size=(31, 1))
    maske_p = p ** 2 / (h ** 2 + p ** 2 + 1e-12)
    return f, s * (1 - maske_p), s * maske_p


def zarf(p: np.ndarray) -> np.ndarray:
    lg = np.log1p(100 * p)
    akis = np.maximum(0, np.diff(lg, axis=1)).sum(0)
    return (akis - akis.mean()) / (akis.std() + 1e-9)


def tayf(f, s) -> np.ndarray:
    guc = (s ** 2).mean(1)
    v = np.array([10 * np.log10(guc[(f >= c / 2 ** (1 / 6)) & (f < c * 2 ** (1 / 6))].mean() + 1e-12)
                  for c in MERKEZLER])
    return v - np.median(v)


def egri(p: np.ndarray, pencere_sn=4.0) -> np.ndarray:
    e = (p ** 2).sum(0)
    n = int(pencere_sn * SR / HOP)
    e = e[: len(e) // n * n].reshape(-1, n).mean(1)
    return 10 * np.log10(e + 1e-12)


def dongu(z: np.ndarray) -> float:
    lo, hi = int(1.5 * SR / HOP), int(6 * SR / HOP)
    ac = np.correlate(z[:6000], z[:6000], "full")[len(z[:6000]) - 1:]
    ac = ac / (ac[0] + 1e-9)
    return float(ac[lo:hi].max())


def analiz(yol: Path) -> dict:
    m = yukle(yol)
    f, h, p = hpss(m)
    return {"perk": float((p ** 2).sum() / ((h ** 2).sum() + (p ** 2).sum())), "zarf": zarf(p), "egri": egri(p),
            "dongu": dongu(zarf(p)), "tayf": np.concatenate([tayf(f, p), tayf(f, h)])}


def karsilastir(c: dict, o: dict) -> dict:
    n = min(len(c["zarf"]), len(o["zarf"]))
    a, b = c["zarf"][:n], o["zarf"][:n]
    groove = max(float(np.corrcoef(a[max(0, k):n + min(0, k)], b[max(0, -k):n - max(0, k)])[0, 1])
                 for k in range(-2, 3))
    n2 = min(len(c["egri"]), len(o["egri"]))
    ce, oe = c["egri"][:n2], o["egri"][:n2]
    ses = oe > oe.max() - 35
    return {"perk_oran": round(c["perk"] / o["perk"], 2), "groove": round(groove, 3),
            "bolum_degisim": round(float(ce[ses].std() / max(oe[ses].std(), 1e-6)), 2),
            "egri_kor": round(float(np.corrcoef(ce[ses], oe[ses])[0, 1]), 2),
            "dongusellik": round(c["dongu"] - o["dongu"], 3)}


def benzerlik(vekt: list[np.ndarray]) -> float:
    v = np.array([x / np.linalg.norm(x) for x in vekt])
    s = v @ v.T
    return float(s[np.triu_indices(len(v), 1)].mean())


def yuklenenler() -> list[tuple[str, Path, Path]]:
    cikti = []
    for yol in sorted((KOK / "calisma").glob("*/durum.json")):
        d = json.loads(yol.read_text(encoding="utf-8"))
        if not d.get("secilen") or d.get("asama") not in ("yuklendi", "paketlendi", "onaylandi"):
            continue
        a = next((x for x in d["adaylar"] if x["no"] == d["secilen"]), None)
        if a and a.get("dosya"):
            cikti.append((d["kimlik"], yol.parent / a["dosya"], yol.parent / d["kaynak"]["dosya"]))
    return cikti


def main(klasorler: list[str]) -> int:
    if not klasorler:
        ciftler = {"secilen": yuklenenler()}
    else:
        ciftler = {}
        for k in klasorler:
            for f in sorted([*Path(k).rglob("*.flac"), *Path(k).rglob("master.wav")]):  # <kimlik>/…/<kol>.flac
                kimlik = f.relative_to(k).parts[0]
                kaynak = next(p for p in [KOK / "calisma" / kimlik / "kaynak.wav",
                                           KOK / "calisma" / "_spike" / "s21" / kimlik / "kaynak.wav",
                                           KOK / "calisma" / "_spike" / "s29" / kimlik / "kaynak.wav"] if p.exists())
                ciftler.setdefault(f.stem, []).append((kimlik, f, kaynak))
    orijinal_onbellek: dict[Path, dict] = {}
    rapor = {}
    for kol, liste in ciftler.items():
        satirlar, cv, ov = [], [], []
        for kimlik, cover, kaynak in liste:
            o = orijinal_onbellek.setdefault(kaynak, analiz(kaynak))
            c = analiz(cover)
            satirlar.append({"kimlik": kimlik, **karsilastir(c, o)})
            cv.append(c["tayf"])
            ov.append(o["tayf"])
        ort = {k: round(float(np.mean([s[k] for s in satirlar])), 3) for k in satirlar[0] if k != "kimlik"}
        rapor[kol] = {"sarkilar": satirlar, "ortalama": ort,
                      "aynilik_cover": round(benzerlik(cv), 3) if len(cv) > 1 else None,
                      "aynilik_orijinal": round(benzerlik(ov), 3) if len(ov) > 1 else None}
        print(f"\n== {kol} ({len(satirlar)} şarkı) ==")
        for s in satirlar:
            print(f"  {s['kimlik'][:36]:36} perk {s['perk_oran']:5} groove {s['groove']:6} "
                  f"bölüm {s['bolum_degisim']:5} eğri {s['egri_kor']:5} döngü {s['dongusellik']:+.3f}")
        print(f"  ORTALAMA {ort}")
        r = rapor[kol]
        print(f"  şarkılar arası aynılık: cover {r['aynilik_cover']} | orijinal {r['aynilik_orijinal']}")
    hedef = KOK / "calisma" / "_spike" / ("s22_" + ("_".join(Path(k).name for k in klasorler) or "yuklenen") + ".json")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    hedef.write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
