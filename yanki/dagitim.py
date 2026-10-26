"""Dağıtım arayüzü ve yayın takvimi (Roadmap Faz 10).

`Dagitimci` hattın dağıtımcıyla konuştuğu tek yer. İki tür: elle (RouteNote, DistroKid: API yok, form insanda; hat
takvimde sırası gelen paketi bildirir, Scryne yükleyip `yanki yuklendi` der) ve otomatik (Tunearo, `yanki/tunearo.py`:
gece koşusu sırası gelen paketi kendisi yükler ve incelemeye gönderir, sonraki gecelerde durumunu yoklar). Hangisi
olduğu `config/yayin.toml` → `dagitimci`; takvim, kuyruk ve bildirim ikisinde aynı.

Takvim (`config/yayin.toml` → `[takvim]`): `paketlendi` şarkılar kuyruk; sıra keşif puanı (kaldırılmış ve aranan şarkı
önce), sonra onay sırası. Haftada `haftada` yükleme (0: sınır yok, sırası gelen her paket aynı koşuda); ilk boş
gün son yüklemeden bir aralık sonra. Önerilen yayın
tarihi yüklemeden `yayin_on_gun` gün sonra (Tunearo'da 1: en erken; RouteNote'ta 21 kullanılıyordu).
`baslangic = "ilk_kabul"`: etkin dağıtımcıda ilk kabul gelene kadar incelemede en çok bir yükleme; o reddedilirse
neden anlaşılana kadar yeni yükleme yok (Roadmap Faz 7: red gelirse nedeni kapak mı AI mı önce o anlaşılmalı; aynı
nedenle kuyruğun tamamı ve hesabın parça kotası yanmasın). `"surekli"`: kabul beklenmez, her gün yükleme sürer;
yalnız düzeltilmemiş bir red varken durur. `"hemen"`: hiçbir kapı yok.

Geri çekme (`geri_cek`): yüklenmiş yayın dağıtımcıdan kaldırılır, şarkı `onaylandi`ya döner; gece koşusu onu güncel
ayarlarla (dağıtımcının ses biçimi, kapak kaynağı) yeniden paketler ve kuyruğa girer (red değildir, takvimi
durdurmaz). Elle dağıtımcıda insan panelden kaldırır; Tunearo'da taslak silinir, canlı yayına takedown istenir,
incelemedeki yayın API'den geri çekilemediği için işaretlenir ve sonuç gelince yoklama bitirir.
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
    # takvim (gece/sürekli koşu) sırası geleni kendisi göndersin mi; yoksa yalnız bildirilir. Varsayılan kapalı: yeni
    # bir dağıtımcı sınıfı alanı unutursa geri alınamaz gönderim onaysız başlamasın (Denetim 7)
    gece: bool

    def yukle(self, calisma: Path, d: durum.Durum, yayin_tarihi: date, gonder: bool = True) -> dict:
        """Paketi yükler, yükleme bilgisini (`takip.yukleme_kaydet` alanları) döner."""
        ...


class Elle:
    """Formu insanın doldurduğu herhangi bir dağıtımcı (DistroKid, boş ayar)."""
    otomatik = False
    gece = False

    def __init__(self, ad: str):
        self.ad = ad

    def yukle(self, calisma: Path, d: durum.Durum, yayin_tarihi: date, gonder: bool = True) -> dict:
        raise NotImplementedError(f"{self.ad or 'dağıtımcı'} için API yok: YUKLE.md ile elle yükle")


def sec(ad: str, kok: Path | None = None) -> Dagitimci:
    if ad == "tunearo":
        from yanki import ayarlar, tunearo

        return tunearo.Tunearo(kok or ayarlar.KOK)
    if ad == "routenote":
        from yanki import ayarlar, routenote

        return routenote.RouteNote.ayardan(kok or ayarlar.KOK)
    if ad == "distributemusic":
        from yanki import ayarlar, distributemusic

        return distributemusic.DistributeMusic(kok or ayarlar.KOK)
    return Elle(ad)


def otomatik_yukle(calisma: Path, dagitimci: Dagitimci, kimlik: str, yayin_tarihi: date,
                   gonder: bool = True) -> dict:
    """API'li dağıtımcıya yükler; gönderildiyse yükleme bilgisi kaydedilir ve şarkı `yuklendi`ye geçer."""
    from yanki import takip

    d = durum.oku(calisma, kimlik)
    if d is None or d.asama != "paketlendi":
        raise ValueError(f"paketlenmiş bir şarkı değil (aşama: {d.asama if d else 'yok'})")
    if (d.hata or "").startswith(RED_ONEKI):
        raise ValueError(f"dağıtımcı reddetti, önce düzeltip yeniden paketle: {d.hata}")
    bilgi = dagitimci.yukle(calisma, d, yayin_tarihi, gonder)
    if not gonder:
        return bilgi
    takip.yukleme_kaydet(calisma, kimlik, {**bilgi, "dagitimci": dagitimci.ad}, dagitimci.ad)
    with durum.guncelle(calisma, kimlik) as taze:
        if taze.asama == "paketlendi":
            taze.gec("yuklendi")
    return bilgi


