"""Kaynak ses: önce `girdi/kaynak/<kimlik>.*` (Scryne bıraktıysa), yoksa YouTube.

Bu ağda googlevideo düğümü TCP üzerinden TLS'i kesiyor, QUIC çalışıyor (spike S8): yt-dlp yalnız adayları ve medya
adresini bulur, medya curl_cffi ile HTTP/3 üzerinden Range parçalarıyla iner.

Süre kontrolü: LRCLIB'deki kayıt süresiyle ±TOLERANS sn. SoundCloud'daki gibi 30 sn önizlemeler, canlı kayıtlar ve
uzatılmış klipler bu kapıda düşer.
"""

import re
from dataclasses import dataclass
from pathlib import Path

from yanki import ses

TOLERANS_SN = 4.0
SES_UZANTILARI = (".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus", ".aac")
ISTENMEYEN = re.compile(
    r"\b(live|concert|cover|karaoke|remix|instrumental|sped ?up|slowed|nightcore|8d|reverb|acoustic version|"
    r"piano version|1 hour|loop|reaction)\b",
    re.I,
)
PARCA = 4 * 1024 * 1024
# Önce Opus (YouTube 251, ~130 kbps, 20 kHz'e kadar tam bant), yoksa AAC (140, 128 kbps; 16 kHz'te kesiyor: kaynak
# kayıtlarda 16–18 kHz bandı −85 dB ölçüldü, 2026-10-11). Kaynak ACE-Step'in anlamsal kodlarına ve eğitime gider.
BICIM = "bestaudio[acodec=opus]/bestaudio[ext=m4a]/bestaudio"


class KaynakYok(LookupError):
    pass


@dataclass(frozen=True)
class Kaynak:
    wav: Path
    nereden: str  # "klasor" | "youtube:<id>"
    baslik: str
    sure_sn: float


@dataclass(frozen=True)
class Aday:
    id: str
    baslik: str
    sure_sn: float | None
    kanal: str = ""


def sec(adaylar: list[Aday], beklenen_sn: float | None) -> Aday:
    """İstenmeyen sürümleri (canlı, cover, remix…) at; beklenen süreye en yakın olanı seç."""
    temiz = [a for a in adaylar if not ISTENMEYEN.search(a.baslik)]
    if beklenen_sn is not None:
        temiz = [a for a in temiz if a.sure_sn is not None and abs(a.sure_sn - beklenen_sn) <= TOLERANS_SN]
        temiz.sort(key=lambda a: abs(a.sure_sn - beklenen_sn))
    if not temiz:
        raise KaynakYok(f"uygun video yok (beklenen süre {beklenen_sn}, {len(adaylar)} aday)")
    return temiz[0]


def klasorden(klasor: Path, kimlik: str) -> Path | None:
    for uz in SES_UZANTILARI:
        if (yol := klasor / f"{kimlik}{uz}").exists():
            return yol
    return None


def youtube_adaylari(sorgu: str, adet: int = 8) -> list[Aday]:
    import yt_dlp

    from yanki import sayac

    hedef = sorgu if sorgu.startswith("http") else f"ytsearch{adet}:{sorgu}"
    try:
        with yt_dlp.YoutubeDL(_ydl_ayar(extract_flat=True)) as ydl:
            bilgi = ydl.extract_info(hedef, download=False)
    except Exception:
        sayac.say("YouTube", False)
        raise
    sayac.say("YouTube", True)
    girdiler = bilgi.get("entries") or [bilgi]
    return [Aday(g["id"], g.get("title") or "", g.get("duration"), g.get("channel") or g.get("uploader") or "")
            for g in girdiler if g]


def youtube_indir(video_id: str, hedef: Path, deneme: int = 3, bekleme_sn: float = 10.0, bicim: str = BICIM) -> Path:
    """İlk parçada boş/403 dönen indirmeler (2026-10-08 gecesi 12 şarkının 2'si, 0 bayt) yeni imzalı adresle
    tekrar denenir."""
    import time

    from yanki import sayac

    for i in range(deneme):
        try:
            sonuc = _indir_bir(video_id, hedef, bicim)
            sayac.say("YouTube indirme", True)
            return sonuc
        except OSError:
            sayac.say("YouTube indirme", False)
            if i == deneme - 1:
                raise
            time.sleep(bekleme_sn * (i + 1))
    raise AssertionError("ulaşılmaz")


def _indir_bir(video_id: str, hedef: Path, bicim: str = BICIM) -> Path:
    import yt_dlp
    from curl_cffi import CurlHttpVersion, requests

    with yt_dlp.YoutubeDL(_ydl_ayar(format=bicim)) as ydl:
        bilgi = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=False)
    url, boyut = bilgi["url"], bilgi.get("filesize") or bilgi.get("filesize_approx")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    son = ""
    with requests.Session(impersonate="chrome") as s, open(hedef, "wb") as f:
        bas = 0
        while boyut is None or bas < boyut:
            r = s.get(url, headers={"Range": f"bytes={bas}-{bas + PARCA - 1}"},
                      http_version=CurlHttpVersion.V3ONLY, timeout=60)
            if r.status_code not in (200, 206) or not r.content:
                son = f", HTTP {r.status_code}"
                break
            f.write(r.content)
            bas += len(r.content)
            if len(r.content) < PARCA:
                break
    if boyut and bas < boyut:
        raise OSError(f"eksik indirme: {bas}/{boyut} bayt{son}")
    if bas == 0:  # boyutu bilinmeyen videoda ilk parça boş/403: yeniden denensin, boş dosya kaynak sayılmasın
        raise OSError(f"boş indirme{son}")
    return hedef


def _ydl_ayar(**ek) -> dict:
    # JS çalışma zamanı: deno kurulu değil, node var (yt-dlp-ejs ile YouTube imza çözümü)
    return {"quiet": True, "no_warnings": True, "noplaylist": True, "js_runtimes": {"node": {}}, **ek}


def hazirla(kimlik: str, sanatci: str, ad: str, beklenen_sn: float | None, klasor: Path, calisma: Path,
            youtube: str | None = None) -> Kaynak:
    hedef = calisma / "kaynak.wav"
    if yerel := klasorden(klasor, kimlik):
        ses.wav48(yerel, hedef)
        nereden, baslik = "klasor", yerel.name
    else:
        adaylar = youtube_adaylari(youtube or f"{sanatci} {ad} official audio")
        # Scryne videoyu sabitlediyse süre kapısı uyarıya döner, seçim yine de onun videosu
        secilen = adaylar[0] if youtube else sec(adaylar, beklenen_sn)
        ham = youtube_indir(secilen.id, calisma / "kaynak_ham.indirilen")  # Opus/WebM ya da AAC: ffmpeg içeriğe bakar
        ses.wav48(ham, hedef)
        ham.unlink(missing_ok=True)
        nereden, baslik = f"youtube:{secilen.id}", secilen.baslik
    sure = ses.sure(hedef)
    if beklenen_sn is not None and abs(sure - beklenen_sn) > TOLERANS_SN and not youtube:
        raise KaynakYok(f"kaynak süresi {sure:.1f} sn, beklenen {beklenen_sn:.1f} sn (önizleme ya da farklı sürüm)")
    return Kaynak(hedef, nereden, baslik, sure)
