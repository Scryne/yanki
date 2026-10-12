"""S27: ACE-Step söz hizalama puanı Scryne'ın aday seçimini tutuyor mu (S24'ün devamı).

S24 (21 şarkı, 3 aday, Scryne kulakla seçti): söz WER 11/21 tuttu (rastgele 7,2), beat ölçüleri rastgele düzeyi.
ACE-Step kılavuzunun yazarının en sevdiği seçim ölçüsü "DiT Lyrics Alignment Score". Eski adaylar üretildikleri
koşullarla (kaynak, adayın stili, o günkü söz biçimi, tohum) işçide "puanla" göreviyle puanlanır; isabet ve seçilenin
sırası WER ile karşılaştırılır.

  uv run --no-sync python spikes/s27_hizalama_secim.py
"""

import sys
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(KOK))
sys.path.insert(0, str(KOK / "spikes"))

from s20_yapi_betim import eski_soz  # noqa: E402

from yanki import ayarlar, dosya, durum, kilit, motor, uzak  # noqa: E402


def main() -> int:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    isler, sarkilar = [], {}
    for d in durum.hepsi(calisma):
        adaylar = [x for x in d.adaylar if x.dosya and x.gecti]
        if not d.secilen or len(adaylar) < 2 or any("otomatik_onay" in n for n in d.notlar) \
                or d.asama not in ("yuklendi", "paketlendi"):
            continue
        k = durum.klasor(calisma, d.kimlik)
        try:
            soz = eski_soz(d.sanatci, d.ad) if d.soz.get("kaynak") == "lrclib" else (k / d.soz["dosya"]).read_text(
                encoding="utf-8")
        except Exception as e:  # noqa: BLE001
            print(f"– {d.kimlik}: eski söz kurulamadı ({e})")
            continue
        sarkilar[d.kimlik] = {"secilen": d.secilen, "wer": {x.no: (x.kapilar.get("soz_wer") or {}).get("deger")
                                                             for x in adaylar}}
        for x in adaylar:
            isler.append(motor.Is(id=f"{d.kimlik}|{x.no}", gorev="puanla", kaynak=str(k / d.kaynak["dosya"]),
                                  puanlanan=str(k / x.dosya), cikti_klasor=str(calisma / "_spike" / "s27" / d.kimlik),
                                  stil=x.stil or d.analiz["stil"], soz=soz, adim=a.cover.adim, tohum=x.tohum,
                                  guc=a.cover.guc, dil=d.analiz.get("dil", "en"), bpm=d.analiz.get("bpm"),
                                  ton=d.analiz.get("ton") or ""))
    print(f"{len(sarkilar)} şarkı, {len(isler)} aday puanlanacak", flush=True)
    for r in uzak.calistir(a, isler, calisma / "_motor" / "s27", zaman_asimi_sn=2 * 3600):
        if r.id is None:
            print("işçi:", r.hata)
            continue
        kimlik, no = r.id.split("|")
        sarkilar[kimlik].setdefault("hizalama", {})[int(no)] = r.hizalama if r.basari else {"hata": r.hata}
    dosya.json_yaz(calisma / "_spike" / "s27.json", sarkilar)
    rastgele = sum(1 / len(s["wer"]) for s in sarkilar.values())
    print(f"\n{len(sarkilar)} şarkı; rastgele isabet ≈ {rastgele:.1f}")
    for ad, anahtar, buyuk in (("dit", "dit", True), ("lm", "lm", True), ("soz_wer", None, False)):
        isabet, sira, n = 0, [], 0
        for s in sarkilar.values():
            h = s.get("hizalama", {})
            if anahtar:
                puan = {no: (h.get(no) or {}).get(anahtar) for no in s["wer"]}
            else:
                puan = dict(s["wer"])
            if any(v is None for v in puan.values()):
                continue
            n += 1
            dizi = sorted(puan, key=lambda no: puan[no], reverse=buyuk)
            isabet += dizi[0] == s["secilen"]
            sira.append(dizi.index(s["secilen"]) + 1)
        if sira:
            print(f"  {ad:8} isabet {isabet}/{n}  seçilenin ort. sırası {sum(sira) / len(sira):.2f}")
    return 0


if __name__ == "__main__":
    with kilit.tek_kosu(KOK / "calisma" / ".yanki.kilit") as alindi:
        if not alindi:
            print("başka bir yanki koşusu sürüyor; bitince tekrar dene")
            raise SystemExit(3)
        raise SystemExit(main())
