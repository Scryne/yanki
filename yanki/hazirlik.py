"""Hazırlık: listedeki şarkı için kaynak ses, sözler, künye; sonra motorla stil/BPM/ton analizi.

Söz ya da kaynak yoksa şarkı `hata` aşamasında durur (neden yazılı). Künye yoksa uyarı: üretim sürer,
paketlemeden önce Scryne'dan istenir.
"""

import json
from dataclasses import asdict
from pathlib import Path

from yanki import ag, durum, kaynak, kunye, motor, sozler
from yanki.ayarlar import Ayarlar
from yanki.liste import VOKAL, Sarki

STIL_SONEKI = "clean modern studio recording"


def girdi_hazirla(a: Ayarlar, s: Sarki, calisma: Path, girdi: Path) -> durum.Durum:
    d = durum.oku(calisma, s.kimlik) or durum.Durum(s.kimlik, s.sanatci, s.ad)
    k = durum.klasor(calisma, s.kimlik)
    try:
        soz = sozler.bul(s.sanatci, s.ad, girdi / "sozler" / f"{s.kimlik}.txt")
    except (ag.Bulunamadi, OSError) as e:
        d.gec("hata", f"söz bulunamadı: {e}. `girdi/sozler/{s.kimlik}.txt` olarak bırakılabilir")
        durum.yaz(calisma, d)
        return d
    (k / "soz.txt").parent.mkdir(parents=True, exist_ok=True)
    (k / "soz.txt").write_text(soz.metin, encoding="utf-8")
    # parçalı üretim sözleri parçalara bu damgalarla dağıtır
    (k / "soz_zaman.json").write_text(json.dumps(soz.satirlar, ensure_ascii=False), encoding="utf-8")
    d.soz = {"kaynak": soz.kaynak, "sure_sn": soz.sure_sn, "dosya": "soz.txt"}

    try:
        kn = kunye.bul(s.sanatci, s.ad)
        d.kunye = asdict(kn)
    except (ag.Bulunamadi, OSError) as e:
        d.kunye = {"uyari": f"künye bulunamadı: {e}"}

    try:
        kyn = kaynak.hazirla(s.kimlik, s.sanatci, s.ad, soz.sure_sn, girdi / "kaynak", k, youtube=s.youtube)
    except (kaynak.KaynakYok, OSError) as e:
        d.gec("hata", f"kaynak ses: {e}. `girdi/kaynak/{s.kimlik}.mp3` olarak bırakılabilir")
        durum.yaz(calisma, d)
        return d
    d.kaynak = {"dosya": kyn.wav.name, "nereden": kyn.nereden, "baslik": kyn.baslik, "sure_sn": kyn.sure_sn}
    d.gec("hazir")
    durum.yaz(calisma, d)
    return d


def stil_kur(s: Sarki, lm_caption: str | None) -> str:
    """Scryne'ın stili esastır; yoksa LM tanımı + listedeki vokal cinsiyeti + temiz kayıt soneki."""
    if s.stil:
        return s.stil
    parcalar = [lm_caption.strip().rstrip(".")] if lm_caption else []
    if s.vokal:
        parcalar.append(f"{VOKAL[s.vokal]} lead vocal")
    parcalar.append(STIL_SONEKI)
    return ", ".join(p for p in parcalar if p)


def analiz_et(a: Ayarlar, sarkilar: list[Sarki], calisma: Path, zaman_asimi_sn: float = 1800) -> None:
    """`hazir` şarkıları tek motor çağrısıyla analiz eder (LM bir kez yüklenir)."""
    hedef = [(s, d) for s in sarkilar if (d := durum.oku(calisma, s.kimlik)) and d.asama == "hazir"]
    if not hedef:
        return
    isler = [motor.Is(id=s.kimlik, gorev="anla", kaynak=str(durum.klasor(calisma, s.kimlik) / d.kaynak["dosya"]))
             for s, d in hedef]
    sonuclar = {r.id: r for r in motor.calistir(a, isler, calisma / "_motor" / "analiz", zaman_asimi_sn)}
    for s, d in hedef:
        r = sonuclar[s.kimlik]
        lm = r.analiz if r.basari else {}
        d.analiz = {
            "stil": stil_kur(s, lm.get("caption")),
            "bpm": s.bpm or _tam(lm.get("bpm")),
            "ton": s.ton or (lm.get("keyscale") or ""),
            "dil": "en",
            "lm": lm,
            "lm_hata": None if r.basari else r.hata,
        }
        d.gec("analiz")
        durum.yaz(calisma, d)


def _tam(x) -> int | None:
    try:
        return round(float(x)) if x not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        return None
