"""Proje yolları ve `config/motor.toml`."""

import tomllib
from dataclasses import dataclass
from pathlib import Path

KOK = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Motor:
    klasor: Path
    model: str
    niceleme: str | None
    cpu_offload: bool

    @property
    def python(self) -> Path:
        return self.klasor / ".venv" / "Scripts" / "python.exe"

    @property
    def checkpoints(self) -> Path:
        return self.klasor / "checkpoints"


@dataclass(frozen=True)
class Cover:
    gorev: str
    guc: float
    adim: int
    aday_sayisi: int
    tohumlar: tuple[int, ...]


@dataclass(frozen=True)
class Onarim:
    gorev: str
    adim: int
    pay_sn: float


@dataclass(frozen=True)
class Gpu:
    bos_esik_mib: int
    bekleme_sn: int


@dataclass(frozen=True)
class Ayarlar:
    kok: Path
    motor: Motor
    cover: Cover
    onarim: Onarim
    gpu: Gpu
    fpcalc: Path


def yukle(yol: Path | None = None, kok: Path = KOK) -> Ayarlar:
    yol = yol or kok / "config" / "motor.toml"
    with open(yol, "rb") as f:
        d = tomllib.load(f)
    m, c, o, g = d["motor"], d["cover"], d["onarim"], d["gpu"]
    if len(c["tohumlar"]) < c["aday_sayisi"]:
        raise ValueError(f"cover.tohumlar ({len(c['tohumlar'])}) aday_sayisi ({c['aday_sayisi']}) kadar olmalı")
    if not 0.0 < c["guc"] <= 1.0:
        raise ValueError(f"cover.guc 0 ile 1 arasında olmalı: {c['guc']}")
    return Ayarlar(
        kok=kok,
        motor=Motor(kok / m["klasor"], m["model"], m.get("niceleme") or None, bool(m["cpu_offload"])),
        cover=Cover(c["gorev"], float(c["guc"]), int(c["adim"]), int(c["aday_sayisi"]), tuple(c["tohumlar"])),
        onarim=Onarim(o["gorev"], int(o["adim"]), float(o["pay_sn"])),
        gpu=Gpu(int(g["bos_esik_mib"]), int(g["bekleme_sn"])),
        fpcalc=kok / d["araclar"]["fpcalc"],
    )
