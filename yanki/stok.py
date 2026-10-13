"""Kapak görseli lisanslı stok fotoğraftan (Unsplash, Pexels), şarkının moduna göre.

Pinterest kapağının (yanki/pinterest.py) yerine geçer: aynı sorgu (stil tanımındaki mod sözcükleri + sözlerdeki imge,
şarkı ya da sanatçı adı yok), aynı insan/yazı süzgeci, bir görsel iki şarkıda kullanılmaz. Fark kaynakta: Unsplash
License ve Pexels License ticari kullanıma ve kapakta kullanıma izin veriyor; Pinterest'teki görsellerin hakkı
paylaşanda değil. Stok fotoğrafların çoğu 4000 px üstü: kısa kenarı 3000'den küçük olan hiç seçilmez, büyütme yok.

Seçilen görsel `calisma/<kimlik>/kapak_stok.jpg`, kaynağı (fotoğrafçı, sayfa, lisans) `kapak_kaynak.json`. Elle
konan `kapak_ozel.jpg` her zaman önce gelir. Beğenilmeyen kapak: `yanki kapak <kimlik> --yeni`.

Erişim: resmi API'ler, ücretsiz anahtar. `.env` → `UNSPLASH_ACCESS_KEY` (unsplash.com/developers, saatte 50 istek),
`PEXELS_API_KEY` (pexels.com/api, saatte 200). Hangisi varsa o; ikisi de varsa önce Unsplash. Unsplash'in API
kuralı gereği kullanılan fotoğraf için `download_location` ucuna haber verilir.
"""

import io
import json
import os
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from yanki import ag, dosya, durum, sayac
from yanki.pinterest import INSAN, YAZI, sorgu

EN_KUCUK = 3000  # kısa kenar; stokta bol, büyütme gerekmez
INDIRME_DENEME = 4
LISANS = {"unsplash": "Unsplash License (unsplash.com/license)", "pexels": "Pexels License (pexels.com/license)"}
SERVIS = {"unsplash": "Unsplash", "pexels": "Pexels"}


class Bulunamadi(LookupError):
    pass


def anahtarlar(kok: Path) -> dict[str, str]:
    """Ortam değişkenleri `.env`'yi ezer."""
    from yanki import spotify

    env = spotify.env_oku(kok)
    sonuc = {}
    for kaynak, ad in (("unsplash", "UNSPLASH_ACCESS_KEY"), ("pexels", "PEXELS_API_KEY")):
        if deger := (os.environ.get(ad) or env.get(ad, "")).strip():
            sonuc[kaynak] = deger
    return sonuc


def _json(url: str, basliklar: dict, servis: str) -> dict:
    istek = urllib.request.Request(url, headers={"Accept": "application/json", **basliklar})
    try:
        with urllib.request.urlopen(istek, timeout=30) as c:
            veri = json.load(c)
        sayac.say(servis, True)
        return veri
    except (*ag.GECICI, ValueError) as e:
        sayac.say(servis, False)
        if isinstance(e, OSError | ValueError):
            raise
        raise OSError(f"{servis} araması: {type(e).__name__}: {e}") from e


def ara(q: str, anahtar: dict[str, str]) -> list[dict]:
    """Ortak biçimde adaylar: kaynak, id, en, boy, aciklama, indir (tam çözünürlük), bildir, fotografci, sayfa."""
    adaylar: list[dict] = []
    if k := anahtar.get("unsplash"):
        v = _json("https://api.unsplash.com/search/photos?" + urllib.parse.urlencode(
            {"query": q, "per_page": 30, "content_filter": "high"}),
            {"Authorization": f"Client-ID {k}", "Accept-Version": "v1"}, SERVIS["unsplash"])
        for p in v.get("results", []):
            adaylar.append({
                "kaynak": "unsplash", "id": f"unsplash:{p['id']}", "en": p.get("width") or 0, "boy": p.get("height") or 0,
                "aciklama": p.get("alt_description") or p.get("description") or "",
                "indir": p["urls"]["raw"] + "&w=3600&q=92&fm=jpg", "bildir": (p.get("links") or {}).get("download_location"),
                "fotografci": (p.get("user") or {}).get("name"),
                "fotografci_url": ((p.get("user") or {}).get("links") or {}).get("html"), "sayfa": (p.get("links") or {}).get("html"),
            })
    if k := anahtar.get("pexels"):
        v = _json("https://api.pexels.com/v1/search?" + urllib.parse.urlencode({"query": q, "per_page": 40}),
                  {"Authorization": k}, SERVIS["pexels"])
        for p in v.get("photos", []):
            adaylar.append({
                "kaynak": "pexels", "id": f"pexels:{p['id']}", "en": p.get("width") or 0, "boy": p.get("height") or 0,
                "aciklama": p.get("alt") or "", "indir": (p.get("src") or {}).get("original"), "bildir": None,
                "fotografci": p.get("photographer"), "fotografci_url": p.get("photographer_url"), "sayfa": p.get("url"),
            })
    return adaylar


