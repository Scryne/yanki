"""Bulucu: dinleme odasından STILLMORE FINDER'ın motoruyla Spotify'da arama (Scryne'ın istediği anda).

STILLMORE (github.com/Caferlyy/distro-finder-bulmaca, `C:\\df-archive`) Spotify istemcisinin içinde çalışıyor ve
istemcinin kendi uçlarıyla (protobuf metadata, GraphQL, PlaylistAPI) bir parçanın distribütörünü (licensor UUID), ISRC/
UPC'sini, dinlenmesini; bir playlist'teki kalkmış şarkıları (neden, kalkmadan önceki dinlenme, 90 günlük pencere,
aynı ISRC'nin yeniden yüklemesi); bir sanatçının özetini ve kataloğunu okuyor. Oda bunu `stillmore.Kopru` (CDP) ile
çağırır: Web API kotası harcanmaz.

Uzun işler (büyük playlist taraması dakikalar sürer) Spotify sayfasında arka planda koşar (`window.__yanki`); bu
modül saniyede bir ilerlemeyi okur. Aynı anda tek iş. Sonuçlar `calisma/bulucu/<tür>-<kimlik>.json`.

Keşifle bağ: seçilen kalkmış şarkılar `girdi/kesif/bulucu.csv`'ye STILLMORE CSV biçiminde yazılır (gece keşfi okur,
her adayı aynı elemelerden geçirir); "gece taransın" denen playlist `calisma/kesif/bulucu_izlenen.json`'a yazılır,
gece keşfi onu STILLMORE havuzuna alır. İki dosyayı yalnız oda yazar, gece koşusu yalnız okur.
"""

import csv
import io
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

from yanki import stillmore

TURLER = ("parca", "playlist", "sanatci", "katalog", "album", "isrc", "upc")
TUR_ADI = {"parca": "Parça", "playlist": "Playlist", "sanatci": "Sanatçı", "katalog": "Sanatçı kataloğu",
           "album": "Albüm", "isrc": "ISRC", "upc": "UPC", "baglan": "Spotify bağlantısı"}
SPOTIFY_ID = re.compile(r"[A-Za-z0-9]{22}")
ISRC = re.compile(r"[A-Z]{2}[A-Z0-9]{3}\d{7}")
ANAHTAR = re.compile(r"(parca|playlist|sanatci|katalog|album|isrc|upc)-[A-Za-z0-9]{1,40}")
IS_ZAMAN_ASIMI = 45 * 60  # 1.000+ parçalık playlist'te her kalkmış şarkı için ISRC araması
GECMIS_EN_COK = 200
CSV_SUTUNLARI = ("Parça", "Sanatçı", "Çalınabilir", "Durum", "Yeniden yüklenmiş", "Spotify ID", "ISRC", "Çıkış",
                 "Dinlenme", "Sayaç", "Kaynak")
SAYAC_YAZI = {True: "duruyor", False: "silinmiş"}  # kesif.stillmore_csv okur: sayacı duran şarkı son 90 günde kalktı


class GirdiHatasi(ValueError):
    pass


def coz(metin: str) -> tuple[str, str]:
    """Yapıştırılan metin → (tür, kimlik). Spotify linki (dil ekli /intl-tr/ da) ya da URI'si, ISRC, UPC/EAN."""
    m = (metin or "").strip()
    if not m:
        raise GirdiHatasi("Spotify linki, ISRC ya da UPC yapıştır")
    bul = re.search(r"(?:open\.spotify\.com/(?:intl-[a-z-]+/)?(?:embed/)?|spotify:)(track|playlist|artist|album)[/:]"
                    r"([A-Za-z0-9]{22})", m)
    if bul:
        return {"track": "parca", "artist": "sanatci"}.get(bul[1], bul[1]), bul[2]
    if "spotify" in m.lower():
        raise GirdiHatasi("Spotify linki tanınmadı: parça, playlist, sanatçı ya da albüm linki olmalı")
    sade = re.sub(r"[\s-]", "", m).upper()
    if ISRC.fullmatch(sade):
        return "isrc", sade
    if re.fullmatch(r"\d{12,14}", sade):
        return "upc", sade
    if SPOTIFY_ID.fullmatch(m):
        raise GirdiHatasi("Yalnız kimlik verildi; parça mı playlist mi bilinmiyor. Linkin tamamını yapıştır")
    raise GirdiHatasi("Spotify linki, ISRC (ör. GBARL9300135) ya da UPC (12–14 rakam) olmalı")


