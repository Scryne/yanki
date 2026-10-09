"""Dinleme sayfası sunucusu (yalnız 127.0.0.1): Scryne adayları dinler, onaylar, aralık işaretler, stili değiştirir,
reddeder; keşif adaylarını listeye ekler ya da eler; yüklenenlerin yayın durumunu görür.

Sunucu motoru çalıştırmaz ve Spotify'a istek atmaz (kota dar; ölçümleri gece koşusu yapar). Onarım ve yeniden üretim
istekleri durum.json'a, keşif kararları calisma/kesif/adaylar.json'a ve girdi/liste.toml'a yazılır.
"""

import contextlib
import json
import re
from dataclasses import asdict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from yanki import durum, kesif, kilit, olay, sozler, uretim
from yanki.ayarlar import Ayarlar

SAYFA = Path(__file__).with_name("sayfa")
DALGA_NOKTA = 1600
SES_UZANTILARI = (".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus")
DUZENLENEBILIR = ("uretildi", "onarim")  # onay, onarım ve onarım kabulü yalnız dinlemedeki şarkıda


def _kimlik_gecerli(kimlik: str) -> bool:
    """Şarkı kimliği `liste.kimlik` biçiminde (a-z, 0-9, tire): yol ayıracı ya da `..` taşıyamaz."""
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", kimlik))


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


