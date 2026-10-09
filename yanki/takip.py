"""Yayın takibi: yüklenen parçalar Spotify'da çıktı mı, adı arandığında kaçıncı sırada?

Her yüklenen şarkı için (ISRC paketin `metadata.json` → `yukleme`'sinde):
- **Canlı mı:** ISRC araması `market`te çalınabilir bir parça döndürüyor mu. İlk görüldüğünde aşama
  `yuklendi → yayinda`. Önceden canlıyken artık bulunmuyorsa `kayip` işaretlenir (kaldırılmış olabilir).
- **Arama sırası:** şarkının adı (dinleyicinin yazacağı gibi, sanatçısız) arandığında bizim parça kaçıncı; her pazarda
  ayrı (arama sonuçları ülkeye göre değişir; global çalışılıyor, Scryne 2026-10-09). Kaldırılmış şarkı stratejisinin
  (bkz. `kesif.py`) başarı ölçüsü bu.
- **Profil:** sanatçı adımızın Spotify kimliği. Her yüklemede "yeni profil" açıldı (RouteNote, 2026-10-08); birden
  fazla kimlik görülürse profil bölünmüş demektir.

Sonuç şarkının `durum.json` → `yayin` alanında: `son` (en son kontrol) ve `gecmis` (sıra değişimi).
"""

import json
from datetime import datetime
from pathlib import Path

from yanki import durum
from yanki.kesif import sade_ad

GECMIS_SINIRI = 60


def yukleme_bilgisi(calisma: Path, kimlik: str) -> dict | None:
    yol = durum.klasor(calisma, kimlik) / "paket" / "metadata.json"
    if not yol.exists():
        return None
    return json.loads(yol.read_text(encoding="utf-8")).get("yukleme")


def kontrol_et(sp, d: durum.Durum, isrc: str, sanatci_adi: str, pazarlar, arama_limiti: int = 20) -> dict:
    """Tek şarkı: ISRC araması (ana pazar, yayınladığımız bir pazar olmalı) + her pazarda ad araması."""
    if isinstance(pazarlar, str):
        pazarlar = (pazarlar,)
    market = pazarlar[0]
    son: dict = {"zaman": datetime.now().isoformat(timespec="seconds"), "market": market, "canli": False,
                 "spotify_id": None, "sanatci_id": None, "arama_sirasi": None, "siralar": {},
                 "arama_limiti": arama_limiti}
    bizim = None
    for t in sp.isrc_ara(isrc, market):
        if t.get("is_playable") is not False and (t.get("external_ids") or {}).get("isrc", isrc).upper() == isrc:
            bizim = t
            break
    if bizim:
        son["canli"], son["spotify_id"] = True, bizim["id"]
        son["sanatci_id"] = next((a.get("id") for a in bizim.get("artists") or []
                                  if a.get("name", "").casefold() == sanatci_adi.casefold()), None)
    if not bizim:
        return son  # yayında değilken ad araması boşuna istek
    sade = sade_ad(d.ad)
    for m in pazarlar:
        son["siralar"][m] = None
        for i, t in enumerate(sp.ara(d.ad, m, adet=arama_limiti), 1):
            ayni_parca = t.get("id") == bizim["id"]
            bizim_adla = sade_ad(t.get("name") or "") == sade and any(
                a.get("name", "").casefold() == sanatci_adi.casefold() for a in t.get("artists") or [])
            if ayni_parca or bizim_adla:
                son["siralar"][m] = i
                break
    bulunan = [x for x in son["siralar"].values() if x]
    son["arama_sirasi"] = min(bulunan) if bulunan else None
    return son


def kaydet(d: durum.Durum, son: dict) -> list[str]:
    """Sonucu duruma yazar, dikkat edilmesi gerekenleri döndürür."""
    uyarilar = []
    onceki = (d.yayin or {}).get("son") or {}
    gecmis = list((d.yayin or {}).get("gecmis") or [])
    if son["canli"] and d.asama == "yuklendi":
        d.gec("yayinda")
    son["kayip"] = bool(onceki.get("canli") and not son["canli"])
    if son["kayip"]:
        uyarilar.append("önceden canlıydı, ISRC artık bulunmuyor (kaldırılmış olabilir)")
    if son["canli"] and not son["sanatci_id"]:
        uyarilar.append("parça canlı ama sanatçı adı eşleşmedi")
    if (son["canli"], son.get("siralar")) != (onceki.get("canli"), onceki.get("siralar")):
        gecmis.append({k: son.get(k) for k in ("zaman", "canli", "arama_sirasi", "siralar")})
    d.yayin = {"son": son, "gecmis": gecmis[-GECMIS_SINIRI:]}
    return uyarilar


def takip_et(sp, calisma: Path, sanatci_adi: str, pazarlar, kimlikler: list[str] | None = None,
             arama_limiti: int = 20) -> list[tuple[durum.Durum, list[str]]]:
    sonuc = []
    for d in durum.hepsi(calisma):
        if d.asama not in ("yuklendi", "yayinda") or (kimlikler and d.kimlik not in kimlikler):
            continue
        y = yukleme_bilgisi(calisma, d.kimlik) or {}
        if not y.get("isrc"):
            sonuc.append((d, ["paketin metadata.json'unda ISRC yok (yükleme bilgisi eksik)"]))
            continue
        son = kontrol_et(sp, d, y["isrc"].upper(), sanatci_adi, pazarlar, arama_limiti)
        son["yayin_tarihi"] = y.get("yayin_tarihi")
        uyarilar = kaydet(d, son)
        durum.yaz(calisma, d)
        sonuc.append((d, uyarilar))
    return sonuc


def profil_kimlikleri(calisma: Path) -> set[str]:
    return {k for d in durum.hepsi(calisma) if (k := ((d.yayin or {}).get("son") or {}).get("sanatci_id"))}
