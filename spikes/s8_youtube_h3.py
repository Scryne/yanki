"""S8: YouTube sesini HTTP/3 ile indir.

Bu ağda googlevideo düğümü (ISS içi önbellek) TCP üzerinden TLS'i kesiyor; Chrome'un kullandığı QUIC çalışıyor.
yt-dlp adresi ve boyutu bulur, medya curl_cffi ile HTTP/3 üzerinden parça parça (Range) iner.

  uv run --no-project --with curl_cffi --with yt-dlp python spikes/s8_youtube_h3.py "<arama ya da URL>" <cikti.m4a>
"""

import sys
import time

import yt_dlp
from curl_cffi import CurlHttpVersion, requests

PARCA = 4 * 1024 * 1024


def main() -> None:
    sorgu, hedef = sys.argv[1], sys.argv[2]
    with yt_dlp.YoutubeDL({"format": "bestaudio[ext=m4a]/bestaudio", "quiet": True, "noplaylist": True}) as ydl:
        bilgi = ydl.extract_info(sorgu if sorgu.startswith("http") else f"ytsearch1:{sorgu}", download=False)
        if "entries" in bilgi:
            bilgi = bilgi["entries"][0]
    url, boyut = bilgi["url"], bilgi.get("filesize") or bilgi.get("filesize_approx")
    print(f"{bilgi['title']} | {bilgi['duration']} sn | {bilgi['ext']} | {boyut} bayt")
    t = time.time()
    with requests.Session(impersonate="chrome") as s, open(hedef, "wb") as f:
        bas = 0
        while boyut is None or bas < boyut:
            r = s.get(url, headers={"Range": f"bytes={bas}-{bas + PARCA - 1}"}, http_version=CurlHttpVersion.V3ONLY,
                      timeout=60)
            if r.status_code not in (200, 206) or not r.content:
                break
            f.write(r.content)
            bas += len(r.content)
            if len(r.content) < PARCA:
                break
    print(f"indi: {bas} bayt, {time.time() - t:.1f} sn")


if __name__ == "__main__":
    main()
