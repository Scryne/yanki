"""Dinleme sayfası sunucusu (yalnız 127.0.0.1): Scryne adayları dinler, onaylar, aralık işaretler, stili değiştirir,
reddeder; keşif adaylarını listeye ekler ya da eler; yüklenenlerin yayın durumunu, hattın panosunu, kapakları görür;
Sanatçı görünümünden RouteNote taslağı ve gönderimi başlatır (iş ayrı süreçte, `yanki/sanatci.py → Isci`).

Sunucu motoru çalıştırmaz ve Spotify Web API'sine istek atmaz (kota dar; ölçümleri gece koşusu yapar). Dışarıya yalnız
Scryne "başka kapak" deyince Pinterest (dağıtımcı Tunearo seçiliyse kazanç da); Bulucu'da arama yapınca Spotify
istemcisinin içindeki STILLMORE (`yanki/bulucu.py`, CDP; Web API kotası harcamaz). Onarım ve yeniden üretim istekleri
durum.json'a, keşif kararları calisma/kesif/adaylar.json'a ve girdi/liste.toml'a yazılır.
"""

import contextlib
import json
import re
import threading
from dataclasses import asdict
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from yanki import durum, kesif, kilit, kulak, olay, sistem, sozler, uretim, yapi
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


class SanatciAyari(BaseModel):
    gece: bool | None = None
    spotify_sanatci_id: str | None = Field(default=None, max_length=40)
    # 0: onaylanınca yayında; yoksa en az 10 (RouteNote incelemesi 5–10 iş günü; 1–9'u sanatci.ayar_yaz reddeder)
    yayin_on_gun: int | None = Field(default=None, ge=0, le=120)
    onay: str | None = Field(default=None, max_length=100)  # gece yüklemesini açmak: sanatçı adı elle yazılır


class GonderimSonucu(BaseModel):
    gonderildi: bool


class GonderOnayi(BaseModel):
    onay: str = Field(max_length=300)  # şarkının adı, elle yazılır: geri alınamaz gönderimin onayı


class BulucuArama(BaseModel):
    girdi: str = Field(max_length=500)


class BulucuBaglan(BaseModel):
    zorla: bool = False  # Spotify çalıyorken de yeniden başlat (müzik durur)


class BulucuKesfe(BaseModel):
    anahtar: str = Field(max_length=60)
    parcalar: list[str] = Field(min_length=1, max_length=1000)


class BulucuIzle(BaseModel):
    playlist: str = Field(max_length=40)
    izle: bool


class KulakOyu(BaseModel):
    en_iyi: str | None = Field(default=None, max_length=40)
    yayinlanir: bool | None = None
    not_: str | None = Field(default=None, alias="not", max_length=500)


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
        return {"hata": str(e), "sira": [], "beklemede": None, "duzeltme": [], "yazarsiz": []}
    yazarsiz = [_ozet(d, calisma) for k in p.yazarsiz if (d := durum.oku(calisma, k))]
    return {"beklemede": p.beklemede, "duzeltme": p.duzeltme, "yazarsiz": yazarsiz,
            "sira": [{"kimlik": x.kimlik, "sanatci": x.sanatci, "ad": x.ad, "yukleme": x.yukleme.isoformat(),
                      # yükleme günü ya da önce: tarihsiz (yayin_on_gun = 0), RouteNote onaylayınca yayında
                      "yayin_tarihi": x.yayin_tarihi.isoformat() if x.yayin_tarihi > x.yukleme else None,
                      "kesif": x.puan > 0,
                      "kapak": _kapak_url(calisma, x.kimlik)} for x in p.sira]}


KAPAK_BOYUTLARI = (96, 480)


