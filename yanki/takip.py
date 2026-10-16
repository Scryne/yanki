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
import re
from datetime import date, datetime, timedelta
from pathlib import Path

from yanki import dosya, durum, performans, spotify
from yanki.kesif import sade_ad

GECMIS_SINIRI = 60


def yukleme_bilgisi(calisma: Path, kimlik: str) -> dict | None:
    yol = durum.klasor(calisma, kimlik) / "paket" / "metadata.json"
    if not yol.exists():
        return None
    return json.loads(yol.read_text(encoding="utf-8")).get("yukleme")


ISRC = re.compile(r"[A-Z]{2}[A-Z0-9]{3}\d{7}")
UPC = re.compile(r"\d{12,13}")
# RouteNote kararı (Scryne, 2026-10-07): mekanik lisans yok → bu bölgeler hariç; AI/cover kabul etmeyen mağazalar
# kaldırılır (YUKLE.md 24–26. adımlar). İlk üç yüklemenin kaydıyla aynı.
ROUTENOTE_VARSAYILAN = {"mekanik_lisans": False, "haric_bolgeler": ["US", "CA", "MX", "IN", "PK"],
                        "haric_magazalar": ["Amazon", "Melon", "Bugs!", "VIBE", "FLO", "Genie Music",
                                            "YouTube Content ID"]}


def yukleme_dogrula(isrc: str | None = None, upc: str | None = None, yayin_tarihi: str | None = None,
                    onizleme: str | None = None) -> dict:
    """Formdan kopyalanan değerleri temizler ve doğrular (ISRC'deki tireler atılır); hatalıysa ValueError."""
    bilgi: dict = {}
    if isrc:
        bilgi["isrc"] = isrc.replace("-", "").replace(" ", "").upper()
        if not ISRC.fullmatch(bilgi["isrc"]):
            raise ValueError(f"ISRC biçimi CC-XXX-YY-NNNNN olmalı (12 karakter): {isrc}")
    if upc:
        bilgi["upc"] = upc.strip()
        if not UPC.fullmatch(bilgi["upc"]):
            raise ValueError(f"UPC 12–13 rakam olmalı: {upc}")
    if yayin_tarihi:
        try:
            bilgi["yayin_tarihi"] = date.fromisoformat(yayin_tarihi.strip()).isoformat()
        except ValueError:
            raise ValueError(f"yayın tarihi YYYY-AA-GG olmalı: {yayin_tarihi}") from None
    if onizleme:
        if not re.fullmatch(r"\d{1,2}:[0-5]\d", onizleme.strip()):
            raise ValueError(f"önizleme başlangıcı d:ss olmalı: {onizleme}")
        bilgi["onizleme"] = onizleme.strip()
    return bilgi


def yukleme_kaydet(calisma: Path, kimlik: str, bilgi: dict, dagitimci: str = "") -> dict:
    """Paketin `metadata.json` → `yukleme`'sine yazar (takip ISRC'yi buradan okur). İlk kayıtta tarih ve
    dağıtımcının varsayılanları eklenir; sonraki çağrılar yalnız verilen alanları günceller."""
    yol = durum.klasor(calisma, kimlik) / "paket" / "metadata.json"
    if not yol.exists():
        raise FileNotFoundError(f"paket yok: {yol}")
    meta = json.loads(yol.read_text(encoding="utf-8"))
    yukleme = meta.get("yukleme")
    if yukleme is None:
        yukleme = {"dagitimci": dagitimci or None, "tarih": date.today().isoformat(),
                   **(ROUTENOTE_VARSAYILAN if dagitimci == "routenote" else {})}
    yukleme.update(bilgi)
    meta["yukleme"] = yukleme
    dosya.json_yaz(yol, meta)
    return yukleme


WEB_GUN = 7  # istemcinin bakamadığı pazarların arama sırası (Web API) şarkı başına en sık bu kadar günde bir


def _web_zamani_mi(onceki: dict | None, simdi: datetime, web_gun: int) -> bool:
    z = (onceki or {}).get("web_kontrol")
    return not z or datetime.fromisoformat(z) <= simdi - timedelta(days=web_gun)


