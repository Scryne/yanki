"""STILLMORE köprüsü: Spotify istemcisinin içindeki STILLMORE FINDER'a CDP ile playlist taraması yaptırmak.

Neden: başkasının (ve Spotify'ın editoryal) playlist'lerini Web API Şubat 2026'dan beri vermiyor; STILLMORE ise
istemcinin kendi `PlaylistAPI`'siyle her playlist'i okuyor ve kaldırılmış her parça için neden, kaldırılmadan önceki
Spotify dinlenmesi, ISRC, sanatçının aylık dinleyicisi ve aynı ISRC'nin çalınabilir yeniden yüklemesini veriyor
(`window.Stillmore.playlist.scan`, stillmore-finder.js v12.1). CSV'yi elle indirmek yerine Yanki bunu gece kendisi
çağırır; Web API kotası harcanmaz (istekler istemcinin kendi iç uçlarına gider).

Spotify'ın CDP portuyla (`--remote-debugging-port`) açık olması gerekir. Gece koşusu: Spotify kapalıysa bayrakla açar,
tarar, kapatır; açık ama bayraksızsa ve çalmıyorsa yeniden başlatır (tarama bitince bayraksız açar); bir şey çalıyorsa
dokunmaz (Scryne dinliyor). Kurulum: STILLMORE eklentisi (`C:\\df-archive`, `docs/arastirma/03`).
"""

import json
import os
import subprocess
import time
import urllib.request
from pathlib import Path

PORT = 9222
SPOTIFY = Path(os.environ.get("APPDATA", "")) / "Spotify" / "Spotify.exe"


class StillmoreYok(RuntimeError):
    pass


# ── Spotify süreci ──────────────────────────────────────────
def cdp_acik(port: int = PORT) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=2):
            return True
    except OSError:
        return False


def _pencere_basliklari() -> list[str]:
    cikti = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         "Get-Process Spotify -ErrorAction SilentlyContinue | Where-Object { $_.MainWindowTitle } | "
         "ForEach-Object { $_.MainWindowTitle }"], capture_output=True, text=True, encoding="utf-8", timeout=20)
    return [x.strip() for x in cikti.stdout.splitlines() if x.strip()]


def calisiyor_mu() -> bool:
    cikti = subprocess.run(["tasklist", "/FI", "IMAGENAME eq Spotify.exe", "/NH"], capture_output=True, text=True,
                           timeout=20)
    return "Spotify.exe" in cikti.stdout


def caliyor_mu() -> bool:
    """Çalarken pencere başlığı "Sanatçı - Şarkı", dururken "Spotify" / "Spotify Premium" / "Spotify Free"."""
    return any(not b.startswith("Spotify") for b in _pencere_basliklari())


def kapat() -> None:
    subprocess.run(["taskkill", "/IM", "Spotify.exe", "/F"], capture_output=True, timeout=30)
    time.sleep(3)


