"""Disk temizliği: artık dinlenmeyecek sesler.

Şarkı başı ~300–450 MB (aday tam sesleri, parçalar, onarım sürümleri); gece iki şarkıyla ayda ~24 GB. 2026-10-18'de
disk %95 doldu (`calisma` 72 GB); Scryne: "seçilen aday sadece kalır, reddedilen şarkılar da silinsin".

- Yüklenmiş (`yuklendi`/`yayinda`) şarkı, yüklemesinin üstünden `gun` geçince (varsayılan 0: ilk temizlikte): seçilen
  adayın kullandığı dosyalar, paket, kaynak ses ve `durum.json` kalır; diğer adayların, kabul edilmemiş onarımların ve
  parçaların sesleri silinir. Yüklemeden önce silinmez: veto penceresinde ve paketlenene kadar seçim değişebiliyor.
- Reddedilmiş şarkı: bütün sesleri (kaynak, adaylar, parçalar, paket) silinir; `durum.json`, sözler ve kapak kalır.
  Durum kalmalı: klasörü olan şarkı keşifte yeniden önerilmez ve listede olsa hazırlık onu yeniden indirmez.
- `_arsiv/<tarih>…/` (`uretim.bastan`'ın taşıdığı eski adaylar) tarihinden `arsiv_gun` gün sonra silinir.

Silinen adayın `dosya` alanı boşaltılır (kapı ölçüleri kalır), dinleme odası onu "üretilmedi" gibi gösterir. Deney
klasörleri (`_spike`, `dinleme`, `olcum`, `_referans`) dokunulmaz.
"""

import shutil
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from yanki import durum

ARA_KLASORLER = ("adaylar", "onarimlar", "parcalar")
RED_KLASORLER = (*ARA_KLASORLER, "paket", "paket_onceki")
SES_UZANTILARI = (".wav", ".flac", ".mp3")
YUKLENMIS = ("yuklendi", "yayinda")


@dataclass
class Plan:
    kimlik: str
    dosyalar: list[Path] = field(default_factory=list)

    @property
    def bayt(self) -> int:
        return sum(f.stat().st_size for f in self.dosyalar if f.exists())


def yuklenme(d: durum.Durum) -> datetime | None:
    """Son yükleme: geri çekilip yeniden yüklenen şarkıda süre yeni yüklemeden sayılır."""
    for g in reversed(d.gecmis):
        if g.get("asama") == "yuklendi":
            return datetime.fromisoformat(g["zaman"])
    return None


def _dosyalar(k: Path, klasorler: tuple[str, ...], koru: set[Path] = frozenset()) -> list[Path]:
    return [f for alt in klasorler if (k / alt).exists()
            for f in sorted((k / alt).rglob("*")) if f.is_file() and f.resolve() not in koru]


def plan(calisma: Path, d: durum.Durum, gun: int = 0, simdi: datetime | None = None) -> Plan | None:
    k = durum.klasor(calisma, d.kimlik)
    if d.asama == "reddedildi":
        p = Plan(d.kimlik, _dosyalar(k, RED_KLASORLER))
        dalga = tuple(u + ".dalga.json" for u in SES_UZANTILARI)
        p.dosyalar += [f for f in sorted(k.iterdir()) if f.is_file()
                       and (f.suffix.lower() in SES_UZANTILARI or f.name.lower().endswith(dalga))]
        return p if p.dosyalar else None
    simdi = simdi or datetime.now()
    zaman = yuklenme(d)
    if d.asama not in YUKLENMIS or zaman is None or zaman > simdi - timedelta(days=gun):
        return None
    secilen = next((a for a in d.adaylar if a.no == d.secilen), None)
    koru: set[Path] = set()
    if secilen and secilen.dosya:
        koru |= {(k / secilen.dosya).resolve(), (k / (secilen.dosya + ".dalga.json")).resolve()}
    p = Plan(d.kimlik, _dosyalar(k, ARA_KLASORLER, koru))
    return p if p.dosyalar else None


def uygula(calisma: Path, d: durum.Durum, p: Plan) -> int:
    k = durum.klasor(calisma, d.kimlik)
    with durum.guncelle(calisma, d.kimlik) as taze:
        ayni = taze.asama == "reddedildi" if d.asama == "reddedildi" else taze.asama in YUKLENMIS
        if not ayni or taze.secilen != d.secilen:
            return 0  # plan yapıldıktan sonra şarkı değişti (ret geri alındı, seçim değişti): silme
        bayt, silinen = 0, set()
        for f in p.dosyalar:
            # tek dosya silinemezse (Windows: dinleme odası o an çalıyor) diğerleri sürer; durum yine yazılır, silinen
            # dosyalar adaylardan düşer (önce hata durumu yazmadan çıkıyor, silinmiş dosyayı gösteren aday kalıyordu)
            try:
                boyut = f.stat().st_size if f.exists() else 0
                f.unlink(missing_ok=True)
            except OSError:
                continue
            bayt += boyut
            silinen.add(f.resolve())
        for a in taze.adaylar:
            if a.dosya and ((k / a.dosya).resolve() in silinen or not (k / a.dosya).exists()):
                a.dosya = ""
            for o in a.onarimlar:
                if o.get("dosya") and ((k / o["dosya"]).resolve() in silinen or not (k / o["dosya"]).exists()):
                    o["dosya"] = ""
        for alt in RED_KLASORLER:  # boş kalan klasörler, en derinden üste (ara klasörün kendisi dahil)
            if not (k / alt).exists():
                continue
            for klasor in [*sorted((k / alt).rglob("*"), key=lambda x: -len(x.parts)), k / alt]:
                if klasor.is_dir() and not any(klasor.iterdir()):
                    klasor.rmdir()
        taze.notlar.append({"temizlik": {"zaman": datetime.now().isoformat(timespec="seconds"),
                                         "dosya": len(silinen), "mb": round(bayt / 1e6)}})
    return bayt


def arsiv_plani(calisma: Path, gun: int = 7, simdi: datetime | None = None) -> list[Path]:
    """`_arsiv/` altında adı tarihle başlayan (`2026-10-12`, `2026-10-12-yayin-silindi`) ve `gun`den eski klasörler."""
    sinir = (simdi or datetime.now()).date() - timedelta(days=gun)
    sonuc = []
    for k in sorted((calisma / "_arsiv").glob("*")):
        try:
            tarih = date.fromisoformat(k.name[:10])
        except ValueError:
            continue
        if k.is_dir() and tarih <= sinir:
            sonuc.append(k)
    return sonuc


def boyut(klasor: Path) -> int:
    return sum(f.stat().st_size for f in klasor.rglob("*") if f.is_file())


def arsiv_sil(klasor: Path) -> int:
    """Silinen bayt; kilitli dosya (Windows) kalırsa geri kalanı silinir, kalan sonraki temizlikte."""
    once = boyut(klasor)
    shutil.rmtree(klasor, ignore_errors=True)
    return once - (boyut(klasor) if klasor.exists() else 0)