# ── takvim ──────────────────────────────────────────────────
@dataclass(frozen=True)
class Takvim:
    acik: bool = True
    haftada: int = 1
    yayin_on_gun: int = 21
    baslangic: str = "ilk_kabul"  # "ilk_kabul" | "surekli" | "hemen"

    @property
    def sinirsiz(self) -> bool:
        """`haftada = 0`: sıradaki her paket aynı koşuda yüklenir (Scryne, 2026-10-10: "yükleyebildiği kadar")."""
        return self.haftada <= 0

    @property
    def aralik(self) -> timedelta:
        if self.sinirsiz:
            return timedelta(0)
        return timedelta(days=max(1, round(7 / self.haftada)))  # tam gün: haftada 2 → 4 günde bir


def takvim_oku(yayin_yolu: Path) -> Takvim:
    with open(yayin_yolu, "rb") as f:
        t = tomllib.load(f).get("takvim", {})
    baslangic = t.get("baslangic", "ilk_kabul")
    if baslangic not in ("ilk_kabul", "surekli", "hemen"):
        raise ValueError(f"takvim.baslangic ilk_kabul, surekli ya da hemen olmalı: {baslangic}")
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
    bugun: date = date.min  # planın kurulduğu gün (verilmezse bugün)
    # orijinal yazarı bilinmeyen paketler: hiçbir dağıtımcı yazarsız cover almıyor; `liste.toml` → `yazarlar` bekler
    yazarsiz: tuple[str, ...] = ()
    # RouteNote'ta insanın elinde bekleyen paketler (kuyruğa girmez): önceki oturumda hazırlanmış taslak (`hazir`;
    # yayın sayfası otomasyona boş geliyor, panelden gönderilir) ya da son tıktan sonra yarıda kalan gönderim
    # (`gonderiliyor`; panelde bakılır). Kuyrukta kalsalar her koşu tarayıcıyı açıp aynı hatayla düşerdi.
    elle_bekleyen: tuple[str, ...] = ()

    @property
    def bugun_yuklenecekler(self) -> list[Sira]:
        """Yükleme günü gelmiş bütün paketler, sırayla (takvim beklemedeyse boş)."""
        gun = self.bugun if self.bugun != date.min else date.today()
        return [] if self.beklemede else [x for x in self.sira if x.yukleme <= gun]

    @property
    def bugun_yuklenecek(self) -> Sira | None:
        return next(iter(self.bugun_yuklenecekler), None)


def _meta(calisma: Path, d: durum.Durum) -> dict:
    import json

    yol = durum.klasor(calisma, d.kimlik) / "paket" / "metadata.json"
    try:
        return json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


ELLE_ADIMLAR = ("hazir", "gonderiliyor")


def _routenote_adim(meta: dict) -> str | None:
    return (meta.get("routenote") or {}).get("adim")


def _yarim(calisma: Path, d: durum.Durum) -> dict | None:
    """API'li dağıtımcıda açılmış ama kaydı tamamlanmamış yükleme (`metadata.json` → `tunearo`): taslak ya da
    gönderilip sonucu kaydedilemeyen (`gonderiliyor`)."""
    kayit = _meta(calisma, d).get("tunearo") or {}
    return kayit if d.asama == "paketlendi" and kayit.get("release_id") else None


