"""Spotify Web API: kaldırılmış şarkı keşfi ve yayın takibi için.

İki token:
- uygulama (Client Credentials): arama, ISRC araması, tek parça. `SPOTIFY_CLIENT_ID` + `SPOTIFY_CLIENT_SECRET`.
- kullanıcı (Authorization Code + PKCE, `yanki spotify-baglan` ile bir kez): playlist parçaları. Token
  `calisma/.spotify.json`'da, depoya girmez.

Şubat 2026 kısıtları (developer.spotify.com, Şubat/Mart/Temmuz 2026 changelog'ları; `docs/arastirma/03`):
- Development Mode uygulamasının sahibinin aktif Premium'u şart, en fazla 5 kullanıcı.
- `/playlists/{id}/tracks` kalktı, yerine `/items`: yalnız kullanıcının sahibi ya da ortağı olduğu playlist'ler,
  diğerleri 403. Başkasının playlist'indeki kaldırılmış şarkıları STILLMORE (Spotify istemcisinin içinden) bulur,
  Yanki CSV'sini okur.
- Arama `limit` en fazla 10 (önce 50); derinlik `offset` ile.

Anahtarlar ortam değişkeninden ya da proje kökündeki `.env`'den okunur (gitignore'da).

Kota (2026-10-09, kendi ölçümümüz): bir günde ~1.000 istekten sonra uygulama 429 + `Retry-After: 83595` (23 saat)
aldı; STILLMORE'da 13 saat ölçülmüştü. Bu yüzden `calisma/.spotify_kota.json`:
- **kilit:** uzun 429'un bitiş zamanı kalıcı yazılır; kilit sürerken hiç istek atılmaz (gece koşusu, elle komut, hepsi).
- **günlük tavan:** `GUNLUK_BUTCE` istekten sonra gün bitene kadar `KotaDoldu`.
Kısa 429'da (≤ 10 sn) bir kez beklenip tekrar denenir.
"""

import base64
import hashlib
import json
import os
import secrets
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

API = "https://api.spotify.com/v1"
HESAP = "https://accounts.spotify.com"
YONLENDIRME = "http://127.0.0.1:8766/callback"  # Spotify `localhost`u reddediyor, 127.0.0.1 döngü adresini kabul ediyor
KAPSAM = "playlist-read-private playlist-read-collaborative"
KISA_BEKLEME_SN = 10  # Retry-After bundan kısaysa bekleyip bir kez daha dene
ARALIK_SN = 0.5  # ardışık istekler arası en az bekleme (30 sn'lik kayan pencereyi toplu taramada doldurmamak için)
GUNLUK_BUTCE = 400  # günde en fazla istek (token hariç); 2026-10-09'da ~1.000'de 23 saatlik kilit


class SpotifyHatasi(RuntimeError):
    pass


class Sinirli(SpotifyHatasi):
    def __init__(self, sn: int, neden: str = ""):
        saat = f" (~{sn / 3600:.1f} saat)" if sn >= 3600 else ""
        super().__init__(f"Spotify istek sınırı: {sn} sn{saat} sonra tekrar dene" + (f" [{neden}]" if neden else ""))
        self.sn = sn


class KotaDoldu(Sinirli):
    pass


class AyarYok(SpotifyHatasi):
    pass


def env_oku(kok: Path) -> dict[str, str]:
    """Ortam değişkenleri `.env`'yi ezer."""
    degerler: dict[str, str] = {}
    yol = kok / ".env"
    if yol.exists():
        for satir in yol.read_text(encoding="utf-8-sig").splitlines():
            satir = satir.strip()
            if satir and not satir.startswith("#") and "=" in satir:
                k, v = satir.split("=", 1)
                degerler[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "SPOTIFY_REDIRECT_URI"):
        if os.environ.get(k):
            degerler[k] = os.environ[k]
    return degerler


