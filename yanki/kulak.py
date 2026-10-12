"""Kulak testi: deneme çıktılarının kör karşılaştırması (dinleme odası → Karşılaştırma).

Scryne (2026-10-12): "şarkı üretimini en iyi seviyeye çıkartmak" öncelik; ölçüler (söz WER, beat) kulağı her türde
tutmuyor (S30: rap ve Tagalogca ölçüde iyileşti, kulakta "bozuk"). Eğitim ve tarif kararları buradaki oylara dayanır.

Bir set, aynı şarkıların farklı kollarla (ör. LoRA'sız / LoRA'lı) aynı tohumla üretilmiş halleri. Kollar şarkıdan
şarkıya karışık sırayla A, B, C diye sunulur; hangisinin hangisi olduğu oy verilene kadar gösterilmez. Oylar
`calisma/dinleme/kulak.json`'a yazılır (kilitle; oda ve betikler aynı anda yazabilir).
"""

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from yanki import dosya, durum, kilit

OY_DOSYASI = "dinleme/kulak.json"
SECIMLER = ("fark_yok", "hepsi_kotu")  # kol adlarının yanında geçerli "en iyi" cevapları


@dataclass(frozen=True)
class Set:
    kimlik: str
    ad: str
    aciklama: str
    klasor: str  # calisma'ya göre
    kollar: dict  # kol → açık adı (oy verilince görünür)
    # şarkı → dosya: kol için `<klasor>/<şarkı>/<kalip>`; {kol} yerine kol adı
    kalip: str = "{kol}.flac"
    sarkilar: tuple = field(default=())  # boşsa klasördeki alt klasörler


SETLER = (
    Set("lora-tur", "Yeni model · 11 tür",
        "Her tür için tanınmış bir şarkı; eğitimde yok. Eski üretim tarifi ile kendi LoRA'mızla (cover görevinde "
        "eğitildi) üretilen aynı tohumlu kayıt.",
        "dinleme/s29", {"N": "eski model", "L": "yeni model (LoRA)"}, "{kol}/{kol}.flac"),
    Set("lora-balad", "Yeni model · balad ve pop",
        "Eğitimde olmayan 6 şarkı; LoRA ölçeği 0 (eski), 0,5 ve 1 (şu an üretimde).",
        "dinleme/lora/20261012-0808", {"lora_0": "eski model", "lora_0.5": "yeni model, yarım güç",
                                       "lora_1": "yeni model (üretimde)"}),
)


def setler() -> dict[str, Set]:
    return {s.kimlik: s for s in SETLER}


def _kaynak(calisma: Path, kimlik: str) -> Path | None:
    for yol in (calisma / "_spike" / "s29" / kimlik / "kaynak.wav", calisma / "_referans" / kimlik / "kaynak.wav",
                calisma / kimlik / "kaynak.wav"):
        if yol.is_file():
            return yol
    return None


def _bilgi(calisma: Path, s: Set, kimlik: str) -> dict:
    """Şarkının adı, sanatçısı, türü (setin kendi kaydından ya da durumdan)."""
    try:
        b = json.loads((calisma / s.klasor / "sonuc.json").read_text(encoding="utf-8"))["bilgi"][kimlik]
        sanatci, _, ad = b["ad"].partition(" — ")
        return {"sanatci": sanatci, "ad": ad or b["ad"], "tur": b.get("tur")}
    except (OSError, ValueError, KeyError):
        pass
    for kok in (calisma / "_referans", calisma):
        if d := durum.oku(kok, kimlik):
            return {"sanatci": d.sanatci, "ad": d.ad, "tur": None}
    return {"sanatci": "", "ad": kimlik, "tur": None}


def sira(set_kimlik: str, sarki: str, kollar) -> list[str]:
    """Kolların kör sırası: şarkıdan şarkıya değişir, aynı şarkıda hep aynı (sayfa yenilenince A yine A)."""
    return sorted(kollar, key=lambda k: hashlib.sha256(f"{set_kimlik}|{sarki}|{k}".encode()).hexdigest())


