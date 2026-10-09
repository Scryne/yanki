"""Dağıtım arayüzü ve yayın takvimi (Roadmap Faz 10'un API'den bağımsız kısmı).

`Dagitimci` hattın dağıtımcıyla konuştuğu tek yer. Bugün tek uygulama elle RouteNote: hat yüklemez (API yok, form
insanda), takvimde sırası gelen paketi bildirir; Scryne yükleyip `yanki yuklendi` der. Arkadaşın dağıtım API'si
gelince `otomatik = True` bir uygulama eklenir, gece koşusu sırası gelen paketi kendisi yükler; takvim, kuyruk ve
bildirim aynı kalır.

Takvim (`config/yayin.toml` → `[takvim]`): `paketlendi` şarkılar kuyruk; sıra keşif puanı (kaldırılmış ve aranan şarkı
önce), sonra onay sırası. Haftada `haftada` yükleme; ilk boş gün son yüklemeden bir aralık sonra. Önerilen yayın
tarihi yüklemeden `yayin_on_gun` gün sonra (ücretsiz inceleme günler sürüyor, Spotify pitch için ≥ 7 gün; YUKLE.md).
`baslangic = "ilk_kabul"`: ilk parça Spotify'a çıkana kadar takvim bekler (Roadmap Faz 7: ilk kabul gelmeden
RouteNote'a daha fazla yükleme yok; red gelirse nedeni kapak mı AI mı önce o anlaşılmalı).
"""

import tomllib
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Protocol

from yanki import durum


class Dagitimci(Protocol):
    ad: str
    otomatik: bool  # True: hat yükler (API); False: insan yükler, hat sırası geleni bildirir

    def yukle(self, calisma: Path, d: durum.Durum) -> dict:
        """Paketi yükler, yükleme bilgisini (`takip.yukleme_kaydet` alanları) döner."""
        ...


class ElleRouteNote:
    ad, otomatik = "routenote", False

    def yukle(self, calisma: Path, d: durum.Durum) -> dict:
        raise NotImplementedError("RouteNote'ta API yok: YUKLE.md ile elle yükle, sonra `yanki yuklendi`")


class Elle:
    """Formu insanın doldurduğu herhangi bir dağıtımcı (DistroKid, boş ayar)."""
    otomatik = False

    def __init__(self, ad: str):
        self.ad = ad

    def yukle(self, calisma: Path, d: durum.Durum) -> dict:
        raise NotImplementedError(f"{self.ad or 'dağıtımcı'} için API yok: YUKLE.md ile elle yükle")


def sec(ad: str) -> Dagitimci:
    return ElleRouteNote() if ad == "routenote" else Elle(ad)


# ── takvim ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Takvim:
    acik: bool = True
    haftada: int = 1
    yayin_on_gun: int = 21
    baslangic: str = "ilk_kabul"  # "ilk_kabul" | "hemen"

    @property
    def aralik(self) -> timedelta:
        return timedelta(days=max(1, round(7 / max(1, self.haftada))))  # tam gün: haftada 2 → 4 günde bir


def takvim_oku(yayin_yolu: Path) -> Takvim:
    with open(yayin_yolu, "rb") as f:
        t = tomllib.load(f).get("takvim", {})
    baslangic = t.get("baslangic", "ilk_kabul")
    if baslangic not in ("ilk_kabul", "hemen"):
        raise ValueError(f"takvim.baslangic ilk_kabul ya da hemen olmalı: {baslangic}")
    return Takvim(bool(t.get("acik", True)), int(t.get("haftada", 1)), int(t.get("yayin_on_gun", 21)), baslangic)


def _gecis(d: durum.Durum, asama: str) -> datetime | None:
    zaman = None
    for g in d.gecmis:
        if g.get("asama") == asama:
            zaman = datetime.fromisoformat(g["zaman"])  # son geçiş (yeniden paketleme)
    return zaman


