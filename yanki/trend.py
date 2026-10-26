"""Gündem keşfi: şu an listelerde olan, yükselen ve çok dinlenen şarkılar (Scryne 2026-10-26: "gündemde hangi popüler
şarkılar varsa, trendde ve çok dinleniyorsa ... daha fazla dinlenme alabiliriz").

Kaynaklar (araştırma 2026-10-26, docs/arastirma/12):
- **Deezer ülke Top-100 listeleri** ("Deezer Charts" kullanıcısı 637006841'in "Top <Ülke>" playlist'leri; günlük,
  anahtarsız, ISRC'li). Kimlikler adla çözülür ve haftada bir tazelenir.
- **Apple Music en çok çalınanlar** (rss.marketingtools.apple.com, ülke başına 100; anahtarsız, ISRC'siz).
- **Spotify Top 50 listeleri** (isteğe bağlı): Web API editoryal listeleri okumuyor (2024-11); Spotify uygulamasının
  içindeki STILLMORE köprüsüyle okunur, parça başına toplam dinlenme gelir → iki gün arası fark günlük dinlenmedir.
  kworb vb. ikinci el Spotify kopyaları kullanılmaz (izin belirsiz).

Puan (`puanla`): her listede `ağırlık × (toplam − sıra + 1) / toplam`, toplanır. Ağırlık: Spotify 1,5 (yayınladığımız
yer), global/dünya listesi ×1,5. Momentum son anlık görüntülerden: son 3 günde ilk kez görülen ×1,3; en iyi sırasında
yükselen +%50'ye kadar; Spotify günlük dinlenmesi varsa log ölçekte ek. Anlık görüntüler `calisma/kesif/trend/`'de
(30 gün). Sonuç keşfin geri kalanına `kesif.Aday(neden="trend")` olarak girer: YouTube/Jev/LRCLIB ölçümü, tür ve dil
süzgeci aynı; Spotify'a boşluk sorulmaz (şarkı zaten yayında).
"""

import json
import math
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from yanki import ag, dosya

DEEZER = "https://api.deezer.com"
DEEZER_LISTE_SAHIBI = 637006841  # "Deezer Charts"
APPLE = "https://rss.marketingtools.apple.com/api/v2/{ulke}/music/most-played/100/songs.json"
SAKLA_GUN = 30
YENI_GUN = 3
AGIRLIK = {"spotify": 1.5, "deezer": 1.0, "apple": 1.0}
GLOBAL = ("worldwide", "global")
FEAT = re.compile(r"\s*(?:,|&|\bx\b|\bfeat\.?|\bft\.?|\bwith\b)\s*", re.I)


@dataclass
class Giris:
    kaynak: str  # "deezer" | "apple" | "spotify"
    liste: str  # "deezer:Turkey", "apple:gb", "spotify:Top 50 - Global"
    sira: int
    toplam: int
    sanatci: str
    ad: str
    isrc: str | None = None
    dinlenme: int | None = None  # Spotify toplam dinlenmesi (yalnız spotify kaynağında)
    cikis: str | None = None
    tur: list = field(default_factory=list)

    @property
    def kimlik(self) -> str:
        from yanki import liste
        from yanki.kesif import sade_ad_gorunur

        return liste.kimlik(ana_sanatci(self.sanatci), sade_ad_gorunur(self.ad))


def ana_sanatci(metin: str) -> str:
    """"Rosé & Bruno Mars", "Artist feat. X" → ilk sanatçı (cover'da sanatçı alanı orijinalin ilk adıdır)."""
    return next((x.strip() for x in FEAT.split(metin or "") if x.strip()), (metin or "").strip())


# ── kaynaklar ───────────────────────────────────────────────
def deezer_listeleri(calisma: Path, json_al=ag.json_al, tazeleme_gun: int = 7) -> dict[str, int]:
    """"Top <Ülke>" adı → playlist kimliği (önbellek `trend/deezer_listeler.json`)."""
    yol = calisma / "kesif" / "trend" / "deezer_listeler.json"
    try:
        k = json.loads(yol.read_text(encoding="utf-8"))
        if date.fromisoformat(k["tarih"]) > date.today() - timedelta(days=tazeleme_gun):
            return k["listeler"]
    except (OSError, ValueError, KeyError):
        pass
    listeler: dict[str, int] = {}
    adres = f"{DEEZER}/user/{DEEZER_LISTE_SAHIBI}/playlists"
    parametre: dict | None = {"limit": 100}
    for _ in range(5):  # sayfalı
        d = json_al(adres, parametre)
        for p in d.get("data") or []:
            if (ad := p.get("title") or "").startswith("Top ") and p.get("nb_tracks", 100) >= 50:
                listeler[ad[4:].strip()] = p["id"]
        if not d.get("next"):
            break
        adres, parametre = d["next"], None
    if listeler:
        dosya.json_yaz(yol, {"tarih": date.today().isoformat(), "listeler": listeler})
    return listeler


