"""Kapak görseli Pinterest'ten, şarkının moduna göre (Scryne, 2026-10-10: "üretilen kapağı istemiyorum, şarkıya göre o
modda Pinterest'ten görsel").

Sorgu şarkının stil tanımındaki mod sözcükleri + sözlerinde en sık geçen imgeden (okyanus, yol, yıldızlar…; yoksa
türün sahnesi) kurulur ("melancholic ocean scenery aesthetic"); şarkı ya da sanatçı adı
sorguya girmez (sanatçının kendi fotoğrafları ve albüm kapakları gelir). Pinterest'in görsel açıklamasına
(`seo_alt_text`) göre insan, yazı ya da logo içeren pinler elenir: dağıtımcı kapakta orijinal sanatçının adını,
fotoğrafını, logosunu kabul etmiyor; yazılı görsel başlıkla çelişir. Bir pin iki şarkıda kullanılmaz. Adaylardan en
büyük ve kareye en yakını seçilir (kapak ortadan kare kırpılıp 3000'e getirilir).

Seçilen görsel `calisma/<kimlik>/kapak_pinterest.jpg`, kaynağı `kapak_kaynak.json`. Scryne'ın elle koyduğu
`kapak_ozel.jpg` her zaman önce gelir. Beğenilmeyen kapak: `yanki kapak <kimlik> --yeni`.

Erişim: Pinterest'in resmi API'si iş hesabı ve uygulama onayı istiyor; sitenin kendi arama ucu girişsiz cevap veriyor
(2026-10-10, `X-Pinterest-PWS-Handler` başlığı olmadan 403). Resmi olmayan uç: bozulursa paketleme o şarkıda hata verir,
şarkı onaylı kalır, sonraki koşu yeniden dener.
"""

import io
import json
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

from yanki import dosya, durum, sayac

ARAMA = "https://www.pinterest.com/resource/BaseSearchResource/get/"
TARAYICI = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 "
            "Safari/537.36")
SERVIS = "Pinterest"
EN_KUCUK = 600  # kısa kenar; altı 3000'e büyütülünce dağılıyor

# stil sözcüğü → görsel mod (sıra önemli: ilk ikisi sorguya girer)
MODLAR = (
    ("melanchol", "melancholic"), ("haunting", "dark moody"), ("nostalg", "nostalgic"), ("dreamy", "dreamy"),
    ("romantic", "romantic"), ("cinematic", "cinematic"), ("sad", "sad"), ("lonely", "lonely"),
    ("emotional", "emotional"), ("raw", "moody"), ("tender", "soft"), ("intimate", "soft"), ("airy", "ethereal"),
    ("soulful", "warm"), ("powerful", "dramatic"), ("uplifting", "golden hour"), ("energetic", "vibrant"),
    ("dark", "dark"),
)
# sözlerdeki imge → sahne (sözlerde en sık geçen; aynı türdeki baladlar aynı sahneye düşmesin)
IMGELER = {
    "ocean": "ocean", "sea": "ocean", "waves": "ocean waves", "beach": "beach", "shore": "beach", "river": "river",
    "lake": "lake", "rain": "rain", "raining": "rain", "storm": "storm", "thunder": "storm", "snow": "snow",
    "winter": "winter", "summer": "summer", "autumn": "autumn", "spring": "spring flowers",
    "stars": "starry sky", "star": "starry sky", "moon": "moonlight", "sun": "sunlight", "sunset": "sunset",
    "sunrise": "sunrise", "sky": "sky", "clouds": "clouds", "heaven": "clouds", "fire": "fire", "flame": "candle",
    "candle": "candle", "road": "empty road", "drive": "night drive", "car": "night drive", "highway": "highway",
    "city": "city lights", "streets": "city street", "street": "city street", "train": "train", "field": "field",
    "flowers": "flowers", "flower": "flowers", "roses": "roses", "garden": "garden", "tree": "tree", "trees": "forest",
    "forest": "forest", "mountain": "mountains", "mountains": "mountains", "desert": "desert", "home": "cozy home",
    "house": "old house", "room": "room", "bed": "bedroom", "window": "window", "door": "door", "light": "light",
    "lights": "lights", "dark": "darkness", "darkness": "darkness", "night": "night", "midnight": "midnight",
    "morning": "morning", "dream": "dreamscape", "dreams": "dreamscape", "paradise": "paradise", "angel": "clouds",
    "time": "clock", "clock": "clock", "piano": "piano keys", "music": "piano keys", "song": "piano keys",
    "photograph": "polaroid", "picture": "polaroid", "memories": "polaroid", "young": "summer",
}
GENEL_IMGE = {"light", "lights", "night", "dark", "time", "home", "room"}  # çok sık: yalnız başka imge yoksa