def kontrol_et(sp, d: durum.Durum, isrc: str, sanatci_adi: str, pazarlar, arama_limiti: int = 20,
               onceki: dict | None = None, istemci=None, web_gun: int = WEB_GUN, simdi: datetime | None = None) -> dict:
    """Tek şarkı: canlı mı (ISRC araması) + pazar pazar ad aramasında sıra.

    Kota (2026-10-10): şarkı başına her gece ISRC + 6 pazar × 2 sayfa = 13 Web API isteği, ~15 canlı şarkıda günlük
    400 tavanını dolduruyordu. `istemci` (Spotify uygulamasının kendi araması, `stillmore.IstemciArama`) varsa
    canlılık ve hesabın ülkesindeki sıra ondan, kotasız ve her gece; diğer pazarlar Web API'den şarkı başına
    `web_gun`'de bir (arada önceki sıra taşınır). İstemci ISRC'de bulanık eşleşme de döndürebildiği için parça ancak
    sanatçısı bizimse ve adı aynıysa "bizim" sayılır."""
    if isinstance(pazarlar, str):
        pazarlar = (pazarlar,)
    simdi = simdi or datetime.now()
    market = pazarlar[0]
    son: dict = {"zaman": simdi.isoformat(timespec="seconds"), "market": market, "canli": False,
                 "spotify_id": None, "sanatci_id": None, "arama_sirasi": None, "siralar": {},
                 "arama_limiti": arama_limiti, "web_kontrol": (onceki or {}).get("web_kontrol")}
    sade = sade_ad(d.ad)
    bizim_sanatci = lambda t: any(  # noqa: E731
        a.get("name", "").casefold() == sanatci_adi.casefold() for a in t.get("artists") or [])
    bizim = None
    for t in (istemci or sp).isrc_ara(isrc, market):
        if t.get("is_playable") is False:
            continue
        if "external_ids" in t:  # Web API: ISRC kesin
            if (t["external_ids"] or {}).get("isrc", isrc).upper() == isrc:
                bizim = t
                break
        elif bizim_sanatci(t) and sade_ad(t.get("name") or "") == sade:  # istemci: ad + sanatçıyla doğrula
            bizim = t
            break
    if bizim:
        son["canli"], son["spotify_id"] = True, bizim["id"]
        son["sanatci_id"] = next((a.get("id") for a in bizim.get("artists") or []
                                  if a.get("name", "").casefold() == sanatci_adi.casefold()), None)
    if not bizim:
        return son  # yayında değilken ad araması boşuna istek
    istemci_pazari = getattr(istemci, "ulke", None)
    web_zamani = _web_zamani_mi(onceki, simdi, web_gun)
    for m in pazarlar:
        if m == istemci_pazari:
            kaynak = istemci
        elif web_zamani:
            kaynak = sp
        else:
            son["siralar"][m] = ((onceki or {}).get("siralar") or {}).get(m)  # haftalık: önceki ölçüm taşınır
            continue
        son["siralar"][m] = None
        try:
            bulunan_ = kaynak.ara(d.ad, m, adet=arama_limiti)
        except spotify.Sinirli:
            # kota pazar döngüsünde doldu: canlılık zaten bulundu, kaydedilsin (önce bütün takip düşüyordu: hiçbir
            # şarkının yayına çıkışı ya da kalkışı yazılmıyordu); kalan pazarların önceki sırası taşınır
            for k in pazarlar[pazarlar.index(m):]:
                son["siralar"].setdefault(k, ((onceki or {}).get("siralar") or {}).get(k))
            son["siralar"][m] = ((onceki or {}).get("siralar") or {}).get(m)
            web_zamani = False
            break
        for i, t in enumerate(bulunan_, 1):
            if t.get("id") == bizim["id"] or (sade_ad(t.get("name") or "") == sade and bizim_sanatci(t)):
                son["siralar"][m] = i
                break
    if web_zamani and any(m != istemci_pazari for m in pazarlar):
        son["web_kontrol"] = son["zaman"]
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
    d.yayin = {**(d.yayin or {}), "son": son, "gecmis": gecmis[-GECMIS_SINIRI:]}  # dinlenme serisi korunur
    return uyarilar


