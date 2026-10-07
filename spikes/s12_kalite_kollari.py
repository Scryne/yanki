"""S12 (Faz 6): kalite kolları — mırıldanma, nefes, titreme için ACE-Step'in örnekleme ayarları.

Aynı kesit (Adele, 0:40–1:25; Scryne'ın onarım için işaretlediği 0:57–1:03'ü içerir), aynı tohum ve tarif; her
varyantta yalnız bir kol değişir. Çıktılar dinleme için MP3'e çevrilir: calisma/dinleme/s12/.

  uv run python spikes/s12_kalite_kollari.py
"""

import json
import subprocess
import time
from pathlib import Path

import soundfile as sf

from yanki import ayarlar, durum, motor, sozler

KIMLIK = "adele-someone-like-you"
BAS, SON = 40.0, 85.0
VARYANTLAR = {
    "0_tarif": {},
    "1_shift3": {"shift": 3.0},
    "2_adg": {"use_adg": True},
    "3_cfg9": {"guidance_scale": 9.0},
    "4_cfg5": {"guidance_scale": 5.0},
    "5_heun": {"sampler_mode": "heun"},
    "6_hiz_kirp2": {"velocity_norm_threshold": 2.0},
    "7_shift3_adg": {"shift": 3.0, "use_adg": True},
}
# 8: tarif aynı, söz temiz — LRCLIB'nin "♪" (enstrümantal ara) satırları söz olarak gitmesin, kıtalar bölüm etiketli
SOZ_TEMIZ = "8_soz_temiz"
NOTA = {"♪", "♫", "♬", "♩"}


def bolumlu(satirlar: list[tuple[float, str]], bas: float, son: float) -> str:
    """♪ satırlarında kıta böler; şarkıda birden çok geçen kıta [chorus], diğerleri [verse]."""
    kitalar, kita = [], []
    for t, m in satirlar:
        if not m.strip() or set(m.strip()) <= NOTA:
            if kita:
                kitalar.append(kita)
            kita = []
        else:
            kita.append((t, m.strip()))
    if kita:
        kitalar.append(kita)
    metinler = [tuple(m for _, m in k) for k in kitalar]
    nakarat = {k for k in metinler if metinler.count(k) > 1}
    bloklar = []
    for k, metin in zip(kitalar, metinler, strict=True):
        icinde = [m for t, m in k if bas <= t < son]
        if icinde:
            bloklar.append(("[chorus]" if metin in nakarat else "[verse]") + "\n" + "\n".join(icinde))
    return "\n\n".join(bloklar)


def main() -> None:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    d = durum.oku(calisma, KIMLIK)
    cikti = calisma / "_spike" / "s12"
    dinleme = calisma / "dinleme" / "s12"
    cikti.mkdir(parents=True, exist_ok=True)
    dinleme.mkdir(parents=True, exist_ok=True)

    ses, sr = sf.read(str(durum.klasor(calisma, KIMLIK) / d.kaynak["dosya"]), dtype="float32", always_2d=True)
    kesit = cikti / "kaynak_kesit.wav"
    sf.write(str(kesit), ses[int(BAS * sr): int(SON * sr)], sr)
    satirlar = sozler.lrclib(d.sanatci, d.ad).satirlar
    soz = "[verse]\n" + "\n".join(m for t, m in satirlar if BAS <= t < SON and m.strip())
    temiz = bolumlu(satirlar, BAS, SON)
    (cikti / "soz.txt").write_text(soz, encoding="utf-8")
    (cikti / "soz_temiz.txt").write_text(temiz, encoding="utf-8")

    isler = [motor.Is(id=ad, gorev="cover", kaynak=str(kesit), cikti_klasor=str(cikti / ad), stil=d.analiz["stil"],
                      soz=soz, adim=a.cover.adim, tohum=a.cover.tohumlar[0], guc=a.cover.guc, bpm=d.analiz.get("bpm"),
                      ton=d.analiz.get("ton") or "", ek=ek)
             for ad, ek in VARYANTLAR.items()]
    isler.append(motor.Is(id=SOZ_TEMIZ, gorev="cover", kaynak=str(kesit), cikti_klasor=str(cikti / SOZ_TEMIZ),
                          stil=d.analiz["stil"], soz=temiz, adim=a.cover.adim, tohum=a.cover.tohumlar[0],
                          guc=a.cover.guc, bpm=d.analiz.get("bpm"), ton=d.analiz.get("ton") or ""))
    t = time.time()
    sonuclar = motor.calistir(a, isler, cikti / "_motor", zaman_asimi_sn=len(isler) * 20 * 60)
    ozet = {}
    for r in sonuclar:
        ozet[r.id] = {"basari": r.basari, "sure_sn": r.sure_sn, "vram_gb": r.vram_tepe_gb, "hata": r.hata}
        if r.basari:
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", r.cikti, "-b:a", "192k",
                            str(dinleme / f"{r.id}.mp3")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(kesit), "-b:a", "192k",
                    str(dinleme / "orijinal_kesit.mp3")], check=True)
    ozet["toplam_sn"] = round(time.time() - t)
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(ozet, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
