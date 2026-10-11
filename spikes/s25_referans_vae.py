"""S25: şarkılar arası aynılık (S22: cover'lar birbirine 0,95, orijinaller 0,83) ve prodüksiyon sesi.

S23: orijinal kaydı tını referansı vermek groove'u yükseltti ama kaydı sızdırdı (dalga kapısı düştü). Kollar (S20 C
tarifi: yeni bölüm yapısı + betim stili, güç 0,7, tohum 42; aynı 6 şarkı):
  X  tını referansı = aynı sanatçının BAŞKA bir şarkısı (Deezer en çok dinlenenlerinden, adı farklı olan ilki):
     prodüksiyon imzası o sanatçıya yaklaşır, cover'ı yapılan kayıt sızmaz
  V  ScragVAE çözücüsü (topluluk ince ayarı; tepe/transient ve yüksek frekans; ayrı işçi, ayrı pod)
Karşılaştırma: S20 C. Beat ölçüleri:
  motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s22_beat.py calisma/dinleme/s25

  uv run --no-sync python spikes/s25_referans_vae.py
"""

import dataclasses
import json
import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "spikes"))

from s20_yapi_betim import dinamik  # noqa: E402

from yanki import ayarlar, dosya, durum, kapilar, katalog, kaynak, kilit, motor, uzak  # noqa: E402
from yanki.kesif import _duz  # noqa: E402
from yanki.motor_isci import betim_stili  # noqa: E402


def baska_sarki(sanatci: str, ad: str, hedef: Path) -> tuple[Path, str] | None:
    """Sanatçının en çok dinlenen, adı bu şarkıdan farklı (sürümü değil) ilk parçası, indirilmiş."""
    if (bilgi := hedef / "referans.json").exists():
        b = json.loads(bilgi.read_text(encoding="utf-8"))
        return Path(b["wav"]), b["ad"]
    s = katalog.sanatci_bul(sanatci)
    if not s:
        return None
    for p in katalog.en_cok_dinlenenler(s, 10):
        if _duz(ad) in _duz(p.ad) or _duz(p.ad) in _duz(ad):
            continue
        hedef.mkdir(parents=True, exist_ok=True)
        try:
            k = kaynak.hazirla("ref", sanatci, p.ad, p.sure_sn, hedef / "_yok", hedef)
        except Exception as e:  # noqa: BLE001
            print(f"  {sanatci} — {p.ad}: indirilemedi ({e})")
            continue
        dosya.json_yaz(bilgi, {"wav": str(k.wav), "ad": p.ad})
        return k.wav, p.ad
    return None


def degerlendir(a, hedef: Path, sonuclar, bilgi, calisma) -> list[dict]:
    tablo = []
    for r in sonuclar:
        if r.id is None:
            print("işçi:", r.hata)
            continue
        kimlik, kol = r.id.split("|")
        satir = {"kimlik": kimlik, "kol": kol, "basari": r.basari, "hata": r.hata}
        if r.basari and r.cikti:
            d = durum.oku(calisma, kimlik)
            kaynak_ = durum.klasor(calisma, kimlik) / d.kaynak["dosya"]
            duzgun = Path(r.cikti).with_name(f"{kol}.flac")
            Path(r.cikti).replace(duzgun)
            try:
                kap = kapilar.degerlendir(duzgun, kaynak_, bilgi[kimlik]["soz"], a.fpcalc,
                                          dil=d.analiz.get("dil", "en"))
            except Exception as e:  # noqa: BLE001
                kap = {"hata": str(e)}
            satir.update(dosya=str(duzgun.relative_to(hedef)), kapilar=kap, **dinamik(duzgun, kaynak_))
            print(kimlik[:30], kol, {n: (v.get("deger"), v.get("gecti")) for n, v in kap.items()
                                     if isinstance(v, dict)})
        tablo.append(satir)
    return tablo


def main() -> int:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    s20 = json.loads((calisma / "dinleme" / "s20" / "sonuc.json").read_text(encoding="utf-8"))
    hedef = calisma / "dinleme" / "s25"
    x_isler, v_isler, bilgi = [], [], {}
    for kimlik, b in s20["bilgi"].items():
        d = durum.oku(calisma, kimlik)
        k = durum.klasor(calisma, kimlik)
        kaynak_ = str(k / d.kaynak["dosya"])
        stil = betim_stili(b["betim"])
        bilgi[kimlik] = {"ad": b["ad"], "stil": stil, "soz": b["yeni_soz"]}
        ortak = dict(kaynak=kaynak_, stil=stil, soz=b["yeni_soz"], adim=a.cover.adim, tohum=a.cover.tohumlar[0],
                     guc=a.cover.guc, dil=d.analiz.get("dil", "en"), bpm=d.analiz.get("bpm"),
                     ton=d.analiz.get("ton") or "")
        ref = baska_sarki(d.sanatci, d.ad, calisma / "_spike" / "s25" / kimlik)
        if ref:
            bilgi[kimlik]["referans"] = ref[1]
            x_isler.append(motor.Is(id=f"{kimlik}|X", gorev="cover", cikti_klasor=str(hedef / kimlik / "X"),
                                    referans=str(ref[0]), **ortak))
            print(f"✓ {b['ad']}: referans {ref[1]}")
        else:
            print(f"– {b['ad']}: sanatçının başka şarkısı bulunamadı")
        v_isler.append(motor.Is(id=f"{kimlik}|V", gorev="cover", cikti_klasor=str(hedef / kimlik / "V"), **ortak))
    tablo = degerlendir(a, hedef, uzak.calistir(a, x_isler, calisma / "_motor" / "s25x", zaman_asimi_sn=2 * 3600),
                        bilgi, calisma)
    av = dataclasses.replace(a, motor=dataclasses.replace(a.motor, vae="scragvae"))
    tablo += degerlendir(av, hedef, uzak.calistir(av, v_isler, calisma / "_motor" / "s25v", zaman_asimi_sn=2 * 3600),
                         bilgi, calisma)
    dosya.json_yaz(hedef / "sonuc.json", {"bilgi": bilgi, "tablo": tablo})
    return 0


if __name__ == "__main__":
    with kilit.tek_kosu(KOK / "calisma" / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        raise SystemExit(main())
