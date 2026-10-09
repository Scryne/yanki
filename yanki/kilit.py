"""Süreçler arası kilitler (Windows: msvcrt.locking). İşletim sistemi dosya kilidi süreç ölünce kendiliğinden kalkar;
çökme sonrası bayat kilit kalmaz.

- `tek_kosu`: gece görevi ile elle başlatılan koşu aynı anda çalışmasın (alınamazsa hemen False).
- `bekleyerek`: kısa bir oku-değiştir-yaz bölümü (bir şarkının `durum.json`'u, keşif kaydı) için; kilit boşalana kadar
  bekler. Dinleme odası gece koşusu sürerken de karar yazabiliyor, ikisi aynı dosyayı aynı anda yazmasın.
"""

import contextlib
import msvcrt
import os
import time
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


class KilitMesgul(TimeoutError):
    pass


@contextlib.contextmanager
def bekleyerek(yol: Path, zaman_asimi_sn: float = 30.0, aralik_sn: float = 0.05) -> Iterator[None]:
    """Kilidi alana kadar bekler (en fazla `zaman_asimi_sn`, sonra `KilitMesgul`). Aynı süreçte iç içe alınmaz:
    Windows kilidi tutamaca bağlı, ikinci tutamaç kendi kilidini bekler."""
    yol.parent.mkdir(parents=True, exist_ok=True)
    bitis = time.monotonic() + zaman_asimi_sn
    with open(yol, "a+b") as f:
        while True:
            try:
                f.seek(0)
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
                break
            except OSError:
                if time.monotonic() >= bitis:
                    raise KilitMesgul(f"kilit {zaman_asimi_sn:.0f} sn boşalmadı: {yol}") from None
                time.sleep(aralik_sn)
        try:
            yield
        finally:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
