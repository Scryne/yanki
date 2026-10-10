"""Dış servis istekleri. Kişisel bilgi taşımaz (User-Agent'ta e-posta yok)."""

import http.client
import json
import time
import urllib.error
import urllib.parse
import urllib.request

from yanki import sayac

KIMLIK = "Yanki/0.1 (+https://github.com/Scryne/yanki)"
# Bağlantı kurulduktan sonra kopan cevaplar (`IncompleteRead`, `RemoteDisconnected`, bağlantı sıfırlandı) da geçici:
# `URLError` değiller, önce yakalanmıyor ve gece koşusunun adımını düşürüyorlardı (2026-10-10, Pinterest ve LRCLIB).
GECICI = (urllib.error.URLError, TimeoutError, ConnectionError, http.client.HTTPException)


class Bulunamadi(LookupError):
    pass


def bekleme_sn(e: urllib.error.HTTPError | None, i: int, tavan: float = 30) -> float:
    """Yeniden denemeden önce: sunucu `Retry-After` verdiyse o (en çok `tavan`), yoksa artan bekleme."""
    try:
        deger = float((e.headers or {}).get("Retry-After") or "") if e is not None else None
    except (TypeError, ValueError):
        deger = None
    return min(tavan, deger) if deger is not None and deger >= 0 else 2.0 * (i + 1)


def json_al(url: str, parametre: dict | None = None, zaman_asimi: float = 30, deneme: int = 4) -> dict | list:
    """4 deneme: LRCLIB yükte sık sık 503 "ServerOverloaded" veriyor (2026-10-10 keşfinde isteklerin %39'u; aynı
    istek birkaç saniye sonra 200), üç denemede ardışık üç 503 şarkıyı "söz yok"a düşürebiliyordu."""
    if parametre:
        url = f"{url}?{urllib.parse.urlencode(parametre)}"
    # Accept-Language: Deezer tür adlarını IP'nin diline çeviriyor (bu ağda Türkçe: "dans", "brezilya müziği"); stil
    # tanımı ACE-Step'e ve tür süzgecine İngilizce gitmeli (2026-10-10)
    istek = urllib.request.Request(url, headers={"User-Agent": KIMLIK, "Accept": "application/json",
                                                 "Accept-Language": "en"})
    servis = sayac.servis(url)
    for i in range(deneme):
        http_hatasi = None
        try:
            with urllib.request.urlopen(istek, timeout=zaman_asimi) as r:
                ham = r.read()
            veri = json.loads(ham)
            sayac.say(servis, True)
            return veri
        except urllib.error.HTTPError as e:
            sayac.say(servis, e.code == 404)  # 404 servisin cevabıdır ("yok"), hata değil
            if e.code == 404:
                raise Bulunamadi(url) from e
            if e.code not in (429, 500, 502, 503, 504) or i == deneme - 1:
                raise
            http_hatasi = e
        except (*GECICI, ValueError) as e:  # ValueError: yarıda kesilmiş gövde JSON olarak çözülemedi
            sayac.say(servis, False)
            if i == deneme - 1:
                if isinstance(e, OSError):
                    raise
                raise OSError(f"{servis}: bozuk ya da yarım cevap ({type(e).__name__}: {e})") from e
        time.sleep(bekleme_sn(http_hatasi, i))
    raise AssertionError("ulaşılmaz")