def deezer_cek(ulke: str, pid: int, json_al=ag.json_al) -> list[Giris]:
    d = json_al(f"{DEEZER}/playlist/{pid}/tracks", {"limit": 100})
    parcalar = [x for x in d.get("data") or [] if x.get("title") and (x.get("artist") or {}).get("name")]
    return [Giris("deezer", f"deezer:{ulke}", i, len(parcalar), x["artist"]["name"], x["title"], x.get("isrc"))
            for i, x in enumerate(parcalar, 1)]


def apple_cek(ulke: str, json_al=ag.json_al) -> list[Giris]:
    d = json_al(APPLE.format(ulke=ulke.lower()))
    parcalar = [x for x in (d.get("feed") or {}).get("results") or [] if x.get("name") and x.get("artistName")]
    return [Giris("apple", f"apple:{ulke.lower()}", i, len(parcalar), x["artistName"], x["name"],
                  cikis=x.get("releaseDate"), tur=[g.get("name") for g in x.get("genres") or [] if g.get("name")])
            for i, x in enumerate(parcalar, 1)]


def spotify_cek(kopru, ad: str, pid: str) -> list[Giris]:
    """STILLMORE köprüsüyle (Spotify uygulamasının içinden) bir Top 50 listesi: sıra, ISRC, toplam dinlenme."""
    ifade = f"""(async () => {{
      const r = await Stillmore.playlist.scan({json.dumps(pid)});
      return r.rows.map(x => ({{ n: x.n, name: x.name, artist: x.artist, isrc: x.isrc || null,
                                 plays: x.plays ?? null, playable: x.playable }}));
    }})()"""
    satirlar = [x for x in kopru.degerlendir(ifade, 300) or [] if x.get("name") and x.get("artist")]
    return [Giris("spotify", f"spotify:{ad}", i, len(satirlar), x["artist"], x["name"], x.get("isrc"),
                  x.get("plays")) for i, x in enumerate(satirlar, 1)]


@dataclass
class Ayar:
    acik: bool = True
    deezer: tuple[str, ...] = ("Worldwide",)
    apple: tuple[str, ...] = ("us",)
    spotify: dict = field(default_factory=dict)  # ad → playlist kimliği
    yeni_aday: int = 60  # bir koşuda en çok kaç yeni aday ölçülsün (YouTube + Jev + LRCLIB)
    en_az_puan: float = 0.5  # bunun altındaki şarkı aday sayılmaz (tek listenin dibi)

    @classmethod
    def oku(cls, t: dict) -> "Ayar":
        return cls(bool(t.get("acik", True)), tuple(t.get("deezer", cls.deezer)), tuple(t.get("apple", cls.apple)),
                   dict(t.get("spotify") or {}), int(t.get("yeni_aday", 60)), float(t.get("en_az_puan", 0.5)))


def topla(calisma: Path, ayar: Ayar, json_al=ag.json_al, kopru=None, yaz=print) -> list[Giris]:
    """Bütün kaynaklardan listeler; tek kaynağın hatası diğerlerini durdurmaz."""
    girisler: list[Giris] = []
    try:
        dz = deezer_listeleri(calisma, json_al)
    except (OSError, ValueError) as e:
        yaz(f"✗ Deezer liste dizini: {e}")
        dz = {}
    for ulke in ayar.deezer:
        if ulke not in dz:
            yaz(f"✗ Deezer'da 'Top {ulke}' listesi yok (config/kesif.toml → [trend] deezer)")
            continue
        try:
            girisler += deezer_cek(ulke, dz[ulke], json_al)
        except (OSError, ValueError, ag.Bulunamadi) as e:
            yaz(f"✗ Deezer Top {ulke}: {e}")
    for ulke in ayar.apple:
        try:
            girisler += apple_cek(ulke, json_al)
        except (OSError, ValueError, ag.Bulunamadi) as e:
            yaz(f"✗ Apple Music {ulke}: {e}")
    if kopru is not None:
        for ad, pid in ayar.spotify.items():
            try:
                girisler += spotify_cek(kopru, ad, pid)
            except Exception as e:  # noqa: BLE001 — köprü/STILLMORE hatası: diğer kaynaklar yeter
                yaz(f"✗ Spotify {ad}: {type(e).__name__}: {e}")
    return girisler


# ── anlık görüntü ve puan ───────────────────────────────────
def klasor(calisma: Path) -> Path:
    return calisma / "kesif" / "trend"


def anlik_yaz(calisma: Path, girisler: list[Giris], gun: date | None = None) -> Path:
    gun = gun or date.today()
    yol = klasor(calisma) / f"{gun.isoformat()}.json"
    dosya.json_yaz(yol, {"zaman": datetime.now().isoformat(timespec="seconds"),
                         "girisler": [asdict(g) for g in girisler]}, None)
    sinir = (gun - timedelta(days=SAKLA_GUN)).isoformat()
    for eski in klasor(calisma).glob("????-??-??.json"):
        if eski.stem < sinir:
            eski.unlink(missing_ok=True)
    return yol


