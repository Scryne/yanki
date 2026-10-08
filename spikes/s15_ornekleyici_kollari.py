"""S15 (Faz 8): ACE-Step'in henüz denenmemiş örnekleyici kolları, nefes ve mırıldanma kusuru için.

S12/S13 ile aynı kesit (Adele 0:40–1:25), temiz söz + tarif. S12'de shift, ADG, CFG 5/9, Heun, hız kırpma denendi;
burada kalanlar: DCW (dalgacık düzeltmesi; XL-SFT'de varsayılan kapalı, `motor/ACE-Step-1.5/docs/en/DCW.md`), SDE
örnekleme, CFG aralığı (kılavuzluk yalnız orta adımlarda), hız EMA'sı. Tohum en büyük kol olduğu için (S13) her kol iki
tohumla: 42 ve 7. Tabanlar zaten var: S12 `8_soz_temiz` (42), S13 `1_tohum7` (7). Çıktılar: calisma/dinleme/s15/.

  uv run python spikes/s15_ornekleyici_kollari.py
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

import soundfile as sf

from yanki import ayarlar, durum, kapilar, motor, sozler

KIMLIK = "adele-someone-like-you"
BAS, SON = 40.0, 85.0
TOHUMLAR = (42, 7)
# ad: ek GenerationParams
KOLLAR = {
    "dcw_low": {"dcw_enabled": True, "dcw_mode": "low", "dcw_scaler": 0.05},
    "dcw_double": {"dcw_enabled": True, "dcw_mode": "double", "dcw_scaler": 0.05, "dcw_high_scaler": 0.02},
    "sde": {"infer_method": "sde"},
    "cfg_aralik": {"cfg_interval_start": 0.1, "cfg_interval_end": 0.9},
    "hiz_ema": {"velocity_ema_factor": 0.1},
}


def mp3(girdi: str | Path, hedef: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(girdi), "-b:a", "192k", str(hedef)], check=True)


def main() -> None:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    d = durum.oku(calisma, KIMLIK)
    cikti, dinleme = calisma / "_spike" / "s15", calisma / "dinleme" / "s15"
    cikti.mkdir(parents=True, exist_ok=True)
    dinleme.mkdir(parents=True, exist_ok=True)

    ses, sr = sf.read(str(durum.klasor(calisma, KIMLIK) / d.kaynak["dosya"]), dtype="float32", always_2d=True)
    kesit = cikti / "kaynak_kesit.wav"
    sf.write(str(kesit), ses[int(BAS * sr) : int(SON * sr)], sr)
    soz = sozler.aralik_sozu(sozler.lrclib(d.sanatci, d.ad).satirlar, BAS, SON)
    (cikti / "soz.txt").write_text(soz, encoding="utf-8")

    isler = [
        motor.Is(id=f"{i}_{kol}_t{tohum}", gorev="cover", kaynak=str(kesit), cikti_klasor=str(cikti / f"{kol}_t{tohum}"),
                 stil=d.analiz["stil"], soz=soz, adim=a.cover.adim, tohum=tohum, guc=a.cover.guc,
                 bpm=d.analiz.get("bpm"), ton=d.analiz.get("ton") or "", ek=ek)
        for i, (kol, ek) in enumerate(KOLLAR.items(), start=1)
        for tohum in TOHUMLAR
    ]
    t = time.time()
    sonuclar = motor.calistir(a, isler, cikti / "_motor", zaman_asimi_sn=len(isler) * 20 * 60)
    ozet = {"toplam_sn": round(time.time() - t)}
    for r in sonuclar:
        ozet[r.id] = {"basari": r.basari, "sure_sn": r.sure_sn, "hata": r.hata}
        if r.basari:
            mp3(r.cikti, dinleme / f"{r.id}.mp3")
            kp = kapilar.degerlendir(Path(r.cikti), kesit, soz, a.fpcalc)
            ozet[r.id]["kapilar"] = {n: v["deger"] for n, v in kp.items()}
            ozet[r.id]["gecti"] = kapilar.hepsi_gecti(kp)
        print(r.id, json.dumps(ozet[r.id], ensure_ascii=False), flush=True)
    # karşılaştırma: aynı tohumların tabanları ve orijinal
    shutil.copy(calisma / "dinleme" / "s12" / "8_soz_temiz.mp3", dinleme / "0_taban_t42.mp3")
    shutil.copy(calisma / "dinleme" / "s13" / "1_tohum7.mp3", dinleme / "0_taban_t7.mp3")
    mp3(kesit, dinleme / "orijinal_kesit.mp3")
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
