"""S21: yeni tarif (bölüm yapısı + şarkıya özel betim) balad dışı türlerde çalışıyor mu.

Scryne (2026-10-12): Spotify'a gidecek şarkılar tek türde olmayacak. Hat şimdiye kadar yalnız balad/pop'ta dinlendi;
keşif ve otomatik onay rap, EDM, Latin vb. türleri eliyor (`onay.DENENMEMIS`). Tür açılmadan önce: her türden tanınmış
bir şarkı, aynı tohum ve tarif, iki kol (A bugünkü üretim, N yeni tarif; isteğe bağlı N3 = N + shift 3). Bu sesler
yalnız deney: listeye ve yayına girmez. Kapılar ve dinamik ölçüleri S20 ile aynı.
Çıktı: calisma/dinleme/s21/.

  uv run --no-sync python spikes/s21_turler.py [--guc 0.85] [--referans]
  (--guc/--referans: üçüncü kol E = N + S23'ün kazanan beat ayarı)
"""

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "spikes"))

from s20_yapi_betim import dinamik, eski_soz  # noqa: E402

from yanki import ayarlar, dosya, durum, hazirlik, kapilar, kaynak, kilit, kunye, motor, sozler, uzak  # noqa: E402
from yanki.liste import Sarki  # noqa: E402

SARKILAR = [  # (sanatçı, ad, tür)
    ("Kendrick Lamar", "HUMBLE.", "rap"),
    ("Drake", "Hotline Bling", "melodik rap / R&B"),
    ("Avicii", "Wake Me Up", "EDM"),
    ("Luis Fonsi", "Despacito", "Latin (İspanyolca)"),
    ("The Weeknd", "Blinding Lights", "synth-pop"),
    ("Imagine Dragons", "Believer", "rock"),
]


def hazirla(a, s: Sarki, k: Path) -> dict:
    """Kaynak ses, söz (yeni ve eski etiketlerle), dil ve bugünkü stil (MusicBrainz sanatçı türleri). Önbellekli."""
    import json

    if (onbellek := k / "bilgi.json").exists():
        return json.loads(onbellek.read_text(encoding="utf-8"))
    k.mkdir(parents=True, exist_ok=True)
    soz = sozler.lrclib(s.sanatci, s.ad)
    (k / "soz.txt").write_text(soz.metin, encoding="utf-8")
    kyn = kaynak.hazirla(s.kimlik, s.sanatci, s.ad, soz.sure_sn, k / "_yok", k)
    d = durum.Durum(s.kimlik, s.sanatci, s.ad, kaynak={"dosya": kyn.wav.name, "sure_sn": kyn.sure_sn},
                    soz={"dosya": "soz.txt", "kaynak": "lrclib"})
    try:
        kun = kunye.bul(s.sanatci, s.ad).__dict__
    except Exception:  # noqa: BLE001
        kun = {}
    from yanki import katalog

    try:
        yedek = [] if kun.get("sanatci_turleri") else katalog.sanatci_turleri(s.sanatci)
    except Exception:  # noqa: BLE001
        yedek = []
    b = {"kaynak": str(kyn.wav), "yeni_soz": soz.metin, "eski_soz": eski_soz(s.sanatci, s.ad),
         "eski_stil": hazirlik.stil_kur(s, kunye=kun, yedek_turler=yedek), **hazirlik.dil_bul(d, k),
         "sure_sn": kyn.sure_sn}
    dosya.json_yaz(onbellek, b)
    return b


