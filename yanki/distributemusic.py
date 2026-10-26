"""DistributeMusic.AI (https://distributemusic.ai/; Scryne 2026-10-26: "dağıtıcı buldum, buradan atıcaz").

İki kip, `config/yayin.toml` → `[distributemusic]`:
- **Panel (varsayılan):** API anahtarı yok. Hat paketi hazırlar (16 bit / 44,1 kHz WAV, 3000×3000 JPG, `YUKLE.md`
  panel alanlarıyla), takvim sırası geleni bildirir; Scryne panelden yükler ve `yanki yuklendi <kimlik>` der.
- **API:** `.env` → `DISTRIBUTEMUSIC_API_KEY` (Label + API planı, docs/arastirma/11). Hat sesi ve kapağı yükler
  (`POST /v1/files`, dönüştürme gerekirse iş yoklanır), yayını açar (`POST /v1/releases`: açmak incelemeye göndermek
  demek, taslak yok), sonra gece koşusu durumu yoklar: `pending → approved/delivered → live` ya da `rejected` /
  `changes_requested` (+ `feedback`). UPC/ISRC `GET /v1/releases/{id}/links`'ten, mağazalar listeleyince gelir.

Belgeyle sınırlı (2026-10-26, canlı denenmedi): `genre`, `song_language`, `version_type` için izinli değer listesi
yayımlanmamış (yalnız örnek: `Electronic`, `en`, `Original`); `composer`/`lyricist` "gerçek ad + soyad". İlk canlı
gönderimde 400 cevabının `detail`'i kayda geçer ve bildirilir, bu eşlemeler oradan sıkılaştırılır.

Kurallar (ToS, 2026-07-31): AI beyanı zorunlu (`is_ai_generated` + `ai_music_link`; beyansız AI hesap kapatma
nedeni). "Yazılı lisansı olmayan telifli melodi" §8'de anında kapatma nedeni ve cover için ayrı kural yok: bu yüzden
`sozlesme_kabul` Scryne destekten yazılı cevap alıp açana kadar kapalıdır; kapalıyken API yolu hiç gönderim yapmaz.
API'de bölge seçimi yok (RouteNote'taki ABD/CA/MX/IN/PK hariç tutması burada uygulanamaz).

Yarıda kalan yükleme kaldığı yerden sürer: dosya yolları ve `release_id` adım adım `metadata.json` →
`distributemusic`'e yazılır. Gönderimden önce `durum = gonderiliyor`; istek sunucuda başarılı olup cevap kaybolursa
sonraki koşu aynı başlıklı yayını listede bulur, ikinci yayın açmaz.
"""

import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime
from pathlib import Path

from yanki import ag, dosya, durum, sayac

VARSAYILAN_ADRES = "https://distributemusic.ai/api/v1"
SERVIS = "DistributeMusic"
AD = "distributemusic"
KABUL = ("approved", "delivered", "live")
RED = ("rejected", "changes_requested")
KALDIRMA = ("takedown", "taken_down", "removed")
# ACE-Step'in paylaşım sayfası yok; "AI link" üretim aracını gösterir. Destekten yazılı cevapla değişebilir.
AI_BAGLANTI = "https://github.com/ace-step/ACE-Step-1.5"


class Hata(RuntimeError):
    def __init__(self, kod: int | None, mesaj: str):
        super().__init__(f"DistributeMusic {kod or 'ağ'}: {mesaj}")
        self.kod = kod


class ErisimYok(Hata):
    """401 (geçersiz anahtar) ya da 403 (Label/API planı yok): tek yayının değil bütün API'nin sorunu."""


def env_oku(kok: Path) -> dict[str, str]:
    from yanki.spotify import env_oku as oku

    degerler = {k: v for k, v in oku(kok).items() if k.startswith("DISTRIBUTEMUSIC_")}
    degerler.update({k: v for k, v in os.environ.items() if k.startswith("DISTRIBUTEMUSIC_") and v})
    return degerler


def _hata_metni(e: urllib.error.HTTPError) -> str:
    try:
        govde = json.loads(e.read() or b"{}")
    except ValueError:
        return e.reason or str(e.code)
    detay = govde.get("detail") if isinstance(govde, dict) else None
    if isinstance(detay, list):  # doğrulama hatası alan alan gelebilir
        return "; ".join(f"{'.'.join(map(str, x.get('loc', [])))}: {x.get('msg')}" if isinstance(x, dict) else str(x)
                         for x in detay)
    return str(detay or e.reason or e.code)


