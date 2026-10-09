"""Dış servis istekleri. Kişisel bilgi taşımaz (User-Agent'ta e-posta yok)."""

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from yanki import sayac

KIMLIK = "Yanki/0.1 (+https://github.com/Scryne/yanki)"


class Bulunamadi(LookupError):
    pass


def json_al(url: str, parametre: dict | None = None, zaman_asimi: float = 30, deneme: int = 3) -> dict | list:
    if parametre:
        url = f"{url}?{urllib.parse.urlencode(parametre)}"
    istek = urllib.request.Request(url, headers={"User-Agent": KIMLIK, "Accept": "application/json"})
    servis = sayac.servis(url)
    for i in range(deneme):
        try:
            with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
                veri = json.load(r)
            sayac.say(servis, True)
            return veri
        except urllib.error.HTTPError as e:
            sayac.say(servis, e.code == 404)  # 404 servisin cevabıdır ("yok"), hata değil
            if e.code == 404:
                raise Bulunamadi(url) from e
            if e.code not in (429, 500, 502, 503, 504) or i == deneme - 1:
                raise
        except (urllib.error.URLError, TimeoutError):
            sayac.say(servis, False)
            if i == deneme - 1:
                raise
        time.sleep(2 * (i + 1))
    raise AssertionError("ulaşılmaz")