def imge(soz: str | None) -> str | None:
    if not soz:
        return None
    from collections import Counter

    sayim = Counter(w for w in re.findall(r"[a-z']+", soz.casefold()) if w in IMGELER)
    ozel = [(n, w) for w, n in sayim.items() if w not in GENEL_IMGE]
    secim = max(ozel or [(n, w) for w, n in sayim.items()], default=None)
    return IMGELER[secim[1]] if secim else None


# türe göre sahne (sözlerde imge yoksa)
SAHNELER = (
    (re.compile(r"\b(rap|hip[ -]?hop|trap|drill)\b"), "city night"),
    (re.compile(r"\b(rock|punk|grunge|metal)\b"), "night drive"),
    (re.compile(r"\b(electronic|edm|house|techno|synth)"), "neon"),
    (re.compile(r"\b(folk|acoustic guitar|country)\b"), "countryside"),
    (re.compile(r"\b(piano|ballad)\b"), "rainy window"),
)
# görsel açıklamasında bunlar varsa elenir: insan (sanatçı fotoğrafı riski) ya da yazı/logo
INSAN = re.compile(r"\b(man|men|woman|women|girl|girls|boy|boys|person|people|couple|lady|guy|child|children|kid|"
                   r"baby|face|faces|portrait|selfie|singer|rapper|band|kissing|hugging|bride|groom|model|"
                   r"he|she|his|her|hand|hands)\b", re.I)
YAZI = re.compile(r"\b(text|words?|written|writing|letters?|quote|quotes|sign|logo|poster|album|cover|caption|"
                  r"says|saying|title|font|typography|meme|book|books|magazine|newspaper|page|pages|record|vinyl|"
                  r"turntable|calendar|card|label|laptop|phone|screen)\b", re.I)  # okunur yazı taşıyan nesneler


class Bulunamadi(LookupError):
    pass


def sorgu(d: durum.Durum, soz: str | None = None) -> str:
    stil = (d.analiz.get("stil") or "").casefold()
    modlar = list(dict.fromkeys(m for anahtar, m in MODLAR if anahtar in stil))[:2] or ["moody"]
    sahne = imge(soz) or next((s for desen, s in SAHNELER if desen.search(stil)), "")
    return " ".join([*modlar, sahne, "scenery aesthetic"]).replace("  ", " ").strip()


def ara(q: str) -> list[dict]:
    veri = {"options": {"query": q, "scope": "pins", "page_size": 50}, "context": {}}
    url = f"{ARAMA}?" + urllib.parse.urlencode({"source_url": f"/search/pins/?q={urllib.parse.quote(q)}",
                                                "data": json.dumps(veri)})
    istek = urllib.request.Request(url, headers={"User-Agent": TARAYICI, "Accept": "application/json",
                                                 "X-Requested-With": "XMLHttpRequest",
                                                 "X-Pinterest-PWS-Handler": "www/search/[scope].js"})
    try:
        with urllib.request.urlopen(istek, timeout=30) as c:
            sonuc = json.load(c)["resource_response"]["data"]["results"]
        sayac.say(SERVIS, True)
        return sonuc
    except (urllib.error.URLError, TimeoutError, KeyError, ValueError):
        sayac.say(SERVIS, False)
        raise


