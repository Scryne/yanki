"""Dinleme sayfası sunucusu (yalnız 127.0.0.1): Scryne adayları dinler, onaylar, aralık işaretler, stili değiştirir,
reddeder; keşif adaylarını listeye ekler ya da eler; yüklenenlerin yayın durumunu görür.

Sunucu motoru çalıştırmaz ve Spotify'a istek atmaz (kota dar; ölçümleri gece koşusu yapar). Onarım ve yeniden üretim
istekleri durum.json'a, keşif kararları calisma/kesif/adaylar.json'a ve girdi/liste.toml'a yazılır.
"""

import json
from dataclasses import asdict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from yanki import durum, kesif, sozler, uretim
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


class StilIstegi(BaseModel):
    stil: str = Field(min_length=3, max_length=500)
    bpm: int | None = Field(default=None, ge=30, le=300)
    ton: str = Field(default="", max_length=20)


class RetIstegi(BaseModel):
    neden: str = ""


class EleIstegi(BaseModel):
    elendi: bool = True


def _kesif_ozet(a: kesif.Aday, listede: set[str]) -> dict:
    return {**asdict(a), "kimlik": a.kimlik, "puan": round(a.puan), "hal": kesif.hal(a),
            "listede": a.kimlik in listede}


def _kota(kok: Path) -> dict:
    """Spotify kota durumu, yalnız dosyadan (istek atmaz)."""
    import time

    from yanki import spotify

    sp = spotify.Spotify(kok)
    k = sp.kota()
    kalan = int(k.get("kilit", 0) - time.time())
    return {"bagli": bool(sp.client_id), "kilit_sn": max(0, kalan), "neden": k.get("neden") if kalan > 0 else None,
            "bugun": k.get("sayi", 0), "tavan": sp.gunluk_butce}


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


def uygulama(a: Ayarlar, calisma: Path, liste_yolu: Path | None = None) -> FastAPI:
    app = FastAPI(title="Yanki dinleme", docs_url=None, redoc_url=None)
    liste_yolu = liste_yolu or a.kok / "girdi" / "liste.toml"

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
        zaman = durum.klasor(calisma, kimlik) / "soz_zaman.json"
        satirlar = json.loads(zaman.read_text(encoding="utf-8")) if zaman.exists() else []
        return {**asdict(d), **_ozet(d), "kesitler": sozler.kesitler(satirlar, d.kaynak.get("sure_sn"))}

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

    @app.post("/api/sarki/{kimlik}/stil")
    def stil(kimlik: str, istek: StilIstegi):
        d = oku(kimlik)
        try:
            uretim.stil_degistir(d, istek.stil, istek.bpm, istek.ton.strip())
        except ValueError as e:
            raise HTTPException(409, str(e)) from e
        durum.yaz(calisma, d)
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/reddet")
    def reddet(kimlik: str, istek: RetIstegi):
        d = oku(kimlik)
        d.notlar.append({"ret": istek.neden})
        d.gec("reddedildi", istek.neden or None)
        durum.yaz(calisma, d)
        return _ozet(d)

    # ---- keşif ----
    @app.get("/api/kesif")
    def kesif_listesi():
        kayit = kesif.oku(calisma)
        listede = kesif.listedekiler(liste_yolu, calisma)
        return {"adaylar": [_kesif_ozet(x, listede) for x in kesif.sirala(kayit)], "kota": _kota(a.kok)}

    def kesif_adayi(kimlik: str) -> tuple[dict, kesif.Aday]:
        kayit = kesif.oku(calisma)
        if kimlik not in kayit:
            raise HTTPException(404, "keşif adayı bulunamadı")
        return kayit, kayit[kimlik]

    @app.post("/api/kesif/{kimlik}/ekle")
    def kesif_ekle(kimlik: str):
        from yanki import kilit

        kayit, x = kesif_adayi(kimlik)
        if kimlik in kesif.listedekiler(liste_yolu, calisma):
            raise HTTPException(409, "bu şarkı zaten listede")
        # liste.toml'a gece koşusu da yazıyor: aynı anda yazılmasın
        with kilit.tek_kosu(calisma / ".yanki.kilit") as alindi:
            if not alindi:
                raise HTTPException(409, "gece koşusu sürüyor; bitince tekrar dene")
            kesif.listeye_yaz([x], liste_yolu, "dinleme odasından eklendi")
            x.elendi = False
            kesif.kaydet(calisma, kayit)
        return _kesif_ozet(x, kesif.listedekiler(liste_yolu, calisma))

    @app.post("/api/kesif/{kimlik}/ele")
    def kesif_ele(kimlik: str, istek: EleIstegi):
        kayit, x = kesif_adayi(kimlik)
        x.elendi = istek.elendi
        kesif.kaydet(calisma, kayit)
        return _kesif_ozet(x, kesif.listedekiler(liste_yolu, calisma))

    # ---- yayın ----
    @app.get("/api/yayin")
    def yayin():
        from yanki import takip

        sarkilar = []
        for d in durum.hepsi(calisma):
            if d.asama not in ("yuklendi", "yayinda"):
                continue
            y = takip.yukleme_bilgisi(calisma, d.kimlik) or {}
            sarkilar.append({"kimlik": d.kimlik, "sanatci": d.sanatci, "ad": d.ad, "asama": d.asama,
                             "yayin_tarihi": y.get("yayin_tarihi"), "dagitimci": y.get("dagitimci"),
                             "isrc": y.get("isrc"), "son": (d.yayin or {}).get("son"),
                             "gecmis": (d.yayin or {}).get("gecmis", [])})
        sarkilar.sort(key=lambda s: s["yayin_tarihi"] or "")
        return {"sarkilar": sarkilar, "kota": _kota(a.kok), "profiller": sorted(takip.profil_kimlikleri(calisma))}

    app.mount("/", StaticFiles(directory=SAYFA, html=True), name="sayfa")
    return app