def _ilk_kabul_bekleme(calisma: Path, hepsi: list[durum.Durum], dagitimci: str | None) -> str | None:
    """`ilk_kabul` kapısı. Dağıtımcı verilmezse eski kural: hiçbir parça Spotify'da değilse bekle."""
    if dagitimci is None:
        if any(d.asama == "yayinda" for d in hepsi):
            return None
        return "ilk parça Spotify'a çıkana kadar bekliyor (dağıtımcı incelemesi)"
    bizim = lambda y: bool(y) and y.get("dagitimci") in (dagitimci, None)  # noqa: E731 — eski kayıtta ad yok
    incelemede, red = [], []
    for d in hepsi:
        meta = _meta(calisma, d)
        y, gecmis = meta.get("yukleme"), list(meta.get("yukleme_gecmisi") or [])
        if bizim(y) and (d.asama == "yayinda" or y.get("dagitim_durumu") in ("approved", "live")):
            return None  # bu dağıtımcı en az bir parçayı kabul etti
        if bizim(y) and d.asama == "yuklendi":
            incelemede.append(d.ad)
        elif d.asama == "paketlendi" and ((meta.get("tunearo") or {}).get("durum") == "gonderiliyor"
                                          or _routenote_adim(meta) == "gonderiliyor"):
            incelemede.append(d.ad)  # gönderildi ama sonuç kaydedilemedi: sunucuda incelemede olabilir
        red += [d.ad for g in gecmis if g.get("red") and g.get("dagitimci") in (dagitimci, None)]
    if incelemede:
        return f"{dagitimci}: ilk kabul bekleniyor ({', '.join(incelemede)} incelemede), o gelene kadar yükleme yok"
    if red:
        return (f"{dagitimci} ilk yüklemeyi reddetti ({', '.join(dict.fromkeys(red))}); neden anlaşılıp düzeltilmeden "
                "yeni yükleme yok (düzeltilen şarkı: yanki yukle <kimlik>)")
    return None


def plan(calisma: Path, t: Takvim, bugun: date | None = None, puanlar: dict[str, float] | None = None,
         dagitimci: str | None = None) -> Plan:
    """Kuyruk ve tarihleri hesaplar (kayıt tutmaz: her çağrıda durumdan yeniden çıkar, elle yükleme hemen yansır).
    `dagitimci`: etkin dağıtımcı; `ilk_kabul` kapısı onun kabul/red geçmişine bakar."""
    bugun = bugun or date.today()
    if puanlar is None:
        from yanki import kesif

        puanlar = {k: a.puan for k, a in kesif.oku(calisma).items()}
    from yanki.tunearo import yazarlar

    hepsi = durum.hepsi(calisma)
    yuklemeler = [z.date() for d in hepsi if d.asama in ("yuklendi", "yayinda") and (z := _gecis(d, "yuklendi"))]
    son = max(yuklemeler, default=None)
    reddedilen = [d.kimlik for d in hepsi if d.asama == "paketlendi" and (d.hata or "").startswith(RED_ONEKI)]
    # yazarsız paket sıraya girmez: her koşuda yüklenmeye çalışılıp düşüyor, özette "yükleme sırası geldi" diye
    # görünüyordu (2026-10-11, Heaven Knows); yazarlar listeye yazılınca paket yenilenir ve sıraya girer
    yazarsiz = tuple(d.kimlik for d in hepsi if d.asama == "paketlendi" and d.kimlik not in reddedilen
                     and (meta := _meta(calisma, d)) and not yazarlar(meta))
    elle_bekleyen = tuple(d.kimlik for d in hepsi if d.asama == "paketlendi" and d.kimlik not in reddedilen
                          and dagitimci in (None, "routenote") and _routenote_adim(_meta(calisma, d)) in ELLE_ADIMLAR)
    # yarım kalan API yüklemesi önce: aynı yayın tamamlanır, açılmış taslak ve parça sahipsiz kalmaz
    kuyruk = sorted((d for d in hepsi if d.asama == "paketlendi" and d.kimlik not in reddedilen
                     and d.kimlik not in yazarsiz and d.kimlik not in elle_bekleyen),
                    key=lambda d: (_yarim(calisma, d) is None, -puanlar.get(d.kimlik, 0.0),
                                   _gecis(d, "onaylandi") or datetime.max, d.kimlik))
    ilk = max(bugun, son + t.aralik) if son else bugun
    sira = [Sira(d.kimlik, d.sanatci, d.ad, gun := ilk + i * t.aralik, gun + timedelta(days=t.yayin_on_gun),
                 puanlar.get(d.kimlik, 0.0)) for i, d in enumerate(kuyruk)]
    beklemede = None
    if not t.acik:
        beklemede = "takvim kapalı (config/yayin.toml → [takvim])"
    elif t.baslangic == "ilk_kabul":
        beklemede = _ilk_kabul_bekleme(calisma, hepsi, dagitimci)
    elif t.baslangic == "surekli" and reddedilen:
        adlar = ", ".join(d.ad for d in hepsi if d.kimlik in reddedilen)
        beklemede = (f"dağıtımcı reddetti ({adlar}); neden anlaşılıp düzeltilmeden yeni yükleme yok "
                     "(düzeltilen şarkı: yanki paketle --yeniden, sonra yanki yukle <kimlik>)")
    if beklemede is None and dagitimci == "tunearo" and (e := erisim_kapali(calisma)):
        beklemede = f"Tunearo API erişimi kapalı ({e}); erişim açılınca yüklemeler kendiliğinden sürer"
    return Plan(sira, beklemede, son, reddedilen, bugun, yazarsiz, elle_bekleyen)