GECIKME_GUN = 3  # yayın tarihinden bu kadar gün sonra hâlâ yoksa: dağıtımcı reddi ya da gecikme şüphesi


def _siralar_metni(siralar: dict) -> str:
    return ", ".join(f"{m} {s or '—'}" for m, s in (siralar or {}).items())


def olaylar(d: durum.Durum, onceki: dict, son: dict, bugun: date | None = None) -> list[tuple[str, str, str, str]]:
    """Bildirilecek değişiklikler: (tür, başlık, metin, tekrar anahtarı). Arama sırası her gün oynayabilir; yalnız en
    iyi sıra değişince bildirilir."""
    bugun = bugun or date.today()
    sonuc = []
    if son["canli"] and not onceki.get("canli"):
        sonuc.append(("yayinda", f"yayında: {d.ad}", f"Spotify'da çıktı. '{d.ad}' aramasında sıra: "
                      f"{_siralar_metni(son.get('siralar'))}", f"yayinda:{d.kimlik}:{son.get('spotify_id')}"))
    elif son["canli"] and onceki.get("canli") and son.get("arama_sirasi") != onceki.get("arama_sirasi"):
        eski, yeni = onceki.get("arama_sirasi"), son.get("arama_sirasi")
        sonuc.append(("sira", f"arama sırası değişti: {d.ad}",
                      f"en iyi sıra {eski or '—'} → {yeni or '—'} ({_siralar_metni(son.get('siralar'))})",
                      f"sira:{d.kimlik}:{son['zaman'][:10]}:{yeni}"))
    if son.get("kayip"):
        sonuc.append(("kayip", f"Spotify'dan kalktı: {d.ad}", "Önceden canlıydı, ISRC artık bulunmuyor; dağıtımcı "
                      "panelinden bak", f"kayip:{d.kimlik}:{son['zaman'][:10]}"))
    tarih = son.get("yayin_tarihi") or son.get("en_gec_yayin")  # tarihsiz (onaylanınca) yayında incelemenin en geç sonu
    if not son["canli"] and tarih and bugun >= date.fromisoformat(tarih) + timedelta(days=GECIKME_GUN):
        if son.get("dagitimci") == "tunearo":  # red API'den kendiliğinden gelir; burada yalnız gecikme
            ne = (f"Tunearo durumu: {son.get('dagitim_durumu') or '?'}. İnceleme ya da mağazaya teslim uzamış "
                  "olabilir; red gelirse gece yoklaması kendisi bildirir (elle: yanki dagitim-durum)")
        else:
            ne = (f"dağıtımcı panelinde red ya da gecikme olabilir. Reddedildiyse: yanki dagitim-red {d.kimlik} "
                  "--neden …")
        sonuc.append(("gecikme", f"yayın tarihi geçti: {d.ad}", f"{tarih} yayın tarihine rağmen Spotify'da yok: {ne}",
                      f"gecikme:{d.kimlik}:{tarih}"))
    return sonuc


S4A = "https://artists.spotify.com/claim"


def profil_olaylari(calisma: Path, sanatci_adi: str) -> list[tuple[str, str, str, str]]:
    """Sanatçı hesabı adımları, bir kez: ilk parça Spotify'da görülünce profili sahiplenme (Spotify for Artists:
    profil fotoğrafı, biyografi, pitch; giriş gerektirir, insanda); iki yayın canlıyken YouTube resmi sanatçı kanalı
    (OAC: Tunearo en az 2 canlı yayın ve sanatçının kendi YouTube kanalını istiyor)."""
    canli = [d for d in durum.hepsi(calisma) if ((d.yayin or {}).get("son") or {}).get("canli")]
    sonuc = []
    if canli:
        profil = next((k for d in canli if (k := d.yayin["son"].get("sanatci_id"))), None)
        adres = f"https://open.spotify.com/artist/{profil}" if profil else "Spotify'da sanatçı sayfası"
        sonuc.append(("profil", f"{sanatci_adi} Spotify'da: profili sahiplen",
                      f"{S4A} → Claim your profile → {adres}. Profil fotoğrafı yapay zekâyla üretilmiş gerçekçi bir "
                      "insan olmasın (AI Persona etiketi önerilerden çıkarır): soyut görsel ya da logo.",
                      "profil:spotify_for_artists"))
    if len(canli) >= 2:
        sonuc.append(("profil", "YouTube resmi sanatçı kanalı (OAC) açılabilir",
                      f"{sanatci_adi}'in iki yayını canlı. YouTube'da {sanatci_adi} adıyla bir kanal aç (giriş "
                      f"gerektirir), sonra: yanki oac --ana <kanal adresi> --konu <\"{sanatci_adi} - Topic\" "
                      "kanalının adresi>. Konu kanalı ve yayınlar resmi kanalda birleşir.", "profil:oac"))
    return sonuc


