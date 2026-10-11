"""S20: bölüm yapısı (yanki/yapi.py) ve şarkıya özel betim (ACE-Step captioner) cover'ı iyileştiriyor mu.

Scryne (2026-10-12): "beat kısmı çok kötü, sürekli aynı şeyler oluyor"; şarkılar tek türde olmayacak. Teşhis: modele
giden sözde bölüm etiketi yoktu (31 şarkının 19'unda nakarat yok), stil sanatçının genel türüydü ("pop, funk song"
piyano baladına). Aynı şarkı, aynı tohum (42), aynı tarif (XL-SFT bf16, cover, güç 0,7, 100 adım); kollar:

  A  bugünkü üretim: eski söz etiketleri + eski stil
  B  yeni bölüm yapısı + eski stil (yalnız yapının etkisi)
  C  yeni yapı + betimleyicinin şarkıya özel betimi
  D  C + shift 3 (ACE-Step SFT için önerilen; tarif 1,0)

Ölçüler: kapılar (söz WER, parmak izi), orijinalin ses yüksekliği eğrisini izleme (2 sn pencere, dB; korelasyon) ve
bölümler arası değişim (eğrinin standart sapması, orijinale oran: 1'den küçükse düzenleme orijinalden düz).
Çıktı: calisma/dinleme/s20/ (OKU.md, sonuc.json, <kimlik>/<kol>.flac).

  uv run --no-sync python spikes/s20_yapi_betim.py [kimlik ...]
"""

import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import soundfile as sf

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))

from yanki import ayarlar, dosya, durum, kapilar, kilit, motor, uzak  # noqa: E402

SARKILAR = ["bruno-mars-when-i-was-your-man", "coldplay-viva-la-vida", "passenger-let-her-go",
            "anise-k-walking-on-air", "the-fray-how-to-save-a-life", "christina-perri-jar-of-hearts"]
KOLLAR = ("A", "B", "C", "D")
ESKI_SOZLER = "3e77dd4"  # yapi.py'den önceki sozler.py
PENCERE_SN = 2.0


def eski_soz(sanatci: str, ad: str) -> str:
    """Eski etiketleyiciyle LRCLIB sözü (bugünkü üretimin modele verdiği metin)."""
    kod = subprocess.run(["git", "show", f"{ESKI_SOZLER}:yanki/sozler.py"], cwd=KOK, capture_output=True, text=True,
                         encoding="utf-8", check=True).stdout
    m = types.ModuleType("eski_sozler")
    exec(compile(kod, "eski_sozler", "exec"), m.__dict__)  # noqa: S102 — kendi deposundaki eski sürüm
    return m.lrclib(sanatci, ad).metin


