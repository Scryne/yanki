"""S29: kalan türler. Scryne (2026-10-12): "tüm modlara, şarkı türüne göre şarkı oluşturabilelim".

S21 rap, EDM, synth-pop, rock'ı açtı (yeni tarif kapılardan geçti; İspanyolca Latin düştü). Keşifte hâlâ kapalı
türlerden her birine tanınmış bir şarkı; kol N = üretim tarifi (bölüm yapısı + betim), isteğe bağlı L = N + LoRA.
Kapılar üretimdeki gibi (dalga 300 Hz üstü, söz WER'i orijinal kayda göre). Yalnız deney: yayına girmez.
Çıktı: calisma/dinleme/s29/.

  uv run --no-sync python spikes/s29_tum_turler.py [--yalniz-hazirla] [--lora <klasör> <ölçek>]
"""

import dataclasses
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "spikes"))

from s20_yapi_betim import dinamik  # noqa: E402
from s21_turler import hazirla  # noqa: E402

from yanki import ayarlar, dosya, kapilar, kilit, motor, uzak  # noqa: E402
from yanki.liste import Sarki  # noqa: E402

SARKILAR = [  # (sanatçı, ad, tür)
    ("Metallica", "Enter Sandman", "metal"),
    ("blink-182", "All the Small Things", "pop-punk"),
    ("Nirvana", "Smells Like Teen Spirit", "grunge"),
    ("Shania Twain", "You're Still the One", "country"),
    ("Frank Sinatra", "Fly Me to the Moon", "jazz"),
    ("B.B. King", "The Thrill Is Gone", "blues"),
    ("Bob Marley & The Wailers", "Three Little Birds", "reggae"),
    ("Daddy Yankee", "Gasolina", "reggaeton (İspanyolca)"),
    ("BLACKPINK", "How You Like That", "K-pop (Korece/İngilizce)"),
    ("Burna Boy", "Last Last", "afrobeats"),
    ("YOASOBI", "Idol", "J-pop (Japonca)"),
    ("Central Cee", "Doja", "UK drill"),
]
KLASOR = KOK / "calisma" / "_spike" / "s29"


def hazirlik_hepsi(a) -> dict:
    bilgi = {}
    for sanatci, ad, tur in SARKILAR:
        s = Sarki(sanatci, ad)
        k = KLASOR / s.kimlik
        try:
            b = hazirla(a, s, k)
        except Exception as e:  # noqa: BLE001
            print(f"✗ {sanatci} — {ad}: {type(e).__name__}: {e}", flush=True)
            continue
        if "orijinal_wer" not in b:  # göreli söz kapısı: orijinal kaydın WER'i (CPU Whisper)
            b["orijinal_wer"] = kapilar.orijinal_wer(Path(b["kaynak"]), b["yeni_soz"], b["dil"])
            dosya.json_yaz(k / "bilgi.json", b)
        bilgi[s.kimlik] = {"ad": f"{sanatci} — {ad}", "tur": tur, **b}
        print(f"✓ {sanatci} — {ad}: dil {b['dil']}, {b['sure_sn']:.0f} sn, orijinal WER {b['orijinal_wer']}",
              flush=True)
    return bilgi


def main(lora: Path | None, olcek: float) -> int:
    a = ayarlar.yukle()
    if lora:
        a = dataclasses.replace(a, motor=dataclasses.replace(a.motor, lora=lora.resolve(), lora_olcek=1.0))
    hedef = a.kok / "calisma" / "dinleme" / "s29"
    bilgi = hazirlik_hepsi(a)
    isler = []
    for kimlik, b in bilgi.items():
        ortak = dict(kaynak=b["kaynak"], adim=a.cover.adim, tohum=a.cover.tohumlar[0], guc=a.cover.guc, dil=b["dil"],
                     soz=b["yeni_soz"], stil_betimden=f"{kimlik}|betim")
        isler += [motor.Is(id=f"{kimlik}|betim", gorev="betimle", kaynak=b["kaynak"]),
                  motor.Is(id=f"{kimlik}|N", gorev="cover", cikti_klasor=str(hedef / kimlik / "N"),
                           lora_olcek=0.0 if lora else None, **ortak)]
        if lora:
            isler.append(motor.Is(id=f"{kimlik}|L", gorev="cover", cikti_klasor=str(hedef / kimlik / "L"),
                                  lora_olcek=olcek, **ortak))
    tablo = []
    for r in uzak.calistir(a, isler, a.kok / "calisma" / "_motor" / "s29", zaman_asimi_sn=3 * 3600):
        if r.id is None:
            print("işçi:", r.hata)
            continue
        kimlik, kol = r.id.split("|")
        if kol == "betim":
            bilgi[kimlik]["betim"] = (r.analiz or {}).get("betim")
            continue
        b = bilgi[kimlik]
        satir = {"kimlik": kimlik, "kol": kol, "basari": r.basari, "hata": r.hata, "hizalama": r.hizalama}
        if r.basari and r.cikti:
            duzgun = Path(r.cikti).with_name(f"{kol}.flac")
            Path(r.cikti).replace(duzgun)
            try:
                kap = kapilar.degerlendir(duzgun, Path(b["kaynak"]), b["yeni_soz"], a.fpcalc, dil=b["dil"],
                                          orijinal_wer=b.get("orijinal_wer"))
            except Exception as e:  # noqa: BLE001
                kap = {"hata": str(e)}
            satir.update(dosya=str(duzgun.relative_to(hedef)), kapilar=kap, **dinamik(duzgun, Path(b["kaynak"])))
        tablo.append(satir)
    dosya.json_yaz(hedef / "sonuc.json", {"bilgi": bilgi, "tablo": tablo})
    s = ["# S29: kalan türler (N üretim tarifi" + (f", L + LoRA {olcek:g}" if lora else "") + ")", "",
         "| şarkı | tür | kol | söz WER (eşik) | orijinal WER | parmak izi | dalga | eğri | kapı |",
         "|---|---|---|---|---|---|---|---|---|"]
    for x in tablo:
        k = x.get("kapilar") or {}
        b = bilgi[x["kimlik"]]
        w = k.get("soz_wer") or {}
        gecti = all(v.get("gecti") for v in k.values()) if k and "hata" not in k else None
        s.append(f"| {b['ad']} | {b['tur']} | {x['kol']} | {w.get('deger', '—')} ({w.get('esik', '—')}) | "
                 f"{b.get('orijinal_wer')} | {(k.get('parmak_izi') or {}).get('deger', '—')} | "
                 f"{(k.get('dalga') or {}).get('deger', '—')} | {x.get('egri_korelasyon', '—')} | "
                 f"{'geçti' if gecti else 'düştü' if gecti is False else x.get('hata') or '—'} |")
    s += ["", "## Betimler", ""] + [f"- **{b['ad']}**: {b.get('betim')}" for b in bilgi.values()]
    dosya.yaz(hedef / "OKU.md", "\n".join(s))
    print("\n".join(s[:len(tablo) + 4]))
    return 0


if __name__ == "__main__":
    if "--yalniz-hazirla" in sys.argv:
        hazirlik_hepsi(ayarlar.yukle())
        raise SystemExit(0)
    lora_ = Path(sys.argv[sys.argv.index("--lora") + 1]) if "--lora" in sys.argv else None
    olcek_ = float(sys.argv[sys.argv.index("--lora") + 2]) if lora_ else 1.0
    with kilit.tek_kosu(KOK / "calisma" / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        raise SystemExit(main(lora_, olcek_))