def ac(cdp: bool, port: int = PORT, bekle_sn: int = 60) -> None:
    if not SPOTIFY.exists():
        raise StillmoreYok(f"Spotify bulunamadı: {SPOTIFY}")
    arg = [f"--remote-debugging-port={port}", "--remote-allow-origins=*", "--minimized"] if cdp else ["--minimized"]
    subprocess.Popen([str(SPOTIFY), *arg], creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
    if not cdp:
        return
    for _ in range(bekle_sn):
        if cdp_acik(port):
            return
        time.sleep(1)
    raise StillmoreYok("Spotify CDP portu açılmadı")


class Oturum:
    """Bağlam yöneticisi: Spotify'ı CDP ile hazırlar, çıkarken eski hâline getirir.
    `yeniden_baslat`: açık ama bayraksız Spotify'ı (çalmıyorsa) kapatıp bayrakla açmaya izin (gece koşusu)."""

    def __init__(self, yeniden_baslat: bool = False, port: int = PORT):
        self.yeniden_baslat, self.port = yeniden_baslat, port
        self.biz_actik = False
        self.bayraksiz_geri_ac = False

    def __enter__(self) -> "Kopru":
        if not cdp_acik(self.port):
            if calisiyor_mu():
                if not self.yeniden_baslat:
                    raise StillmoreYok("Spotify CDP portu olmadan açık (gece koşusu yeniden başlatır)")
                if caliyor_mu():
                    raise StillmoreYok("Spotify şu an çalıyor; tarama atlandı (dinleme kesilmesin)")
                kapat()
                self.bayraksiz_geri_ac = True
            else:
                self.biz_actik = True
            ac(cdp=True, port=self.port)
        k = Kopru(self.port)
        k.hazir_bekle()
        return k

    def __exit__(self, *_):
        if self.biz_actik or self.bayraksiz_geri_ac:
            kapat()
        if self.bayraksiz_geri_ac:
            ac(cdp=False)


# ── CDP ─────────────────────────────────────────────────────
class Kopru:
    def __init__(self, port: int = PORT):
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=5) as r:
            sayfalar = json.load(r)
        ana = next((p for p in sayfalar if p.get("type") == "page" and "xpui" in p.get("url", "")), None)
        if ana is None:
            raise StillmoreYok("Spotify arayüz sayfası bulunamadı")
        self.ws_adres = ana["webSocketDebuggerUrl"]
        self._id = 0

    def degerlendir(self, ifade: str, zaman_asimi: float = 120):
        """JS ifadesini çalıştırır (Promise beklenir), JSON'a çevrilebilir değeri döndürür."""
        from websockets.sync.client import connect

        with connect(self.ws_adres, max_size=64 * 1024 * 1024, open_timeout=10) as ws:
            self._id += 1
            ws.send(json.dumps({"id": self._id, "method": "Runtime.evaluate", "params": {
                "expression": ifade, "awaitPromise": True, "returnByValue": True, "timeout": int(zaman_asimi * 1000)}}))
            bitis = time.monotonic() + zaman_asimi + 10
            while time.monotonic() < bitis:
                m = json.loads(ws.recv(timeout=zaman_asimi + 10))
                if m.get("id") != self._id:
                    continue
                r = m.get("result", {})
                if "exceptionDetails" in r:
                    hata = r["exceptionDetails"].get("exception", {}).get("description") or r["exceptionDetails"]
                    raise StillmoreYok(f"STILLMORE hatası: {str(hata)[:300]}")
                return r.get("result", {}).get("value")
        raise StillmoreYok("CDP cevabı zaman aşımına uğradı")

    def hazir_bekle(self, sn: int = 60) -> None:
        for _ in range(sn):
            try:
                if self.degerlendir("!!(window.Stillmore && window.Stillmore.playlist)", 5):
                    return
            except Exception:  # noqa: BLE001 — sayfa daha yükleniyor
                pass
            time.sleep(1)
        raise StillmoreYok("STILLMORE eklentisi Spotify'da yüklenmedi (yama silinmiş olabilir: \\STILLMORE\\Onarim)")

    def playlist_bilgi(self, playlist_id: str) -> dict:
        return self.degerlendir(f"Stillmore.playlist.info({json.dumps(playlist_id)})", 30)

    def kaldirilanlar(self, playlist_id: str, zaman_asimi: float = 600) -> list[dict]:
        """Playlist'teki çalınamayan parçalar, STILLMORE'un incelemesiyle (neden, dinlenme, ISRC, yeniden yükleme)."""
        ifade = f"""(async () => {{
          const r = await Stillmore.playlist.scan({json.dumps(playlist_id)});
          return r.rows.filter(x => x.playable === false).map(x => ({{
            trackId: x.trackId, name: x.name, artist: x.artist, album: x.album, addedAt: x.addedAt,
            reason: x.removed && x.removed.reasonCode, plays: x.removed ? x.removed.plays : null,
            isrc: (x.removed && x.removed.isrc) || x.isrc || null, releaseDate: x.removed && x.removed.releaseDate,
            artistListeners: x.removed && x.removed.artistListeners,
            reuploads: ((x.removed && x.removed.reuploads) || []).map(u => u.id)
          }}));
        }})()"""
        return self.degerlendir(ifade, zaman_asimi) or []


def adaylara(satirlar: list[dict], playlist_id: str):
    """STILLMORE satırları → keşif adayları. Aynı ISRC'nin çalınabilir yeniden yüklemesi varsa boşluk yok, atlanır."""
    from yanki.kesif import Aday

    adaylar = []
    for x in satirlar:
        if x.get("reuploads") or not x.get("name") or not x.get("artist"):
            continue
        adaylar.append(Aday(
            sanatci=x["artist"].split(",")[0].strip(), ad=x["name"].strip(), kaynak=f"stillmore:{playlist_id}",
            spotify_id=x.get("trackId"), isrc=(x.get("isrc") or "").upper() or None, album=x.get("album") or None,
            cikis=x.get("releaseDate") or None, neden="kismi" if x.get("reason") == "country" else "kaldirildi",
            spotify_dinlenme=x.get("plays") if isinstance(x.get("plays"), int) else None,
        ))
    return adaylar


# ── Taranacak playlist havuzu ───────────────────────────────
def havuz_yolu(calisma: Path) -> Path:
    return calisma / "kesif" / "stillmore.json"


def havuz_oku(calisma: Path) -> dict[str, dict]:
    yol = havuz_yolu(calisma)
    return json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}


def havuz_yaz(calisma: Path, havuz: dict[str, dict]) -> None:
    yol = havuz_yolu(calisma)
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(havuz, ensure_ascii=False, indent=1), encoding="utf-8")


def havuza_ekle(havuz: dict[str, dict], playlist_id: str, ad: str, kaynak: str, toplam: int | None = None) -> bool:
    if playlist_id in havuz:
        return False
    havuz[playlist_id] = {"ad": ad, "kaynak": kaynak, "toplam": toplam, "son_tarama": None, "calinamayan": None,
                          "aday": None}
    return True


def sec(havuz: dict[str, dict], adet: int, tazeleme_gun: int, simdi=None) -> list[str]:
    """Hiç taranmamışlar önce, sonra en eski taranan; son `tazeleme_gun` içinde taranan atlanır."""
    from datetime import datetime, timedelta

    simdi = simdi or datetime.now()
    sinir = simdi - timedelta(days=tazeleme_gun)
    uygun = [(v.get("son_tarama") or "", k) for k, v in havuz.items()
             if not v.get("son_tarama") or datetime.fromisoformat(v["son_tarama"]) < sinir]
    return [k for _, k in sorted(uygun)][:adet]