def _gorsel(pin: dict) -> dict:
    return (pin.get("images") or {}).get("orig") or {}


def uygun(pin: dict) -> bool:
    g = _gorsel(pin)
    aciklama = pin.get("seo_alt_text") or ""
    return bool(
        pin.get("type") == "pin" and not pin.get("is_promoted") and not pin.get("story_pin_data")
        and g.get("url") and min(g.get("width") or 0, g.get("height") or 0) >= EN_KUCUK
        and aciklama and not INSAN.search(aciklama) and not YAZI.search(aciklama))


def _puan(pin: dict) -> float:
    g = _gorsel(pin)
    en, boy = g["width"], g["height"]
    return min(en, boy) * min(en, boy) / max(en, boy)  # kısa kenar, kareden uzaklaştıkça cezalı (kırpılan kısım)


def kullanilanlar(calisma: Path) -> set[str]:
    sonuc = set()
    for yol in calisma.glob("*/kapak_kaynak.json"):
        try:
            k = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sonuc.update(x for x in (k.get("pin_id"), k.get("imza"), *k.get("onceki", [])) if x)
    return sonuc


def sec(adaylar: list[dict], kullanilan: set[str]) -> dict | None:
    temiz = [p for p in adaylar if uygun(p) and p.get("id") not in kullanilan
             and p.get("image_signature") not in kullanilan]
    return max(temiz, key=_puan, default=None)


def _indir(url: str) -> bytes:
    istek = urllib.request.Request(url, headers={"User-Agent": TARAYICI, "Referer": "https://www.pinterest.com/"})
    try:
        with urllib.request.urlopen(istek, timeout=60) as c:
            veri = c.read()
        sayac.say(SERVIS, True)
        return veri
    except (urllib.error.URLError, TimeoutError):
        sayac.say(SERVIS, False)
        raise


def getir(calisma: Path, d: durum.Durum, yeni: bool = False, arayici=ara, indirici=_indir) -> Path:
    """Şarkıya kapak görseli bulur, `kapak_pinterest.jpg` olarak kaydeder. yeni=True: öncekini bırakıp başka pin."""
    from PIL import Image

    k = durum.klasor(calisma, d.kimlik)
    hedef, kaynak_yolu = k / "kapak_pinterest.jpg", k / "kapak_kaynak.json"
    if hedef.exists() and not yeni:
        return hedef
    onceki = json.loads(kaynak_yolu.read_text(encoding="utf-8")) if kaynak_yolu.exists() else {}
    kullanilan = kullanilanlar(calisma)
    soz_yolu = k / "soz.txt"
    q = sorgu(d, soz_yolu.read_text(encoding="utf-8") if soz_yolu.exists() else None)
    secilen = None
    for deneme in (q, f"{q.split(' scenery')[0]} landscape aesthetic", "moody scenery aesthetic"):
        secilen = sec(arayici(deneme), kullanilan)
        if secilen:
            q = deneme
            break
    if secilen is None:
        raise Bulunamadi(f"Pinterest'te uygun görsel yok (sorgu: {q})")
    g = _gorsel(secilen)
    with Image.open(io.BytesIO(indirici(g["url"]))) as img:
        img.convert("RGB").save(hedef, "JPEG", quality=95)
    dosya.json_yaz(kaynak_yolu, {
        "pin_id": secilen["id"], "imza": secilen.get("image_signature"), "url": g["url"],
        "pin": f"https://www.pinterest.com/pin/{secilen['id']}/", "aciklama": secilen.get("seo_alt_text"),
        "boyut": [g["width"], g["height"]], "sorgu": q, "zaman": datetime.now().isoformat(timespec="seconds"),
        # beğenilmeyenler bir daha seçilmesin
        "onceki": [*onceki.get("onceki", []), *([onceki["pin_id"]] if yeni and onceki.get("pin_id") else [])],
    })
    return hedef