def gecerli(tur: str, kimlik: str) -> bool:
    if tur in ("parca", "playlist", "sanatci", "katalog", "album"):
        return bool(SPOTIFY_ID.fullmatch(kimlik))
    if tur == "isrc":
        return bool(ISRC.fullmatch(kimlik))
    return tur == "upc" and bool(re.fullmatch(r"\d{12,14}", kimlik))


# ── Spotify sayfasında koşan yardımcı (STILLMORE'un window.Stillmore API'si, v12.x) ──────────────────────────────
# Sonuçlar burada kırpılır: büyük playlist'in ham satırları (her biri kalkmış şarkının tüm incelemesi) WebSocket'ten
# taşınmasın. Süre STILLMORE'un `durationMs`'inden alınmaz: metadata'daki sint32 alan zigzag çözülmeden okunuyor
# (12.13: her süre iki katı; 2026-10-16 ölçüldü), ses özelliklerindeki `duration_ms` doğru.
YARDIMCI_SURUM = 1
YARDIMCI = Path(__file__).with_name("bulucu_yardimci.js").read_text(encoding="utf-8").replace(
    "__SURUM__", str(YARDIMCI_SURUM))


# ── kayıtlar ─────────────────────────────────────────────────────────────────────────────────────────────────────
def klasor(calisma: Path) -> Path:
    return calisma / "bulucu"


def sonuc_yolu(calisma: Path, anahtar: str) -> Path:
    if not ANAHTAR.fullmatch(anahtar):
        raise GirdiHatasi("geçersiz kayıt")
    return klasor(calisma) / f"{anahtar}.json"


