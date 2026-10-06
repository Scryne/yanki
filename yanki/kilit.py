"""Tek koşu kilidi: gece görevi ile elle başlatılan koşu aynı dosyalara yazmasın.

İşletim sistemi dosya kilidi (Windows: msvcrt.locking) süreç ölünce kendiliğinden kalkar;
çökme sonrası bayat kilit kalmaz.
"""

import contextlib
import msvcrt
import os
from collections.abc import Iterator
from pathlib import Path


@contextlib.contextmanager
def tek_kosu(yol: Path) -> Iterator[bool]:
    yol.parent.mkdir(parents=True, exist_ok=True)
    f = open(yol, "a+b")  # noqa: SIM115 — kilit süresince açık kalmalı
    try:
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            yield False
            return
        f.truncate(0)
        f.write(str(os.getpid()).encode())
        f.flush()
        try:
            yield True
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
    finally:
        f.close()
