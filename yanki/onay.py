"""Veto penceresi (otomatik onay): dinlemeye çıkan şarkı `sure_saat` içinde Scryne'dan karar almazsa öneri aday
onaylanır.

Hedef (Scryne, 2026-10-09): dağıtım API'si gelince hattın baştan sona kendiliğinden yürümesi; insan dinler ve isterse
veto eder (onaylar, onarım ister ya da reddeder: hepsi şarkıyı `uretildi`den çıkarır ve pencereyi kapatır).

Öneri kuralı: kapılardan geçmiş, bekleyen onarımı olmayan adaylardan söz WER'i en düşük iki aday arasından ACE-Step
söz hizalama puanı yüksek olan (puanı yoksa en düşük WER'li). 2026-10-12 (S27): 21 şarkıda 14 isabet.
Ölçüm (2026-10-09, Scryne'ın 15 şarkıdaki seçimi): en düşük söz WER seçimi 4/15 tuttu (%27; şarkı başı ~3,4 aday,
rastgele ~%29), parmak izi/dalga en iyi %47, tohum eşit dağılmış. Yani hiçbir ölçü kulağı tahmin etmiyor: otomatik onay
"Scryne'ın favorisi"ni değil "kapılardan geçmiş, sözü en anlaşılır" adayı seçer. Bu yüzden `config/yayin.toml` →
`[otomatik_onay]` varsayılan kapalı; dağıtım API'siyle birlikte açılır (Faz 10), seçim modeli Faz 12'de.
"""

import re
import tomllib
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from pathlib import Path

from yanki import durum, estetik

# Kulaktan geçmeden yayına girebilecek şarkı (2026-10-10, Scryne her şeyi bıraktı; hedef: dinlenme ve sağlıklı profil):
# tarifi dinleme testiyle seçilmiş tür ve dil (piyano/akustik balad, pop, piyano rock; İngilizce) ve sözü anlaşılır
# aday. Rap, metal vb. ACE-Step'te hiç dinlenmedi; kötü bir cover atlanır, atlama profili algoritmada aşağı çeker ve
# Orvane'in tür kimliğini bulandırır. Bunlar Scryne'ın kulağına kalır (bildirilir).
# Keşif de aynı kalıpla süzer (`kesif.Aday.uygun`), Deezer'ın tür adları ("Brazilian Music", "Electro", "Films/Games")
# dahil: hattın yapamadığı türdeki aday kendiliğinden listeye girmez, GPU ve kulak boşa gitmez (2026-10-10: üç rap
# şarkısının dokuz adayı da söz kapısında kaldı).
# Varsayılan; asıl liste config'te (yayin.toml [otomatik_onay] denenmemis_turler, kesif.toml [kesif] haric_turler):
# bir tür dinlenip tarifi doğrulandıkça listeden çıkar (Scryne, 2026-10-12: "şarkılar tek türde olmayacak").
DENENMEMIS_VARSAYILAN = (
    "rap", "hip[ -]?hop", "trap", "drill", "metal", "punk", "grunge", "hardcore", "edm", "techno", "house", "dubstep",
    "trance", "electro", "dance", "reggae", "reggaeton", "latin", "salsa", "mexicano", "brazilian", "sertanejo",
    "forr[oó]", "african", "afrobeats?", "asian", "indian", "bollywood", "country", "jazz", "blues", "gospel", "opera",
    "classical", "kids", "films", "games", "k-?pop", "j-?pop", "anime")


def tur_kalibi(turler) -> re.Pattern | None:
    """Tür adları (düzenli ifade parçaları) → kelime sınırlı kalıp; liste boşsa None (hiçbir tür engelli değil)."""
    turler = tuple(turler)
    return re.compile(r"\b(" + "|".join(turler) + r")\b", re.I) if turler else None


DENENMEMIS = tur_kalibi(DENENMEMIS_VARSAYILAN)


@dataclass(frozen=True)
class Ayar:
    acik: bool = False
    sure_saat: float = 72.0
    diller: tuple[str, ...] = ("en",)
    en_yuksek_wer: float = 0.15
    denenmemis_turler: tuple[str, ...] = DENENMEMIS_VARSAYILAN
    # öneriyi hangi kural verir: "kural" (söz WER'i + hizalama), "estetik" (yanki/estetik.py puanı) ya da "otomatik"
    # (estetik, Scryne'ın kulak seçimlerinde Faz 12 eşiğini ve kuralı geçince; `secici_coz`)
    secici: str = "kural"


SECICILER = ("kural", "estetik", "otomatik")
ESTETIK_EN_AZ = 10  # otomatik geçiş için estetik puanı olan en az bu kadar kulak seçimi


