"""Veto penceresi (otomatik onay): dinlemeye çıkan şarkı `sure_saat` içinde Scryne'dan karar almazsa öneri aday
onaylanır.

Hedef (Scryne, 2026-10-09): dağıtım API'si gelince hattın baştan sona kendiliğinden yürümesi; insan dinler ve isterse
veto eder (onaylar, onarım ister ya da reddeder: hepsi şarkıyı `uretildi`den çıkarır ve pencereyi kapatır).

Öneri kuralı: kapılardan geçmiş, bekleyen onarımı olmayan adaylardan en düşük söz WER'li (eşitlikte küçük numara).
Ölçüm (2026-10-09, Scryne'ın 15 şarkıdaki seçimi): en düşük söz WER seçimi 4/15 tuttu (%27; şarkı başı ~3,4 aday,
rastgele ~%29), parmak izi/dalga en iyi %47, tohum eşit dağılmış. Yani hiçbir ölçü kulağı tahmin etmiyor: otomatik onay
"Scryne'ın favorisi"ni değil "kapılardan geçmiş, sözü en anlaşılır" adayı seçer. Bu yüzden `config/yayin.toml` →
`[otomatik_onay]` varsayılan kapalı; dağıtım API'siyle birlikte açılır (Faz 10), seçim modeli Faz 12'de.
"""

import re
import tomllib
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from yanki import durum

# Kulaktan geçmeden yayına girebilecek şarkı (2026-10-10, Scryne her şeyi bıraktı; hedef: dinlenme ve sağlıklı profil):
# tarifi dinleme testiyle seçilmiş tür ve dil (piyano/akustik balad, pop, piyano rock; İngilizce) ve sözü anlaşılır
# aday. Rap, metal vb. ACE-Step'te hiç dinlenmedi; kötü bir cover atlanır, atlama profili algoritmada aşağı çeker ve
# Orvane'in tür kimliğini bulandırır. Bunlar Scryne'ın kulağına kalır (bildirilir).
DENENMEMIS = re.compile(r"\b(rap|hip[ -]?hop|trap|drill|metal|punk|grunge|hardcore|edm|techno|house|dubstep|trance|"
                        r"reggaeton|latin|salsa|country|jazz|blues|gospel|opera|k-?pop|afrobeats?)\b", re.I)


@dataclass(frozen=True)
class Ayar:
    acik: bool = False
    sure_saat: float = 72.0
    diller: tuple[str, ...] = ("en",)
    en_yuksek_wer: float = 0.15


def ayar_oku(yayin_yolu: Path) -> Ayar:
    with open(yayin_yolu, "rb") as f:
        d = tomllib.load(f).get("otomatik_onay", {})
    return Ayar(bool(d.get("acik", False)), float(d.get("sure_saat", 72)), tuple(d.get("diller", ["en"])),
                float(d.get("en_yuksek_wer", 0.15)))


def _wer(a: durum.Aday) -> float | None:
    return (a.kapilar.get("soz_wer") or {}).get("deger")


def engel(d: durum.Durum, ayar: Ayar) -> str | None:
    """Kendiliğinden onaylanamama nedeni (None: onaylanabilir). Engelli şarkı Scryne'ın kararını bekler."""
    stil = d.analiz.get("stil") or ""
    if m := DENENMEMIS.search(stil):
        return f"{m.group(1)}: bu türde tarif dinlenmedi"
    if (dil := d.analiz.get("dil", "en")) not in ayar.diller:
        return f"dil {dil}: bu dilde tarif dinlenmedi"
    a = oneri(d)
    if a is not None and ((w := _wer(a)) is None or w > ayar.en_yuksek_wer):
        return f"en iyi aday söz WER {w if w is not None else '?'} > {ayar.en_yuksek_wer} (söz anlaşılmıyor olabilir)"
    return None


def oneri(d: durum.Durum) -> durum.Aday | None:
    adaylar = [a for a in d.adaylar if a.gecti and a.dosya
               and not any(o.get("durum") == "bekliyor" for o in a.onarimlar)]
    if not adaylar:
        return None
    return min(adaylar, key=lambda a: (_wer(a) if _wer(a) is not None else float("inf"), a.no))


def dinlemeye_cikis(d: durum.Durum) -> datetime | None:
    """Şarkının son kez `uretildi`ye geçtiği an (onarım ya da yeniden üretim pencereyi baştan başlatır)."""
    for g in reversed(d.gecmis):
        if g.get("asama") == "uretildi":
            return datetime.fromisoformat(g["zaman"])
    return None


def onay_zamani(d: durum.Durum, ayar: Ayar) -> datetime | None:
    if not ayar.acik or d.asama != "uretildi" or (cikis := dinlemeye_cikis(d)) is None or engel(d, ayar):
        return None
    return cikis + timedelta(hours=ayar.sure_saat)


def uygula(calisma: Path, ayar: Ayar, simdi: datetime | None = None) -> list[tuple[durum.Durum, durum.Aday]]:
    """Süresi dolan şarkılarda öneriyi onaylar (gece koşusu, paketlemeden önce)."""
    simdi = simdi or datetime.now()
    onaylanan = []
    for d in durum.hepsi(calisma):
        zaman = onay_zamani(d, ayar)
        if zaman is None or zaman > simdi or oneri(d) is None:
            continue
        with durum.guncelle(calisma, d.kimlik) as taze:  # tam o anda Scryne karar verdiyse onunki geçerli
            zaman = onay_zamani(taze, ayar)
            if zaman is None or zaman > simdi or (a := oneri(taze)) is None:
                continue
            taze.secilen = a.no
            taze.notlar.append({"otomatik_onay": {"zaman": simdi.isoformat(timespec="seconds"), "aday": a.no,
                                                  "kural": "en düşük söz WER", "sure_saat": ayar.sure_saat}})
            taze.gec("onaylandi")
        onaylanan.append((taze, a))
    return onaylanan


def kulak_bekleyen(calisma: Path, ayar: Ayar) -> list[tuple[durum.Durum, str]]:
    """Dinlemede olup kendiliğinden onaylanamayacak şarkılar ve nedeni."""
    if not ayar.acik:
        return []
    return [(d, e) for d in durum.hepsi(calisma) if d.asama == "uretildi" and (e := engel(d, ayar))]


def yaklasan(calisma: Path, ayar: Ayar, saat: float = 24, simdi: datetime | None = None) -> list[durum.Durum]:
    simdi = simdi or datetime.now()
    return [d for d in durum.hepsi(calisma) if (z := onay_zamani(d, ayar)) and z <= simdi + timedelta(hours=saat)]
