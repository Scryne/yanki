"""S32 kolları: karışım ve mastering. Kör test için her kol üretimdeki mastering'den geçer (paket.master: −14 LUFS,
ton eşleme orijinale), yani yayına gidecek haliyle ve aynı ses yüksekliğinde dinlenir.

- **A:** üretimdeki ep20 çıktısı (taban).
- **B (parça parça ton eşleme):** ep20 çıktısı Demucs parçalarından yeniden karışır; vokal olduğu gibi kalır, davul,
  bas ve diğer parçanın her biri orijinalin aynı parçasına göre frekans eğrisi (ton.py, parça sınırlarıyla) ve vokale
  göre seviye alır. Arkadaşın yapımcı istemindeki "orijinalin davul/bas/tını karakterine yaklaş, vokale dokunma"nın
  otomatik hali. Ritmi ve eksik enstrümanı düzeltemez; inceliği ve zayıf bası hedefler.
- **E:** s32_ayri_beat.py E çıktısı (orijinal eşliğin enstrümantal cover'ı) + ep20 vokali; eşliğin vokale göre
  seviyesi orijinaldeki gibi.
- **C:** s32_ayri_beat.py C çıktısı (ep20 vokali üstüne xl-base `complete`) olduğu gibi.

  uv run --no-sync python spikes/s32_karisim.py
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import kulak, paket, ses, ton  # noqa: E402

CALISMA = KOK / "calisma"
KLASOR = CALISMA / "_spike" / "s32"
DINLEME = CALISMA / "dinleme" / "s32"
ESLIK = ("drums", "bass", "other")
# parça eğrisi: karışımdakinden geniş (parça tek başına, maskelenme yok), yükseltme yine sınırlı (yapay ürün büyür)
ORAN, KESME, YUKSELTME = 1.0, 12.0, 6.0
SEVIYE_SINIR_DB = 12.0


def _rms_db(x: np.ndarray) -> float:
    return float(10 * np.log10(np.mean(x ** 2) + 1e-12))


def _oku(yol: Path) -> tuple[np.ndarray, int]:
    return sf.read(str(yol), dtype="float32", always_2d=True)


def parca_egrisi(cover: Path, orijinal: Path) -> list[tuple[float, float]]:
    c = np.asarray(ton.MERKEZLER)
    fark = ton.bant_spektrumu(orijinal) - ton.bant_spektrumu(cover)
    fark = fark - np.median(fark[(c >= 200) & (c <= 4000)])  # seviye ayrı ayarlanır
    yumusak = np.convolve(np.pad(fark, 1, mode="edge"), np.ones(3) / 3, mode="valid")
    d = np.clip(yumusak * ORAN, -KESME, YUKSELTME)
    d[(c < ton.ALT_HZ) | (c > ton.UST_HZ)] = 0.0
    return [(float(hz), round(float(db), 2)) for hz, db in zip(c, d, strict=True)]


def _filtrele(girdi: Path, hedef: Path, filtre: str) -> np.ndarray:
    subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(girdi), "-af", filtre,
                    "-c:a", "pcm_f32le", str(hedef)], check=True)
    return _oku(hedef)[0]


def kol_b(sarki: str, hedef: Path) -> dict:
    o, c = KLASOR / sarki / "orijinal", KLASOR / sarki / "ep20"
    vokal, sr = _oku(c / "vocals.wav")
    ov = _rms_db(_oku(o / "vocals.wav")[0])
    cv = _rms_db(vokal)
    toplam, bilgi = vokal.copy(), {}
    for p in ESLIK:
        egri = parca_egrisi(c / f"{p}.wav", o / f"{p}.wav")
        x, _ = _oku(c / f"{p}.wav")
        # orijinalde parçanın vokale göre seviyesi; cover'da aynı fark kurulur
        kazanc = float(np.clip((_rms_db(_oku(o / f"{p}.wav")[0]) - ov) - (_rms_db(x) - cv),
                               -SEVIYE_SINIR_DB, SEVIYE_SINIR_DB))
        filtre = f"volume={kazanc:.2f}dB," + ton.ffmpeg_filtresi(egri)
        y = _filtrele(c / f"{p}.wav", hedef.with_name(f"_{p}.wav"), filtre)
        n = min(len(toplam), len(y))
        toplam = toplam[:n] + y[:n]
        hedef.with_name(f"_{p}.wav").unlink()
        bilgi[p] = {"kazanc_db": round(kazanc, 2), "egri": egri}
    sf.write(str(hedef), toplam, sr, subtype="FLOAT")
    return bilgi


def kol_e(sarki: str, eslik: Path, hedef: Path) -> dict:
    o, c = KLASOR / sarki / "orijinal", KLASOR / sarki / "ep20"
    vokal, sr = _oku(c / "vocals.wav")
    e, esr = _oku(eslik)
    if esr != sr:
        e = _filtrele(eslik, hedef.with_name("_e.wav"), f"aresample={sr}")
        hedef.with_name("_e.wav").unlink()
    oe = _rms_db(sum(_oku(o / f"{p}.wav")[0] for p in ESLIK)) - _rms_db(_oku(o / "vocals.wav")[0])
    kazanc = float(np.clip(oe - (_rms_db(e) - _rms_db(vokal)), -SEVIYE_SINIR_DB, SEVIYE_SINIR_DB))
    n = min(len(vokal), len(e))
    sf.write(str(hedef), vokal[:n] + e[:n] * 10 ** (kazanc / 20), sr, subtype="FLOAT")
    return {"kazanc_db": round(kazanc, 2)}


def _cikti(asama: str, sarki: str) -> Path | None:
    yol = KLASOR / f"sonuc_{asama}.json"
    if not yol.exists():
        return None
    r = json.loads(yol.read_text(encoding="utf-8")).get(f"{sarki}|{asama}") or {}
    return Path(r["cikti"]) if r.get("basari") and r.get("cikti") and Path(r["cikti"]).exists() else None


def main() -> None:
    y = paket.yayin_ayarlari(KOK / "config" / "yayin.toml")
    set_ = kulak.setler()["egitim-5"]
    rapor = {}
    for sarki in kulak.sarki_listesi(CALISMA, set_):
        if not (KLASOR / sarki / "ep20" / "vocals.wav").exists():
            continue
        orijinal = kulak.dosya_yolu(CALISMA, set_, sarki, "orijinal")
        k = DINLEME / sarki
        k.mkdir(parents=True, exist_ok=True)
        ham = {"A": kulak.dosya_yolu(CALISMA, set_, sarki, "ep20")}
        b = k / "_B_ham.wav"
        rapor[sarki] = {"B": kol_b(sarki, b)}
        ham["B"] = b
        if e := _cikti("E", sarki):
            rapor[sarki]["E"] = kol_e(sarki, e, k / "_E_ham.wav")
            ham["E"] = k / "_E_ham.wav"
        if c := _cikti("C", sarki):
            ham["C"] = c
        for kol, girdi in ham.items():
            if not (k / f"{kol}.flac").exists() or kol in ("B", "E"):
                paket.master(girdi, k / f"{kol}.flac", y, referans=orijinal)
        for gecici in k.glob("_*_ham.wav"):
            gecici.unlink()
        print(f"  {sarki[:36]:36} {' '.join(sorted(ham))}  B kazanç " +
              " ".join(f"{p} {rapor[sarki]['B'][p]['kazanc_db']:+.1f}" for p in ESLIK), flush=True)
    (KLASOR / "karisim.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