def egri(yol: Path) -> np.ndarray:
    x, sr = sf.read(str(yol), dtype="float32", always_2d=True)
    m = x.mean(1)
    n = int(PENCERE_SN * sr)
    p = m[: len(m) // n * n].reshape(-1, n)
    return 10 * np.log10((p ** 2).mean(1) + 1e-10)


def dinamik(cikti: Path, kaynak: Path) -> dict:
    a, b = egri(cikti), egri(kaynak)
    n = min(len(a), len(b))
    a, b = a[:n], b[:n]
    ses = b > b.max() - 40  # orijinalde sessiz giriş/çıkış dışı
    return {"egri_korelasyon": round(float(np.corrcoef(a[ses], b[ses])[0, 1]), 3),
            "degisim_orani": round(float(a[ses].std() / max(b[ses].std(), 1e-6)), 3)}


def main(kimlikler: list[str]) -> int:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    hedef = calisma / "dinleme" / "s20"
    isler, bilgi = [], {}
    for kimlik in kimlikler:
        d = durum.oku(calisma, kimlik)
        k = durum.klasor(calisma, kimlik)
        kaynak = str(k / d.kaynak["dosya"])
        yeni = (k / d.soz["dosya"]).read_text(encoding="utf-8")
        eski = eski_soz(d.sanatci, d.ad)
        bilgi[kimlik] = {"ad": f"{d.sanatci} — {d.ad}", "eski_stil": d.analiz["stil"], "eski_soz": eski,
                         "yeni_soz": yeni}
        ortak = dict(kaynak=kaynak, adim=a.cover.adim, tohum=a.cover.tohumlar[0], guc=a.cover.guc,
                     dil=d.analiz.get("dil", "en"), bpm=d.analiz.get("bpm"), ton=d.analiz.get("ton") or "")
        betim = f"{kimlik}|betim"
        isler += [
            motor.Is(id=betim, gorev="betimle", kaynak=kaynak),
            motor.Is(id=f"{kimlik}|A", gorev="cover", cikti_klasor=str(hedef / kimlik / "A"), stil=d.analiz["stil"],
                     soz=eski, **ortak),
            motor.Is(id=f"{kimlik}|B", gorev="cover", cikti_klasor=str(hedef / kimlik / "B"), stil=d.analiz["stil"],
                     soz=yeni, **ortak),
            motor.Is(id=f"{kimlik}|C", gorev="cover", cikti_klasor=str(hedef / kimlik / "C"), stil_betimden=betim,
                     soz=yeni, **ortak),
            motor.Is(id=f"{kimlik}|D", gorev="cover", cikti_klasor=str(hedef / kimlik / "D"), stil_betimden=betim,
                     soz=yeni, ek={"shift": 3.0}, **ortak),
        ]
    sonuclar = uzak.calistir(a, isler, calisma / "_motor" / "s20", zaman_asimi_sn=3 * 3600)
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
            d = durum.oku(calisma, kimlik)
            k = durum.klasor(calisma, kimlik)
            cikti = Path(r.cikti)
            duzgun = cikti.with_name(f"{kol}.flac")
            cikti.replace(duzgun)
            soz = bilgi[kimlik]["eski_soz" if kol == "A" else "yeni_soz"]
            try:
                kap = kapilar.degerlendir(duzgun, k / d.kaynak["dosya"], soz, a.fpcalc, dil=d.analiz.get("dil", "en"))
            except Exception as e:  # noqa: BLE001
                kap = {"hata": str(e)}
            satir.update(dosya=str(duzgun.relative_to(hedef)), kapilar=kap,
                         **dinamik(duzgun, k / d.kaynak["dosya"]))
        tablo.append(satir)
    dosya.json_yaz(hedef / "sonuc.json", {"bilgi": bilgi, "tablo": tablo})
    yaz_oku(hedef, bilgi, tablo)
    print((hedef / "OKU.md").read_text(encoding="utf-8"))
    return 0


def yaz_oku(hedef: Path, bilgi: dict, tablo: list[dict]) -> None:
    s = ["# S20: bölüm yapısı ve şarkıya özel betim", "",
         "Aynı şarkı, aynı tohum, aynı tarif. **A** bugünkü üretim · **B** yeni bölüm yapısı · **C** yeni yapı + "
         "şarkıya özel betim · **D** C + shift 3. Dinle: hangisinde beat/eşlik orijinal gibi değişiyor (kıta sade, "
         "nakarat dolu), hangisi daha az tekdüze; vokal ve sözler net mi.", "",
         "Eğri: orijinalin ses yüksekliği inişlerini izleme (1 = birebir). Değişim: bölümler arası değişimin "
         "orijinale oranı (1'in altı: orijinalden düz).", "",
         "| şarkı | kol | söz WER | parmak izi | eğri | değişim | kapı |", "|---|---|---|---|---|---|---|"]
    for x in tablo:
        k = x.get("kapilar") or {}
        wer = (k.get("soz_wer") or {}).get("deger")
        pi = (k.get("parmak_izi") or {}).get("deger")
        gecti = all(v.get("gecti") for v in k.values()) if k and "hata" not in k else None
        s.append(f"| {bilgi[x['kimlik']]['ad']} | {x['kol']} | {wer if wer is not None else '—'} | "
                 f"{pi if pi is not None else '—'} | {x.get('egri_korelasyon', '—')} | {x.get('degisim_orani', '—')} | "
                 f"{'geçti' if gecti else 'düştü' if gecti is False else x.get('hata') or '—'} |")
    s += ["", "## Stiller", ""]
    for b in bilgi.values():
        s += [f"### {b['ad']}", "", f"- Eski: {b['eski_stil']}", f"- Betim: {b.get('betim') or b.get('betim_hata')}",
              ""]
    dosya.yaz(hedef / "OKU.md", "\n".join(s))


if __name__ == "__main__":
    # gece/gündüz koşusu açık kalmış pod sanıp bu deneyin pod'unu silmesin: hattın kilidi tutulur
    with kilit.tek_kosu(KOK / "calisma" / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        raise SystemExit(main(sys.argv[1:] or SARKILAR))