def anliklar(calisma: Path, once: date | None = None) -> dict[str, list[Giris]]:
    """Tarih → girişler, bugünden (ya da `once`'den) önceki anlık görüntüler."""
    once = once or date.today()
    sonuc = {}
    for yol in sorted(klasor(calisma).glob("????-??-??.json")):
        if yol.stem >= once.isoformat():
            continue
        try:
            veri = json.loads(yol.read_text(encoding="utf-8"))
            sonuc[yol.stem] = [Giris(**g) for g in veri.get("girisler") or []]
        except (OSError, ValueError, TypeError):
            continue
    return sonuc


def puanla(girisler: list[Giris], gecmis: dict[str, list[Giris]] | None = None,
           gun: date | None = None) -> dict[str, dict]:
    """Kimlik → {skor, sanatci, ad, isrc, listeler, en_iyi, ilk_gorulme, yukselis, gunluk_dinlenme, tarih}."""
    gun = gun or date.today()
    gecmis = gecmis or {}
    sonuc: dict[str, dict] = {}
    for g in girisler:
        x = sonuc.setdefault(g.kimlik, {"sanatci": ana_sanatci(g.sanatci), "ad": g.ad, "isrc": None, "skor": 0.0,
                                        "listeler": [], "en_iyi": g.sira, "tur": [], "cikis": None})
        agirlik = AGIRLIK.get(g.kaynak, 1.0) * (1.5 if any(k in g.liste.lower() for k in GLOBAL) else 1.0)
        x["skor"] += agirlik * (g.toplam - g.sira + 1) / max(g.toplam, 1)
        x["listeler"].append({"liste": g.liste, "sira": g.sira})
        x["en_iyi"] = min(x["en_iyi"], g.sira)
        x["isrc"] = x["isrc"] or g.isrc
        x["tur"] = x["tur"] or g.tur
        x["cikis"] = x["cikis"] or g.cikis
        if g.dinlenme:
            x["dinlenme"] = max(x.get("dinlenme") or 0, g.dinlenme)
    gecmis_sira = sorted(gecmis)
    for kimlik, x in sonuc.items():
        gorulen = [t for t in gecmis_sira if any(g.kimlik == kimlik for g in gecmis[t])]
        x["ilk_gorulme"] = gorulen[0] if gorulen else gun.isoformat()
        carpan = 1.0
        if x["ilk_gorulme"] >= (gun - timedelta(days=YENI_GUN)).isoformat():
            carpan *= 1.3  # yeni giriş: gündeme yeni girdi
        # 3 gün (yoksa en eski) önceki en iyi sıraya göre yükseliş
        hedef = (gun - timedelta(days=YENI_GUN)).isoformat()
        once = [t for t in gorulen if t <= hedef] or gorulen[:1]
        if once:
            eski = min((g.sira for g in gecmis[once[-1]] if g.kimlik == kimlik), default=None)
            if eski is not None:
                x["yukselis"] = eski - x["en_iyi"]
                carpan *= 1 + 0.5 * max(0, min(x["yukselis"], 50)) / 50
        # Spotify günlük dinlenmesi: en yakın önceki anlık görüntüyle fark
        if x.get("dinlenme"):
            for t in reversed(gecmis_sira):
                onceki = max((g.dinlenme or 0 for g in gecmis[t] if g.kimlik == kimlik), default=0)
                if onceki and onceki < x["dinlenme"]:
                    gun_farki = max(1, (gun - date.fromisoformat(t)).days)
                    x["gunluk_dinlenme"] = round((x["dinlenme"] - onceki) / gun_farki)
                    carpan *= 1 + min(1.0, math.log10(max(x["gunluk_dinlenme"], 1)) / 7)
                    break
        x["skor"] = round(x["skor"] * carpan, 3)
        x["tarih"] = gun.isoformat()
    return sonuc


def adaylar(puanlar: dict[str, dict], ayar: Ayar, bilinen: set[str]) -> list:
    """Puanı eşiği geçen şarkılar `kesif.Aday` olarak (yüksek puan önce). Bilinen (listede/çalışmada/elenmiş) kimlik
    yeniden ölçülmez ama trend bilgisi `kesif.tasi` ile güncellenir: çağıran onları da verir."""
    from yanki.kesif import DUZENLEME, Aday

    sonuc = []
    for kimlik, x in sorted(puanlar.items(), key=lambda kv: -kv[1]["skor"]):
        if x["skor"] < ayar.en_az_puan or DUZENLEME.search(x["ad"]):
            continue
        a = Aday(x["sanatci"], x["ad"], "trend:" + ",".join(sorted({y["liste"] for y in x["listeler"]})),
                 isrc=x["isrc"], neden="trend", geri_geldi=False,
                 trend={k: x.get(k) for k in ("skor", "en_iyi", "listeler", "ilk_gorulme", "yukselis",
                                              "gunluk_dinlenme", "dinlenme", "tarih", "cikis")})
        if a.kimlik != kimlik:  # ad sadeleştirmesi farklı kimlik verdiyse liste kimliğiyle eşleşmez: atla
            continue
        sonuc.append(a)
    return sonuc