def ayar_oku(yayin_yolu: Path, calisma: Path | None = None) -> Ayar:
    """`calisma` verilirse "otomatik" seçici ölçüye göre "kural" ya da "estetik"e çözülür."""
    with open(yayin_yolu, "rb") as f:
        d = tomllib.load(f).get("otomatik_onay", {})
    secici = str(d.get("secici", "kural"))
    if secici not in SECICILER:
        raise ValueError(f"otomatik_onay.secici {', '.join(SECICILER)} olmalı: {secici}")
    ayar = Ayar(bool(d.get("acik", False)), float(d.get("sure_saat", 72)), tuple(d.get("diller", ["en"])),
                float(d.get("en_yuksek_wer", 0.15)),
                tuple(d.get("denenmemis_turler", DENENMEMIS_VARSAYILAN)), secici)
    return replace(ayar, secici=secici_coz(calisma, secici)) if calisma is not None else ayar


def secici_coz(calisma: Path, secici: str) -> str:
    """`otomatik`: estetik seçici en az `ESTETIK_EN_AZ` kulak seçiminde `ISABET_ESIGI`ni tutturup kuraldan iyiyse
    `estetik`, değilse `kural` (Faz 12: öneri Scryne'ı ≥ %70 tutarsa veto penceresinde varsayılan)."""
    if secici != "otomatik":
        return secici
    e = isabet(calisma)["estetik"]
    if e["sarki"] >= ESTETIK_EN_AZ and e["oran"] >= ISABET_ESIGI and e["isabet"] > e["kural_isabet"]:
        return "estetik"
    return "kural"


def _wer(a: durum.Aday) -> float | None:
    return (a.kapilar.get("soz_wer") or {}).get("deger")


def engel(d: durum.Durum, ayar: Ayar) -> str | None:
    """Kendiliğinden onaylanamama nedeni (None: onaylanabilir). Engelli şarkı Scryne'ın kararını bekler."""
    stil = d.analiz.get("stil") or ""
    if (kalip := tur_kalibi(ayar.denenmemis_turler)) and (m := kalip.search(stil)):
        return f"{m.group(1)}: bu türde tarif dinlenmedi"
    if (dil := d.analiz.get("dil", "en")) not in ayar.diller:
        return f"dil {dil}: bu dilde tarif dinlenmedi"
    a = oneri(d, ayar.secici)
    if a is not None and ((w := _wer(a)) is None or w > ayar.en_yuksek_wer):
        return f"en iyi aday söz WER {w if w is not None else '?'} > {ayar.en_yuksek_wer} (söz anlaşılmıyor olabilir)"
    return None


def _tarif_imzasi(a: durum.Aday) -> tuple:
    t = a.tarif or {}
    return (t.get("model"), t.get("lora"), tuple(sorted((t.get("ek") or {}).items())))


def oneri(d: durum.Durum, secici: str = "kural") -> durum.Aday | None:
    """`secici` "estetik": en yüksek estetik puanlı aday (adaylardan birinin puanı yoksa kural: eksik bilgiyle
    seçilmez); çözülmemiş "otomatik" kural sayılır."""
    adaylar = [a for a in d.adaylar if a.gecti and a.dosya
               and not any(o.get("durum") == "bekliyor" for o in a.onarimlar)]
    if not adaylar:
        return None
    # yeniden üretilen şarkıda yalnız en yeni tarifin adayları (2026-10-15: CFG 10 kör testte 9'a 3 kazandı; eski
    # adaylar dosyada kalıyor, söz WER'i düşük diye eski tarif seçilmesin). Dinleme odası da yalnız onları sıralıyor.
    if tarifli := [a for a in adaylar if a.tarif]:
        son = max(tarifli, key=lambda a: a.tarif.get("tarih") or "")
        adaylar = [a for a in tarifli if _tarif_imzasi(a) == _tarif_imzasi(son)]
    if secici == "estetik" and all(estetik.puan(a.estetik) is not None for a in adaylar):
        return max(adaylar, key=lambda a: (estetik.puan(a.estetik), -a.no))
    # Söz WER'i en düşük iki aday arasından ACE-Step söz hizalama puanı yüksek olan (S27, 2026-10-12: Scryne'ın 21
    # şarkıdaki seçimini 14 tuttu; yalnız WER 11, yalnız hizalama 9, rastgele 7,2). Puanı olmayan adayda yalnız WER.
    sirali = sorted(adaylar, key=lambda a: (_wer(a) if _wer(a) is not None else float("inf"), a.no))
    iki = sirali[:2]
    if len(iki) == 2 and all(_hizalama(a) is not None for a in iki):
        return max(iki, key=lambda a: (_hizalama(a), -sirali.index(a)))
    return sirali[0]