def dinlenme_olc(istemci, son: dict) -> int | None:
    """Canlı parçamızın Spotify sayacı, Spotify uygulamasının içinden (STILLMORE; yalnız istemci varken: Web API sayacı
    vermiyor). Ölçülemezse None: dinlenme serisine nokta yazılmaz, takip sürer."""
    from yanki import stillmore

    kopru = getattr(istemci, "kopru", None)
    if kopru is None or not son.get("canli") or not son.get("spotify_id"):
        return None
    try:
        return kopru.dinlenme(son["spotify_id"])
    except stillmore.StillmoreYok as e:
        print(f"  dinlenme okunamadı ({son['spotify_id']}): {e}")
        return None


def takip_et(sp, calisma: Path, sanatci_adi: str, pazarlar, kimlikler: list[str] | None = None,
             arama_limiti: int = 20, bildir=None, istemci=None, web_gun: int = WEB_GUN
             ) -> list[tuple[durum.Durum, list[str]]]:
    """`bildir(tur, baslik, metin, anahtar)` verilirse değişiklikler bildirilir (gece koşusu, `yanki takip`).
    `istemci`: Spotify uygulaması üzerinden kotasız arama (`kontrol_et`)."""
    sonuc = []
    for d in durum.hepsi(calisma):
        if d.asama not in ("yuklendi", "yayinda") or (kimlikler and d.kimlik not in kimlikler):
            continue
        y = yukleme_bilgisi(calisma, d.kimlik) or {}
        if not y.get("isrc"):
            if y.get("release_id"):  # API'li dağıtımcı: ISRC kabulde gelir, `yanki dagitim-durum` yazar
                sonuc.append((d, [f"ISRC henüz yok: dağıtımcı incelemesi sürüyor ({y.get('dagitim_durumu')})"]))
            else:
                sonuc.append((d, [f"ISRC yok: dağıtımcının atadığı ISRC'yi `yanki yuklendi {d.kimlik} --isrc …` ile "
                                  "ekle"]))
            continue
        son = kontrol_et(sp, d, y["isrc"].upper(), sanatci_adi, pazarlar, arama_limiti,
                         onceki=(d.yayin or {}).get("son"), istemci=istemci, web_gun=web_gun)
        son.update(yayin_tarihi=y.get("yayin_tarihi"), en_gec_yayin=y.get("en_gec_yayin"), dagitimci=y.get("dagitimci"),
                   dagitim_durumu=y.get("dagitim_durumu"))
        son["dinlenme"] = dinlenme_olc(istemci, son)
        with durum.guncelle(calisma, d.kimlik) as taze:
            onceki = dict((taze.yayin or {}).get("son") or {})
            uyarilar = kaydet(taze, son)
            if son["dinlenme"] is not None:
                performans.dinlenme_ekle(taze, son["dinlenme"])
        if bildir:
            for olay in olaylar(taze, onceki, son):
                bildir(*olay)
        sonuc.append((taze, uyarilar))
    if bildir:
        for olay in profil_olaylari(calisma, sanatci_adi):
            bildir(*olay)
    return sonuc


def profil_kimlikleri(calisma: Path) -> set[str]:
    return {k for d in durum.hepsi(calisma) if (k := ((d.yayin or {}).get("son") or {}).get("sanatci_id"))}
