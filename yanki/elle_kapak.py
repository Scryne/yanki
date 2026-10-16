"""Elle yayın taslağına Pinterest'ten kapak (Scryne 2026-10-16: "AI cover'larda Pinterest'ten buluyorduk, ondan olmaz
mı"): Yanki'nin cover kapaklarındaki gibi insansız, yazısız, iki yayında kullanılmamış pin. Kendi şarkında stil betimi
olmadığı için sorgu genel bir mod ("moody atmospheric scenery aesthetic"). Kaynak taslakta `kapak_kaynak.json`.
"""

import json
from pathlib import Path

from yanki import dosya, elle, pinterest

# Pinterest pinlerinin kısa kenarı çoğunlukla 1000–1126 px (2026-10-16 ölçümü: 46 uygun pinde 1400'ü geçen yok); görsel
# 3000×3000'e büyütülür (Yanki cover'larında alt sınır 600). Dağıtıcıya giden dosya 3000 px.
PINTEREST_EN_AZ = 1000
SORGULAR = ("moody atmospheric scenery aesthetic", "moody scenery aesthetic")


class Hata(ValueError):
    pass


def pinterest_kapak(calisma: Path, kimlik: str, arayici=None, indirici=None) -> str:
    """Taslağa Pinterest'ten kapak. Beğenilmeyen pinler ("Başka kapak") bir daha seçilmez: `pinterest.kullanilanlar`
    önceki seçimleri (`onceki`) de sayar; Yanki şarkılarında kullanılmış pin de alınmaz."""
    arayici, indirici = arayici or pinterest.ara, indirici or pinterest._indir
    elle.oku(calisma, kimlik)  # taslak var mı
    k = elle.klasor(calisma, kimlik)
    try:
        onceki = json.loads((k / "kapak_kaynak.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        onceki = {}
    reddedilen = [*onceki.get("onceki", []), *[x for x in (onceki.get("pin_id"), onceki.get("imza")) if x]]
    kullanilan = pinterest.kullanilanlar(calisma) | pinterest.kullanilanlar(elle.kok_klasor(calisma))
    for sorgu in SORGULAR:
        try:
            adaylar = arayici(sorgu)
        except (OSError, LookupError, ValueError):
            continue
        buyuk = [p for p in pinterest.sirali_adaylar(adaylar, kullanilan)
                 if min(pinterest._gorsel(p).get("width") or 0, pinterest._gorsel(p).get("height") or 0)
                 >= PINTEREST_EN_AZ]
        for pin in buyuk[:pinterest.INDIRME_DENEME]:
            g = pinterest._gorsel(pin)
            try:
                elle.kapak_kaydet(calisma, kimlik, "pinterest.jpg", indirici(g["url"]), en_az=PINTEREST_EN_AZ)
            except (OSError, elle.Hata):
                continue
            dosya.json_yaz(k / "kapak_kaynak.json", {
                "pin_id": pin["id"], "imza": pin.get("image_signature"), "url": g["url"],
                "pin": f"https://www.pinterest.com/pin/{pin['id']}/", "aciklama": pin.get("seo_alt_text"),
                "boyut": [g["width"], g["height"]], "sorgu": sorgu, "onceki": reddedilen})
            meta = elle.oku(calisma, kimlik)
            meta["kapak"] = {**(meta.get("kapak") or {}), "kaynak": "pinterest",
                             "pin": f"https://www.pinterest.com/pin/{pin['id']}/"}
            elle._yaz(calisma, kimlik, meta)
            return f"kapak: Pinterest ({pin.get('seo_alt_text') or pin['id']})"
    raise Hata(f"Pinterest'te {PINTEREST_EN_AZ} px'lik uygun görsel bulunamadı; kapağı kendin sürükle")
