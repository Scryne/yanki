"""Dinleme sayfası sunucusu (yalnız 127.0.0.1): Scryne adayları dinler, onaylar, aralık işaretler, stili değiştirir,
reddeder; keşif adaylarını listeye ekler ya da eler; yüklenenlerin yayın durumunu, hattın panosunu, kapakları ve
Tunearo kazancını görür.

Sunucu motoru çalıştırmaz ve Spotify'a istek atmaz (kota dar; ölçümleri gece koşusu yapar). Dışarıya yalnız iki
istek: kazanç (Tunearo, 6 saat önbellekli) ve Scryne "başka kapak" deyince Pinterest. Onarım ve yeniden üretim
istekleri durum.json'a, keşif kararları calisma/kesif/adaylar.json'a ve girdi/liste.toml'a yazılır.
"""

import contextlib
import json
import re
import threading
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from yanki import durum, kesif, kilit, olay, sozler, uretim, yapi
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
                      "yayin_tarihi": x.yayin_tarihi.isoformat(), "kesif": x.puan > 0,
                      "kapak": _kapak_url(calisma, x.kimlik)} for x in p.sira]}


KAPAK_BOYUTLARI = (96, 480)


def _yarim_yukleme(calisma: Path, kimlik: str) -> bool:
    """Paketin dağıtımcıda açılmış ama kaydı tamamlanmamış yayını var mı (taslak ya da gönderiliyor)."""
    import json

    try:
        meta = json.loads((durum.klasor(calisma, kimlik) / "paket" / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    return bool((meta.get("tunearo") or {}).get("release_id"))


def kapak_kaynagi(calisma: Path, kimlik: str) -> Path | None:
    """Şarkının görünen kapağı: paketteki (dağıtımcıya giden) > elle seçilen > Pinterest'ten seçilen. Noktalı
    dosyalar sayılmaz."""
    k = durum.klasor(calisma, kimlik)
    paketteki = sorted(x for x in (k / "paket").glob("*.jpg") if not x.name.startswith("."))
    for yol in (*paketteki, k / "kapak_ozel.jpg", k / "kapak_pinterest.jpg"):
        if yol.is_file():
            return yol
    return None


_KUCUK_KILIDI = threading.Lock()


def kapak_kucuk(calisma: Path, kimlik: str, kaynak: Path, boyut: int) -> Path:
    """Kare küçük kapak, `calisma/.kapak_onbellek/`'te, kaynağın değişme zamanına göre. Paket klasörüne yazılmaz:
    oraya yazılan küçük resim kapak sanılıyor ve yükleyicinin "pakette tek JPG" kuralını bozuyordu (2026-10-10,
    görsel doğrulamada bulundu). Aynı anda gelen istekler tek üretim yapar."""
    from PIL import Image

    hedef = calisma / ".kapak_onbellek" / f"{kimlik}_{kaynak.parent.name}_{kaynak.stem}_{boyut}.jpg"
    taze = lambda: hedef.exists() and hedef.stat().st_mtime >= kaynak.stat().st_mtime  # noqa: E731
    if taze():
        return hedef
    with _KUCUK_KILIDI:
        if taze():
            return hedef
        hedef.parent.mkdir(exist_ok=True)
        with Image.open(kaynak) as img:
            en, boy = img.size
            kenar = min(en, boy)
            kare = img.convert("RGB").crop(((en - kenar) // 2, (boy - kenar) // 2, (en + kenar) // 2,
                                            (boy + kenar) // 2))
            gecici = hedef.with_suffix(".yaziliyor")
            kare.resize((boyut, boyut), Image.Resampling.LANCZOS).save(gecici, "JPEG", quality=86)
        gecici.replace(hedef)
    return hedef


def _kapak_url(calisma: Path, kimlik: str) -> str | None:
    yol = kapak_kaynagi(calisma, kimlik)
    return f"/kapak/{kimlik}?v={int(yol.stat().st_mtime)}" if yol else None


def _ozet(d: durum.Durum, calisma: Path | None = None) -> dict:
    return {"kimlik": d.kimlik, "sanatci": d.sanatci, "ad": d.ad, "asama": d.asama, "hata": d.hata,
            "gecen_aday": sum(a.gecti for a in d.adaylar),
            "bekleyen_onarim": sum(o["durum"] == "bekliyor" for a in d.adaylar for o in a.onarimlar),
            "kapak": _kapak_url(calisma, d.kimlik) if calisma else None,
            "guncel": d.gecmis[-1]["zaman"] if d.gecmis else None, "dil": d.analiz.get("dil")}


def _bolumler(satirlar: list, sure_sn: float | None, ad: str) -> list[dict]:
    """Sözler bölüm yapısıyla ve kaynağın zaman damgalarıyla (yanki/yapi.py; cover kaynağın zamanlamasını izler):
    dinleme odasında çalan satır vurgulanır, satıra tıklayınca oraya gidilir."""
    if not satirlar:
        return []
    try:
        bolumler = yapi.coz([(None if t is None else float(t), m) for t, m in satirlar], sure_sn, ad=ad)
    except (ValueError, TypeError):
        return []
    return [{"ad": b.ad, "bas": b.bas, "satirlar": [[t, m] for t, m in b.satirlar]} for b in bolumler]


def _oneri(d: durum.Durum) -> dict | None:
    """Hattın önerdiği aday ve kısa gerekçesi (onay.oneri: söz WER'i en düşük iki aday arasından ACE-Step söz
    hizalaması yüksek olan). Yalnız öneri: karar Scryne'ın kulağı."""
    from yanki import onay

    a = onay.oneri(d)
    if a is None:
        return None
    wer = (a.kapilar.get("soz_wer") or {}).get("deger")
    hiz = onay._hizalama(a)
    neden = [f"söz hatası {str(wer).replace('.', ',')}" if wer is not None else None,
             f"söz hizalaması {hiz:.3f}".replace(".", ",") if hiz is not None else None]
    return {"aday": a.no, "neden": " · ".join(x for x in neden if x)}


def kosu_durumu(calisma: Path) -> dict:
    """Şu an bir koşu sürüyor mu (gece/gündüz ya da elle `yanki uret`): `.yanki.kilit`'in ilk baytı işletim sistemi
    kilidiyle tutuluyorsa okunamaz. Kilit alınmaz (koşunun başlamasını engellemesin). Kiralık GPU açıksa
    `calisma/.runpod/acik_pod` vardır (pod kapanınca silinir); açılış zamanı dosyanın zamanı."""
    from datetime import datetime

    kilit_yolu, pod = calisma / ".yanki.kilit", calisma / ".runpod" / "acik_pod"
    suruyor = False
    if kilit_yolu.exists():
        try:
            with open(kilit_yolu, "rb") as f:
                f.read(1)
        except OSError:
            suruyor = True
    sonuc: dict = {"suruyor": suruyor, "pod": None}
    if pod.exists():
        acilis = datetime.fromtimestamp(pod.stat().st_mtime)
        sonuc["pod"] = {"acilis": acilis.isoformat(timespec="minutes"),
                        "dakika": int((datetime.now() - acilis).total_seconds() // 60)}
    return sonuc


def _son_gece(calisma: Path) -> dict | None:
    """En son gece koşusunun özeti, günlükten (başlangıç, bitiş, kod, sorunlu adımlar)."""
    gunlukler = sorted((calisma / "gunluk").glob("????-??-??.log"))
    if not gunlukler:
        return None
    try:
        satirlar = gunlukler[-1].read_text(encoding="utf-8-sig", errors="replace").splitlines()
    except OSError:
        return None
    bas = next((s for s in reversed(satirlar) if s.startswith("=== ") and "başladı" in s), None)
    if bas is None:
        return None
    sonra = satirlar[satirlar.index(bas) + 1:]
    bitti = next((s for s in sonra if s.startswith("=== ") and "bitti" in s), None)
    adimlar = [s[3:].split(" (")[0] for s in sonra if s.startswith("── ") and not s.startswith("── koşu bitti")
               and not s.startswith("── dış servisler")]
    sorunlu = next((s.split("sorunlu adım: ")[1] for s in sonra if "sorunlu adım: " in s), None)
    kod = re.search(r"kod (\d+)", bitti or "")
    return {"bas": bas[4:23], "bit": bitti[4:23] if bitti else None, "kod": int(kod.group(1)) if kod else None,
            "suruyor": bitti is None, "adim": adimlar[-1] if adimlar else None, "sorunlu": sorunlu}


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


YEREL_HOSTLAR = ("127.0.0.1", "localhost", "::1")
GUVENLI_YONTEMLER = ("GET", "HEAD", "OPTIONS")


def uygulama(a: Ayarlar, calisma: Path, liste_yolu: Path | None = None) -> FastAPI:
    app = FastAPI(title="Yanki dinleme", docs_url=None, redoc_url=None)
    liste_yolu = liste_yolu or a.kok / "girdi" / "liste.toml"

    @app.middleware("http")
    async def yerel_koruma(istek: Request, devam):
        """Oda yalnız 127.0.0.1'de dinliyor, ama tarayıcıda açık başka bir site iki yoldan ulaşabilirdi: yazan uçlara
        form/`fetch` ile istek (gövdesiz "Reddi geri al", "Listeye ekle", "Başka kapak" doğrudan çalışıyordu) ve DNS
        yeniden bağlama (kendi alan adını 127.0.0.1'e çevirip okuma uçlarını okumak). Host yerel olmalı; yazan istek
        başka bir kökenden (`Origin`, `Sec-Fetch-Site`) gelemez. Origin'siz istek (curl, betik) geçer."""
        if istek.url.hostname not in YEREL_HOSTLAR:
            return JSONResponse({"detail": "dinleme odası yalnız 127.0.0.1 adresinden açılır"}, 403)
        if istek.method not in GUVENLI_YONTEMLER:
            koken = istek.headers.get("origin")
            if (koken is not None and urlparse(koken).hostname not in YEREL_HOSTLAR) or \
                    istek.headers.get("sec-fetch-site") == "cross-site":
                return JSONResponse({"detail": "başka bir siteden gelen istek reddedildi"}, 403)
        return await devam(istek)

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
        return [_ozet(d, calisma) for d in durum.hepsi(calisma)]

    @app.get("/kapak/{kimlik}")
    def kapak(kimlik: str, boyut: int = 96):
        if not _kimlik_gecerli(kimlik) or boyut not in KAPAK_BOYUTLARI:
            raise HTTPException(404, "kapak yok")
        yol = kapak_kaynagi(calisma, kimlik)
        if yol is None:
            raise HTTPException(404, "kapak yok")
        return FileResponse(kapak_kucuk(calisma, kimlik, yol, boyut), media_type="image/jpeg",
                            headers={"Cache-Control": "max-age=86400"})

    @app.post("/api/sarki/{kimlik}/kapak")
    def yeni_kapak(kimlik: str):
        """Pinterest'ten başka kapak (öncekiler bir daha seçilmez); paketliyse paket yeni kapakla yenilenir."""
        from yanki import paket, pinterest

        d = oku(kimlik)
        if d.asama not in ("uretildi", "onarim", "onaylandi", "paketlendi"):
            raise HTTPException(409, "kapak yalnız yüklenmemiş şarkıda değişir (dağıtımcıdaki kapak sabit)")
        if (durum.klasor(calisma, kimlik) / "kapak_ozel.jpg").exists():
            raise HTTPException(409, "elle seçilmiş kapak_ozel.jpg var; o kullanılıyor")
        with kilit.tek_kosu(calisma / ".yanki.kilit") as alindi:  # paket gece koşusuyla aynı anda yazılmasın
            if not alindi:
                raise HTTPException(409, "gece ya da gündüz koşusu sürüyor; bitince tekrar dene")
            try:
                pinterest.getir(calisma, d, yeni=(durum.klasor(calisma, kimlik) / "kapak_pinterest.jpg").exists())
            except (OSError, LookupError, ValueError) as e:
                raise HTTPException(502, f"Pinterest'ten kapak alınamadı: {e}") from e
            if d.asama == "paketlendi":
                hatalar: list = []
                paket.paketle(calisma, a.kok / "config" / "yayin.toml", [kimlik], yeniden=True, hatalar=hatalar)
                if hatalar:
                    raise HTTPException(500, f"yeniden paketlenemedi: {hatalar[0][1]}")
        kaynak = json.loads((durum.klasor(calisma, kimlik) / "kapak_kaynak.json").read_text(encoding="utf-8"))
        return {**_ozet(durum.oku(calisma, kimlik), calisma), "kapak_bilgi": kaynak}

    @app.get("/api/sarki/{kimlik}")
    def sarki(kimlik: str):
        d = oku(kimlik)
        zaman = durum.klasor(calisma, kimlik) / "soz_zaman.json"
        satirlar = json.loads(zaman.read_text(encoding="utf-8")) if zaman.exists() else []
        from yanki import onay, takip

        ayar = onay.ayar_oku(a.kok / "config" / "yayin.toml")
        oto = onay.onay_zamani(d, ayar)
        oneri = onay.oneri(d) if oto else None
        k = durum.klasor(calisma, kimlik)
        kaynak = k / "kapak_kaynak.json"
        return {**asdict(d), **_ozet(d, calisma), "kesitler": sozler.kesitler(satirlar, d.kaynak.get("sure_sn")),
                "bolumler": _bolumler(satirlar, d.kaynak.get("sure_sn"), d.ad), "oneri": _oneri(d),
                "otomatik_onay": {"zaman": oto.isoformat(timespec="minutes"), "aday": oneri.no}
                if oto and oneri else None,
                "onay_engeli": onay.engel(d, ayar) if ayar.acik and d.asama == "uretildi" else None,
                "kapak_bilgi": json.loads(kaynak.read_text(encoding="utf-8")) if kaynak.exists() else None,
                "kapak_elle": (k / "kapak_ozel.jpg").exists(),
                "yukleme": takip.yukleme_bilgisi(calisma, kimlik)}

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
        return _ozet(d, calisma)

    @app.post("/api/sarki/{kimlik}/onarim-kabul")
    def onarim_kabul(kimlik: str, istek: KabulIstegi):
        with guncelle(kimlik) as d:
            if d.asama not in DUZENLENEBILIR:
                raise HTTPException(409, f"bu aşamada onarım kabul edilemez: {d.asama}")
            try:
                uretim.onarim_kabul(d, istek.aday, istek.onarim)
            except (ValueError, StopIteration) as e:
                raise HTTPException(409, f"kabul edilemedi: {e}") from e
        return _ozet(d, calisma)

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
        return _ozet(d, calisma)

    @app.post("/api/sarki/{kimlik}/stil")
    def stil(kimlik: str, istek: StilIstegi):
        with guncelle(kimlik) as d:
            try:
                uretim.stil_degistir(d, istek.stil, istek.bpm, istek.ton.strip())
            except ValueError as e:
                raise HTTPException(409, str(e)) from e
        return _ozet(d, calisma)

    @app.post("/api/sarki/{kimlik}/reddet")
    def reddet(kimlik: str, istek: RetIstegi):
        with guncelle(kimlik) as d:
            if d.asama in ("yuklendi", "yayinda", "reddedildi"):
                raise HTTPException(409, f"bu aşamada reddedilemez: {d.asama}")
            if d.asama == "paketlendi" and _yarim_yukleme(calisma, kimlik):
                raise HTTPException(409, "bu paketin Tunearo'da açılmış bir yayını var (yarım yükleme); önce "
                                         f"`yanki geri-cek {kimlik}` ya da yüklemenin bitmesini bekle")
            d.notlar.append({"ret": istek.neden})
            d.gec("reddedildi", istek.neden or None)
        return _ozet(d, calisma)

    @app.post("/api/sarki/{kimlik}/geri-al")
    def geri_al(kimlik: str):
        """Reddi geri alır: şarkı reddedilmeden önceki aşamasına döner (yanlış tık, fikir değişikliği)."""
        with guncelle(kimlik) as d:
            if d.asama != "reddedildi":
                raise HTTPException(409, "yalnız reddedilmiş şarkı geri alınabilir")
            onceki = next((g["asama"] for g in reversed(d.gecmis[:-1]) if g.get("asama") != "reddedildi"), "yeni")
            d.notlar.append({"ret_geri_alindi": onceki})
            d.gec(onceki)
        return _ozet(d, calisma)

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
        # liste.toml'a gece keşfi de yazıyor: liste kendi kilidiyle yazılır (koşu sürerken de eklenebilir; hazırlık
        # adımı listeyi okur, atomik yazım yarım dosya göstermez)
        try:
            with kesif.kayit_kilidi(calisma):
                kayit = kesif.oku(calisma)
                x = kesif_adayi(kayit, kimlik)
                kesif.listeye_yaz([x], liste_yolu, "dinleme odasından eklendi")
                x.elendi = False
                kesif.kaydet(calisma, kayit)
        except kilit.KilitMesgul as e:
            raise HTTPException(409, "liste şu an güncelleniyor; birkaç saniye sonra tekrar dene") from e
        except ValueError as e:  # aynı şarkı o arada eklendi
            raise HTTPException(409, f"listeye eklenemedi: {e}") from e
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
                             "dagitim_durumu": y.get("dagitim_durumu"), "upc": y.get("upc"),
                             "isrc": y.get("isrc"), "son": (d.yayin or {}).get("son"),
                             "gecmis": (d.yayin or {}).get("gecmis", []), "kapak": _kapak_url(calisma, d.kimlik),
                             "geri_cek": bool(y.get("geri_cek"))})
        sarkilar.sort(key=lambda s: s["yayin_tarihi"] or "")
        return {"sarkilar": sarkilar, "kota": _kota(a.kok), "profiller": sorted(takip.profil_kimlikleri(calisma)),
                "takvim": _takvim(a.kok, calisma), "olaylar": olay.oku(calisma, son=8)[::-1]}

    # ---- pano ----
    @app.get("/api/pano")
    def pano():
        """Hattın tek bakışta durumu (ağa çıkmaz): aşama sayıları, Scryne'dan beklenenler, dağıtım, sıra, bildirimler,
        son gece koşusu, otomasyon ayarları."""
        from yanki import dagitim, onay, paket, takip

        yayin_yolu = a.kok / "config" / "yayin.toml"
        hepsi = durum.hepsi(calisma)
        say = lambda *asamalar: sum(d.asama in asamalar for d in hepsi)  # noqa: E731
        ayar = onay.ayar_oku(yayin_yolu)
        dagitimda = []
        for d in hepsi:
            if d.asama in ("yuklendi", "yayinda"):
                y = takip.yukleme_bilgisi(calisma, d.kimlik) or {}
                dagitimda.append({**_ozet(d, calisma), "dagitimci": y.get("dagitimci"),
                                  "dagitim_durumu": y.get("dagitim_durumu"), "yayin_tarihi": y.get("yayin_tarihi"),
                                  "canli": bool(((d.yayin or {}).get("son") or {}).get("canli")),
                                  "geri_cek": bool(y.get("geri_cek"))})
        dagitimda.sort(key=lambda x: x["yayin_tarihi"] or "")
        try:
            kesif_oneri = sum(x.puan > 0 and not x.elendi for x in kesif.oku(calisma).values())
        except (OSError, ValueError):
            kesif_oneri = 0
        try:
            y = paket.yayin_ayarlari(yayin_yolu)
            t = dagitim.takvim_oku(yayin_yolu)
            from yanki import uzak

            ayarlar = {"dagitimci": y.dagitimci, "kapak": y.kapak, "takvim_acik": t.acik, "haftada": t.haftada,
                       "oto_onay": ayar.acik, "oto_onay_saat": ayar.sure_saat,
                       "uretim": (f"kiralık GPU ({a.uzak.gpu.replace('NVIDIA ', '')})" if a.uzak.acik
                                  else "evdeki GPU"),
                       "uzak_ay_usd": uzak.bu_ay_harcama(a.kok) if a.uzak.acik else None,
                       "uzak_butce": a.uzak.aylik_butce if a.uzak.acik else None,
                       "tarif": {"model": a.motor.model, "lora": uretim.lora_adi(a.motor.lora),
                                 "lora_olcek": a.motor.lora_olcek if a.motor.lora else None, "betim": a.motor.betim,
                                 "aday": a.cover.aday_sayisi, "adim": a.cover.adim, "guc": a.cover.guc}}
        except (OSError, ValueError, KeyError):
            ayarlar = {}
        from yanki import tunearo

        uyarilar = []
        if (e := tunearo.erisim_durumu(calisma)):
            uyarilar.append({"baslik": "Tunearo API erişimi kapalı",
                             "metin": f"{e.get('ilk', '')[:16].replace('T', ' ')}'dan beri her istek reddediliyor; "
                                      "yükleme ve durum yoklaması bekliyor. Hesap sahibi erişimi açınca hat sürer."})
        return {
            "uyarilar": uyarilar,
            "hat": [
                {"ad": "Keşif", "sayi": kesif_oneri, "alt": "aday"},
                {"ad": "Üretim", "sayi": say("yeni", "hazir", "analiz", "onarim"), "alt": "şarkı"},
                {"ad": "Dinleme", "sayi": say("uretildi"), "alt": "şarkı"},
                {"ad": "Paket", "sayi": say("onaylandi", "paketlendi"), "alt": "hazır"},
                {"ad": "İnceleme", "sayi": say("yuklendi"), "alt": "dağıtımcıda"},
                {"ad": "Yayında", "sayi": say("yayinda"), "alt": "Spotify"},
            ],
            "kulak": [{**_ozet(d, calisma), "neden": n} for d, n in onay.kulak_bekleyen(calisma, ayar)],
            "yakinda": [{**_ozet(d, calisma), "zaman": z.isoformat(timespec="minutes")} for d in hepsi
                        if (z := onay.onay_zamani(d, ayar))],
            "hatada": [_ozet(d, calisma) for d in hepsi if d.asama == "hata"],
            "dagitim": dagitimda, "takvim": _takvim(a.kok, calisma), "ayarlar": ayarlar,
            "olaylar": olay.oku(calisma, son=12)[::-1], "gece": _son_gece(calisma), "kota": _kota(a.kok),
            "simdi": {**kosu_durumu(calisma), "uretimde": [_ozet(d, calisma) for d in hepsi
                                                           if d.asama in ("analiz", "onarim")]},
        }

    @app.get("/api/kazanc")
    def kazanc(yenile: bool = False):
        """Tunearo'daki bizim yayınların kazancı (önbellekli; anahtar yoksa bağlı değil)."""
        from yanki import tunearo

        try:
            return {"bagli": True, **tunearo.kazanc(calisma, tunearo.Istemci.kokten(a.kok), zorla=yenile)}
        except tunearo.AyarYok:
            return {"bagli": False}
        except (tunearo.TunearoHatasi, OSError) as e:
            # dağıtımcıya ulaşılamaması sayfanın hatası değil (erişim kapalıyken her açılışta konsol hatası veriyordu)
            return {"bagli": True, "ulasilamadi": True, "erisim_kapali": "403" in str(e), "hata": str(e)[:300]}

    app.mount("/", StaticFiles(directory=SAYFA, html=True), name="sayfa")
    return app