def _takvim(kok: Path, calisma: Path) -> dict:
    """Yükleme sırası (yalnız durumdan hesaplanır, ağa çıkmaz)."""
    from yanki import dagitim, paket

    try:
        p = dagitim.plan(calisma, dagitim.takvim_oku(kok / "config" / "yayin.toml"),
                         dagitimci=paket.yayin_ayarlari(kok / "config" / "yayin.toml").dagitimci)
    except (OSError, ValueError, KeyError) as e:
        return {"hata": str(e), "sira": [], "beklemede": None, "duzeltme": []}
    return {"beklemede": p.beklemede, "duzeltme": p.duzeltme,
            "sira": [{"kimlik": x.kimlik, "sanatci": x.sanatci, "ad": x.ad, "yukleme": x.yukleme.isoformat(),
                      "yayin_tarihi": x.yayin_tarihi.isoformat(), "kesif": x.puan > 0} for x in p.sira]}


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
        d = durum.oku(calisma, kimlik) if _kimlik_gecerli(kimlik) else None
        if d is None:
            raise HTTPException(404, "şarkı bulunamadı")
        return d

    @contextlib.contextmanager
    def guncelle(kimlik: str):
        """Kararlar kilit altında taze duruma yazılır: gece koşusu aynı şarkıya yazarken birbirini ezmesinler."""
        oku(kimlik)
        try:
            with durum.guncelle(calisma, kimlik) as d:
                yield d
        except kilit.KilitMesgul as e:
            raise HTTPException(409, "şarkı şu an gece koşusunca güncelleniyor; birkaç saniye sonra tekrar dene") from e

    def guvenli(kimlik: str, yol: str) -> Path:
        """Yalnız bir şarkı klasörünün içindeki ses dosyaları. Kimlik doğrulanmazsa `%2E%2E` kimliği klasörü proje
        köküne çıkarıp `.env`'yi (Spotify sırları) verirdi."""
        if not _kimlik_gecerli(kimlik) or Path(yol).suffix.lower() not in SES_UZANTILARI:
            raise HTTPException(404, "dosya yok")
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
        from yanki import onay

        oto = onay.onay_zamani(d, onay.ayar_oku(a.kok / "config" / "yayin.toml"))
        oneri = onay.oneri(d) if oto else None
        return {**asdict(d), **_ozet(d), "kesitler": sozler.kesitler(satirlar, d.kaynak.get("sure_sn")),
                "otomatik_onay": {"zaman": oto.isoformat(timespec="minutes"), "aday": oneri.no}
                if oto and oneri else None}

    @app.get("/ses/{kimlik}/{yol:path}")
    def ses(kimlik: str, yol: str):
        return FileResponse(guvenli(kimlik, yol))

    @app.get("/api/dalga/{kimlik}/{yol:path}")
    def dalga_ucu(kimlik: str, yol: str):
        hedef = guvenli(kimlik, yol)
        try:
            return dalga(hedef)
        except (RuntimeError, ValueError) as e:  # bozuk/yarım ses dosyası (soundfile hatası RuntimeError türevi)
            raise HTTPException(422, f"ses okunamadı: {e}") from e

    @app.post("/api/sarki/{kimlik}/onar")
    def onar(kimlik: str, istek: OnarIstegi):
        with guncelle(kimlik) as d:
            if d.asama not in DUZENLENEBILIR:
                raise HTTPException(409, f"bu aşamada onarım istenemez: {d.asama}")
            if not any(x.no == istek.aday for x in d.adaylar):
                raise HTTPException(404, "aday yok")
            try:
                uretim.onarim_iste(a, d, istek.aday, istek.bas, istek.son)
            except ValueError as e:
                raise HTTPException(422, str(e)) from e
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/onarim-kabul")
    def onarim_kabul(kimlik: str, istek: KabulIstegi):
        with guncelle(kimlik) as d:
            if d.asama not in DUZENLENEBILIR:
                raise HTTPException(409, f"bu aşamada onarım kabul edilemez: {d.asama}")
            try:
                uretim.onarim_kabul(d, istek.aday, istek.onarim)
            except (ValueError, StopIteration) as e:
                raise HTTPException(409, f"kabul edilemedi: {e}") from e
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/onayla")
    def onayla(kimlik: str, istek: OnayIstegi):
        with guncelle(kimlik) as d:
            # yüklenmiş/paketlenmiş şarkı yeniden onaylanırsa paketi sessizce yeniden üretilirdi
            if d.asama not in DUZENLENEBILIR:
                raise HTTPException(409, f"bu aşamada onaylanamaz: {d.asama}")
            aday = next((x for x in d.adaylar if x.no == istek.aday), None)
            if aday is None or not aday.gecti or not aday.dosya:
                raise HTTPException(409, "yalnız kapılardan geçmiş bir aday onaylanabilir")
            if any(o["durum"] == "bekliyor" for o in aday.onarimlar):
                raise HTTPException(409, "bu adayın bekleyen onarımı var; önce üretilmesini bekle")
            d.secilen = istek.aday
            d.gec("onaylandi")
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/stil")
    def stil(kimlik: str, istek: StilIstegi):
        with guncelle(kimlik) as d:
            try:
                uretim.stil_degistir(d, istek.stil, istek.bpm, istek.ton.strip())
            except ValueError as e:
                raise HTTPException(409, str(e)) from e
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/reddet")
    def reddet(kimlik: str, istek: RetIstegi):
        with guncelle(kimlik) as d:
            if d.asama in ("yuklendi", "yayinda", "reddedildi"):
                raise HTTPException(409, f"bu aşamada reddedilemez: {d.asama}")
            d.notlar.append({"ret": istek.neden})
            d.gec("reddedildi", istek.neden or None)
        return _ozet(d)

    @app.post("/api/sarki/{kimlik}/geri-al")
    def geri_al(kimlik: str):
        """Reddi geri alır: şarkı reddedilmeden önceki aşamasına döner (yanlış tık, fikir değişikliği)."""
        with guncelle(kimlik) as d:
            if d.asama != "reddedildi":
                raise HTTPException(409, "yalnız reddedilmiş şarkı geri alınabilir")
            onceki = next((g["asama"] for g in reversed(d.gecmis[:-1]) if g.get("asama") != "reddedildi"), "yeni")
            d.notlar.append({"ret_geri_alindi": onceki})
            d.gec(onceki)
        return _ozet(d)

    # ---- keşif ----
    @app.get("/api/kesif")
    def kesif_listesi():
        kayit = kesif.oku(calisma)
        listede = kesif.listedekiler(liste_yolu, calisma)
        return {"adaylar": [_kesif_ozet(x, listede) for x in kesif.sirala(kayit)], "kota": _kota(a.kok)}

    def kesif_adayi(kayit: dict, kimlik: str) -> kesif.Aday:
        if kimlik not in kayit:
            raise HTTPException(404, "keşif adayı bulunamadı")
        return kayit[kimlik]

    @app.post("/api/kesif/{kimlik}/ekle")
    def kesif_ekle(kimlik: str):
        if kimlik in kesif.listedekiler(liste_yolu, calisma):
            raise HTTPException(409, "bu şarkı zaten listede")
        # liste.toml'a gece koşusu da yazıyor: aynı anda yazılmasın
        with kilit.tek_kosu(calisma / ".yanki.kilit") as alindi:
            if not alindi:
                raise HTTPException(409, "gece koşusu sürüyor; bitince tekrar dene")
            with kesif.kayit_kilidi(calisma):
                kayit = kesif.oku(calisma)
                x = kesif_adayi(kayit, kimlik)
                kesif.listeye_yaz([x], liste_yolu, "dinleme odasından eklendi")
                x.elendi = False
                kesif.kaydet(calisma, kayit)
        return _kesif_ozet(x, kesif.listedekiler(liste_yolu, calisma))

    @app.post("/api/kesif/{kimlik}/ele")
    def kesif_ele(kimlik: str, istek: EleIstegi):
        try:
            with kesif.kayit_kilidi(calisma):
                kayit = kesif.oku(calisma)
                x = kesif_adayi(kayit, kimlik)
                x.elendi = istek.elendi
                kesif.kaydet(calisma, kayit)
        except kilit.KilitMesgul as e:
            raise HTTPException(409, "keşif kaydı şu an güncelleniyor; tekrar dene") from e
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
        return {"sarkilar": sarkilar, "kota": _kota(a.kok), "profiller": sorted(takip.profil_kimlikleri(calisma)),
                "takvim": _takvim(a.kok, calisma), "olaylar": olay.oku(calisma, son=8)[::-1]}

    app.mount("/", StaticFiles(directory=SAYFA, html=True), name="sayfa")
    return app
