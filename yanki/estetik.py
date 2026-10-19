"""Aday estetiği: dinlemeye çıkan adaylara hazır müzik değerlendiricilerinin puanı (Faz 12, aday seçimi).

Ölçü (2026-10-16, `yanki isabet`): öneri kuralı (söz WER'i + ACE-Step hizalaması) Scryne'ın kulak seçimini 12 şarkıda
3 tuttu (rastgele 2,1); veto penceresiyle kendiliğinden onaylanan şarkıda yayına giden aday şansa yakın. Kapı ölçüleri
(söz, beat, parmak izi) kulağı açıklamıyor. Burada eğitimsiz iki değerlendirici adayı dinler (`degerlendirici_isci.py`,
`docs/arastirma/10`): SongEval (tam şarkı, beş eksen) ve Audiobox Aesthetics. Puan `Aday.estetik`'e yazılır; dosya
temizlikte silinse de puan kalır, böylece seçici Scryne'ın sonraki seçimleriyle ölçülebilir (`onay.isabet`).

Değerlendirici kendi venv'inde (`araclar/degerlendirici/`, README'deki adım), varsayılan CPU'da (aday başı ~80 sn;
GPU oyun ya da üretimle paylaşılıyor), düşük öncelikle. Kurulu değilse adım atlanır.
"""

import json
import subprocess
import sys
from pathlib import Path

from yanki import dosya, durum

KLASOR = Path("araclar") / "degerlendirici"
SURUM = "songeval-1+audiobox-0.0.4"  # puanın hangi değerlendiricilerle alındığı (değişirse yeniden puanlanır)
ADAY_SN = 80  # CPU'da aday başı ölçülen süre (2026-10-18, 4 dk şarkı); zaman aşımı bundan
DINLEMEDE = ("uretildi", "onarim")


def python(kok: Path) -> Path:
    return kok / KLASOR / ".venv" / ("Scripts/python.exe" if sys.platform == "win32" else "bin/python")


def hazir(kok: Path) -> bool:
    return python(kok).is_file() and (kok / KLASOR / "SongEval" / "ckpt" / "model.safetensors").is_file()


def puan(e: dict | None) -> float | None:
    """Tek sayı: SongEval'in beş ekseninin ortalaması (1–5). Hangi birleşimin Scryne'ı en iyi tuttuğu
    `docs/arastirma/10`'da; puanı olmayan aday için None."""
    s = (e or {}).get("songeval")
    return round(sum(s.values()) / len(s), 4) if s else None


def bekleyenler(calisma: Path) -> list[tuple[durum.Durum, durum.Aday]]:
    """Dinlemedeki şarkıların puanı olmayan (ya da eski sürümle puanlanmış), kapıdan geçmiş adayları; en eski
    dinlemeye çıkan önce (veto penceresi önce onun dolar)."""
    sonuc = []
    for d in sorted((d for d in durum.hepsi(calisma) if d.asama in DINLEMEDE),
                    key=lambda d: next((g["zaman"] for g in reversed(d.gecmis) if g.get("asama") == "uretildi"), "")):
        k = durum.klasor(calisma, d.kimlik)
        sonuc += [(d, a) for a in d.adaylar if a.gecti and a.dosya and (k / a.dosya).is_file()
                  and (a.estetik or {}).get("surum") != SURUM]
    return sonuc


def puanla(kok: Path, calisma: Path, en_cok: int = 8, calistir=subprocess.run, bildir=print) -> int:
    """En çok `en_cok` adayı puanlar, puanları durumlara yazar; puanlanan aday sayısı."""
    hedef = bekleyenler(calisma)[:en_cok]
    if not hedef:
        return 0
    is_klasoru = calisma / ".estetik"
    girdi, cikti = is_klasoru / "girdi.json", is_klasoru / "sonuc.json"
    yollar = {str((durum.klasor(calisma, d.kimlik) / a.dosya).resolve()): (d.kimlik, a.no, a.dosya) for d, a in hedef}
    dosya.json_yaz(girdi, {"songeval": str((kok / KLASOR / "SongEval").resolve()), "dosyalar": list(yollar),
                           "cpu": True})
    cikti.unlink(missing_ok=True)
    try:
        r = calistir([str(python(kok)), "-I", str(Path(__file__).with_name("degerlendirici_isci.py")), str(girdi),
                      str(cikti)], capture_output=True, text=True, encoding="utf-8", errors="replace",
                     timeout=ADAY_SN * 3 * len(yollar) + 600, env={**_ortam(), "HF_HUB_DISABLE_SYMLINKS_WARNING": "1"},
                     creationflags=getattr(subprocess, "BELOW_NORMAL_PRIORITY_CLASS", 0))
        if r.returncode != 0:
            bildir(f"estetik: değerlendirici {r.returncode} koduyla bitti: {(r.stderr or '')[-400:]}")
    except subprocess.TimeoutExpired:
        bildir("estetik: değerlendirici zaman aşımına uğradı; biten adaylar yazılıyor")
    try:
        sonuclar = json.loads(cikti.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0
    yazilan = 0
    for yol, (kimlik, no, dosya_) in yollar.items():
        x = sonuclar.get(yol)
        if not x or "hata" in x:
            if x:
                bildir(f"estetik: {kimlik} aday {no}: {x['hata']}")
            continue
        with durum.guncelle(calisma, kimlik) as taze:
            a = next((y for y in taze.adaylar if y.no == no and y.dosya == dosya_), None)
            if a is None:  # o arada aday yeniden üretildi ya da silindi
                continue
            a.estetik = {"songeval": x["songeval"], "audiobox": x["audiobox"], "surum": SURUM}
            yazilan += 1
    return yazilan


def _ortam() -> dict:
    import os

    return {k: v for k, v in os.environ.items() if not k.startswith(("PYTHON", "VIRTUAL_ENV"))}
