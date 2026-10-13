"""S32: beat'i vokalden ayrı üretmek. Scryne (2026-10-14): vokal yeterli; beat ince, bas zayıf, enstrüman eksik,
ritim yanlış, hepsi aynı.
Bugün vokal ve eşlik tek geçişli cover'da birlikte çıkıyor; ek eğitim beat'i düzeltmedi (S31b).

Aynı 17 şarkı (kör test seti `egitim-5`), üretimdeki ep20 çıktısının vokali (Demucs, s32_beat_olcum.py) korunur:
- **E (enstrümantal cover):** orijinalin vokalsiz eşliği (Demucs davul + bas + diğer) üretim tarifiyle cover'lanır
  (xl-sft + ep20 LoRA, güç 0,7, `[Instrumental]`, stil betimden). Model kapasitesini vokale bölmez, aranjmanı
  orijinalin eşliğinden alır. Sonra ep20 vokaliyle karıştırılır (s32_karisim.py).
- **C (complete):** ep20 vokali kaynak, ACE-Step'in `complete` görevi (yalnız xl-base) üstüne eşlik kurar; stil aynı
  betimden. Orijinal kayıt hiç girmez; ritim ve armoni vokalden.
İki model iki pod demek: önce E (betimler de burada çıkar, `betim.json`'a yazılır), sonra C.

  uv run --no-sync python spikes/s32_ayri_beat.py E|C
"""

import dataclasses
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import ayarlar, dosya, kulak, motor, uzak  # noqa: E402
from yanki.motor_isci import betim_stili  # noqa: E402

CALISMA = KOK / "calisma"
KLASOR = CALISMA / "_spike" / "s32"
DINLEME = CALISMA / "dinleme" / "s32"
EP20_IS = CALISMA / "dinleme" / "lora" / "20261012-1702" / "motor_is.json"
EN_AZ_BAKIYE = 1.0  # yalnız bu deneme: iki kısa pod (~0,5 $ her biri), hesaptaki 3,21 $ ile ikincisi de açılsın


def tarifler() -> dict[str, dict]:
    """ep20 kör test çıktısının üretim tarifi (söz, dil, bpm, ton, güç, adım, tohum, yedek stil)."""
    isler = json.loads(EP20_IS.read_text(encoding="utf-8"))["isler"]
    return {i["id"].split("|")[0]: i for i in isler if i["gorev"] == "cover" and i["id"].endswith("|ep20")}


def enstrumantal(sarki: str) -> Path:
    hedef = KLASOR / sarki / "orijinal" / "enstrumantal.wav"
    if not hedef.exists():
        parcalar = [sf.read(str(KLASOR / sarki / "orijinal" / f"{p}.wav"), dtype="float32", always_2d=True)
                    for p in ("drums", "bass", "other")]
        sf.write(str(hedef), np.sum([x for x, _ in parcalar], axis=0), parcalar[0][1])
    return hedef


def ayar(model: str | None = None, lora_yok: bool = False):
    a = ayarlar.yukle()
    m = dataclasses.replace(a.motor, **({"model": model} if model else {}), **({"lora": None} if lora_yok else {}))
    return dataclasses.replace(a, motor=m, uzak=dataclasses.replace(a.uzak, en_az_bakiye=EN_AZ_BAKIYE))


def main(asama: str) -> int:
    set_ = kulak.setler()["egitim-5"]
    tarif = tarifler()
    sarkilar = [s for s in kulak.sarki_listesi(CALISMA, set_) if (KLASOR / s / "ep20" / "vocals.wav").exists()]
    print(f"{len(sarkilar)} şarkı, aşama {asama}")
    isler = []
    if asama == "E":
        a = ayar()
        for s in sarkilar:
            t = tarif[s]
            kaynak = kulak.dosya_yolu(CALISMA, set_, s, "orijinal")
            isler += [motor.Is(id=f"{s}|betim", gorev="betimle", kaynak=str(kaynak)),
                      motor.Is(id=f"{s}|E", gorev="cover", kaynak=str(enstrumantal(s)),
                               cikti_klasor=str(DINLEME / s / "E"), stil=t["stil"], soz="[Instrumental]",
                               adim=int(t["adim"]), tohum=int(t["tohum"]), guc=float(t["guc"]), dil=t["dil"],
                               bpm=t["bpm"], ton=t["ton"] or "", stil_betimden=f"{s}|betim",
                               ek={"instrumental": True})]
    else:
        a = ayar("acestep-v15-xl-base", lora_yok=True)
        betim = json.loads((KLASOR / "betim.json").read_text(encoding="utf-8"))
        for s in sarkilar:
            t = tarif[s]
            isler.append(motor.Is(id=f"{s}|C", gorev="complete", kaynak=str(KLASOR / s / "ep20" / "vocals.wav"),
                                  cikti_klasor=str(DINLEME / s / "C"), stil=betim_stili(betim.get(s) or t["stil"]),
                                  soz=t["soz"], adim=64, tohum=int(t["tohum"]), dil=t["dil"], bpm=t["bpm"],
                                  ton=t["ton"] or ""))
    sonuc = uzak.calistir(a, isler, CALISMA / "_motor" / f"s32{asama}", zaman_asimi_sn=3 * 3600)
    kayit = {r.id: {"basari": r.basari, "hata": r.hata, "cikti": r.cikti, "stil": r.stil, "sure_sn": r.sure_sn}
             for r in sonuc}
    if asama == "E":
        betim = {r.id.split("|")[0]: r.analiz["betim"] for r in sonuc
                 if r.id and r.id.endswith("|betim") and r.basari and r.analiz}
        dosya.json_yaz(KLASOR / "betim.json", betim)
    dosya.json_yaz(KLASOR / f"sonuc_{asama}.json", kayit)
    basarili = sum(1 for k, v in kayit.items() if v["basari"] and not k.endswith("|betim"))
    print(f"{basarili}/{len(sarkilar)} başarılı")
    for k, v in kayit.items():
        if not v["basari"]:
            print(f"  ✗ {k}: {str(v['hata'])[:200]}")
    return 0 if basarili else 1


if __name__ == "__main__":
    if len(sys.argv) != 2 or sys.argv[1] not in ("E", "C"):
        raise SystemExit(__doc__)
    raise SystemExit(main(sys.argv[1]))
