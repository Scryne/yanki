"""Dinleme odasının Sanatçı görünümü (Scryne 2026-10-15: "artist bölümü aç, her şeyi oradan kontrol edebileyim").

Orvane'ın kataloğu dağıtımdaki haliyle (kuyruk → RouteNote taslağı → inceleme → Spotify), dağıtım ayarları ve
odadan başlatılan uzun işler (RouteNote taslağı, gönderim, giriş). İşler `yanki` komutunun kendisini alt süreçte
çalıştırır: oda kapanırsa iş yarıda kalmaz, günlüğü `calisma/gunluk/oda-*.log`'da kalır. Aynı anda tek iş: RouteNote
profili iki tarayıcıda birden açılamıyor.
"""

import json
import os
import re
import subprocess
import sys
import threading
from datetime import date, datetime, timedelta
from pathlib import Path

from yanki import durum

DURUM_SIRASI = ("taslak_hazir", "taslak_yarim", "kuyruk", "inceleme", "yayinda")
YAYIN_ON_GUN_ASGARI = 10  # RouteNote incelemesi 5–10 iş günü; daha yakın tarih incelemede geçer


def _meta(calisma: Path, kimlik: str) -> dict:
    try:
        return json.loads((durum.klasor(calisma, kimlik) / "paket" / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def hal(d: durum.Durum, meta: dict) -> str:
    """Katalogdaki yer: kuyruk (paket hazır, RouteNote'a dokunulmadı) · taslak_yarim (bir adımda kaldı) ·
    taslak_hazir (dört adım tamam, "Distribute" bekliyor) · inceleme · yayinda."""
    if d.asama == "yayinda" or ((d.yayin or {}).get("son") or {}).get("canli"):
        return "yayinda"
    if d.asama == "yuklendi":
        return "inceleme"
    adim = (meta.get("routenote") or {}).get("adim")
    if adim == "hazir":
        return "taslak_hazir"
    return "taslak_yarim" if adim else "kuyruk"


def guncel_tarif(a) -> dict:
    from yanki import uretim

    return {"model": a.motor.model, "lora": uretim.lora_adi(a.motor.lora), "ek": dict(a.cover.ek)}


def tarif_eski(d: durum.Durum, guncel: dict) -> bool | None:
    """Paketteki aday bugünkü üretim tarifiyle mi üretildi (model, LoRA, ek ayarlar: CFG 10 2026-10-14'ten beri).
    Tarifi kayıtlı olmayan aday bilinmez (None). `ek` 2026-10-15'ten önce kaydedilmiyordu: o adaylar CFG 10 öncesi."""
    aday = next((x for x in d.adaylar if x.no == d.secilen), None)
    t = getattr(aday, "tarif", None) if aday else None
    if not t:
        return None
    return any(t.get(k, {} if k == "ek" else None) != v for k, v in guncel.items())


def katalog(calisma: Path, kapak_url, guncel: dict | None = None) -> list[dict]:
    from yanki import takip

    satirlar = []
    for d in durum.hepsi(calisma):
        if d.asama not in ("paketlendi", "yuklendi", "yayinda"):
            continue
        meta = _meta(calisma, d.kimlik)
        rn = meta.get("routenote") or {}
        y = takip.yukleme_bilgisi(calisma, d.kimlik) or {}
        son = (d.yayin or {}).get("son") or {}
        satirlar.append({
            "kimlik": d.kimlik, "ad": d.ad, "orijinal": d.sanatci, "asama": d.asama, "hal": hal(d, meta),
            "kapak": kapak_url(calisma, d.kimlik), "dagitimci": y.get("dagitimci") or ("routenote" if rn else None),
            "upc": rn.get("upc") or y.get("upc"), "isrc": rn.get("isrc") or y.get("isrc"),
            "adim": rn.get("adim"), "yayin_tarihi": y.get("yayin_tarihi") or rn.get("yayin_tarihi"),
            "taslak_tarihi": rn.get("tarih"), "hazirlanma": meta.get("hazirlanma"),
            "canli": bool(son.get("canli")), "spotify_id": son.get("spotify_id"),
            "arama_sirasi": son.get("arama_sirasi"), "son_bakis": son.get("zaman"),
            "eski_tarif": tarif_eski(d, guncel) if guncel else None,
        })
    upcler = {x["upc"] for x in satirlar if x["upc"]}
    satirlar += [x for x in arsivdekiler(calisma) if x["upc"] not in upcler]
    satirlar.sort(key=lambda x: (DURUM_SIRASI.index(x["hal"]), x["yayin_tarihi"] or "", x["ad"]))
    return satirlar


def arsiv_kapak(calisma: Path, upc: str) -> Path | None:
    p = arsiv_paketleri(calisma).get(upc)
    if p is None:
        return None
    adaylar = [x for x in sorted(p.glob("*.jpg")) if not x.name.startswith(".")]
    return next((x for x in adaylar if "_-_" in x.name), adaylar[0] if adaylar else None)  # paketin kapağı önce


def arsiv_paketleri(calisma: Path) -> dict[str, Path]:
    """Arşive alınmış ama dağıtımcıda yaşayan yayınların paket klasörü, UPC'ye göre. 2026-10-10'da hat baştan
    kurulurken RouteNote'a elle yüklenen üç parça (Adele, Calum Scott, Coldplay) arşive taşındı; yayınları sürüyor
    (Scryne: "RouteNote'taki üç parça orada kalır")."""
    paketler = {}
    for meta_yolu in sorted((calisma / "_arsiv").glob("*/*/paket/metadata.json")):
        try:
            m = json.loads(meta_yolu.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for y in [m.get("yukleme"), *(m.get("yukleme_gecmisi") or [])]:
            if y and y.get("dagitimci") == "routenote" and y.get("upc"):
                paketler[y["upc"]] = meta_yolu.parent
    return paketler


def _routenote_yuklemesi(meta: dict, upc: str) -> dict:
    return next(y for y in [meta.get("yukleme"), *(meta.get("yukleme_gecmisi") or [])] if y and y.get("upc") == upc)


def arsivdekiler(calisma: Path) -> list[dict]:
    satirlar = []
    for upc, p in arsiv_paketleri(calisma).items():
        meta = json.loads((p / "metadata.json").read_text(encoding="utf-8"))
        y = _routenote_yuklemesi(meta, upc)
        satirlar.append({
            "kimlik": None, "ad": meta.get("baslik"), "orijinal": meta.get("orijinal_sanatci"), "asama": "yuklendi",
            "hal": "inceleme", "kapak": f"/api/sanatci/kapak/{upc}?v=1", "dagitimci": "routenote", "upc": upc,
            "isrc": y.get("isrc"), "adim": None, "yayin_tarihi": y.get("yayin_tarihi"), "taslak_tarihi": None,
            "hazirlanma": meta.get("hazirlanma"), "canli": False, "spotify_id": None, "arama_sirasi": None,
            "son_bakis": None, "eski_tarif": True, "arsiv": True,
            # hat 2026-10-10'da "panelden kaldırıldı" kaydetti; RouteNote 2026-10-15'te üçünü hâlâ incelemede gösteriyor
            "uyari": (f"Kayıtta geri çekildi ({y['geri_cekme_tarihi']}), ama RouteNote'ta kaldırılmadı: "
                      f"{y.get('yayin_tarihi')} tarihinde yayına girer. Kalsın mı, panelden kaldırılsın mı?")
            if y.get("geri_cekildi") else None,
        })
    return satirlar


def oturum(calisma: Path) -> dict:
    """RouteNote oturumu yalnız diskten: profil var mı, çerezler en son ne zaman yazıldı (siteye istek atılmaz)."""
    from yanki import routenote

    profil = calisma / routenote.PROFIL
    cerez = next((p for p in (profil / "Default" / "Network" / "Cookies", profil / "Default" / "Cookies")
                  if p.exists()), None)
    return {"profil": profil.is_dir(),
            "son": datetime.fromtimestamp(cerez.stat().st_mtime).isoformat(timespec="minutes") if cerez else None}


# ── ayarlar (config/yayin.toml; yorumlar korunur) ──────────

AYARLAR = {  # odadan değiştirilebilen: (bölüm, anahtar, tür)
    "gece": ("routenote", "gece", bool),
    "spotify_sanatci_id": ("routenote", "spotify_sanatci_id", str),
    "yayin_on_gun": ("takvim", "yayin_on_gun", int),
}


def ayar_oku(kok: Path) -> dict:
    import tomllib

    with open(kok / "config" / "yayin.toml", "rb") as f:
        t = tomllib.load(f)
    return {ad: t.get(bolum, {}).get(anahtar) for ad, (bolum, anahtar, _) in AYARLAR.items()}


def _toml_deger(v) -> str:
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    return json.dumps(v, ensure_ascii=False)


def ayar_yaz(kok: Path, degisiklik: dict) -> dict:
    """Yalnız `AYARLAR`'daki anahtarların satırı değişir; satır sonundaki yorum ve dosyanın geri kalanı olduğu gibi."""
    yol = kok / "config" / "yayin.toml"
    metin = yol.read_text(encoding="utf-8")
    for ad, v in degisiklik.items():
        bolum, anahtar, tur = AYARLAR[ad]
        if tur is int and not 1 <= int(v) <= 120:
            raise ValueError(f"{ad} 1 ile 120 arasında olmalı")
        if tur is str and not re.fullmatch(r"[A-Za-z0-9]{0,40}", str(v)):
            raise ValueError(f"{ad}: Spotify kimliği yalnız harf ve rakam")
        m = re.search(rf"(?ms)^\[{re.escape(bolum)}\]\s*$(.*?)(?=^\[|\Z)", metin)
        if m is None:
            raise ValueError(f"config/yayin.toml'da [{bolum}] yok")
        govde = m.group(1)
        satir = re.compile(rf"(?m)^({re.escape(anahtar)}\s*=\s*)([^#\n]*?)(\s*(?:#.*)?)$")
        if not satir.search(govde):
            raise ValueError(f"[{bolum}] içinde {anahtar} yok")
        deger = _toml_deger(tur(v))
        yeni = satir.sub(lambda s, deger=deger: s.group(1) + deger + s.group(3), govde, count=1)
        metin = metin[:m.start(1)] + yeni + metin[m.end(1):]
    import tomllib

    tomllib.loads(metin)  # bozuk dosya yazılmaz
    gecici = yol.with_suffix(".yaziliyor")
    gecici.write_text(metin, encoding="utf-8")
    gecici.replace(yol)
    return ayar_oku(kok)


def yeni_yayin_tarihi(kok: Path, bugun: date | None = None) -> date:
    gun = max(int(ayar_oku(kok).get("yayin_on_gun") or 21), YAYIN_ON_GUN_ASGARI)
    return (bugun or date.today()) + timedelta(days=gun)


# ── odadan başlatılan işler ────────────────────────────────

IS_KOMUTLARI = {  # ad → (yanki argümanları, kimlik gerekir mi)
    "taslak": (["yukle", "{kimlik}", "--taslak"], True),
    "gonder": (["yukle", "{kimlik}"], True),
    "giris": (["routenote", "giris"], False),
}


class Isci:
    """Tek iş: alt süreç + günlük dosyası. Durum `calisma/.oda_is.json`'da (oda yeniden açılınca son iş görünür)."""

    def __init__(self, kok: Path, calisma: Path):
        self.kok, self.calisma = kok, calisma
        self._kilit = threading.Lock()
        self._surec: subprocess.Popen | None = None
        self._kayit_yolu = calisma / ".oda_is.json"

    def _kayit(self) -> dict | None:
        try:
            return json.loads(self._kayit_yolu.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def durum(self, satir: int = 40) -> dict | None:
        with self._kilit:
            k = self._kayit()
            if k is None:
                return None
            if k.get("bitis") is None:
                if self._surec is not None and self._surec.pid == k.get("pid"):
                    if (kod := self._surec.poll()) is not None:
                        k.update(bitis=datetime.now().isoformat(timespec="seconds"), kod=kod)
                        self._kayit_yolu.write_text(json.dumps(k, ensure_ascii=False), encoding="utf-8")
                else:
                    k["sahipsiz"] = True  # oda yeniden açıldı: süreç izlenemiyor (iş yine de sürmüş olabilir)
            try:
                gunluk = Path(k["gunluk"]).read_text(encoding="utf-8", errors="replace").splitlines()
            except OSError:
                gunluk = []
            return {**k, "suruyor": k.get("bitis") is None and not k.get("sahipsiz"), "gunluk_son": gunluk[-satir:]}

    def baslat(self, ad: str, kimlik: str | None = None) -> dict:
        arg, kimlikli = IS_KOMUTLARI[ad]
        if kimlikli and not kimlik:
            raise ValueError("şarkı kimliği gerekli")
        with self._kilit:
            if self._surec is not None and self._surec.poll() is None:
                raise RuntimeError("başka bir iş sürüyor; bitince yeniden dene")
            zaman = datetime.now()
            gunluk = self.calisma / "gunluk" / f"oda-{zaman:%Y%m%d-%H%M%S}-{ad}.log"
            gunluk.parent.mkdir(parents=True, exist_ok=True)
            komut = [sys.executable, "-m", "yanki.cli", *[a.format(kimlik=kimlik) for a in arg]]
            ortam = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
            with open(gunluk, "w", encoding="utf-8") as f:
                f.write(f"$ yanki {' '.join(komut[3:])}\n")
                f.flush()
                self._surec = subprocess.Popen(komut, cwd=self.kok, stdout=f, stderr=subprocess.STDOUT, env=ortam,
                                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            k = {"ad": ad, "kimlik": kimlik, "pid": self._surec.pid, "baslangic": zaman.isoformat(timespec="seconds"),
                 "gunluk": str(gunluk), "bitis": None, "kod": None}
            self._kayit_yolu.write_text(json.dumps(k, ensure_ascii=False), encoding="utf-8")
            return k
