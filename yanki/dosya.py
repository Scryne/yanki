"""Atomik dosya yazımı: önce geçici dosya, sonra yerine koyma. Koşu yarıda kesilse de (güç, Ctrl+C, çökme) yarım
yazılmış bir JSON kalmaz; okuyan taraf eski ya da yeni sürümü görür."""

import json
from pathlib import Path


def yaz(yol: Path, metin: str) -> Path:
    yol.parent.mkdir(parents=True, exist_ok=True)
    gecici = yol.with_name(yol.name + ".tmp")
    gecici.write_text(metin, encoding="utf-8")
    gecici.replace(yol)
    return yol


def json_yaz(yol: Path, veri, indent: int | None = 2) -> Path:
    return yaz(yol, json.dumps(veri, ensure_ascii=False, indent=indent))