def dosya_yolu(calisma: Path, s: Set, sarki: str, kol: str) -> Path | None:
    """Kolun ses dosyası ya da `orijinal`; sette olmayan ad için None (yol dışarı çıkamaz)."""
    if kol == "orijinal":
        return _kaynak(calisma, sarki)
    if kol not in s.kollar or sarki not in sarki_listesi(calisma, s):
        return None
    yol = calisma / s.klasor / sarki / s.kalip.format(kol=kol)
    return yol if yol.is_file() else None


def sarki_listesi(calisma: Path, s: Set) -> list[str]:
    if s.sarkilar:
        return list(s.sarkilar)
    kok = calisma / s.klasor
    return sorted(p.name for p in kok.iterdir() if p.is_dir()) if kok.is_dir() else []


def oylar(calisma: Path) -> dict:
    try:
        return json.loads((calisma / OY_DOSYASI).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def oy_ver(calisma: Path, set_kimlik: str, sarki: str, en_iyi: str | None = None, yayinlanir: bool | None = None,
           notu: str | None = None) -> dict:
    """Bir şarkının oyunu günceller (verilen alanlar). `en_iyi`: kol adı, `fark_yok` ya da `hepsi_kotu`."""
    s = setler().get(set_kimlik)
    if s is None or sarki not in sarki_listesi(calisma, s):
        raise LookupError("sette böyle bir şarkı yok")
    if en_iyi is not None and en_iyi not in (*s.kollar, *SECIMLER):
        raise ValueError(f"geçersiz seçim: {en_iyi}")
    with kilit.bekleyerek(calisma / ".kulak.kilit"):
        hepsi = oylar(calisma)
        oy = hepsi.get(f"{set_kimlik}/{sarki}", {})
        if en_iyi is not None:
            oy["en_iyi"] = en_iyi
            if en_iyi in SECIMLER:
                oy.pop("yayinlanir", None)
        if yayinlanir is not None:
            oy["yayinlanir"] = yayinlanir
        if notu is not None:
            oy["not"] = notu.strip()[:500]
        oy["zaman"] = datetime.now().isoformat(timespec="seconds")
        hepsi[f"{set_kimlik}/{sarki}"] = oy
        dosya.json_yaz(calisma / OY_DOSYASI, hepsi)
    return oy


def gorunum(calisma: Path) -> list[dict]:
    """Dinleme odasına: setler, şarkılar, kör kollar (oy verilmişse açık adlarıyla) ve setin özeti."""
    tum = oylar(calisma)
    sonuc = []
    for s in SETLER:
        sarkilar, sayim = [], {k: 0 for k in (*s.kollar, *SECIMLER)}
        yayinlanir = 0
        for sarki in sarki_listesi(calisma, s):
            kollar = [k for k in sira(s.kimlik, sarki, s.kollar) if dosya_yolu(calisma, s, sarki, k)]
            if len(kollar) < 2:
                continue
            oy = tum.get(f"{s.kimlik}/{sarki}")
            if oy and oy.get("en_iyi") in sayim:
                sayim[oy["en_iyi"]] += 1
                yayinlanir += bool(oy.get("yayinlanir"))
            acik = bool(oy and oy.get("en_iyi"))  # kör: kolun adı yalnız oy verilince
            sarkilar.append({**_bilgi(calisma, s, sarki), "kimlik": sarki,
                             "orijinal": _kaynak(calisma, sarki) is not None,
                             "kollar": [{"kol": k, "harf": "ABCDEF"[i], "ad": s.kollar[k] if acik else None}
                                        for i, k in enumerate(kollar)],
                             "oy": oy})
        sonuc.append({"kimlik": s.kimlik, "ad": s.ad, "aciklama": s.aciklama, "sarkilar": sarkilar,
                      "ozet": {"oylanan": sum(1 for x in sarkilar if x["oy"] and x["oy"].get("en_iyi")),
                               "toplam": len(sarkilar), "sayim": sayim, "yayinlanir": yayinlanir,
                               "kollar": s.kollar}})
    return sonuc