def _cok_parcali(alanlar: dict[str, str], dosya_adi: str, icerik: bytes, tur: str) -> tuple[bytes, str]:
    sinir = uuid.uuid4().hex
    parcalar = [f'--{sinir}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode()
                for k, v in alanlar.items()]
    parcalar.append(f'--{sinir}\r\nContent-Disposition: form-data; name="file"; filename="{dosya_adi}"\r\n'
                    f"Content-Type: {tur}\r\n\r\n".encode() + icerik + b"\r\n")
    parcalar.append(f"--{sinir}--\r\n".encode())
    return b"".join(parcalar), f"multipart/form-data; boundary={sinir}"


class Istemci:
    """İnce JSON istemcisi. GET ağ hatasında ve 429/5xx'te yeniden denenir (429'da `Retry-After`); POST denenmez
    (yayın açmak incelemeye göndermek: ikinci yayın açmasın)."""

    def __init__(self, anahtar: str, adres: str = VARSAYILAN_ADRES, zaman_asimi: float = 60, uyu=time.sleep):
        if not anahtar:
            raise ErisimYok(None, "DISTRIBUTEMUSIC_API_KEY yok (.env ya da ortam değişkeni)")
        self.anahtar, self.adres, self.zaman_asimi, self._uyu = anahtar, adres.rstrip("/"), zaman_asimi, uyu

    @classmethod
    def kokten(cls, kok: Path) -> "Istemci":
        e = env_oku(kok)
        return cls(e.get("DISTRIBUTEMUSIC_API_KEY", ""), e.get("DISTRIBUTEMUSIC_API_BASE_URL") or VARSAYILAN_ADRES)

    def istek(self, yontem: str, yol: str, govde: dict | None = None, ham: tuple[bytes, str] | None = None) -> dict:
        basliklar = {"Authorization": f"Bearer {self.anahtar}", "Accept": "application/json", "User-Agent": ag.KIMLIK}
        veri = None
        if ham is not None:
            veri, basliklar["Content-Type"] = ham
        elif govde is not None:
            veri, basliklar["Content-Type"] = json.dumps(govde).encode(), "application/json"
        deneme = 1 if yontem == "POST" else 4
        for i in range(deneme):
            http_hatasi = None
            r = urllib.request.Request(f"{self.adres}{yol}", data=veri, method=yontem, headers=basliklar)
            try:
                with urllib.request.urlopen(r, timeout=self.zaman_asimi if ham is None else 900) as c:
                    sonuc = json.loads(c.read() or b"{}")
                sayac.say(SERVIS, True)
                return sonuc
            except urllib.error.HTTPError as e:
                sayac.say(SERVIS, e.code == 404)
                mesaj = _hata_metni(e)
                if e.code == 404:
                    raise ag.Bulunamadi(f"{yol}: {mesaj}") from e
                if e.code in (401, 403):
                    raise ErisimYok(e.code, f"{yontem} {yol}: {mesaj}") from e
                if (e.code != 429 and e.code < 500) or i == deneme - 1:
                    raise Hata(e.code, f"{yontem} {yol}: {mesaj}") from e
                http_hatasi = e
            except (*ag.GECICI, ValueError) as e:
                sayac.say(SERVIS, False)
                if i == deneme - 1:
                    raise Hata(None, f"{yontem} {yol}: {type(e).__name__}: {e}") from e
            self._uyu(ag.bekleme_sn(http_hatasi, i, tavan=60))
        raise AssertionError("ulaşılmaz")

    def get(self, yol: str) -> dict:
        return self.istek("GET", yol)

    def post(self, yol: str, govde: dict) -> dict:
        return self.istek("POST", yol, govde)

    def dosya_yukle(self, yol: Path, tur: str, bekle_sn: float = 600) -> str:
        """`POST /v1/files` (`kind=audio|cover`). Mağazaya hazır dosyada yol hemen gelir; dönüştürülecekse iş
        (`job_id`) bitene kadar yoklanır. Dönen: yayında kullanılacak `path`."""
        icerik_turu = {"audio": "audio/wav", "cover": "image/jpeg"}[tur]
        cevap = self.istek("POST", "/files", ham=_cok_parcali({"kind": tur}, yol.name, yol.read_bytes(),
                                                              icerik_turu))
        if cevap.get("path"):
            return cevap["path"]
        is_ = cevap.get("job_id")
        if not is_:
            raise Hata(None, f"dosya yükleme ({yol.name}): cevapta path da job_id de yok: {cevap}")
        bitis = time.monotonic() + bekle_sn
        while True:
            j = self.get(f"/files/jobs/{is_}")
            if j.get("status") == "done" and j.get("path"):
                return j["path"]
            if j.get("status") == "failed":
                raise Hata(None, f"dosya dönüştürme ({yol.name}): {j.get('error') or 'nedeni yazılmamış'}")
            if time.monotonic() > bitis:
                raise Hata(None, f"dosya dönüştürme ({yol.name}) {bekle_sn:.0f} sn'de bitmedi (iş {is_})")
            self._uyu(5)