class Spotify:
    def __init__(self, kok: Path, client_id: str = "", client_secret: str = "", yonlendirme: str = "",
                 gunluk_butce: int = GUNLUK_BUTCE):
        e = env_oku(kok) if not client_id else {}
        self.client_id = client_id or e.get("SPOTIFY_CLIENT_ID", "")
        self.client_secret = client_secret or e.get("SPOTIFY_CLIENT_SECRET", "")
        self.yonlendirme = yonlendirme or e.get("SPOTIFY_REDIRECT_URI", "") or YONLENDIRME
        self.token_yolu = kok / "calisma" / ".spotify.json"
        self._uygulama: tuple[str, float] | None = None
        self._son_istek = 0.0
        self.aralik_sn = ARALIK_SN
        self.istek_sayisi = 0  # bu nesnenin API istekleri (token hariç): keşif bütçesi buna bakar
        self.kota_yolu = kok / "calisma" / ".spotify_kota.json"
        self.gunluk_butce = gunluk_butce

    # ── Kota ────────────────────────────────────────────────
    def kota(self) -> dict:
        try:
            k = json.loads(self.kota_yolu.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            k = {}
        bugun = time.strftime("%Y-%m-%d")
        if k.get("gun") != bugun:
            k = {"gun": bugun, "sayi": 0, "kilit": k.get("kilit", 0), "neden": k.get("neden", "")}
        return k

    def _kota_yaz(self, k: dict) -> None:
        self.kota_yolu.parent.mkdir(parents=True, exist_ok=True)
        gecici = self.kota_yolu.with_suffix(".tmp")
        gecici.write_text(json.dumps(k), encoding="utf-8")
        gecici.replace(self.kota_yolu)

    def kilitle(self, sn: int, neden: str = "") -> None:
        k = self.kota()
        k["kilit"], k["neden"] = time.time() + sn, neden
        self._kota_yaz(k)

    def kota_kontrol(self) -> dict:
        """İstek atmadan önce: kilit ya da günlük tavan varsa istek atılmadan fırlatır."""
        k = self.kota()
        kalan = int(k.get("kilit", 0) - time.time())
        if kalan > 0:
            raise Sinirli(kalan, k.get("neden") or "kayıtlı kilit")
        if k["sayi"] >= self.gunluk_butce:
            gece = time.mktime(time.strptime(k["gun"], "%Y-%m-%d")) + 86400
            raise KotaDoldu(int(gece - time.time()), f"günlük tavan {self.gunluk_butce} istek")
        return k

    # ── HTTP ────────────────────────────────────────────────
    def _http(self, yontem: str, url: str, basliklar: dict, veri: bytes | None = None) -> tuple[int, dict, bytes]:
        istek = urllib.request.Request(url, data=veri, headers=basliklar, method=yontem)
        try:
            with urllib.request.urlopen(istek, timeout=30) as r:
                return r.status, dict(r.headers), r.read()
        except urllib.error.HTTPError as h:
            return h.code, dict(h.headers or {}), h.read() or b""

    def _form(self, url: str, alanlar: dict, yetki: str | None = None) -> dict:
        basliklar = {"Content-Type": "application/x-www-form-urlencoded"}
        if yetki:
            basliklar["Authorization"] = yetki
        kod, _, govde = self._http("POST", url, basliklar, urllib.parse.urlencode(alanlar).encode())
        if kod != 200:
            raise SpotifyHatasi(f"token isteği {kod}: {govde[:200].decode(errors='replace')}")
        return json.loads(govde)

    def _get(self, yol: str, parametre: dict | None, token: str) -> dict:
        url = yol if yol.startswith("http") else API + yol
        if parametre:
            url += ("&" if "?" in url else "?") + urllib.parse.urlencode(parametre)
        for deneme in range(2):
            k = self.kota_kontrol()
            bekle = self._son_istek + self.aralik_sn - time.monotonic()
            if bekle > 0:
                time.sleep(bekle)
            self._son_istek = time.monotonic()
            self.istek_sayisi += 1
            k["sayi"] += 1
            self._kota_yaz(k)
            kod, basliklar, govde = self._http("GET", url, {"Authorization": f"Bearer {token}"})
            if kod == 200:
                return json.loads(govde)
            if kod == 429:
                sn = int({k.lower(): v for k, v in basliklar.items()}.get("retry-after", "60") or 60)
                if sn <= KISA_BEKLEME_SN and deneme == 0:
                    time.sleep(sn + 1)
                    continue
                try:
                    neden = (json.loads(govde or b"{}").get("error") or {}).get("reason") or ""
                except ValueError:
                    neden = ""
                self.kilitle(sn, neden or "429")
                raise Sinirli(sn, neden)
            if kod in (500, 502, 503) and deneme == 0:
                time.sleep(3)
                continue
            raise SpotifyHatasi(f"GET {url.split('?')[0]} → {kod}: {govde[:200].decode(errors='replace')}")
        raise AssertionError("ulaşılmaz")

    # ── Token'lar ───────────────────────────────────────────
    def uygulama_token(self) -> str:
        if self._uygulama and self._uygulama[1] > time.time() + 60:
            return self._uygulama[0]
        if not (self.client_id and self.client_secret):
            raise AyarYok("SPOTIFY_CLIENT_ID ve SPOTIFY_CLIENT_SECRET yok (.env ya da ortam değişkeni)")
        self.kota_kontrol()  # kilitliyken token isteği de atılmaz
        yetki = base64.b64encode(f"{self.client_id}:{self.client_secret}".encode()).decode()
        t = self._form(f"{HESAP}/api/token", {"grant_type": "client_credentials"}, f"Basic {yetki}")
        self._uygulama = (t["access_token"], time.time() + int(t.get("expires_in", 3600)))
        return self._uygulama[0]

    def baglanti_adresi(self) -> tuple[str, str, str]:
        """PKCE: (yetki adresi, doğrulayıcı, durum)."""
        if not self.client_id:
            raise AyarYok("SPOTIFY_CLIENT_ID yok (.env ya da ortam değişkeni)")
        dogrulayici = secrets.token_urlsafe(64)[:96]
        meydan = base64.urlsafe_b64encode(hashlib.sha256(dogrulayici.encode()).digest()).rstrip(b"=").decode()
        durum = secrets.token_urlsafe(16)
        adres = f"{HESAP}/authorize?" + urllib.parse.urlencode({
            "client_id": self.client_id, "response_type": "code", "redirect_uri": self.yonlendirme,
            "code_challenge_method": "S256", "code_challenge": meydan, "scope": KAPSAM, "state": durum,
        })
        return adres, dogrulayici, durum

    def kodu_degistir(self, kod: str, dogrulayici: str) -> None:
        t = self._form(f"{HESAP}/api/token", {
            "grant_type": "authorization_code", "code": kod, "redirect_uri": self.yonlendirme,
            "client_id": self.client_id, "code_verifier": dogrulayici,
        })
        self._token_yaz(t, None)

    def _token_yaz(self, t: dict, eski_yenileme: str | None) -> None:
        self.token_yolu.parent.mkdir(parents=True, exist_ok=True)
        kayit = {"access_token": t["access_token"], "refresh_token": t.get("refresh_token") or eski_yenileme,
                 "bitis": time.time() + int(t.get("expires_in", 3600))}
        gecici = self.token_yolu.with_suffix(".tmp")
        gecici.write_text(json.dumps(kayit), encoding="utf-8")
        gecici.replace(self.token_yolu)

    def bagli_mi(self) -> bool:
        return self.token_yolu.exists()

    def kullanici_token(self) -> str:
        if not self.token_yolu.exists():
            raise AyarYok("Spotify hesabı bağlı değil: `uv run yanki spotify-baglan`")
        k = json.loads(self.token_yolu.read_text(encoding="utf-8"))
        if k["bitis"] > time.time() + 60:
            return k["access_token"]
        self.kota_kontrol()
        t = self._form(f"{HESAP}/api/token", {"grant_type": "refresh_token", "refresh_token": k["refresh_token"],
                                              "client_id": self.client_id})
        self._token_yaz(t, k["refresh_token"])
        return t["access_token"]

    # ── Uçlar ───────────────────────────────────────────────
    def ara(self, sorgu: str, market: str, adet: int = 10) -> list[dict]:
        """İlk `adet` sonuç; sayfa başı 10 (Şubat 2026 sınırı), fazlası `offset` ile ardışık isteklerle."""
        sonuc: list[dict] = []
        while len(sonuc) < adet:
            limit = min(10, adet - len(sonuc))
            d = self._get("/search", {"q": sorgu, "type": "track", "market": market, "limit": limit,
                                      "offset": len(sonuc)}, self.uygulama_token())
            sayfa = [x for x in (d.get("tracks") or {}).get("items") or [] if x]
            sonuc += sayfa
            if len(sayfa) < limit:
                break
        return sonuc

    def isrc_ara(self, isrc: str, market: str) -> list[dict]:
        return self.ara(f"isrc:{isrc}", market)

    def parca(self, parca_id: str, market: str) -> dict:
        return self._get(f"/tracks/{parca_id}", {"market": market}, self.uygulama_token())

    def playlist(self, playlist_id: str) -> dict:
        return self._get(f"/playlists/{playlist_id}", {"fields": "name,snapshot_id"}, self.kullanici_token())

    def playlist_parcalari(self, playlist_id: str, market: str):
        """Kullanıcı token'ıyla tüm sayfalar → parça nesneleri. `market` verilince çalınamayan parça
        `is_playable: false` döner. Yalnız kendi/ortak playlist'ler (başkasınınki 403)."""
        token = self.kullanici_token()
        url: str | None = f"{API}/playlists/{playlist_id}/items"
        parametre: dict | None = {"market": market, "limit": 50, "additional_types": "track"}
        while url:
            try:
                d = self._get(url, parametre, token)
            except SpotifyHatasi as e:
                if "→ 403" in str(e):
                    raise SpotifyHatasi("playlist okunamadı (403): Web API yalnız kendi ya da ortak olduğun "
                                        "playlist'leri veriyor; başkasınınki için STILLMORE CSV'si") from e
                raise
            for g in d.get("items") or []:
                t = (g or {}).get("item") or (g or {}).get("track")  # Şubat 2026'da alan adı değişti, ikisi de
                if t and t.get("type") == "track" and not g.get("is_local"):
                    yield t
            url, parametre = d.get("next"), None


def kimlik_ayikla(metin: str, tur: str = "playlist") -> str:
    """URL, URI ya da çıplak kimlik → 22 karakterlik Spotify kimliği."""
    metin = metin.strip()
    for ayrac in (f"open.spotify.com/{tur}/", f"spotify:{tur}:"):
        if ayrac in metin:
            metin = metin.split(ayrac, 1)[1]
            break
    metin = metin.split("?")[0].split("/")[0]
    if len(metin) != 22 or not metin.isalnum():
        raise ValueError(f"Spotify {tur} kimliği değil: {metin!r}")
    return metin
