"""Dinleme sayfası sunucusu (yalnız 127.0.0.1): Scryne adayları dinler, onaylar, aralık işaretler, reddeder.

Sunucu motoru çalıştırmaz; onarım isteği durum.json'a "bekliyor" diye yazılır, `yanki uret` onu işler.
"""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from yanki import durum, uretim
from yanki.ayarlar import Ayarlar

SAYFA = Path(__file__).with_name("sayfa")
DALGA_NOKTA = 1600


class OnarIstegi(BaseModel):
    aday: int
    bas: float = Field(ge=0)
    son: float = Field(gt=0)


class KabulIstegi(BaseModel):
    aday: int
    onarim: str


class OnayIstegi(BaseModel):
    aday: int


class RetIstegi(BaseModel):
    neden: str = ""


def _ozet(d: durum.Durum) -> dict:
    return {"kimlik": d.kimlik, "sanatci": d.sanatci, "ad": d.ad, "asama": d.asama, "hata": d.hata,
            "gecen_aday": sum(a.gecti for a in d.adaylar),
            "bekleyen_onarim": sum(o["durum"] == "bekliyor" for a in d.adaylar for o in a.onarimlar)}


def dalga(yol: Path, nokta: int = DALGA_NOKTA) -> dict:
    """Dalga formu tepe değerleri; dosyanın değişme zamanına göre önbelleklenir."""
    import soundfile as sf

    onbellek = yol.with_name(yol.name + ".dalga.json")
    if onbellek.exists() and onbellek.stat().st_mtime >= yol.stat().st_mtime:
        return json.loads(onbellek.read_text(encoding="utf-8"))
    ses, sr = sf.read(str(yol), dtype="float32", always_2d=True)
    m = np.abs(ses).max(axis=1)
    kova = max(1, len(m) // nokta)
    tepe = m[: kova * (len(m) // kova)].reshape(-1, kova).max(axis=1)
    tepe = tepe / (tepe.max() or 1.0)
    veri = {"sure": round(len(ses) / sr, 3), "tepe": [round(float(x), 3) for x in tepe]}
    onbellek.write_text(json.dumps(veri), encoding="utf-8")
    return veri


def uygulama(a: Ayarlar, calisma: Path) -> FastAPI:
    app = FastAPI(title="Yanki dinleme", docs_url=None, redoc_url=None)

    def oku(kimlik: str) -> durum.Durum:
        d = durum.oku(calisma, kimlik) if "/" not in kimlik and "\\" not in kimlik else None
        if d is None:
            raise HTTPException(404, "şarkı bulunamadı")
        return d

    def guvenli(kimlik: str, yol: str) -> Path:
        kok = durum.klasor(calisma, kimlik).resolve()
        hedef = (kok / yol).resolve()
        if not hedef.is_relative_to(kok) or not hedef.is_file():
            raise HTTPException(404, "dosya yok")
        return hedef

    @app.get("/api/sarkilar")
    def sarkilar():
        return [_ozet(d) for d in durum.hepsi(calisma)]

    @app.get("/api/sarki/{kimlik}")
    def sarki(kimlik: str):
        d = oku(kimlik)
        return {**asdict(d), **_ozet(d)}

    @app.get("/ses/{kimlik}/{yol:path}")
    def ses(kimlik: str, yol: str):
        return FileResponse(guvenli(kimlik, yol))

    @app.get("/api/dalga/{kimlik}/{yol:path}")
    def dalga_ucu(kimlik: str, yol: str):
        return dalga(guvenli(kimlik, yol))

    @app.post("/api/sarki/{kimlik}/onar")
    def onar(kimlik: str, istek: OnarIstegi):
        d = oku(kimlik)
        if d.asama not in ("uretildi", "onarim"):
            raise HTTPException(409, f"bu aşamada onarım istenemez: {d.asama}")
        if not any(x.no == istek.aday for x in d.adaylar):
            raise HTTPException(404, "aday yok")
        try:
            uretim.onarim_iste(a, d, istek.aday, istek.bas, istek.son)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        durum.yaz(calisma, d)
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/onarim-kabul")
    def onarim_kabul(kimlik: str, istek: KabulIstegi):
        d = oku(kimlik)
        try:
            uretim.onarim_kabul(d, istek.aday, istek.onarim)
        except (ValueError, StopIteration) as e:
            raise HTTPException(409, f"kabul edilemedi: {e}") from e
        durum.yaz(calisma, d)
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/onayla")
    def onayla(kimlik: str, istek: OnayIstegi):
        d = oku(kimlik)
        aday = next((x for x in d.adaylar if x.no == istek.aday), None)
        if aday is None or not aday.gecti:
            raise HTTPException(409, "yalnız kapılardan geçmiş bir aday onaylanabilir")
        if any(o["durum"] == "bekliyor" for o in aday.onarimlar):
            raise HTTPException(409, "bu adayın bekleyen onarımı var; önce üretilmesini bekle")
        d.secilen = istek.aday
        d.gec("onaylandi")
        durum.yaz(calisma, d)
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/reddet")
    def reddet(kimlik: str, istek: RetIstegi):
        d = oku(kimlik)
        d.notlar.append({"ret": istek.neden})
        d.gec("reddedildi", istek.neden or None)
        durum.yaz(calisma, d)
        return _ozet(d)

    app.mount("/", StaticFiles(directory=SAYFA, html=True), name="sayfa")
    return app
