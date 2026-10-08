"""S17 (Faz 8): "mırıldanma" = orijinal şarkıcının sustuğu yerde cover'ın vokal üretmesi mi?

Scryne'ın S12/S13 yorumu: "nefes yerlerinde ve mırıldanmalarda kötü". Kaynak ve cover Demucs (htdemucs_ft, CPU) ile
ayrılır; kaynakta vokal yokken cover'da vokal enerjisi olan kareler "hayalet vokal". Tek etiketle (Adele aday 1,
58–62 sn; onarım 1-1 kabul, 1-2 ret) yön kontrolü: etiket aralığı şarkının en hayaletli pencereleri arasında mı,
kabul edilen onarımda azalıyor mu. Tutarsa iki kullanım: hayalet aralıkları kısan son işlem ve gece onarım işareti.

  uv run python spikes/s17_hayalet_vokal.py
"""

import json
import subprocess
from pathlib import Path

import numpy as np
import soundfile as sf

K = Path("calisma/adele-someone-like-you")
SURUMLER = {"kaynak": K / "kaynak.wav", "once": K / "adaylar/1/tam.flac", "onarim_kabul": K / "onarimlar/1-1/tam.flac",
            "onarim_ret": K / "onarimlar/1-2/tam.flac", "aday4_yuklenen": K / "adaylar/4/tam.flac"}
ETIKET = (58.0, 62.0)
KOK = Path("calisma/_spike/s17")
DEMUCS = ["uv", "run", "--no-project", "--python", "3.11", "--with", "demucs", "--with", "soundfile",
          "--with", "torchaudio<2.9", "python", "-m", "demucs"]
KARE = 0.05  # sn
PENCERE = 2.0  # sn


def ayir(ad: str, yol: Path) -> Path:
    girdi = KOK / "girdi" / f"{ad}.wav"
    hedef = KOK / "htdemucs_ft" / ad / "vocals.wav"
    if not hedef.exists():
        girdi.parent.mkdir(parents=True, exist_ok=True)
        x, sr = sf.read(str(yol), dtype="float32", always_2d=True)
        sf.write(str(girdi), x, sr)
        subprocess.run([*DEMUCS, "--two-stems=vocals", "-n", "htdemucs_ft", "-d", "cpu", "-o", str(KOK), str(girdi)],
                       check=True, capture_output=True)
    return hedef


def zarf_db(yol: Path) -> np.ndarray:
    x, sr = sf.read(str(yol), dtype="float32", always_2d=True)
    m = x.mean(1)
    n = int(KARE * sr)
    k = len(m) // n
    rms = np.sqrt((m[: k * n].reshape(k, n) ** 2).mean(1) + 1e-12)
    return 20 * np.log10(rms)


def main() -> None:
    zarflar = {ad: zarf_db(ayir(ad, yol)) for ad, yol in SURUMLER.items()}
    n = min(len(z) for z in zarflar.values())
    zarflar = {ad: z[:n] for ad, z in zarflar.items()}
    kaynak = zarflar["kaynak"]
    # her izi kendi tepesine göre: vokal var = tepe −35 dB üstü
    sessiz = kaynak < kaynak.max() - 35
    # hizalama: cover kaynağın zamanlamasını izliyor mu (zarf korelasyonu, ±1 sn kaydırma)
    sonuc = {}
    for ad, z in zarflar.items():
        if ad == "kaynak":
            continue
        kaymalar = range(-20, 21)
        r = [np.corrcoef(np.roll(z, s), kaynak)[0, 1] for s in kaymalar]
        en_iyi = list(kaymalar)[int(np.argmax(r))] * KARE
        # hayalet: kaynak sessizken cover vokali kendi tepesinin −25 dB'inden yüksek
        hayalet = sessiz & (z > z.max() - 25)
        w = int(PENCERE / KARE)
        pencere = np.convolve(hayalet.astype(float), np.ones(w), "valid") / w  # pencere içi hayalet oranı
        etiket_maks = float(pencere[int(ETIKET[0] / KARE) : int(ETIKET[1] / KARE)].max())
        sira = int((pencere > etiket_maks).sum() / w)  # etiketten daha hayaletli kaç pencere (örtüşmesiz yaklaşık)
        en_kotu = sorted({round(float(i * KARE)) for i in np.argsort(pencere)[::-1][:400]})[:15]
        sonuc[ad] = {"hizalama_sn": en_iyi, "hizalama_r": round(max(r), 3),
                     "hayalet_sn_toplam": round(float(hayalet.sum() * KARE), 1),
                     "etiket_hayalet_orani": round(etiket_maks, 2), "etiketten_kotu_pencere": sira,
                     "en_hayaletli_saniyeler": en_kotu}
        print(ad, json.dumps(sonuc[ad], ensure_ascii=False), flush=True)
    (KOK / "ozet.json").write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