@dataclass(frozen=True)
class Sira:
    kimlik: str
    sanatci: str
    ad: str
    yukleme: date
    yayin_tarihi: date
    puan: float


@dataclass(frozen=True)
class Plan:
    sira: list[Sira]
    beklemede: str | None  # takvim neden işlemiyor (None: işliyor)
    son_yukleme: date | None
    duzeltme: list[str]  # dağıtımcının reddettiği, yeniden paketlenmeyi bekleyen şarkılar

    @property
    def bugun_yuklenecek(self) -> Sira | None:
        return self.sira[0] if self.sira and not self.beklemede and self.sira[0].yukleme <= date.today() else None


def plan(calisma: Path, t: Takvim, bugun: date | None = None, puanlar: dict[str, float] | None = None) -> Plan:
    """Kuyruk ve tarihleri hesaplar (kayıt tutmaz: her çağrıda durumdan yeniden çıkar, elle yükleme hemen yansır)."""
    bugun = bugun or date.today()
    if puanlar is None:
        from yanki import kesif

        puanlar = {k: a.puan for k, a in kesif.oku(calisma).items()}
    hepsi = durum.hepsi(calisma)
    yuklemeler = [z.date() for d in hepsi if d.asama in ("yuklendi", "yayinda") and (z := _gecis(d, "yuklendi"))]
    son = max(yuklemeler, default=None)
    reddedilen = [d.kimlik for d in hepsi if d.asama == "paketlendi" and (d.hata or "").startswith(RED_ONEKI)]
    kuyruk = sorted((d for d in hepsi if d.asama == "paketlendi" and d.kimlik not in reddedilen),
                    key=lambda d: (-puanlar.get(d.kimlik, 0.0), _gecis(d, "onaylandi") or datetime.max, d.kimlik))
    ilk = max(bugun, son + t.aralik) if son else bugun
    sira = [Sira(d.kimlik, d.sanatci, d.ad, gun := ilk + i * t.aralik, gun + timedelta(days=t.yayin_on_gun),
                 puanlar.get(d.kimlik, 0.0)) for i, d in enumerate(kuyruk)]
    beklemede = None
    if not t.acik:
        beklemede = "takvim kapalı (config/yayin.toml → [takvim])"
    elif t.baslangic == "ilk_kabul" and not any(d.asama == "yayinda" for d in hepsi):
        beklemede = "ilk parça Spotify'a çıkana kadar bekliyor (dağıtımcı incelemesi)"
    return Plan(sira, beklemede, son, reddedilen)


RED_ONEKI = "dağıtımcı reddi: "


def red_kaydet(calisma: Path, kimlik: str, neden: str) -> durum.Durum:
    """Dağıtımcı reddi: şarkı `paketlendi`ye döner (düzeltilip yeniden yüklenebilir), yükleme bilgisi geçmişe taşınır,
    neden notlara yazılır (Faz 10: keşfe geri besleme bu notlardan)."""
    import json

    from yanki import dosya

    with durum.guncelle(calisma, kimlik) as d:
        if d.asama not in ("yuklendi", "yayinda"):
            raise ValueError(f"yüklenmiş bir şarkı değil (aşama: {d.asama})")
        meta_yolu = durum.klasor(calisma, kimlik) / "paket" / "metadata.json"
        if meta_yolu.exists():
            meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
            if meta.get("yukleme"):
                meta.setdefault("yukleme_gecmisi", []).append({**meta.pop("yukleme"), "red": neden,
                                                               "red_tarihi": date.today().isoformat()})
                dosya.json_yaz(meta_yolu, meta)
        d.notlar.append({"dagitim_red": {"neden": neden, "tarih": date.today().isoformat()}})
        d.yayin = {}
        d.gec("paketlendi", f"{RED_ONEKI}{neden}")  # takvim bunu düzeltilene (yeniden paketlenene) kadar atlar
    return d