# ── eşleme ──────────────────────────────────────────────────
def yazarlar(meta: dict) -> str:
    """"Ad Soyad, Ad Soyad". API "gerçek yasal ad (ad + soyad)" istiyor: soyadı bilinmeyen yazar varsa gönderilmez."""
    adlar = meta.get("orijinal_yazar_adlari") or []
    if adlar:
        if any(not a or not s for a, s in adlar):
            return ""
        return ", ".join(f"{a} {s}" for a, s in adlar)
    tam = [a for a in meta.get("orijinal_yazarlar") or [] if len(a.split()) > 1]
    return ", ".join(tam) if tam and len(tam) == len(meta.get("orijinal_yazarlar") or []) else ""


def ayar_oku(yayin_yolu: Path) -> dict:
    import tomllib

    try:
        with open(yayin_yolu, "rb") as f:
            t = tomllib.load(f).get(AD, {})
    except OSError:
        t = {}
    return {"gece": bool(t.get("gece", False)), "sozlesme_kabul": bool(t.get("sozlesme_kabul", False)),
            "surum_turu": str(t.get("surum_turu") or "Cover"), "ai_baglanti": str(t.get("ai_baglanti") or AI_BAGLANTI),
            "api": bool(t.get("api", True))}


def yayin_alanlari(meta: dict, d: durum.Durum, yayin_tarihi: date, ayar: dict, ses_yolu: str, kapak_yolu: str) -> dict:
    from yanki import tunearo

    yazan = yazarlar(meta)
    return {
        "title": meta["baslik"], "artist_name": meta["sanatci"], "release_type": "single",
        "genre": tunearo.tur_sec(d.analiz.get("stil", ""), (d.kunye or {}).get("sanatci_turleri")),
        "release_date": yayin_tarihi.isoformat(), "song_language": meta.get("dil") or "en",
        "version_type": ayar["surum_turu"], "composer": yazan, "lyricist": yazan, "cover_path": kapak_yolu,
        "tracks": [{"title": meta["baslik"], "audio_path": ses_yolu, "explicit": bool(meta.get("acik_icerik"))}],
        "is_ai_generated": True, "ai_music_link": ayar["ai_baglanti"],
        "distribution_agreement_accepted": True,
    }


def _paket_dosyalari(p: Path) -> tuple[Path, Path]:
    gorunur = lambda desen: [x for x in p.glob(desen) if not x.name.startswith(".")]  # noqa: E731
    sesler, kapaklar = sorted(gorunur("*.wav")), sorted(gorunur("*.jpg"))
    if len(sesler) != 1 or len(kapaklar) != 1:
        raise ValueError(f"pakette tek WAV ve tek kapak olmalı ({p}): {len(sesler)} ses, {len(kapaklar)} kapak "
                         "(eski FLAC paket: `yanki paketle --yeniden <kimlik>`)")
    return sesler[0], kapaklar[0]


def _meta_yaz(yol: Path, deger: dict) -> None:
    meta = json.loads(yol.read_text(encoding="utf-8"))
    meta[AD] = deger
    dosya.json_yaz(yol, meta)


