"""S33: örnekleme ayarları. Scryne (2026-10-14): model en iyi halinde değil, üretime geçmiyoruz. S31b'de ek eğitim
ep20'yi yenemedi, S32'de beat'i sonradan işlemek (ton eşleme, ayrı beat, complete) kör testte A'ya kaybetti (13/17).
Denenmemiş kaldıraç: ACE-Step'in örnekleyici ayarları. Üretim hep varsayılanla koştu (ode + euler, CFG 7, DCW kapalı).

Kollar (ep20 LoRA, üretim tarifi: güç 0,7, 100 adım, tohum 42, betimden stil; yalnız bir ayar değişir):
  A  varsayılan (taban; stil bu koşunun betiminden, diğer kollarla aynı metin)
  D  DCW açık (dalgacık uzayında düzeltme, CVPR 2026; XL-SFT'de varsayılan kapalı; "double", 0,05 / 0,02)
  H  heun örnekleyici (ikinci derece; adım başı iki model çağrısı)
  S  sde (stokastik çıkarım)
  G  CFG 10 (varsayılan 7)
İkinci tur (araştırma 2026-10-14: issue #1019 "SFT'de CFG 7 agresif beat, 2 daha iyi"; INFERENCE.md'de
"en iyi kalite" ADG ile):
  J  ADG (uyarlamalı ikili yönlendirme; xl-sft'de etkin)
  L  CFG 3
  K  cover gücü 0,5 (kaynağa daha az yaslanır, eşliği model daha çok kendisi kurar)
Aynı 17 şarkı (kör test seti). Betimler S32'nin (`_spike/s32/betim.json`), söz ve üst veri ep20 kör testinin işinden.

  uv run --no-sync python spikes/s33_ornekleme.py
"""

import dataclasses
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import ayarlar, dosya, kilit, kulak, motor, uzak  # noqa: E402
from yanki.motor_isci import betim_stili  # noqa: E402

CALISMA = KOK / "calisma"
DINLEME = CALISMA / "dinleme" / "s33"
EP20_IS = CALISMA / "dinleme" / "lora" / "20261012-1702" / "motor_is.json"
BETIM = CALISMA / "_spike" / "s32" / "betim.json"
EN_AZ_BAKIYE = 1.0  # yalnız bu deneme: ~1,5 $'lık tek pod, hesaptaki 2,42 $ ile açılsın

KOLLAR = {
    "A": {},
    "D": {"dcw_enabled": True, "dcw_mode": "double", "dcw_scaler": 0.05, "dcw_high_scaler": 0.02},
    "H": {"sampler_mode": "heun"},
    "S": {"infer_method": "sde"},
    "G": {"guidance_scale": 10.0},
    "J": {"use_adg": True},
    "L": {"guidance_scale": 3.0},
    "K": {"guc": 0.5},
}


def main(kollar: list[str]) -> int:
    a = ayarlar.yukle()
    a = dataclasses.replace(a, uzak=dataclasses.replace(a.uzak, en_az_bakiye=EN_AZ_BAKIYE))
    isler_ep20 = json.loads(EP20_IS.read_text(encoding="utf-8"))["isler"]
    tarif = {i["id"].split("|")[0]: i for i in isler_ep20 if i["gorev"] == "cover" and i["id"].endswith("|ep20")}
    betim = json.loads(BETIM.read_text(encoding="utf-8"))
    set_ = kulak.setler()["egitim-5"]
    isler = []
    for s in kulak.sarki_listesi(CALISMA, set_):
        t = tarif[s]
        kaynak = kulak.dosya_yolu(CALISMA, set_, s, "orijinal")
        stil = betim_stili(betim[s]) if s in betim else t["stil"]
        for kol in kollar:
            isler.append(motor.Is(id=f"{s}|{kol}", gorev="cover", kaynak=str(kaynak),
                                  cikti_klasor=str(DINLEME / s / kol), stil=stil, soz=t["soz"], adim=int(t["adim"]),
                                  tohum=int(t["tohum"]), dil=t["dil"], bpm=t["bpm"], ton=t["ton"] or "",
                                  guc=float(KOLLAR[kol].get("guc", t["guc"])),
                                  ek={k: v for k, v in KOLLAR[kol].items() if k != "guc"}))
    print(f"{len(isler)} iş ({len(isler) // len(kollar)} şarkı × {kollar})")
    sonuc = uzak.calistir(a, isler, CALISMA / "_motor" / "s33", zaman_asimi_sn=5 * 3600)
    yol = DINLEME / "sonuc.json"
    kayit = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}  # turlar aynı dosyada birikir
    for r in sonuc:
        if r.id is None:
            print("işçi:", r.hata)
            continue
        if r.basari and r.cikti:
            s, kol = r.id.split("|")
            duzgun = DINLEME / s / f"{kol}.flac"
            Path(r.cikti).replace(duzgun)
            r = dataclasses.replace(r, cikti=str(duzgun))
        kayit[r.id] = {"basari": r.basari, "hata": r.hata, "cikti": r.cikti, "stil": r.stil, "sure_sn": r.sure_sn}
    dosya.json_yaz(yol, kayit)
    basarili = sum(1 for r in sonuc if r.id and kayit[r.id]["basari"])
    print(f"{basarili}/{len(isler)} başarılı")
    for k, v in kayit.items():
        if k.split("|")[1] in kollar and not v["basari"]:
            print(f"  ✗ {k}: {str(v['hata'])[:200]}")
    return 0 if basarili else 1


if __name__ == "__main__":
    secilen = sys.argv[1:] or ["A", "D", "H", "S", "G"]
    if any(k not in KOLLAR for k in secilen):
        raise SystemExit(__doc__)
    with kilit.tek_kosu(CALISMA / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        raise SystemExit(main(secilen))
