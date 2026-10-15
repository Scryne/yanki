"""Atomik dosya yazımı: önce geçici dosya, sonra yerine koyma. Koşu yarıda kesilse de (güç, Ctrl+C, çökme) yarım
yazılmış bir JSON kalmaz; okuyan taraf eski ya da yeni sürümü görür.

Windows'ta hedef o an başka bir süreçte açıksa (dinleme odası `durum.json`'u okurken gece koşusu yazıyor) yerine koyma
`PermissionError` verir: kısa aralıklarla yeniden denenir. Geçici dosyanın adı süreç ve iş parçacığına özgü: iki yazar
aynı geçici dosyayı ezmesin.
"""

import json
import os
import threading
import time
from pathlib import Path

YERINE_KOYMA_DENEME = 40  # × 0,05 sn ≈ 2 sn: okuyucunun dosyayı bırakması için yeter


def yaz(yol: Path, metin: str) -> Path:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(f"{yol.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    # içerik diske inmeden yeniden adlandırma kalıcı olursa güç kesintisinde dosya boş kalabilir (NTFS)
    with open(gecici, "w", encoding="utf-8") as f:
        f.write(metin)
        f.flush()
        os.fsync(f.fileno())
    for i in range(YERINE_KOYMA_DENEME):
        try:
            gecici.replace(yol)
            return yol
        except PermissionError:
            if i == YERINE_KOYMA_DENEME - 1:
                gecici.unlink(missing_ok=True)
                raise
            time.sleep(0.05)
    raise AssertionError("ulaşılmaz")


def json_yaz(yol: Path, veri, indent: int | None = 2) -> Path:
    return yaz(yol, json.dumps(veri, ensure_ascii=False, indent=indent))
