"""S13 (Faz 6): temiz söz (S12'nin kazananı, artık hatta) üstünde nefes ve mırıldanma için kollar.

S12 ile aynı kesit (Adele 0:40–1:25); taban = temiz söz + tarif + tohum 42 (S12 `8_soz_temiz`, Scryne: "çok az nefes
yerlerinde ve mırıldanmalarda kötü, onun dışında gayet güzel"). Her varyantta tek kol değişir. Çıktılar:
calisma/dinleme/s13/.

  uv run python spikes/s13_temiz_soz_kollari.py [--tohum-kontrol]
"""

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

import soundfile as sf

from yanki import ayarlar, durum, kapilar, motor, sozler

KIMLIK = "adele-someone-like-you"
BAS, SON = 40.0, 85.0
VOKAL_EK = ", clear close-miked lead vocal, crisp diction, no humming, no background vocals"
# ad: (tohum, güç, stil eki, ek GenerationParams)
VARYANTLAR = {
    "1_tohum7": (7, None, "", {}),
    "2_tohum123": (123, None, "", {}),
    "3_tohum2024": (2024, None, "", {}),
    "4_guc06": (42, 0.6, "", {}),
    "5_guc08": (42, 0.8, "", {}),
    "6_cfg5": (42, None, "", {"guidance_scale": 5.0}),
    "7_stil_net_vokal": (42, None, VOKAL_EK, {}),
    "8_stil_net_vokal_cfg5": (42, None, VOKAL_EK, {"guidance_scale": 5.0}),
}
# --tohum-kontrol: 7'nin kazancı tohum şansı mı (S13'te tohum tek başına WER'i 0,042–0,113 oynattı)
TOHUM_KONTROL = {
    "9_stil_net_vokal_tohum7": (7, None, VOKAL_EK, {}),
    "10_stil_net_vokal_tohum123": (123, None, VOKAL_EK, {}),
}


def mp3(girdi: str | Path, hedef: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(girdi), "-b:a", "192k", str(hedef)], check=True)


def main() -> None:
    varyantlar = TOHUM_KONTROL if "--tohum-kontrol" in sys.argv else VARYANTLAR
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    d = durum.oku(calisma, KIMLIK)
    cikti, dinleme = calisma / "_spike" / "s13", calisma / "dinleme" / "s13"
    cikti.mkdir(parents=True, exist_ok=True)
    dinleme.mkdir(parents=True, exist_ok=True)

    ses, sr = sf.read(str(durum.klasor(calisma, KIMLIK) / d.kaynak["dosya"]), dtype="float32", always_2d=True)
    kesit = cikti / "kaynak_kesit.wav"
    sf.write(str(kesit), ses[int(BAS * sr) : int(SON * sr)], sr)
    soz = sozler.aralik_sozu(sozler.lrclib(d.sanatci, d.ad).satirlar, BAS, SON)
    (cikti / "soz.txt").write_text(soz, encoding="utf-8")

    isler = [
        motor.Is(id=ad, gorev="cover", kaynak=str(kesit), cikti_klasor=str(cikti / ad), stil=d.analiz["stil"] + ek_stil,
                 soz=soz, adim=a.cover.adim, tohum=tohum, guc=guc or a.cover.guc, bpm=d.analiz.get("bpm"),
                 ton=d.analiz.get("ton") or "", ek=ek)
        for ad, (tohum, guc, ek_stil, ek) in varyantlar.items()
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
    # karşılaştırma için: taban (S12 kazananı) ve orijinal
    shutil.copy(calisma / "dinleme" / "s12" / "8_soz_temiz.mp3", dinleme / "0_taban_temiz_soz.mp3")
    mp3(kesit, dinleme / "orijinal_kesit.mp3")
    ad = "ozet_tohum.json" if varyantlar is TOHUM_KONTROL else "ozet.json"
    (cikti / ad).write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
