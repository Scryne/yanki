"""S18 (Faz 8): INT8 niceleme vokal kalitesini düşürüyor mu?

XL-SFT 8 GB'a yalnız INT8 ile sığdığı için (S1: bf16 adım başı 72–150 sn) tam hassasiyetle kalite hiç
karşılaştırılmadı. S17: mırıldanma söylenen cümlenin içinde (sesin kalitesi), son işlemle düzelmez → darboğaz modelin
kendisi olabilir. Aynı kesit (Adele 0:40–1:25), temiz söz + tarif, tohum 42 ve 7; tabanlar INT8 (S12 `8_soz_temiz`,
S13 `1_tohum7`). Kollar: FP8 (RTX 4060 Ada destekliyor, INT8 ile aynı bellek) ve bf16 (nicelemesiz; yavaş, gece).
Farklı niceleme aynı tohumda bile farklı sayısal yol demek: karşılaştırma yön gösterir, birebir değil.
Çıktılar: calisma/dinleme/s18/.

  set ACESTEP_GENERATION_TIMEOUT=14400 & uv run python spikes/s18_niceleme.py
"""

import dataclasses
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
KOLLAR = {"fp8": "fp8_weight_only", "bf16": None}  # sırayla: hızlı olan önce


def mp3(girdi: str | Path, hedef: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(girdi), "-b:a", "192k", str(hedef)], check=True)


def main() -> None:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    d = durum.oku(calisma, KIMLIK)
    cikti, dinleme = calisma / "_spike" / "s18", calisma / "dinleme" / "s18"
    cikti.mkdir(parents=True, exist_ok=True)
    dinleme.mkdir(parents=True, exist_ok=True)
    shutil.copy(calisma / "dinleme" / "s12" / "8_soz_temiz.mp3", dinleme / "0_int8_t42.mp3")
    shutil.copy(calisma / "dinleme" / "s13" / "1_tohum7.mp3", dinleme / "0_int8_t7.mp3")

    ses, sr = sf.read(str(durum.klasor(calisma, KIMLIK) / d.kaynak["dosya"]), dtype="float32", always_2d=True)
    kesit = cikti / "kaynak_kesit.wav"
    sf.write(str(kesit), ses[int(BAS * sr) : int(SON * sr)], sr)
    mp3(kesit, dinleme / "orijinal_kesit.mp3")
    soz = sozler.aralik_sozu(sozler.lrclib(d.sanatci, d.ad).satirlar, BAS, SON)

    ozet_yolu = cikti / "ozet.json"
    ozet = json.loads(ozet_yolu.read_text(encoding="utf-8")) if ozet_yolu.exists() else {}
    for kol, niceleme in KOLLAR.items():
        ak = dataclasses.replace(a, motor=dataclasses.replace(a.motor, niceleme=niceleme))
        isler = [
            motor.Is(id=f"{kol}_t{tohum}", gorev="cover", kaynak=str(kesit), cikti_klasor=str(cikti / f"{kol}_t{tohum}"),
                     stil=d.analiz["stil"], soz=soz, adim=a.cover.adim, tohum=tohum, guc=a.cover.guc,
                     bpm=d.analiz.get("bpm"), ton=d.analiz.get("ton") or "")
            for tohum in TOHUMLAR
            if not ozet.get(f"{kol}_t{tohum}", {}).get("basari")
        ]
        t = time.time()
        for r in motor.calistir(ak, isler, cikti / f"_motor_{kol}", zaman_asimi_sn=len(isler) * 4 * 3600):
            ozet[r.id] = {"basari": r.basari, "sure_sn": r.sure_sn, "hata": r.hata, "vram_tepe_gb": r.vram_tepe_gb}
            if r.basari:
                mp3(r.cikti, dinleme / f"{r.id}.mp3")
                kp = kapilar.degerlendir(Path(r.cikti), kesit, soz, a.fpcalc)
                ozet[r.id]["kapilar"] = {n: v["deger"] for n, v in kp.items()}
                ozet[r.id]["gecti"] = kapilar.hepsi_gecti(kp)
            print(r.id, json.dumps(ozet[r.id], ensure_ascii=False), flush=True)
            ozet_yolu.write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"{kol}: {round(time.time() - t)} sn", flush=True)


if __name__ == "__main__":
    main()