class DistributeMusic:
    ad = AD

    def __init__(self, kok: Path, istemci: Istemci | None = None, ayar: dict | None = None):
        self.kok = kok
        self._istemci = istemci
        self.ayar = ayar if ayar is not None else ayar_oku(kok / "config" / "yayin.toml")

    @property
    def otomatik(self) -> bool:
        """API anahtarı varsa (ve `api` kapatılmamışsa) hat yükler; yoksa panel kipi (insan yükler)."""
        return self.ayar.get("api", True) and (self._istemci is not None
                                               or bool(env_oku(self.kok).get("DISTRIBUTEMUSIC_API_KEY")))

    @property
    def gece(self) -> bool:
        """Takvim sırası gelen paketi koşuda kendiliğinden göndersin mi: anahtar, açık `gece` ve Scryne'ın kabulü."""
        return self.otomatik and self.ayar.get("gece", False) and self.ayar.get("sozlesme_kabul", False)

    @property
    def api(self) -> Istemci:
        if self._istemci is None:
            self._istemci = Istemci.kokten(self.kok)
        return self._istemci

    def _bul(self, baslik: str, sanatci: str) -> dict | None:
        """Cevabı kaybolan gönderim: aynı başlık ve sanatçıyla açılmış en yeni yayın."""
        cevap = self.api.get("/releases")
        liste = cevap.get("releases") or cevap.get("data") or (cevap if isinstance(cevap, list) else [])
        return next((r for r in liste if (r.get("title") or "").casefold() == baslik.casefold()
                     and (r.get("artist_name") or sanatci).casefold() == sanatci.casefold()), None)

    def yukle(self, calisma: Path, d: durum.Durum, yayin_tarihi: date, gonder: bool = True) -> dict:
        """Dosyaları yükler ve (gonder=True ise) yayını açar = incelemeye gönderir. Dönen sözlük
        `takip.yukleme_kaydet`'e gider. gonder=False: yalnız dosyalar yüklenir (yollar kayda geçer)."""
        if not self.ayar.get("sozlesme_kabul"):
            raise ValueError("DistributeMusic: `config/yayin.toml` → [distributemusic] sozlesme_kabul = false. Cover "
                             "kuralı için destekten yazılı cevap alınmadan API gönderimi yapılmaz (docs/arastirma/11)")
        p = durum.klasor(calisma, d.kimlik) / "paket"
        meta_yolu = p / "metadata.json"
        meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
        if not meta.get("sanatci"):
            raise ValueError("pakette sanatçı adı yok (config/yayin.toml → sanatci_adi)")
        if not yazarlar(meta):
            raise ValueError("orijinal yazarların ad + soyadı eksik (DistributeMusic gerçek yasal ad istiyor): "
                             "`girdi/liste.toml` → `yazarlar`, sonra `yanki paketle --yeniden <kimlik>`")
        ses, kapak = _paket_dosyalari(p)
        kayit = dict(meta.get(AD) or {})
        if kayit.get("release_id"):  # önceki koşu göndermiş: olduğu gibi kaydet, yoklama sürdürür
            return self._sonuc(kayit, date.fromisoformat(kayit.get("yayin_tarihi") or yayin_tarihi.isoformat()),
                               {"status": kayit.get("durum") or "pending"})
        if kayit.get("durum") == "gonderiliyor":  # gönderildi ama cevap kaydedilemedi: ikinci yayın açma
            bulunan = self._bul(meta["baslik"], meta["sanatci"])
            if bulunan:
                kayit.update(release_id=bulunan.get("release_id") or bulunan.get("id"),
                             durum=bulunan.get("status") or "pending")
                _meta_yaz(meta_yolu, kayit)
                return self._sonuc(kayit, date.fromisoformat(kayit.get("yayin_tarihi") or yayin_tarihi.isoformat()),
                                   bulunan)
        # aynı dosya yeniden yüklenmez (yeniden paketlenince adı/boyutu değişir)
        imza = lambda f: f"{f.name}:{f.stat().st_size}"  # noqa: E731
        if kayit.get("ses_imza") != imza(ses):
            kayit.update(ses_yolu=self.api.dosya_yukle(ses, "audio"), ses_imza=imza(ses))
            _meta_yaz(meta_yolu, kayit)
        if kayit.get("kapak_imza") != imza(kapak):
            kayit.update(kapak_yolu=self.api.dosya_yukle(kapak, "cover"), kapak_imza=imza(kapak))
            _meta_yaz(meta_yolu, kayit)
        if not gonder:
            return {}
        alanlar = yayin_alanlari(meta, d, yayin_tarihi, self.ayar, kayit["ses_yolu"], kayit["kapak_yolu"])
        kayit.update(durum="gonderiliyor", yayin_tarihi=yayin_tarihi.isoformat())
        _meta_yaz(meta_yolu, kayit)
        try:
            st = self.api.post("/releases", alanlar)
        except Hata as e:
            if e.kod is not None and e.kod < 500:  # sunucu reddetti, yayın açılmadı: yeniden denenebilir
                kayit.update(durum="hata", son_hata=str(e))
                _meta_yaz(meta_yolu, kayit)
            raise
        kayit.update(release_id=st.get("release_id") or st.get("id"), display_id=st.get("display_id"),
                     durum=st.get("status", "pending"), gonderildi=datetime.now().isoformat(timespec="seconds"))
        _meta_yaz(meta_yolu, kayit)
        return self._sonuc(kayit, yayin_tarihi, st)

    @staticmethod
    def _sonuc(kayit: dict, yayin_tarihi: date, st: dict) -> dict:
        return {"release_id": kayit.get("release_id"), "display_id": kayit.get("display_id"),
                "yayin_tarihi": yayin_tarihi.isoformat(), "dagitim_durumu": st.get("status", "pending")}

    def geri_cek(self, calisma: Path, d: durum.Durum, neden: str, bastan: bool = False) -> str:
        """API'de takedown ucu yok: panelden kaldırılır ($5), sonra `yanki geri-cek <kimlik> --kaldirildi`."""
        raise ValueError("DistributeMusic API'si yayın kaldırmıyor: panelden kaldır (takedown), sonra "
                         f"`yanki geri-cek {d.kimlik} --kaldirildi`")

    def yokla(self, calisma: Path, bildir=None) -> list[tuple[durum.Durum, str, str | None]]:
        """API ile yüklenmiş şarkıların durumu. Değişeni kaydeder ve bildirir; red / düzeltme isteği şarkıyı
        `paketlendi`ye döndürür (`dagitim.red_kaydet`). Dönen: (şarkı, durum, önceki durum)."""
        from yanki import dagitim, takip

        sonuc = []
        if not self.otomatik:  # panel kipi: durum panelde (e-posta bildirimi gelirse sonra bağlanır)
            return sonuc
        for d in durum.hepsi(calisma):
            y = takip.yukleme_bilgisi(calisma, d.kimlik) or {}
            if d.asama not in ("yuklendi", "yayinda") or y.get("dagitimci") != self.ad or not y.get("release_id"):
                continue
            rid = y["release_id"]
            try:
                st = self.api.get(f"/releases/{rid}")
            except ErisimYok:
                raise
            except ag.Bulunamadi:
                if bildir:
                    bildir("kayip", f"DistributeMusic'te yok: {d.ad}", f"yayın {rid} bulunamadı",
                           f"{AD}:yok:{d.kimlik}:{rid}")
                sonuc.append((d, "bulunamadi", y.get("dagitim_durumu")))
                continue
            except Hata as e:
                print(f"  {d.ad}: durum alınamadı: {e}")
                sonuc.append((d, "hata", y.get("dagitim_durumu")))
                continue
            st = st.get("release") or st
            yeni, eski = st.get("status"), y.get("dagitim_durumu")
            guncel = {"dagitim_durumu": yeni, "dagitim_kontrol": datetime.now().isoformat(timespec="seconds")}
            if yeni in RED:
                neden = str(st.get("feedback") or "neden yazılmamış").strip()
                guncel["red_metni"] = neden
                takip.yukleme_kaydet(calisma, d.kimlik, guncel)
                ozet = neden[:300]
                etiket = "düzeltme istedi" if yeni == "changes_requested" else "reddetti"
                d = dagitim.red_kaydet(calisma, d.kimlik, f"DistributeMusic {etiket}: {ozet}")
                if bildir:
                    bildir("red", f"DistributeMusic {etiket}: {d.ad}", ozet, f"{AD}:red:{d.kimlik}:{rid}:{yeni}")
                sonuc.append((d, yeni, eski))
                continue
            if yeni in KABUL and not (y.get("upc") and y.get("isrc")):
                try:
                    bag = self.api.get(f"/releases/{rid}/links")
                except (Hata, ag.Bulunamadi):
                    bag = {}
                if bag.get("upc"):
                    guncel["upc"] = str(bag["upc"])
                isrc = next((t.get("isrc") for t in bag.get("tracks") or [] if t.get("isrc")), None)
                if isrc:
                    guncel["isrc"] = isrc.replace("-", "").upper()
                if (bag.get("smartlink") or {}).get("spotify"):
                    guncel["spotify"] = bag["smartlink"]["spotify"]
            takip.yukleme_kaydet(calisma, d.kimlik, guncel)
            if bildir and yeni != eski:
                metin = {"approved": "kabul edildi, mağazalara gönderiliyor",
                         "delivered": "mağazalara teslim edildi",
                         "live": f"mağazalarda canlı (UPC {guncel.get('upc') or y.get('upc') or '—'})",
                         }.get(yeni, f"durum: {yeni}")
                bildir("kayip" if yeni in KALDIRMA else "dagitim", f"DistributeMusic: {d.ad}", metin,
                       f"{AD}:{d.kimlik}:{rid}:{yeni}")
            sonuc.append((d, yeni, eski))
        return sonuc
