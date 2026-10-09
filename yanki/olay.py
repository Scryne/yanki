"""Olaylar: hattın kendiliğinden fark ettiği, Scryne'ın bilmesi gereken şeyler (Roadmap Faz 13: bildirimler).

Parça yayına çıktı, arama sırası değişti, yayın tarihi geçtiği halde parça yok (dağıtımcı reddi ya da gecikme), takvimde
yükleme sırası geldi, gündüz üretimi bitti. Her olay `calisma/olaylar.jsonl`'a yazılır ve Windows bildirimi olarak
gösterilir (`scripts/bildir.ps1`, tıklayınca dinleme odası). `anahtar` verilen olay bir kez bildirilir: yayın tarihi
geçmiş bir parça her gece yeniden bildirilmesin.

Ortamda `YANKI_BILDIRIMSIZ=1` varsa yalnız kayıt (testler).
"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path

BETIK = Path(__file__).resolve().parents[1] / "scripts" / "bildir.ps1"
ODA = "http://127.0.0.1:8765/"


def yol(calisma: Path) -> Path:
    return calisma / "olaylar.jsonl"


def oku(calisma: Path, son: int | None = None) -> list[dict]:
    try:
        satirlar = yol(calisma).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    olaylar = []
    for s in satirlar[-son:] if son else satirlar:
        try:
            olaylar.append(json.loads(s))
        except ValueError:
            continue  # yarım satır (güç kesintisi): atla
    return olaylar


def bildirildi_mi(calisma: Path, anahtar: str) -> bool:
    return any(o.get("anahtar") == anahtar for o in oku(calisma))


def bildir(calisma: Path, tur: str, baslik: str, metin: str, anahtar: str | None = None,
           adres: str = ODA) -> bool:
    """Kaydeder ve bildirir; `anahtar` daha önce bildirildiyse hiçbir şey yapmaz (False)."""
    if anahtar and bildirildi_mi(calisma, anahtar):
        return False
    kayit = {"zaman": datetime.now().isoformat(timespec="seconds"), "tur": tur, "baslik": baslik, "metin": metin,
             "anahtar": anahtar}
    yol(calisma).parent.mkdir(parents=True, exist_ok=True)
    with open(yol(calisma), "a", encoding="utf-8") as f:
        f.write(json.dumps(kayit, ensure_ascii=False) + "\n")
    print(f"bildirim: {baslik} — {metin}")
    if not os.environ.get("YANKI_BILDIRIMSIZ") and BETIK.exists():
        try:  # bildirim en iyi çaba: gösterilemezse koşu sürer
            subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                            str(BETIK), "-Baslik", f"Yanki: {baslik}", "-Metin", metin, "-Adres", adres],
                           capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
    return True
