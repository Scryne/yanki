"""Dış servis istekleri. Kişisel bilgi taşımaz (User-Agent'ta e-posta yok)."""

import http.client
import ipaddress
import json
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from yanki import sayac

KIMLIK = "Yanki/0.1 (+https://github.com/Scryne/yanki)"

# ── ad çözümleme ────────────────────────────────────────────
# Bu ağda IPv6 kaydı olmayan bazı adlarda AAAA sorgusu zaman aşımına düşüyor ve her çözümleme ~12 sn sürüyor
# (2026-10-11: dashboard.tunearo.com, ölçüm AF_INET 0,11 sn / AF_UNSPEC 12,06 sn; 21 yayının yoklaması 4 dk). Python
# her bağlantıda yeniden çözüyor. Çözümleme IPv4 ve IPv6 için ayrı ayrı ve aynı anda yapılır: IPv4 gelince IPv6 en çok
# `IPV6_PAYI_SN` beklenir, gelmezse IPv4 adresleriyle devam edilir. Sonuç süreç içinde `DNS_ONBELLEK_SN` saklanır.
DNS_ONBELLEK_SN = 300.0
IPV6_PAYI_SN = 0.3
_gercek_getaddrinfo = socket.getaddrinfo
_dns_onbellek: dict[tuple, tuple[float, list]] = {}
_dns_kilit = threading.Lock()


def _adres_mi(host) -> bool:
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        return False


def _cozumle(host, port, family=0, type=0, proto=0, flags=0):  # noqa: A002 — socket.getaddrinfo imzası
    if family != socket.AF_UNSPEC or not isinstance(host, str) or not host or _adres_mi(host) or host == "localhost":
        return _gercek_getaddrinfo(host, port, family, type, proto, flags)
    anahtar = (host.lower(), port, type, proto, flags)
    with _dns_kilit:
        kayit = _dns_onbellek.get(anahtar)
    if kayit and kayit[0] > time.monotonic():
        return list(kayit[1])
    sonuc: dict[int, list | BaseException] = {}
    hazir = {aile: threading.Event() for aile in (socket.AF_INET, socket.AF_INET6)}

    def coz(aile: int) -> None:
        try:
            sonuc[aile] = _gercek_getaddrinfo(host, port, aile, type, proto, flags)
        except BaseException as e:  # noqa: BLE001 — çağıran ipliğe taşınır
            sonuc[aile] = e
        hazir[aile].set()

    for aile in hazir:
        threading.Thread(target=coz, args=(aile,), daemon=True).start()
    hazir[socket.AF_INET].wait()
    hazir[socket.AF_INET6].wait(IPV6_PAYI_SN if not isinstance(sonuc[socket.AF_INET], BaseException) else None)
    adresler = [x for aile in (socket.AF_INET, socket.AF_INET6)
                if isinstance(r := sonuc.get(aile), list) for x in r]
    if not adresler:
        hata = sonuc.get(socket.AF_INET)
        raise hata if isinstance(hata, BaseException) else socket.gaierror(socket.EAI_NONAME, "ad çözülemedi")
    with _dns_kilit:
        _dns_onbellek[anahtar] = (time.monotonic() + DNS_ONBELLEK_SN, adresler)
    return list(adresler)


socket.getaddrinfo = _cozumle
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
