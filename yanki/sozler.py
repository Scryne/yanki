"""Sözler: Scryne'ın söz dosyası → LRCLIB → yok.

ACE-Step söz olmadan anlamsız vokal üretiyor (spike S1); söz bulunamayan şarkı hazırlıkta durur.
"""

from dataclasses import dataclass
from pathlib import Path

from yanki import ag

LRCLIB = "https://lrclib.net/api"


@dataclass(frozen=True)
class Soz:
    metin: str  # ACE-Step biçimi: [verse]/[chorus] etiketli kıtalar
    kaynak: str  # "dosya" | "lrclib"
    sure_sn: float | None  # LRCLIB'deki kaydın süresi; kaynak sesi doğrulamak için


def etiketle(duz: str) -> str:
    """Kıtaları etiketler: birden çok geçen kıta [chorus], diğerleri [verse]. Var olan etiketlere dokunmaz."""
    if "[" in duz and "]" in duz.split("\n", 1)[0]:
        return duz.strip()
    kitalar = [k.strip() for k in duz.replace("\r", "").split("\n\n") if k.strip()]
    tekrar = {k for k in kitalar if kitalar.count(k) > 1}
    return "\n\n".join(("[chorus]" if k in tekrar else "[verse]") + "\n" + k for k in kitalar)


def lrclib(sanatci: str, ad: str, json_al=ag.json_al) -> Soz:
    try:
        d = json_al(f"{LRCLIB}/get", {"artist_name": sanatci, "track_name": ad})
    except ag.Bulunamadi:
        bulunan = json_al(f"{LRCLIB}/search", {"artist_name": sanatci, "track_name": ad})
        bulunan = [b for b in bulunan if b.get("plainLyrics") and not b.get("instrumental")]
        if not bulunan:
            raise ag.Bulunamadi(f"LRCLIB'de söz yok: {sanatci} — {ad}") from None
        d = bulunan[0]
    if d.get("instrumental") or not (d.get("plainLyrics") or "").strip():
        raise ag.Bulunamadi(f"LRCLIB kaydı sözsüz: {sanatci} — {ad}")
    return Soz(etiketle(d["plainLyrics"]), "lrclib", float(d["duration"]) if d.get("duration") else None)


def bul(sanatci: str, ad: str, dosya: Path, json_al=ag.json_al) -> Soz:
    """Scryne `girdi/sozler/<kimlik>.txt` bıraktıysa o esastır."""
    if dosya.exists() and dosya.read_text(encoding="utf-8").strip():
        sure = None
        try:
            sure = lrclib(sanatci, ad, json_al).sure_sn
        except (ag.Bulunamadi, OSError):
            pass
        return Soz(etiketle(dosya.read_text(encoding="utf-8")), "dosya", sure)
    return lrclib(sanatci, ad, json_al)