def _hizalama(a: durum.Aday) -> float | None:
    """Adayın DiT söz hizalama puanı (parçaların ortalaması); yoksa None."""
    degerler = [p["dit"] for p in (a.hizalama or []) if isinstance(p, dict) and p.get("dit") is not None]
    return sum(degerler) / len(degerler) if degerler else None


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
        if zaman is None or zaman > simdi or oneri(d, ayar.secici) is None:
            continue
        with durum.guncelle(calisma, d.kimlik) as taze:  # tam o anda Scryne karar verdiyse onunki geçerli
            zaman = onay_zamani(taze, ayar)
            if zaman is None or zaman > simdi or (a := oneri(taze, ayar.secici)) is None:
                continue
            taze.secilen = a.no
            kural = ("en yüksek estetik puanı" if ayar.secici == "estetik" and a.estetik
                     else "en düşük iki WER'den hizalaması yüksek")
            taze.notlar.append({"otomatik_onay": {"zaman": simdi.isoformat(timespec="seconds"), "aday": a.no,
                                                  "kural": kural,
                                                  "sure_saat": ayar.sure_saat}})
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


def _kulak_secimi(d: durum.Durum) -> durum.Aday | None:
    """Scryne'ın kulakla seçtiği aday; seçim yoksa, aday dosyada yoksa ya da son seçim otomatik onaysa None."""
    if d.secilen is None or d.asama in ("reddedildi",):
        return None
    secilen = next((a for a in d.adaylar if a.no == d.secilen), None)
    if secilen is None:
        return None
    oto = [n["otomatik_onay"] for n in d.notlar if isinstance(n, dict) and isinstance(n.get("otomatik_onay"), dict)]
    if oto and oto[-1].get("aday") == d.secilen:
        # otomatik onaydan sonra Scryne başka aday seçmediyse seçim kulağın değil (sonradan aynı adayı seçmesi ayırt
        # edilemez: ölçüme girmez)
        return None
    return secilen


def isabet(calisma: Path) -> dict:
    """Öneri kuralının (`oneri`) Scryne'ın kulak seçimlerini ne sıklıkla tuttuğu (Faz 12: ≥ %70 ise veto penceresinde
    varsayılan). Yeniden üretim seçimi sıfırladığı için seçim, şarkının bugünkü adaylarının hepsi dinlenirken yapıldı:
    kural da onları görür (otomatik onay o anda ne seçerdi). Karşılaştırma: yalnız en düşük söz WER'i (kapıdan geçmiş
    bütün adaylarda) ve rastgele seçimin beklenen isabeti. Ağa çıkmaz."""
    satirlar = []
    for d in durum.hepsi(calisma):
        if (secilen := _kulak_secimi(d)) is None:
            continue
        # dosyası temizlikte silinmiş aday da sayılır (`dosya` boşalır, kapı ölçüleri ve puan kalır): seçim o gün bütün
        # adaylar dinlenerek yapıldı (2026-10-18: yüklenmiş şarkılar temizlenince ölçüm 12 şarkıdan 0'a düşmüştü)
        gecen = [a for a in d.adaylar if a.gecti]
        if len(gecen) < 2 or secilen not in gecen:
            continue  # tek aday (seçim yok) ya da seçilen kapıdan geçmemiş: kuralın sınanacağı bir karar değil
        # bekleyen onarım seçimden sonra istenmiş olabilir: kural onarımsız hâli görür
        kopya = durum.Durum(d.kimlik, d.sanatci, d.ad, adaylar=[
            durum.Aday(**{**a.__dict__, "onarimlar": [], "dosya": a.dosya or "temizlendi"}) for a in gecen])
        kural = oneri(kopya)
        es = oneri(kopya, "estetik") if all(estetik.puan(a.estetik) is not None for a in gecen) else None
        wer_sirali = sorted(gecen, key=lambda a: (_wer(a) if _wer(a) is not None else float("inf"), a.no))
        satirlar.append({"kimlik": d.kimlik, "ad": d.ad, "aday_sayisi": len(gecen), "secilen": secilen.no,
                         "oneri": kural.no if kural else None, "en_dusuk_wer": wer_sirali[0].no,
                         "estetik": es.no if es else None, "stil": (d.analiz.get("stil") or "")[:80]})
    n = len(satirlar)
    tutan = sum(s["oneri"] == s["secilen"] for s in satirlar)
    puanli = [s for s in satirlar if s["estetik"] is not None]
    es_tutan = sum(s["estetik"] == s["secilen"] for s in puanli)
    return {"sarki": n, "isabet": tutan, "oran": tutan / n if n else None,
            "yalniz_wer": sum(s["en_dusuk_wer"] == s["secilen"] for s in satirlar),
            "rastgele": sum(1 / s["aday_sayisi"] for s in satirlar), "esik": ISABET_ESIGI, "satirlar": satirlar,
            # estetik seçici yalnız bütün adayları puanlı şarkılarda, aynı şarkılarda kuralla yan yana
            "estetik": {"sarki": len(puanli), "isabet": es_tutan, "oran": es_tutan / len(puanli) if puanli else 0.0,
                        "kural_isabet": sum(s["oneri"] == s["secilen"] for s in puanli),
                        "rastgele": sum(1 / s["aday_sayisi"] for s in puanli)}}


ISABET_ESIGI = 0.70  # Faz 12: öneri bu oranda Scryne'ı tutarsa veto penceresinde varsayılan olur