def sonuc_yaz(calisma: Path, veri: dict) -> str:
    from yanki import dosya

    anahtar = f"{veri['tur']}-{veri['id']}"
    veri = {**veri, "anahtar": anahtar, "zaman": datetime.now().isoformat(timespec="seconds")}
    dosya.json_yaz(sonuc_yolu(calisma, anahtar), veri, indent=None)
    eski = sorted(klasor(calisma).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[GECMIS_EN_COK:]
    for p in eski:
        p.unlink(missing_ok=True)
    return anahtar


def sonuc_oku(calisma: Path, anahtar: str) -> dict | None:
    yol = sonuc_yolu(calisma, anahtar)
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _ozet_sayi(v: dict) -> str | None:
    tur = v.get("tur")
    if tur == "playlist":
        return f"{len(v.get('satirlar') or [])} kalkmış / {v.get('toplam') or 0}"
    if tur == "album":
        return f"{len(v.get('satirlar') or [])} parça"
    if tur in ("isrc", "upc"):
        return f"{len(v.get('sonuclar') or [])} sonuç"
    if tur == "katalog":
        return f"{len(v.get('yayinlar') or [])} yayın"
    if tur == "parca":
        return "çalınamıyor" if v.get("calinir") is False else v.get("distributor") or None
    return None


def gecmis(calisma: Path, adet: int = 30) -> list[dict]:
    yollar = sorted(klasor(calisma).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:adet]
    sonuc = []
    for p in yollar:
        try:
            v = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        sonuc.append({"anahtar": v.get("anahtar") or p.stem, "tur": v.get("tur"), "ad": v.get("ad") or v.get("id"),
                      "alt": v.get("sanatci") or v.get("sahip") or TUR_ADI.get(v.get("tur"), ""),
                      "zaman": v.get("zaman"), "sayi": _ozet_sayi(v), "resim": v.get("resim") or None})
    return sonuc


# ── keşifle bağ ──────────────────────────────────────────────────────────────────────────────────────────────────
CSV_KILIDI = threading.Lock()


def csv_yolu(kok: Path) -> Path:
    return kok / "girdi" / "kesif" / "bulucu.csv"


def gonderilenler(kok: Path) -> set[str]:
    """Keşfe gönderilmiş Spotify kimlikleri (`bulucu.csv`)."""
    try:
        metin = csv_yolu(kok).read_text(encoding="utf-8-sig")
    except OSError:
        return set()
    return {(r.get("Spotify ID") or "").strip() for r in csv.DictReader(io.StringIO(metin))} - {""}


def kesfe_gonder(kok: Path, satirlar: list[dict], kaynak: str) -> tuple[int, int]:
    """Kalkmış şarkılar keşif girdisine (STILLMORE CSV biçimi, `kesif.stillmore_csv` okur). Yeniden yüklenmiş ya da
    çalınabilen satır yazılmaz (boşluk yok); aynı Spotify kimliği iki kez yazılmaz. (eklenen, atlanan)."""
    from yanki import dosya

    with CSV_KILIDI:
        yol = csv_yolu(kok)
        try:
            metin = yol.read_text(encoding="utf-8-sig")
        except OSError:
            metin = ""
        eski = list(csv.DictReader(io.StringIO(metin))) if metin else []
        var = {(r.get("Spotify ID") or "").strip() for r in eski}
        yeni = []
        for s in satirlar:
            # çalınan kopya: playlist satırındaki her kopya çalınıyor; parça kaydındaki ISRC sonuçlarında `calinir`
            canli_kopya = any(k.get("calinir") is not False for k in s.get("kopyalar") or [])
            if not s.get("id") or s["id"] in var or canli_kopya or s.get("calinir") is True or not s.get("ad"):
                continue
            var.add(s["id"])
            yeni.append({"Parça": s["ad"], "Sanatçı": s.get("sanatci") or "", "Çalınabilir": "Hayır",
                         "Durum": "Ülkende kapalı" if s.get("neden") == "country" else "Kaldırılmış",
                         "Yeniden yüklenmiş": "", "Spotify ID": s["id"], "ISRC": s.get("isrc") or "",
                         "Çıkış": s.get("cikis") or "",
                         "Dinlenme": "" if s.get("dinlenme") is None else str(s["dinlenme"]),
                         "Sayaç": SAYAC_YAZI.get((s.get("pencere") or {}).get("sayi_duruyor"), ""),
                         "Kaynak": kaynak})
        if yeni:
            cikti = io.StringIO()
            w = csv.DictWriter(cikti, fieldnames=CSV_SUTUNLARI, extrasaction="ignore", lineterminator="\n")
            w.writeheader()
            w.writerows([*eski, *yeni])
            yol.parent.mkdir(parents=True, exist_ok=True)
            dosya.yaz(yol, "\ufeff" + cikti.getvalue())
        return len(yeni), len(satirlar) - len(yeni)


def izlenen_yolu(calisma: Path) -> Path:
    return calisma / "kesif" / "bulucu_izlenen.json"


def izlenenler(calisma: Path) -> dict[str, dict]:
    try:
        return json.loads(izlenen_yolu(calisma).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def izle(calisma: Path, playlist_id: str, ad: str, toplam: int | None, acik: bool) -> dict[str, dict]:
    from yanki import dosya

    if not SPOTIFY_ID.fullmatch(playlist_id):
        raise GirdiHatasi("geçersiz playlist")
    with CSV_KILIDI:
        v = izlenenler(calisma)
        if acik:
            v[playlist_id] = {"ad": ad, "toplam": toplam, "eklendi": datetime.now().isoformat(timespec="seconds")}
        else:
            v.pop(playlist_id, None)
        dosya.json_yaz(izlenen_yolu(calisma), v, indent=1)
    return v


def havuza_isle(havuz: dict[str, dict], izlenen: dict[str, dict]) -> int:
    """Gece keşfi: odadan "gece taransın" denen playlist'ler havuza (`kaynak = bulucu`); bırakılanlar havuzdan çıkar.
    Değişen kayıt sayısı."""
    degisen = 0
    for pid, v in izlenen.items():
        if stillmore.havuza_ekle(havuz, pid, v.get("ad") or "", "bulucu", v.get("toplam")):
            degisen += 1
    for pid in [k for k, v in havuz.items() if v.get("kaynak") == "bulucu" and k not in izlenen]:
        del havuz[pid]
        degisen += 1
    return degisen


def yanki_durumu(satirlar: list[dict], calisma: Path, liste_yolu: Path, kok: Path) -> None:
    """Her kalkmış şarkının hattaki yeri (yerinde yazar): listede/üretimde, keşifte (hal + puan), keşfe gönderildi."""
    from yanki import kesif

    try:
        kayit = kesif.oku(calisma)
    except (OSError, ValueError):
        kayit = {}
    try:
        listede = kesif.listedekiler(liste_yolu, calisma)
    except (OSError, ValueError):
        listede = set()
    gonderilen = gonderilenler(kok)
    for s in satirlar:
        if not s.get("ad") or not s.get("sanatci"):
            s["yanki"] = None
            continue
        aday = kesif.Aday(sanatci=kesif.ilk_sanatci(s["sanatci"]), ad=s["ad"], kaynak="bulucu")
        k = aday.kimlik
        a = kayit.get(k)
        # düzenleme (remix, sped up…) keşifte hiç sorulmaz: odada "Keşfe gönder" çıkmaz
        s["yanki"] = {"kimlik": k, "listede": k in listede, "gonderildi": s.get("id") in gonderilen,
                      "duzenleme": aday.duzenleme,
                      "hal": ("elendi" if a.elendi else kesif.hal(a)) if a else None,
                      "puan": round(a.puan) if a and a.puan > 0 and not a.elendi else None}


# ── iş ───────────────────────────────────────────────────────────────────────────────────────────────────────────
class Bulucu:
    """Odanın tek Bulucu işçisi: Spotify bağlantısı ve aramalar arka plan iş parçacığında, aynı anda tek iş."""

    def __init__(self, calisma: Path, kopru_ac=None, uyku=time.sleep):
        self.calisma = calisma
        self._kopru_ac = kopru_ac or (lambda: stillmore.Kopru())
        self._uyku = uyku
        self._kilit = threading.Lock()
        self._is: dict | None = None
        self._durum_onbellek: tuple[float, dict] | None = None

    # bağlantı ------------------------------------------------------------------------------------------------
    def baglanti(self, taze: bool = False) -> dict:
        """Spotify ve STILLMORE hâli. CDP açıksa sürüm ve hesabın ülkesi (20 sn önbellek; iş sürerken önbellekten)."""
        simdi = time.monotonic()
        if not taze and self._durum_onbellek and (simdi - self._durum_onbellek[0] < 20 or self.suruyor()):
            return self._durum_onbellek[1]
        d = {"cdp": stillmore.cdp_acik(), "spotify": None, "stillmore": None, "ulke": None, "hata": None}
        if d["cdp"]:
            d["spotify"] = True
            try:
                k = self._kopru_ac()
                d["stillmore"] = k.degerlendir("window.Stillmore ? Stillmore.version || '?' : null", 5)
                d["ulke"] = k.ulke() if d["stillmore"] else None
                if not d["stillmore"]:
                    d["hata"] = "STILLMORE Spotify'da yüklenmedi (yama silinmiş olabilir: KUR.bat ya da onar.ps1)"
            except stillmore.StillmoreYok as e:
                d["hata"] = str(e)
        else:
            try:
                d["spotify"] = stillmore.calisiyor_mu()
            except Exception:  # noqa: BLE001 — tasklist yoksa bilinmiyor
                d["spotify"] = None
        self._durum_onbellek = (simdi, d)
        return d

    def _baglan(self, is_: dict) -> dict:
        is_["ilerleme"] = {"bitti": 0, "toplam": 0, "etiket": "Spotify açılıyor"}
        if not stillmore.cdp_acik():
            if stillmore.calisiyor_mu():
                is_["ilerleme"]["etiket"] = "Spotify yeniden başlatılıyor"
                stillmore.kapat()
            stillmore.ac(cdp=True)
        is_["ilerleme"]["etiket"] = "STILLMORE bekleniyor"
        k = stillmore.kopru_bekle()
        k.hazir_bekle()
        self._durum_onbellek = None
        return self.baglanti(taze=True)

    # iş --------------------------------------------------------------------------------------------------------
    def suruyor(self) -> bool:
        return bool(self._is and self._is["durum"] == "suruyor")

    def durum(self) -> dict | None:
        if self._is is None:
            return None
        return {k: v for k, v in self._is.items() if k != "_no"}

    def baslat(self, tur: str, kimlik: str | None = None) -> dict:
        if tur != "baglan" and (tur not in TURLER or not kimlik or not gecerli(tur, kimlik)):
            raise GirdiHatasi("geçersiz arama")
        with self._kilit:
            if self.suruyor():
                raise RuntimeError(f"{TUR_ADI.get(self._is['tur'], 'bir iş')} sürüyor; bitince yeniden dene")
            self._is = {"tur": tur, "kimlik": kimlik, "durum": "suruyor", "ilerleme": None, "hata": None,
                        "anahtar": None, "baslangic": datetime.now().isoformat(timespec="seconds"), "bitis": None}
            is_ = self._is
        threading.Thread(target=self._calistir, args=(is_,), daemon=True, name=f"bulucu-{tur}").start()
        return self.durum()

    def _calistir(self, is_: dict) -> None:
        try:
            if is_["tur"] == "baglan":
                self._baglan(is_)
            else:
                is_["anahtar"] = sonuc_yaz(self.calisma, self._ara(is_))
            is_["durum"] = "bitti"
        except Exception as e:  # noqa: BLE001 — CDP koptu, STILLMORE hatası, zaman aşımı: odada gösterilir
            is_["hata"] = str(e)[:500] or type(e).__name__
            is_["durum"] = "hata"
        finally:
            is_["bitis"] = datetime.now().isoformat(timespec="seconds")

    def _ara(self, is_: dict) -> dict:
        if not stillmore.cdp_acik():
            raise stillmore.StillmoreYok("Spotify bağlı değil: önce \"Spotify'a bağlan\"")
        k = self._kopru_ac()
        k.degerlendir(YARDIMCI, 15)
        no = k.degerlendir(f"window.__yanki.baslat({json.dumps(is_['tur'])}, {json.dumps(is_['kimlik'])})", 15)
        bitis = time.monotonic() + IS_ZAMAN_ASIMI
        hata_sayisi = 0
        while time.monotonic() < bitis:
            self._uyku(1)
            try:
                d = k.degerlendir("window.__yanki ? window.__yanki.durum() : null", 15)
                hata_sayisi = 0
            except stillmore.StillmoreYok:
                hata_sayisi += 1  # sayfa bir an meşgul: birkaç kez dene
                if hata_sayisi >= 10:
                    raise
                continue
            if not d or d.get("no") != no:
                raise stillmore.StillmoreYok("Spotify sayfası yenilendi; aramayı yeniden başlat")
            is_["ilerleme"] = d.get("ilerleme")
            if d["durum"] == "hata":
                raise RuntimeError(d.get("hata") or "STILLMORE hatası")
            if d["durum"] == "bitti":
                veri = k.degerlendir(f"window.__yanki.sonuc({int(no)})", 120)
                if not veri:
                    raise RuntimeError("STILLMORE sonucu boş döndü")
                return veri
        raise TimeoutError(f"{TUR_ADI.get(is_['tur'])} {IS_ZAMAN_ASIMI // 60} dakikada bitmedi")