def _yarim_yukleme(calisma: Path, kimlik: str) -> bool:
    """Paketin dağıtımcıda açılmış yayını var mı (RouteNote taslağı ya da gönderim; eski Tunearo kaydı)."""
    try:
        meta = json.loads((durum.klasor(calisma, kimlik) / "paket" / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    rn = meta.get("routenote") or {}
    return bool(rn.get("upc") or rn.get("adim") or (meta.get("tunearo") or {}).get("release_id"))


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


GOREV_ONBELLEK_SN = 600  # pano her 30 sn'de soruluyor; görev hâli PowerShell'le ~1 sn


def uygulama(a: Ayarlar, calisma: Path, liste_yolu: Path | None = None, gorev_oku=None, bulucu_isci=None) -> FastAPI:
    app = FastAPI(title="Yanki dinleme", docs_url=None, redoc_url=None)
    gorev_onbellek: dict = {}

    def gorevler() -> dict[str, str]:
        import time

        if time.monotonic() - gorev_onbellek.get("zaman", -GOREV_ONBELLEK_SN) >= GOREV_ONBELLEK_SN:
            gorev_onbellek.update(zaman=time.monotonic(), deger=(gorev_oku or sistem.gorev_durumlari)())
        return gorev_onbellek["deger"]

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
            # köken odanın kendisi olmalı: yerelde çalışan başka bir sayfa (başka port) da yazan uçlara ulaşamasın
            koken = istek.headers.get("origin")
            kendisi = f"{istek.url.scheme}://{istek.url.netloc}"
            if (koken is not None and koken.rstrip("/") != kendisi) or \
                    istek.headers.get("sec-fetch-site") not in (None, "same-origin", "none"):
                return JSONResponse({"detail": "başka bir sayfadan gelen istek reddedildi"}, 403)
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

        def uygun() -> durum.Durum:
            d = oku(kimlik)
            if d.asama not in ("uretildi", "onarim", "onaylandi", "paketlendi"):
                raise HTTPException(409, "kapak yalnız yüklenmemiş şarkıda değişir (dağıtımcıdaki kapak sabit)")
            if (durum.klasor(calisma, kimlik) / "kapak_ozel.jpg").exists():
                raise HTTPException(409, "elle seçilmiş kapak_ozel.jpg var; o kullanılıyor")
            if d.asama == "paketlendi" and _yarim_yukleme(calisma, kimlik):
                raise HTTPException(409, "RouteNote'ta bu paketin taslağı açık; kapak taslakta sabit (taslağı silince: "
                                         f"yanki routenote taslak-silindi {kimlik})")
            return d

        uygun()
        with kilit.tek_kosu(calisma / ".yanki.kilit") as alindi:  # paket gece koşusuyla aynı anda yazılmasın
            if not alindi:
                raise HTTPException(409, "gece ya da gündüz koşusu sürüyor; bitince tekrar dene")
            d = uygun()  # kilit beklenirken koşu şarkıyı yüklemiş olabilir
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
            if d.asama == "paketlendi":
                if (i := isci.durum(satir=0)) and i.get("suruyor") and i.get("kimlik") == kimlik:
                    raise HTTPException(409, "bu şarkı için RouteNote işi sürüyor; bitince yeniden dene")
                if _yarim_yukleme(calisma, kimlik):
                    raise HTTPException(409, "bu paketin RouteNote'ta açılmış bir taslağı var; önce taslağı panelden "
                                             f"sil, sonra `yanki routenote taslak-silindi {kimlik}`")
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

    # ---- kulak testi: deneme çıktılarının kör karşılaştırması (yanki/kulak.py) ----
    @app.get("/api/kulak")
    def kulak_listesi():
        return kulak.gorunum(calisma)

    @app.post("/api/kulak/{set_kimlik}/{sarki}")
    def kulak_oyu(set_kimlik: str, sarki: str, istek: KulakOyu):
        try:
            kulak.oy_ver(calisma, set_kimlik, sarki, istek.en_iyi, istek.yayinlanir, istek.not_)
        except LookupError as e:
            raise HTTPException(404, str(e)) from e
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        except kilit.KilitMesgul as e:
            raise HTTPException(409, "oy kaydı şu an yazılıyor; tekrar dene") from e
        return kulak.gorunum(calisma)

    @app.get("/kulak-ses/{set_kimlik}/{sarki}/{kol}")
    def kulak_sesi(set_kimlik: str, sarki: str, kol: str):
        s = kulak.setler().get(set_kimlik)
        yol = kulak.dosya_yolu(calisma, s, sarki, kol) if s and _kimlik_gecerli(sarki) else None
        if yol is None:
            raise HTTPException(404, "dosya yok")
        return FileResponse(yol)

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

    # ---- sanatçı (yanki/sanatci.py) ----
    from yanki import sanatci

    isci = sanatci.Isci(a.kok, calisma)

    @app.get("/api/sanatci")
    def sanatci_ozet():
        """Orvane: katalog dağıtımdaki haliyle, dağıtım ayarları, RouteNote oturumu (diskten), son iş."""
        from yanki import paket, takip

        yayin_yolu = a.kok / "config" / "yayin.toml"
        y = paket.yayin_ayarlari(yayin_yolu)
        return {"ad": y.sanatci_adi, "dagitimci": y.dagitimci, "ayar": sanatci.ayar_oku(a.kok),
                "katalog": sanatci.katalog(calisma, _kapak_url, sanatci.guncel_tarif(a)),
                "profiller": sorted(takip.profil_kimlikleri(calisma)), "oturum": sanatci.oturum(calisma),
                "is": isci.durum(), "takvim": _takvim(a.kok, calisma),
                "yeni_yayin_tarihi": (t := sanatci.yeni_yayin_tarihi(a.kok)) and t.isoformat()}

    @app.get("/api/sanatci/kapak/{upc}")
    def sanatci_kapak(upc: str, boyut: int = 96):
        """Arşivdeki (dağıtımcıda yaşayan) yayının kapağı."""
        if not re.fullmatch(r"\d{12,13}", upc) or boyut not in KAPAK_BOYUTLARI:
            raise HTTPException(404, "kapak yok")
        kaynak = sanatci.arsiv_kapak(calisma, upc)
        if kaynak is None:
            raise HTTPException(404, "kapak yok")
        return FileResponse(kapak_kucuk(calisma, f"arsiv-{upc}", kaynak, boyut),
                            headers={"Cache-Control": "max-age=86400"})

    @app.post("/api/sanatci/ayar")
    def sanatci_ayar(istek: SanatciAyari):
        from yanki import paket

        degisiklik = {k: v for k, v in istek.model_dump().items() if v is not None and k != "onay"}
        if not degisiklik:
            raise HTTPException(422, "değişiklik yok")
        if degisiklik.get("gece") is True:
            # gece yüklemesi her gece sıradaki paketleri kulaktan geçmeden geri alınamaz biçimde gönderir: tek tıkla
            # açılmasın (şarkı gönderimindeki gibi ad yazılır)
            ad = paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").sanatci_adi
            if not sanatci.onay_tutar(istek.onay or "", ad):
                raise HTTPException(422, "gece yüklemesini açmak için sanatçı adını aynen yaz")
        try:
            return sanatci.ayar_yaz(a.kok, degisiklik)
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        except OSError as e:  # Windows: dosya o an başka bir süreçte açık
            raise HTTPException(409, f"ayar dosyası yazılamadı ({e.strerror or e}); birazdan yeniden dene") from e

    def is_baslat(ad: str, kimlik: str | None = None) -> dict:
        # koşu kilidi tutuluyken `yanki yukle` kilidi alamayıp çıkar; tarayıcı profili de aynı anda tek pencerede
        if kosu_durumu(calisma)["suruyor"]:
            raise HTTPException(409, "gece ya da sürekli koşu sürüyor; bitince yeniden dene")
        try:
            return isci.baslat(ad, kimlik)
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/api/sanatci/{kimlik}/taslak")
    def sanatci_taslak(kimlik: str):
        """RouteNote taslağı: dört adım doldurulur, gönderilmez (`yanki yukle --taslak`)."""
        d = oku(kimlik)
        if d.asama != "paketlendi":
            raise HTTPException(409, f"yalnız paketlenmiş şarkı (aşama: {d.asama})")
        return is_baslat("taslak", kimlik)

    @app.post("/api/sanatci/{kimlik}/gonder")
    def sanatci_gonder(kimlik: str, istek: GonderOnayi):
        """Geri alınamaz: şartlar kabul edilir, "Distribute Free" (`yanki yukle`). Onay için şarkının adı elle yazılır;
        gece koşusunun kapısı (`[routenote] gece`) burada aranmaz, Scryne'ın kendi tıklaması."""
        d = oku(kimlik)
        if d.asama != "paketlendi":
            raise HTTPException(409, f"yalnız paketlenmiş şarkı (aşama: {d.asama})")
        if not sanatci.onay_tutar(istek.onay, d.ad):
            raise HTTPException(422, "onay için şarkının adını aynen yaz")
        return is_baslat("gonder", kimlik)

    @app.post("/api/sanatci/{kimlik}/gonderim-sonucu")
    def sanatci_gonderim_sonucu(kimlik: str, istek: GonderimSonucu):
        """Yarıda kalan gönderim: Scryne RouteNote panelinde gördüğünü söyler (hat yeniden göndermez)."""
        from yanki import routenote

        oku(kimlik)
        try:
            return {"mesaj": routenote.gonderim_sonucu(calisma, kimlik, istek.gonderildi)}
        except ValueError as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/api/sanatci/giris")
    def sanatci_giris():
        """RouteNote girişi: tarayıcı penceresi açılır, Scryne girer (şifre hatta tutulmaz)."""
        return is_baslat("giris")

    @app.get("/api/sanatci/is")
    def sanatci_is():
        return isci.durum() or {}

    # ---- bulucu: STILLMORE motoruyla Spotify araması (yanki/bulucu.py) ----
    from yanki import bulucu, stillmore

    bul = bulucu_isci or bulucu.Bulucu(calisma)

    def bulucu_sonucu(anahtar: str) -> dict:
        try:
            v = bulucu.sonuc_oku(calisma, anahtar)
        except bulucu.GirdiHatasi as e:
            raise HTTPException(404, str(e)) from e
        if v is None:
            raise HTTPException(404, "kayıt bulunamadı; aramayı yeniden yap")
        return v

    def izlenen_ozet() -> list[dict]:
        """Gece taranan STILLMORE havuzu (en yeni tarama önce) ve odadan izlenenler."""
        izlenen = bulucu.izlenenler(calisma)
        try:
            havuz = stillmore.havuz_oku(calisma)
        except (OSError, ValueError):
            havuz = {}
        kayitlar = {**{k: {"ad": v.get("ad"), "toplam": v.get("toplam"), "kaynak": "bulucu"}
                       for k, v in izlenen.items()}, **havuz}
        sonuc = [{"id": k, "ad": v.get("ad") or k, "toplam": v.get("toplam"), "son_tarama": v.get("son_tarama"),
                  "calinamayan": v.get("calinamayan"), "aday": v.get("aday"), "kaynak": v.get("kaynak"),
                  "izleniyor": k in izlenen} for k, v in kayitlar.items()]
        sonuc.sort(key=lambda x: x["son_tarama"] or "", reverse=True)  # hiç taranmamış en sonda
        sonuc.sort(key=lambda x: not x["izleniyor"])  # odadan izlenenler başta (sıralama kararlı)
        return sonuc

    @app.get("/api/bulucu")
    def bulucu_ozet():
        return {"baglanti": bul.baglanti(), "is": bul.durum(), "gecmis": bulucu.gecmis(calisma),
                "izlenen": izlenen_ozet()}

    @app.post("/api/bulucu/baglan")
    def bulucu_baglan(istek: BulucuBaglan):
        """Spotify'ı STILLMORE köprüsüyle (CDP) açar. Bayraksız açıksa yeniden başlatılır: çalıyorsa önce sorulur."""
        if not stillmore.cdp_acik() and stillmore.calisiyor_mu() and not istek.zorla and stillmore.caliyor_mu():
            raise HTTPException(409, "Spotify şu an çalıyor; bağlanmak için yeniden başlatılması gerek (müzik durur)")
        try:
            return bul.baslat("baglan")
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/api/bulucu/ara")
    def bulucu_ara(istek: BulucuArama):
        try:
            tur, kimlik = bulucu.coz(istek.girdi)
            if not stillmore.cdp_acik():
                raise HTTPException(409, "Spotify bağlı değil: önce \"Spotify'a bağlan\"")
            return bul.baslat(tur, kimlik)
        except bulucu.GirdiHatasi as e:
            raise HTTPException(422, str(e)) from e
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e

    @app.post("/api/bulucu/ac/{tur}/{kimlik}")
    def bulucu_ac(tur: str, kimlik: str):
        """Sonuçtaki bir bağlantıdan yeni arama (playlist'teki parça, sanatçının listesi, ISRC sonucu)."""
        if not bulucu.gecerli(tur, kimlik):
            raise HTTPException(422, "geçersiz arama")
        if not stillmore.cdp_acik():
            raise HTTPException(409, "Spotify bağlı değil: önce \"Spotify'a bağlan\"")
        try:
            return bul.baslat(tur, kimlik)
        except RuntimeError as e:
            raise HTTPException(409, str(e)) from e

    @app.get("/api/bulucu/is")
    def bulucu_is():
        return bul.durum() or {}

    @app.get("/api/bulucu/sonuc/{anahtar}")
    def bulucu_sonuc(anahtar: str):
        v = bulucu_sonucu(anahtar)
        satirlar = v.get("satirlar") if v.get("tur") == "playlist" else [v] if v.get("tur") == "parca" else []
        bulucu.yanki_durumu(satirlar, calisma, liste_yolu, a.kok)
        if v.get("tur") == "playlist":
            v["izleniyor"] = v.get("id") in bulucu.izlenenler(calisma)
        return v

    @app.post("/api/bulucu/kesfe")
    def bulucu_kesfe(istek: BulucuKesfe):
        """Seçilen kalkmış şarkılar gece keşfinin girdisine: aynı elemelerden geçer, uyan listeye girer."""
        v = bulucu_sonucu(istek.anahtar)
        satirlar = v.get("satirlar") if v.get("tur") == "playlist" else [v] if v.get("tur") == "parca" else []
        istenen = set(istek.parcalar)
        secilen = [s for s in satirlar if s.get("id") in istenen]
        if not secilen:
            raise HTTPException(404, "seçilen şarkılar bu kayıtta yok")
        try:
            eklenen, atlanan = bulucu.kesfe_gonder(a.kok, secilen, f"bulucu:{istek.anahtar}")
        except OSError as e:
            raise HTTPException(409, f"keşif girdisi yazılamadı ({e.strerror or e}); birazdan yeniden dene") from e
        return {"eklenen": eklenen, "atlanan": atlanan}

    @app.post("/api/bulucu/izle")
    def bulucu_izle(istek: BulucuIzle):
        """Playlist gece STILLMORE taramasına alınır ya da bırakılır (havuzu gece koşusu günceller)."""
        v = bulucu.sonuc_oku(calisma, f"playlist-{istek.playlist}") if bulucu.SPOTIFY_ID.fullmatch(istek.playlist) \
            else None
        onceki = bulucu.izlenenler(calisma).get(istek.playlist) or {}
        try:
            bulucu.izle(calisma, istek.playlist, (v or {}).get("ad") or onceki.get("ad") or "",
                        (v or {}).get("toplam") or onceki.get("toplam"), istek.izle)
        except bulucu.GirdiHatasi as e:
            raise HTTPException(422, str(e)) from e
        except OSError as e:
            raise HTTPException(409, f"kayıt yazılamadı ({e.strerror or e}); birazdan yeniden dene") from e
        return {"izlenen": izlenen_ozet()}

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
            from yanki import ayarlar as ayarlar_
            from yanki import uzak

            ayarlar = {"dagitimci": y.dagitimci, "kapak": y.kapak,
                       "uretim_acik": ayarlar_.operasyon_oku(a.kok).surekli_uretim,
                       "takvim_acik": t.acik, "haftada": t.haftada,
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
        from yanki import paket, tunearo

        uyarilar = []
        if kapali := sistem.kapali_gorevler(gorevler()):
            uyarilar.append({"baslik": "Otomatik koşu kapalı", "etiket": "zamanlayıcı",
                             "metin": f"Görev Zamanlayıcı'da {', '.join(f'Yanki\\{g}' for g in kapali)} devre dışı: "
                                      "keşif, hazırlık, otomatik onay, paket, takip ve yedek koşmuyor. Açmak: "
                                      "Görev Zamanlayıcı → Yanki → görev → Etkinleştir (ya da scripts/gorev_kur.ps1)."})
        if paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").dagitimci == "tunearo" and \
                (e := tunearo.erisim_durumu(calisma)):
            uyarilar.append({"baslik": "Tunearo API erişimi kapalı", "etiket": "dağıtım",
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
                                                           if d.asama in ("analiz", "onarim")],
                      "uretim_acik": ayarlar.get("uretim_acik", True),
                      "otomatik_kapali": bool(sistem.kapali_gorevler(gorevler()))},
        }

    @app.get("/api/kazanc")
    def kazanc(yenile: bool = False):
        """Dağıtımcıdaki yayınların kazancı. API'si olan yalnız Tunearo'ydu (önbellekli); RouteNote'un kazanç raporu
        kendi panelinde, hatta bağlı değil."""
        from yanki import paket, tunearo

        dagitimci = paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").dagitimci
        if dagitimci != "tunearo":
            return {"bagli": False, "mesaj": "RouteNote kazancı RouteNote panelinde (Accounting); hatta bağlı değil."
                    if dagitimci == "routenote" else "Dağıtımcı seçilmedi; kazanç dağıtımcı seçilince görünür."}
        try:
            return {"bagli": True, **tunearo.kazanc(calisma, tunearo.Istemci.kokten(a.kok), zorla=yenile)}
        except tunearo.AyarYok:
            return {"bagli": False}
        except (tunearo.TunearoHatasi, OSError) as e:
            # dağıtımcıya ulaşılamaması sayfanın hatası değil (erişim kapalıyken her açılışta konsol hatası veriyordu)
            return {"bagli": True, "ulasilamadi": True, "erisim_kapali": "403" in str(e), "hata": str(e)[:300]}

    app.mount("/", StaticFiles(directory=SAYFA, html=True), name="sayfa")
    return app
