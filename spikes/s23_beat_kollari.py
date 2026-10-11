"""S23: beat kolları. S22 teşhisi (yüklenen 22 şarkı): cover'ın vurmalıları orijinalden döngüsel (+0,11; en çok +0,52),
orijinalin groove'unu zayıf izliyor (korelasyon 0,30), piyano baladlarına genel davul ekleniyor (vurmalı enerji ×1,5),
şarkılar birbirine orijinallerden çok benziyor (0,941 / 0,891). Scryne: "beatleri çok kötü ve aynıydı".

Varsayım: cover gücü 0,7 → adımların son %30'u kaynaksız (sessizlik bağlamı, "text2music"); vurmalı ayrıntı
(transient, hi-hat) o son adımlarda çıkıyor ve kaynaktan bağımsız uyduruluyor. Ayrıca miks/tını referansı yok.
Kollar (S20 C ile aynı şarkı, tohum 42, yeni bölüm yapısı + S20 betiminden stil):
  G85  güç 0,85          G100  güç 1,0
  R70  güç 0,7 + orijinal kayıt tını referansı      R85  güç 0,85 + tını referansı
Karşılaştırma: S20 C (güç 0,7, referanssız). Kapılar burada; beat ölçüleri:
  motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s22_beat.py calisma/dinleme/s20 calisma/dinleme/s23

  uv run --no-sync python spikes/s23_beat_kollari.py
"""

import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "spikes"))

from s20_yapi_betim import dinamik  # noqa: E402

from yanki import ayarlar, dosya, durum, kapilar, kilit, motor, uzak  # noqa: E402
from yanki.motor_isci import betim_stili  # noqa: E402

KOLLAR = {"G85": (0.85, False), "G100": (1.0, False), "R70": (0.7, True), "R85": (0.85, True)}


def main() -> int:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    s20 = json.loads((calisma / "dinleme" / "s20" / "sonuc.json").read_text(encoding="utf-8"))
    hedef = calisma / "dinleme" / "s23"
    isler, bilgi = [], {}
    for kimlik, b in s20["bilgi"].items():
        if not b.get("betim"):
            print(f"– {kimlik}: S20 betimi yok, atlandı")
            continue
        d = durum.oku(calisma, kimlik)
        k = durum.klasor(calisma, kimlik)
        kaynak = str(k / d.kaynak["dosya"])
        stil = betim_stili(b["betim"])
        bilgi[kimlik] = {"ad": b["ad"], "stil": stil, "soz": b["yeni_soz"]}
        for kol, (guc, referans) in KOLLAR.items():
            isler.append(motor.Is(id=f"{kimlik}|{kol}", gorev="cover", kaynak=kaynak,
                                  cikti_klasor=str(hedef / kimlik / kol), stil=stil, soz=b["yeni_soz"],
                                  adim=a.cover.adim, tohum=a.cover.tohumlar[0], guc=guc,
                                  referans=kaynak if referans else None, dil=d.analiz.get("dil", "en"),
                                  bpm=d.analiz.get("bpm"), ton=d.analiz.get("ton") or ""))
    sonuclar = uzak.calistir(a, isler, calisma / "_motor" / "s23", zaman_asimi_sn=3 * 3600)
    tablo = []
    for r in sonuclar:
        if r.id is None:
            print("işçi:", r.hata)
            continue
        kimlik, kol = r.id.split("|")
        satir = {"kimlik": kimlik, "kol": kol, "basari": r.basari, "hata": r.hata}
        if r.basari and r.cikti:
            d = durum.oku(calisma, kimlik)
            kaynak = durum.klasor(calisma, kimlik) / d.kaynak["dosya"]
            duzgun = Path(r.cikti).with_name(f"{kol}.flac")
            Path(r.cikti).replace(duzgun)
            try:
                kap = kapilar.degerlendir(duzgun, kaynak, bilgi[kimlik]["soz"], a.fpcalc, dil=d.analiz.get("dil", "en"))
            except Exception as e:  # noqa: BLE001
                kap = {"hata": str(e)}
            satir.update(dosya=str(duzgun.relative_to(hedef)), kapilar=kap, **dinamik(duzgun, kaynak))
        tablo.append(satir)
    dosya.json_yaz(hedef / "sonuc.json", {"bilgi": bilgi, "tablo": tablo})
    for x in tablo:
        k = x.get("kapilar") or {}
        print(x["kimlik"][:30], x["kol"], {n: (v.get("deger"), v.get("gecti")) for n, v in k.items()
                                          if isinstance(v, dict)}, x.get("hata") or "")
    return 0


if __name__ == "__main__":
    with kilit.tek_kosu(KOK / "calisma" / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        raise SystemExit(main())
