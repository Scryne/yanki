"""Disk temizliği: yüklenmiş şarkılarda artık dinlenmeyecek ara sesler.

Şarkı başı ~300–450 MB (aday tam sesleri, parçalar, onarım sürümleri); gece iki şarkıyla ayda ~24 GB (2026-10-09:
`calisma` 5,6 GB, disk 188 GB boş). Yalnız yüklenmiş (`yuklendi`/`yayinda`) ve yüklemesinin üstünden `gun` geçmiş
şarkılarda: seçilen adayın kullandığı dosyalar, paket, kaynak ses ve `durum.json` kalır; diğer adayların, kabul
edilmemiş onarımların ve parçaların sesleri silinir. Silinen adayın `dosya` alanı boşaltılır (kapı ölçüleri kalır),
dinleme odası onu "üretilmedi" gibi gösterir. Deney klasörleri (`_spike`, `dinleme`, `olcum`) dokunulmaz.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from yanki import durum

ARA_KLASORLER = ("adaylar", "onarimlar", "parcalar")


@dataclass
class Plan:
    kimlik: str
    dosyalar: list[Path] = field(default_factory=list)

    @property
    def bayt(self) -> int:
        return sum(f.stat().st_size for f in self.dosyalar if f.exists())


def yuklenme(d: durum.Durum) -> datetime | None:
    for g in d.gecmis:
        if g.get("asama") == "yuklendi":
            return datetime.fromisoformat(g["zaman"])
    return None


def plan(calisma: Path, d: durum.Durum, gun: int = 14, simdi: datetime | None = None) -> Plan | None:
    simdi = simdi or datetime.now()
    zaman = yuklenme(d)
    if d.asama not in ("yuklendi", "yayinda") or zaman is None or zaman > simdi - timedelta(days=gun):
        return None
    k = durum.klasor(calisma, d.kimlik)
    secilen = next((a for a in d.adaylar if a.no == d.secilen), None)
    koru: set[Path] = set()
    if secilen and secilen.dosya:
        koru |= {(k / secilen.dosya).resolve(), (k / (secilen.dosya + ".dalga.json")).resolve()}
    p = Plan(d.kimlik)
    for alt in ARA_KLASORLER:
        if (k / alt).exists():
            p.dosyalar += [f for f in sorted((k / alt).rglob("*")) if f.is_file() and f.resolve() not in koru]
    return p if p.dosyalar else None


def uygula(calisma: Path, d: durum.Durum, p: Plan) -> int:
    k = durum.klasor(calisma, d.kimlik)
    bayt = p.bayt
    silinen = {f.resolve() for f in p.dosyalar}
    for f in p.dosyalar:
        f.unlink(missing_ok=True)
    for a in d.adaylar:
        if a.dosya and (k / a.dosya).resolve() in silinen:
            a.dosya = ""
        for o in a.onarimlar:
            if o.get("dosya") and (k / o["dosya"]).resolve() in silinen:
                o["dosya"] = ""
    for alt in ARA_KLASORLER:  # boş kalan klasörler, en derinden üste (ara klasörün kendisi dahil)
        if not (k / alt).exists():
            continue
        for klasor in [*sorted((k / alt).rglob("*"), key=lambda x: -len(x.parts)), k / alt]:
            if klasor.is_dir() and not any(klasor.iterdir()):
                klasor.rmdir()
    d.notlar.append({"temizlik": {"zaman": datetime.now().isoformat(timespec="seconds"), "dosya": len(p.dosyalar),
                                  "mb": round(bayt / 1e6)}})
    durum.yaz(calisma, d)
    return bayt