ERISIM_DENEME_SAAT = 6  # erişim kapalı görüldükten bu kadar sonra takvim bir yüklemeyi yeniden dener


def erisim_kapali(calisma: Path, simdi: datetime | None = None) -> str | None:
    """Tunearo erişimi yakın zamanda kapalı görüldüyse kısa açıklama. Takvim her 30 dk'da yüklemeyi denemesin; durum
    yoklaması (3 saatte bir) erişim açılınca kaydı siler. Kayıt `ERISIM_DENEME_SAAT`'ten eskiyse takvim yeniden dener
    (yüklenmiş şarkı yoksa yoklama da yok: kayıt başka türlü kalkmazdı)."""
    from yanki import tunearo

    e = tunearo.erisim_durumu(calisma)
    if not e:
        return None
    try:
        son = datetime.fromisoformat(e["son"])
    except (KeyError, ValueError):
        return None
    if (simdi or datetime.now()) - son > timedelta(hours=ERISIM_DENEME_SAAT):
        return None
    return f"{e['ilk'][:16].replace('T', ' ')}'dan beri"


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
            if meta.get("routenote"):  # RouteNote reddedilen yayını katalogdan çıkarıyor: yeniden gönderim yeni taslak
                meta.setdefault("routenote_gecmisi", []).append({**meta.pop("routenote"), "red": neden,
                                                                 "red_tarihi": date.today().isoformat()})
            dosya.json_yaz(meta_yolu, meta)
        d.notlar.append({"dagitim_red": {"neden": neden, "tarih": date.today().isoformat()}})
        d.yayin = {}
        d.gec("paketlendi", f"{RED_ONEKI}{neden}")  # takvim bunu düzeltilene (yeniden paketlenene) kadar atlar
    return d


# ── geri çekme ──────────────────────────────────────────────
def geri_cekildi_kaydet(calisma: Path, kimlik: str, neden: str | None = None, yeni_yayin: bool = True,
                        son_durum: str | None = None, bastan: bool | None = None) -> durum.Durum:
    """Yayın dağıtımcıdan kalktı: yükleme bilgisi geçmişe (`geri_cekildi`), şarkı `onaylandi`ya döner (eski paket
    başka dağıtımcının biçiminde ya da eski kapakla olabilir: sonraki paketleme güncel ayarlarla yeniler).
    `yeni_yayin`: Tunearo kaydı da geçmişe taşınır, sonraki yükleme yeni yayın açar (silinen taslak, takedown);
    False: reddedilmiş yayın aynı kayıtla düzeltilip yeniden gönderilir (parça kotası yanmaz)."""
    import json

    from yanki import dosya

    bugun = date.today().isoformat()
    with durum.guncelle(calisma, kimlik) as d:
        if d.asama not in ("yuklendi", "yayinda"):
            raise ValueError(f"yüklenmiş bir şarkı değil (aşama: {d.asama})")
        meta_yolu = durum.klasor(calisma, kimlik) / "paket" / "metadata.json"
        if meta_yolu.exists():
            meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
            y = meta.pop("yukleme", None) or {}
            isaret = y.pop("geri_cek", None) or {}
            neden = neden or isaret.get("neden") or "geri çekildi"
            bastan = isaret.get("bastan", False) if bastan is None else bastan
            meta.setdefault("yukleme_gecmisi", []).append(
                {**y, "geri_cekildi": neden, "geri_cekme_tarihi": bugun, **({"son_durum": son_durum} if son_durum
                                                                            else {})})
            if meta.get("routenote"):  # kaldırılan yayının UPC'si: yeniden yükleme yeni taslak açar
                meta.setdefault("routenote_gecmisi", []).append(meta.pop("routenote"))
            if meta.get("tunearo"):
                if yeni_yayin:
                    meta.setdefault("tunearo_gecmisi", []).append(meta.pop("tunearo"))
                else:
                    meta["tunearo"]["durum"] = son_durum
            dosya.json_yaz(meta_yolu, meta)
        neden = neden or "geri çekildi"
        d.notlar.append({"geri_cekildi": {"neden": neden, "tarih": bugun}})
        d.yayin = {}
        d.gec("onaylandi")
    if bastan:  # eski paketle sıraya dönmesin: adaylar arşive, şarkı yeniden üretime (uretim.bastan)
        from yanki import uretim

        d = uretim.bastan(calisma, kimlik, f"geri çekildi: {neden}")
    return d