def main(e_guc: float | None, e_referans: bool) -> int:
    a = ayarlar.yukle()
    hedef = a.kok / "calisma" / "dinleme" / "s21"
    isler, bilgi = [], {}
    for sanatci, ad, tur in SARKILAR:
        s = Sarki(sanatci, ad)
        try:
            b = hazirla(a, s, a.kok / "calisma" / "_spike" / "s21" / s.kimlik)
        except Exception as e:  # noqa: BLE001 — bir şarkı düşerse diğerleri sürer
            print(f"✗ {sanatci} — {ad}: {type(e).__name__}: {e}")
            continue
        bilgi[s.kimlik] = {"ad": f"{sanatci} — {ad}", "tur": tur, **b}
        ortak = dict(kaynak=b["kaynak"], adim=a.cover.adim, tohum=a.cover.tohumlar[0], guc=a.cover.guc, dil=b["dil"])
        betim = f"{s.kimlik}|betim"
        isler += [motor.Is(id=betim, gorev="betimle", kaynak=b["kaynak"]),
                  motor.Is(id=f"{s.kimlik}|A", gorev="cover", cikti_klasor=str(hedef / s.kimlik / "A"),
                           stil=b["eski_stil"], soz=b["eski_soz"], **ortak),
                  motor.Is(id=f"{s.kimlik}|N", gorev="cover", cikti_klasor=str(hedef / s.kimlik / "N"),
                           stil_betimden=betim, soz=b["yeni_soz"], **ortak)]
        if e_guc is not None or e_referans:
            isler.append(motor.Is(id=f"{s.kimlik}|E", gorev="cover", cikti_klasor=str(hedef / s.kimlik / "E"),
                                  stil_betimden=betim, soz=b["yeni_soz"],
                                  referans=b["kaynak"] if e_referans else None,
                                  **{**ortak, "guc": e_guc if e_guc is not None else a.cover.guc}))
        print(f"✓ hazır: {sanatci} — {ad} (dil {b['dil']}, stil: {b['eski_stil']})")
    sonuclar = uzak.calistir(a, isler, a.kok / "calisma" / "_motor" / "s21", zaman_asimi_sn=3 * 3600)
    tablo = []
    for r in sonuclar:
        if r.id is None:
            print("işçi:", r.hata)
            continue
        kimlik, kol = r.id.split("|")
        if kol == "betim":
            bilgi[kimlik]["betim"] = (r.analiz or {}).get("betim")
            bilgi[kimlik]["betim_hata"] = r.hata
            continue
        satir = {"kimlik": kimlik, "kol": kol, "basari": r.basari, "hata": r.hata}
        if r.basari and r.cikti:
            b = bilgi[kimlik]
            cikti = Path(r.cikti)
            duzgun = cikti.with_name(f"{kol}.flac")
            cikti.replace(duzgun)
            soz = b["eski_soz" if kol == "A" else "yeni_soz"]
            try:
                kap = kapilar.degerlendir(duzgun, Path(b["kaynak"]), soz, a.fpcalc, dil=b["dil"])
            except Exception as e:  # noqa: BLE001
                kap = {"hata": str(e)}
            satir.update(dosya=str(duzgun.relative_to(hedef)), kapilar=kap, **dinamik(duzgun, Path(b["kaynak"])))
        tablo.append(satir)
    dosya.json_yaz(hedef / "sonuc.json", {"bilgi": bilgi, "tablo": tablo})
    s = ["# S21: yeni tarif balad dışı türlerde", "",
         "Aynı şarkı, aynı tohum. **A** bugünkü üretim · **N** yeni tarif (bölüm yapısı + şarkıya özel betim)"
         + (f" · **E** N + güç {e_guc if e_guc is not None else a.cover.guc}"
            + (" + tını referansı" if e_referans else "") if e_guc is not None or e_referans else "")
         + ". Yalnız deney: yayına girmez.", "",
         "| şarkı | tür | kol | söz WER | parmak izi | eğri | değişim | kapı |", "|---|---|---|---|---|---|---|---|"]
    for x in tablo:
        k = x.get("kapilar") or {}
        wer = (k.get("soz_wer") or {}).get("deger")
        pi = (k.get("parmak_izi") or {}).get("deger")
        gecti = all(v.get("gecti") for v in k.values()) if k and "hata" not in k else None
        b = bilgi[x["kimlik"]]
        s.append(f"| {b['ad']} | {b['tur']} | {x['kol']} | {wer if wer is not None else '—'} | "
                 f"{pi if pi is not None else '—'} | {x.get('egri_korelasyon', '—')} | {x.get('degisim_orani', '—')} | "
                 f"{'geçti' if gecti else 'düştü' if gecti is False else x.get('hata') or '—'} |")
    s += ["", "## Stiller", ""]
    for b in bilgi.values():
        s += [f"### {b['ad']} ({b['tur']}, dil {b['dil']})", "", f"- Eski: {b['eski_stil']}",
              f"- Betim: {b.get('betim') or b.get('betim_hata')}", ""]
    dosya.yaz(hedef / "OKU.md", "\n".join(s))
    print((hedef / "OKU.md").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    if "--yalniz-hazirla" in sys.argv:  # ağ işleri (kilitsiz, ücretsiz): kaynak ses, söz, stil
        a_ = ayarlar.yukle()
        for sanatci_, ad_, _ in SARKILAR:
            s_ = Sarki(sanatci_, ad_)
            try:
                b_ = hazirla(a_, s_, a_.kok / "calisma" / "_spike" / "s21" / s_.kimlik)
                print(f"✓ {sanatci_} — {ad_}: dil {b_['dil']} ({b_['dil_tespit']}), {b_['sure_sn']:.0f} sn, "
                      f"stil: {b_['eski_stil']}")
            except Exception as e:  # noqa: BLE001
                print(f"✗ {sanatci_} — {ad_}: {type(e).__name__}: {e}")
        raise SystemExit(0)
    with kilit.tek_kosu(KOK / "calisma" / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        guc = float(sys.argv[sys.argv.index("--guc") + 1]) if "--guc" in sys.argv else None
        raise SystemExit(main(guc, "--referans" in sys.argv))