def uygun(a: dict) -> bool:
    """Yeterince büyük, açıklaması var (içeriği bilinmeyen elenir), açıklamada insan ya da yazı yok."""
    return bool(a.get("indir") and min(a.get("en") or 0, a.get("boy") or 0) >= EN_KUCUK and a.get("aciklama")
                and not INSAN.search(a["aciklama"]) and not YAZI.search(a["aciklama"]))


def _puan(a: dict) -> float:
    en, boy = a["en"], a["boy"]
    return min(en, boy) * min(en, boy) / max(en, boy)  # kareye yakın ve büyük önce (kırpılan kısım az)


def kullanilanlar(calisma: Path) -> set[str]:
    sonuc = set()
    for yol in calisma.glob("*/kapak_kaynak.json"):
        try:
            k = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sonuc.update(x for x in (k.get("stok_id"), *k.get("onceki", [])) if x)
    return sonuc


def sirali_adaylar(adaylar: list[dict], kullanilan: set[str]) -> list[dict]:
    return sorted((a for a in adaylar if uygun(a) and a["id"] not in kullanilan), key=_puan, reverse=True)


def _indir(url: str, deneme: int = 2) -> bytes:
    import time

    istek = urllib.request.Request(url, headers={"User-Agent": "yanki (stok kapak)"})
    for i in range(deneme):
        try:
            with urllib.request.urlopen(istek, timeout=90) as c:
                return c.read()
        except ag.GECICI as e:
            if i == deneme - 1:
                raise OSError(f"görsel indirilemedi: {type(e).__name__}: {e}") from e
            time.sleep(2)
    raise AssertionError("ulaşılmaz")


def _bildir(a: dict, anahtar: dict[str, str]) -> None:
    """Unsplash API kuralı: kullanılan fotoğrafın indirildiği bildirilir. Düşmesi kapağı bozmaz."""
    if a["kaynak"] != "unsplash" or not a.get("bildir") or not anahtar.get("unsplash"):
        return
    try:
        _json(a["bildir"], {"Authorization": f"Client-ID {anahtar['unsplash']}"}, SERVIS["unsplash"])
    except (OSError, ValueError):
        pass


def getir(calisma: Path, d: durum.Durum, yeni: bool = False, arayici=ara, indirici=_indir, anahtar=None) -> Path:
    """Şarkıya stok kapak bulur, `kapak_stok.jpg` olarak kaydeder. yeni=True: öncekini bırakıp başka görsel."""
    from PIL import Image

    k = durum.klasor(calisma, d.kimlik)
    hedef, kaynak_yolu = k / "kapak_stok.jpg", k / "kapak_kaynak.json"
    if hedef.exists() and not yeni:
        return hedef
    anahtar = anahtarlar(calisma.parent) if anahtar is None else anahtar
    if arayici is ara and not anahtar:
        raise Bulunamadi(".env → UNSPLASH_ACCESS_KEY ya da PEXELS_API_KEY yok: stok kapak aranamıyor")
    onceki = json.loads(kaynak_yolu.read_text(encoding="utf-8")) if kaynak_yolu.exists() else {}
    kullanilan = kullanilanlar(calisma)
    soz_yolu = k / "soz.txt"
    q = sorgu(d, soz_yolu.read_text(encoding="utf-8") if soz_yolu.exists() else None)
    secilen, son_hata = None, None
    # stok aramaları "aesthetic" yerine düz sahneyle daha iyi sonuç veriyor; sonra genişletilir
    for deneme in (q.replace(" aesthetic", ""), f"{q.split(' scenery')[0]} landscape", "moody landscape"):
        for aday in sirali_adaylar(arayici(deneme, anahtar), kullanilan)[:INDIRME_DENEME]:
            try:
                with Image.open(io.BytesIO(indirici(aday["indir"]))) as img:
                    if min(img.size) < EN_KUCUK:
                        raise ValueError(f"gerçek boyut {img.size[0]}×{img.size[1]} küçük")
                    img.convert("RGB").save(hedef, "JPEG", quality=95)
            except (OSError, ValueError) as e:  # PIL.UnidentifiedImageError OSError türevi
                son_hata = e
                continue
            secilen, q = aday, deneme
            break
        if secilen:
            break
    if secilen is None:
        raise Bulunamadi(f"stok fotoğrafta uygun görsel yok (sorgu: {q})" + (f"; son hata: {son_hata}" if son_hata
                                                                               else ""))
    _bildir(secilen, anahtar)
    dosya.json_yaz(kaynak_yolu, {
        "kaynak": secilen["kaynak"], "stok_id": secilen["id"], "sayfa": secilen.get("sayfa"),
        "fotografci": secilen.get("fotografci"), "fotografci_url": secilen.get("fotografci_url"),
        "lisans": LISANS[secilen["kaynak"]], "aciklama": secilen.get("aciklama"),
        "boyut": [secilen["en"], secilen["boy"]], "sorgu": q, "zaman": datetime.now().isoformat(timespec="seconds"),
        "onceki": [*onceki.get("onceki", []),
                   *([x for x in (onceki.get("stok_id"), onceki.get("pin_id"), onceki.get("imza")) if x] if yeni else [])],
    })
    return hedef