def geri_cek(calisma: Path, kimlik: str, neden: str, kok: Path | None = None, kaldirildi: bool = False,
             bastan: bool = False) -> str:
    """Yüklenmiş şarkıyı dağıtımcıdan geri çeker. Dönen: "tamam" (kuyruğa döndü) | "bekliyor" (Tunearo incelemesinde:
    işaretlendi, gece yoklaması sonuç gelince bitirir). Elle dağıtımcıda yayını insan panelden kaldırır, sonra
    `kaldirildi=True` ile kaydedilir."""
    from yanki import takip

    d = durum.oku(calisma, kimlik)
    if d is None:
        raise durum.Yok(kimlik)
    if d.asama not in ("yuklendi", "yayinda"):
        raise ValueError(f"yüklenmiş bir şarkı değil (aşama: {d.asama})")
    ad = (takip.yukleme_bilgisi(calisma, kimlik) or {}).get("dagitimci") or "routenote"
    dagitimci = sec(ad, kok)
    if hasattr(dagitimci, "geri_cek"):  # Tunearo; RouteNote'ta kaldırma panelden (insan)
        return dagitimci.geri_cek(calisma, d, neden, bastan=bastan)
    if not kaldirildi:
        raise ValueError(f"{ad} için API yok: yayını panelden kaldır, sonra aynı komutu --kaldirildi ile ver")
    geri_cekildi_kaydet(calisma, kimlik, neden, bastan=bastan)
    return "tamam"


# Otomatik yüklemesi düşen paket her 30 dk'da yeniden denenmez: ilk düşüşten sonra bir kez hemen (geçici ağ/sayfa
# hatası), sonra 2, 4, 8, 16, en çok 24 saatte bir. 2026-10-16: bir paketin RouteNote formu (#edit-did12) gece
# 01:00'den beri her koşuda 45 sn zaman aşımıyla düştü; her deneme tarayıcı açıp 75 sn sürdü, koşu her seferinde
# "sorunlu" bitti. Odadaki "Şimdi yeniden dene" kaydı siler (`yukleme_hatasi_sil`).
YUKLEME_TEKRAR_SAAT_EN_COK = 24


def yukleme_hatalari_yolu(calisma: Path) -> Path:
    return calisma / ".yukleme_hatalari.json"


def yukleme_hatalari(calisma: Path, kuyrukta: set[str]) -> dict:
    """Kuyruktaki paketlerin otomatik yükleme düşüşleri ({kimlik: {sayi, son, hata}}); kuyruktan çıkanınki atılır."""
    import json

    try:
        veri = json.loads(yukleme_hatalari_yolu(calisma).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v for k, v in veri.items() if k in kuyrukta and isinstance(v, dict)} if isinstance(veri, dict) else {}


def yukleme_hatalari_yaz(calisma: Path, hatalar: dict) -> None:
    from yanki import dosya

    try:
        dosya.json_yaz(yukleme_hatalari_yolu(calisma), hatalar)
    except OSError as e:  # kayıt yazılamazsa paket yalnız daha sık denenir
        print(f"yükleme hataları kaydedilemedi: {e}")


def yukleme_hatasi_sil(calisma: Path, kimlik: str) -> bool:
    """Paketin düşüş kaydını siler: sonraki koşu beklemeden dener. Kayıt yoksa False. Oda bunu koşu sürerken çağırmaz
    (koşu kaydı bellekte tutup sonunda yazar)."""
    import json

    yol = yukleme_hatalari_yolu(calisma)
    try:
        veri = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if not isinstance(veri, dict) or veri.pop(kimlik, None) is None:
        return False
    yukleme_hatalari_yaz(calisma, veri)
    return True


def yukleme_sonraki_deneme(kayit: dict | None) -> datetime | None:
    """Düşen yüklemenin en erken yeniden deneneceği an (None: hemen)."""
    if not kayit or int(kayit.get("sayi", 0)) < 2:
        return None
    try:
        son = datetime.fromisoformat(kayit["son"])
    except (KeyError, TypeError, ValueError):
        return None
    return son + timedelta(hours=min(YUKLEME_TEKRAR_SAAT_EN_COK, 2 ** (int(kayit["sayi"]) - 1)))
