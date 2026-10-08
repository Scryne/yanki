"""S16 (Faz 8): cover'a giden kaynakta vokal/eşlik dengesi kirliliği azaltır mı?

Tur 3–4 bulgusu: text2music temiz, cover kirli → kirlilik kaynak koşullamasından geliyor. Yoğun miksin anlamsal
kodları melodiyi ve sözü bulanık taşıyor olabilir. Kaynak kesit Demucs (htdemucs_ft, CPU) ile vokal + eşlik olarak
ayrılır, oranları değişmiş kaynaklarla cover alınır. S12/S13/S15 ile aynı kesit (Adele 0:40–1:25), temiz söz +
tarif, tohum 42 ve 7 (tabanlar S12 `8_soz_temiz` ve S13 `1_tohum7`). Çıktılar: calisma/dinleme/s16/.

  uv run python spikes/s16_kaynak_ayristirma.py
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

import numpy as np
import soundfile as sf

from yanki import ayarlar, durum, kapilar, motor, sozler

KIMLIK = "adele-someone-like-you"
BAS, SON = 40.0, 85.0
TOHUMLAR = (42, 7)
# ad: (vokal kazancı, eşlik kazancı)
KAYNAKLAR = {
    "vokal_one": (1.0, 0.5),  # eşlik −6 dB: melodi ve söz kodlarda baskın
    "yalniz_vokal": (1.0, 0.0),  # a cappella: eşliği stil tanımından kurar
    "vokal_kisik": (0.5, 1.0),  # vokal −6 dB: kaynağın vokal tınısı çıktıya daha az sızar mı
}
DEMUCS = ["uv", "run", "--no-project", "--python", "3.11", "--with", "demucs", "--with", "soundfile",
          "--with", "torchaudio<2.9", "python", "-m", "demucs"]


def mp3(girdi: str | Path, hedef: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(girdi), "-b:a", "192k", str(hedef)], check=True)


def ayir(kesit: Path, kok: Path) -> tuple[np.ndarray, np.ndarray, int]:
    hedef = kok / "htdemucs_ft" / kesit.stem
    if not (hedef / "vocals.wav").exists():
        subprocess.run([*DEMUCS, "--two-stems=vocals", "-n", "htdemucs_ft", "-d", "cpu", "-o", str(kok), str(kesit)],
                       check=True)
    v, sr = sf.read(str(hedef / "vocals.wav"), dtype="float32", always_2d=True)
    e, _ = sf.read(str(hedef / "no_vocals.wav"), dtype="float32", always_2d=True)
    return v, e, sr


def main() -> None:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    d = durum.oku(calisma, KIMLIK)
    cikti, dinleme = calisma / "_spike" / "s16", calisma / "dinleme" / "s16"
    cikti.mkdir(parents=True, exist_ok=True)
    dinleme.mkdir(parents=True, exist_ok=True)

    ses, sr = sf.read(str(durum.klasor(calisma, KIMLIK) / d.kaynak["dosya"]), dtype="float32", always_2d=True)
    kesit = cikti / "kaynak_kesit.wav"
    sf.write(str(kesit), ses[int(BAS * sr) : int(SON * sr)], sr)
    soz = sozler.aralik_sozu(sozler.lrclib(d.sanatci, d.ad).satirlar, BAS, SON)

    v, e, ayr_sr = ayir(kesit, cikti / "ayrim")
    kaynaklar = {}
    for ad, (kv, ke) in KAYNAKLAR.items():
        karisim = kv * v + ke * e
        karisim *= 0.89 / max(1e-6, float(np.abs(karisim).max()))  # −1 dBFS tepe: ses düzeyi kol olmasın
        kaynaklar[ad] = cikti / f"kaynak_{ad}.wav"
        sf.write(str(kaynaklar[ad]), karisim, ayr_sr)
        mp3(kaynaklar[ad], dinleme / f"kaynak_{ad}.mp3")

    isler = [
        motor.Is(id=f"{i}_{ad}_t{tohum}", gorev="cover", kaynak=str(yol), cikti_klasor=str(cikti / f"{ad}_t{tohum}"),
                 stil=d.analiz["stil"], soz=soz, adim=a.cover.adim, tohum=tohum, guc=a.cover.guc,
                 bpm=d.analiz.get("bpm"), ton=d.analiz.get("ton") or "")
        for i, (ad, yol) in enumerate(kaynaklar.items(), start=1)
        for tohum in TOHUMLAR
    ]
    t = time.time()
    sonuclar = motor.calistir(a, isler, cikti / "_motor", zaman_asimi_sn=len(isler) * 20 * 60)
    ozet = {"toplam_sn": round(time.time() - t)}
    for r in sonuclar:
        ozet[r.id] = {"basari": r.basari, "sure_sn": r.sure_sn, "hata": r.hata}
        if r.basari:
            mp3(r.cikti, dinleme / f"{r.id}.mp3")
            # kapı orijinal kesitle: ayrıştırılmış kaynak orijinal kaydı daha çok taşıyor olabilir
            kp = kapilar.degerlendir(Path(r.cikti), kesit, soz, a.fpcalc)
            ozet[r.id]["kapilar"] = {n: v["deger"] for n, v in kp.items()}
            ozet[r.id]["gecti"] = kapilar.hepsi_gecti(kp)
        print(r.id, json.dumps(ozet[r.id], ensure_ascii=False), flush=True)
    shutil.copy(calisma / "dinleme" / "s12" / "8_soz_temiz.mp3", dinleme / "0_taban_t42.mp3")
    shutil.copy(calisma / "dinleme" / "s13" / "1_tohum7.mp3", dinleme / "0_taban_t7.mp3")
    mp3(kesit, dinleme / "orijinal_kesit.mp3")
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
