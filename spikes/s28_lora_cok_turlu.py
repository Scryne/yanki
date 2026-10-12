"""S28: çok türlü LoRA (2026-10-12 gecesi; 95 şarkı, betimli stil, bölüm etiketli söz, 40 epoch) cover'ı iyileştirir mi.

Eğitimin kendi denemesi pod elle silinince yarıda kaldı (LoRA indi). Aynı deneme üretim tarifiyle: S20'nin 6 şarkısı
(balad, orkestral rock, folk, dance-pop + rap, indie rock), betimden stil, yeni bölüm yapısı, tohum 42, güç 0,7;
LoRA ölçeği 0 (bugünkü üretim) / 0,5 / 1. Kapılar burada; beat ölçüleri:
  motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s22_beat.py calisma/dinleme/s28

  uv run --no-sync python spikes/s28_lora_cok_turlu.py <lora klasörü> [ad]
"""

import dataclasses
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "spikes"))

from s20_yapi_betim import dinamik  # noqa: E402

from yanki import ayarlar, dosya, durum, kapilar, kilit, motor, uzak  # noqa: E402

SARKILAR = ["bruno-mars-when-i-was-your-man", "coldplay-viva-la-vida", "passenger-let-her-go",
            "anise-k-walking-on-air", "the-fray-how-to-save-a-life", "christina-perri-jar-of-hearts"]
OLCEKLER = (0.0, 0.5, 1.0)


def main(lora: Path, ad: str) -> int:
    a = ayarlar.yukle()
    a = dataclasses.replace(a, motor=dataclasses.replace(a.motor, lora=lora.resolve(), lora_olcek=1.0))
    calisma = a.kok / "calisma"
    hedef = calisma / "dinleme" / ad
    isler, soz = [], {}
    for kimlik in SARKILAR:
        d = durum.oku(calisma, kimlik)
        k = durum.klasor(calisma, kimlik)
        kaynak = str(k / d.kaynak["dosya"])
        soz[kimlik] = (k / d.soz["dosya"]).read_text(encoding="utf-8")
        betim = f"{kimlik}|betim"
        isler.append(motor.Is(id=betim, gorev="betimle", kaynak=kaynak))
        for olcek in OLCEKLER:
            isler.append(motor.Is(id=f"{kimlik}|{olcek:g}", gorev="cover", kaynak=kaynak, stil_betimden=betim,
                                  cikti_klasor=str(hedef / kimlik / f"lora_{olcek:g}"), soz=soz[kimlik],
                                  adim=a.cover.adim, tohum=a.cover.tohumlar[0], guc=a.cover.guc, lora_olcek=olcek,
                                  dil=d.analiz.get("dil", "en"), bpm=d.analiz.get("bpm"),
                                  ton=d.analiz.get("ton") or ""))
    tablo = []
    for r in uzak.calistir(a, isler, calisma / "_motor" / ad, zaman_asimi_sn=2 * 3600):
        if r.id is None:
            print("işçi:", r.hata)
            continue
        kimlik, kol = r.id.split("|")
        if kol == "betim":
            continue
        satir = {"kimlik": kimlik, "olcek": float(kol), "basari": r.basari, "hata": r.hata, "hizalama": r.hizalama}
        if r.basari and r.cikti:
            d = durum.oku(calisma, kimlik)
            kaynak = durum.klasor(calisma, kimlik) / d.kaynak["dosya"]
            duzgun = Path(r.cikti).with_name(f"lora_{kol}.flac")
            Path(r.cikti).replace(duzgun)
            try:
                kap = kapilar.degerlendir(duzgun, kaynak, soz[kimlik], a.fpcalc, dil=d.analiz.get("dil", "en"),
                                          orijinal_wer=d.analiz.get("orijinal_wer"))
            except Exception as e:  # noqa: BLE001
                kap = {"hata": str(e)}
            satir.update(dosya=str(duzgun.relative_to(hedef)), kapilar=kap, **dinamik(duzgun, kaynak))
            print(kimlik[:30], kol, {n: (v.get("deger"), v.get("gecti")) for n, v in kap.items()
                                     if isinstance(v, dict)}, r.hizalama, flush=True)
        tablo.append(satir)
    dosya.json_yaz(hedef / "sonuc.json", {"lora": str(lora), "tablo": tablo})
    return 0


if __name__ == "__main__":
    with kilit.tek_kosu(KOK / "calisma" / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        raise SystemExit(main(Path(sys.argv[1]), sys.argv[2] if len(sys.argv) > 2 else "s28"))
