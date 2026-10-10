"""Tunearo dağıtım API'si (arkadaşın dağıtım sitesi; Roadmap Faz 10, 2026-10-10). Doküman: https://api.tunearo.com/

Hat paketi kendisi yükler: yayın (taslak) → kapak → parça → ses → incelemeye gönder. Sonra gece koşusu durumu yoklar:
`pending → approved → live` ya da `rejected` (neden yazılı). Kabulde UPC ve ISRC'yi Tunearo atar, `metadata.json` →
`yukleme`'ye yazılır; `yanki takip` ISRC'yle Spotify'da arar.

Canlı bulgular (2026-10-10, dokümanla farkı):
- Liste uçları `{"data": [...]}` döner (doküman `artists`/`tracks` diyor); tekil uçlar dokümandaki gibi.
- `primary_genre` serbest metin, doğrulama yok → tür kodda standart adlardan seçilir (`tur_sec`).
- API ile açılan yayında `services` boş geliyor: mağazalar açıkça gönderilir (panelden açılan yayınlarda 34 mağaza).
- `artist_ids` verilmezse `primary_artist_name` adına yeni sanatçı açılıyor → sanatçı adıyla bulunur, bir kez açılır.
- Hesap arkadaşın, başka sanatçıların yayınları da orada: hat yalnız kendi kaydettiği `release_id`'lere dokunur.
- Tunearo'nun kalite kontrolü ses eşleşmesi (`acr_match_count`) ve AI tespiti (`ai_detected`) yapıyor; AI tespiti
  tek başına red değil (canlı yayında `ai_detected: true`), orijinal kayıtla eşleşen remix/cover "derivative work"
  diye reddedilmiş (`qc_proof_required`).

Yükleme kaldığı yerden sürer: `release_id`/`track_id` adım adım paketin `metadata.json` → `tunearo`'suna yazılır,
yarıda kalan koşu aynı yayını tamamlar (hesabın parça kotası boşa yanmaz). Reddedilen yayın yeniden paketlenince aynı
yayın düzeltilip yeniden gönderilir.

Anahtar `.env` → `TUNEARO_API_KEY` (ortam değişkeni ezer). Webhook için herkese açık HTTPS adres gerekiyor; hat yerel
çalıştığı için durum yoklamayla izlenir (öneri: yayın başına dakikada en çok bir; gece bir kez).
"""

import json
import os
import re
import tempfile
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

from yanki import ag, dosya, durum, sayac

VARSAYILAN_ADRES = "https://dashboard.tunearo.com/api/public/v1"
SERVIS = "Tunearo"
# Panelden açılan yayınların mağaza listesi (2026-10-10, 34 mağaza). Hariç tutulanlar config/yayin.toml → [tunearo].
MAGAZALAR = ("apple", "deezer", "spotify", "youtube_music", "tidal", "amazon", "ami", "qobuz", "pandora", "kkbox",
             "7digital", "imusica", "soundcloud", "iheartradio", "anghami", "soundexchange", "jiosaavn", "awa",
             "netease", "siriusxm", "youtube_cid", "facebook_audio", "facebook_rights", "mixcloud", "tiktok",
             "boomplay", "peloton", "audiomack", "trebel", "kuack", "kuaishou", "audible_magic", "tuned_global",
             "lissen")
DUZENLENEBILIR = ("draft", "rejected")
KABUL = ("approved", "live")
KALDIRMA = ("takedown", "takedown_requested", "taken_down")


class TunearoHatasi(RuntimeError):
    def __init__(self, kod: int | None, mesaj: str):
        super().__init__(f"Tunearo {kod or 'ağ'}: {mesaj}")
        self.kod = kod


class AyarYok(TunearoHatasi):
    pass


def env_oku(kok: Path) -> dict[str, str]:
    from yanki.spotify import env_oku as oku

    degerler = {k: v for k, v in oku(kok).items() if k.startswith("TUNEARO_")}
    degerler.update({k: v for k, v in os.environ.items() if k.startswith("TUNEARO_") and v})
    return degerler


class Istemci:
    """İnce JSON istemcisi. Okumalar ve PATCH/PUT ağ hatasında yeniden denenir; POST denenmez (yinelenen yayın ya da
    parça açıp kotayı yakmasın)."""

    def __init__(self, anahtar: str, adres: str = VARSAYILAN_ADRES, zaman_asimi: float = 60):
        if not anahtar:
            raise AyarYok(None, "TUNEARO_API_KEY yok (.env ya da ortam değişkeni)")
        self.anahtar, self.adres, self.zaman_asimi = anahtar, adres.rstrip("/"), zaman_asimi

    @classmethod
    def kokten(cls, kok: Path) -> "Istemci":
        e = env_oku(kok)
        return cls(e.get("TUNEARO_API_KEY", ""), e.get("TUNEARO_API_BASE_URL") or VARSAYILAN_ADRES)

    def istek(self, yontem: str, yol: str, govde: dict | None = None) -> dict:
        veri = json.dumps(govde).encode() if govde is not None else None
        basliklar = {"Authorization": f"Bearer {self.anahtar}", "Accept": "application/json", "User-Agent": ag.KIMLIK}
        if veri is not None:
            basliklar["Content-Type"] = "application/json"
        deneme = 1 if yontem == "POST" else 3
        for i in range(deneme):
            r = urllib.request.Request(f"{self.adres}{yol}", data=veri, method=yontem, headers=basliklar)
            try:
                with urllib.request.urlopen(r, timeout=self.zaman_asimi) as c:
                    sonuc = json.loads(c.read() or b"{}")
                sayac.say(SERVIS, True)
                return sonuc
            except urllib.error.HTTPError as e:
                sayac.say(SERVIS, e.code == 404)
                mesaj = _hata_metni(e)
                if e.code == 404:
                    raise ag.Bulunamadi(f"{yol}: {mesaj}") from e
                if e.code < 500 or i == deneme - 1:
                    raise TunearoHatasi(e.code, f"{yontem} {yol}: {mesaj}") from e
            except (urllib.error.URLError, TimeoutError) as e:
                sayac.say(SERVIS, False)
                if i == deneme - 1:
                    raise TunearoHatasi(None, f"{yontem} {yol}: {e}") from e
            time.sleep(2 * (i + 1))
        raise AssertionError("ulaşılmaz")

    def get(self, yol: str) -> dict:
        return self.istek("GET", yol)

    def post(self, yol: str, govde: dict | None = None) -> dict:
        return self.istek("POST", yol, govde or {})

    def patch(self, yol: str, govde: dict) -> dict:
        return self.istek("PATCH", yol, govde)

    def delete(self, yol: str) -> dict:
        return self.istek("DELETE", yol)

    def dosya_yukle(self, imzali_adres: str, yol: Path, tur: str) -> None:
        """Ön imzalı adrese (Tunearo deposu, 2 saat geçerli) doğrudan PUT; dosya API sunucusundan geçmez."""
        r = urllib.request.Request(imzali_adres, data=yol.read_bytes(), method="PUT",
                                   headers={"Content-Type": tur, "User-Agent": ag.KIMLIK})
        try:
            with urllib.request.urlopen(r, timeout=max(self.zaman_asimi, 600)):
                pass
            sayac.say(SERVIS, True)
        except urllib.error.HTTPError as e:
            sayac.say(SERVIS, False)
            raise TunearoHatasi(e.code, f"dosya yükleme ({yol.name}): {_hata_metni(e)}") from e
        except (urllib.error.URLError, TimeoutError) as e:
            sayac.say(SERVIS, False)
            raise TunearoHatasi(None, f"dosya yükleme ({yol.name}): {e}") from e


def _hata_metni(e: urllib.error.HTTPError) -> str:
    try:
        govde = json.loads(e.read() or b"{}")
    except ValueError:
        return e.reason or str(e.code)
    mesaj = govde.get("error") or e.reason
    if govde.get("issues"):
        mesaj += " (" + "; ".join(f"{x.get('field')}: {x.get('message')}" for x in govde["issues"]) + ")"
    return str(mesaj)


def _liste(cevap: dict, ad: str) -> list:
    return cevap.get("data") or cevap.get(ad) or []


# ── eşleme ──────────────────────────────────────────────────
# Önce şarkının stil metni (öncelik sırasıyla), sonra MusicBrainz sanatçı türleri kendi sırasıyla (ilki en çok oy alan);
# hiçbiri yoksa Pop. Canlı: Adele'nin türleri "pop, soul, …, r&b" → metin birleştirilince R&B/Soul çıkıyordu.
TURLER = (
    (re.compile(r"\b(rap|hip[ -]?hop|trap|drill)\b"), "Hip Hop/Rap"),
    (re.compile(r"\b(r&b|rnb|neo[ -]?soul)\b"), "R&B/Soul"),
    (re.compile(r"\balternative\b|\bindie\b"), "Alternative"),
    (re.compile(r"\b(rock|metal|punk|grunge)\b"), "Rock"),
    (re.compile(r"\b(electronic|edm|house|techno|trance|dubstep|synthwave)\b"), "Electronic"),
    (re.compile(r"\b(dance)\b"), "Dance"),
    (re.compile(r"\b(country)\b"), "Country"),
    (re.compile(r"\b(jazz)\b"), "Jazz"),
    (re.compile(r"\b(reggaeton|latin|salsa|bachata)\b"), "Latin"),
    (re.compile(r"\b(singer[ -]songwriter)\b"), "Singer/Songwriter"),
    (re.compile(r"\b(pop|ballad)\b"), "Pop"),
)


def _tur(metin: str) -> str | None:
    metin = metin.casefold()
    return next((ad for desen, ad in TURLER if desen.search(metin)), None)


def tur_sec(stil: str, sanatci_turleri: list | None = None) -> str:
    return next((t for m in (stil or "", *(sanatci_turleri or [])) if (t := _tur(m))), "Pop")


ZAMAN = re.compile(r"^\s*\[\d{1,2}:\d{2}(?:\.\d+)?\]\s*")
ETIKET = re.compile(r"^\s*\[[^\]]*\]\s*$")


def duz_soz(metin: str) -> str:
    """`soz.txt` (kıta etiketli, zaman damgalı) → mağazaya gidecek düz söz: etiket satırı ve zaman damgası yok."""
    satirlar = [ZAMAN.sub("", s).rstrip() for s in metin.replace("\r", "").split("\n") if not ETIKET.match(s)]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(satirlar)).strip()


def yazarlar(meta: dict) -> str:
    """Tek metin, virgüllü: API yazar alanlarını dizi almıyor (`|` da bölünmüyor, `contributors` yok sayılıyor;
    2026-10-10 taslakta denendi)."""
    adlar = [" ".join(x for x in a if x) for a in meta.get("orijinal_yazar_adlari") or []]
    return ", ".join(adlar or meta.get("orijinal_yazarlar") or [])


def yayin_alanlari(meta: dict, d: durum.Durum, yayin_tarihi: date, ayar: dict, sanatci_id: str) -> dict:
    from yanki.paket import DIL_ADI

    sanatci = meta["sanatci"]
    haric_magaza = set(ayar.get("haric_magazalar", []))
    alanlar = {
        "title": meta["baslik"], "primary_artist_name": sanatci, "artist_ids": [sanatci_id], "release_type": "Single",
        "primary_genre": tur_sec(d.analiz.get("stil", ""), (d.kunye or {}).get("sanatci_turleri")),
        "release_date": yayin_tarihi.isoformat(), "label_name": meta.get("etiket") or sanatci,
        "language": DIL_ADI.get(meta.get("dil", "en"), "English"), "explicit_content": bool(meta.get("acik_icerik")),
        "previously_released": False,
        # © beste orijinal yazarların, ℗ kayıt bizim (RouteNote formundaki 11–12. satırla aynı karar)
        "copyright_holder": yazarlar(meta) or sanatci,
        "producer_copyright_year": date.today().year, "producer_copyright_holder": sanatci,
        "services": "|".join(m for m in MAGAZALAR if m not in haric_magaza),
    }
    if meta.get("orijinal_yil"):
        alanlar["copyright_year"] = int(meta["orijinal_yil"])
    if ayar.get("haric_bolgeler"):
        alanlar["licensed_territories_exclude"] = "|".join(ayar["haric_bolgeler"])
    return alanlar


def parca_alanlari(meta: dict, soz: str | None) -> dict:
    from yanki.paket import DIL_ADI

    sanatci, yazan = meta["sanatci"], yazarlar(meta)
    alanlar = {"title": meta["baslik"], "track_number": 1, "primary_artist_name": sanatci,
               "explicit_content": bool(meta.get("acik_icerik")),
               "language": DIL_ADI.get(meta.get("dil", "en"), "English"), "producer": sanatci}
    if yazan:
        alanlar.update(composer=yazan, songwriter=yazan)
        if soz:
            alanlar["lyricist"] = yazan
    if soz:
        alanlar["lyrics"] = soz  # POST'ta düşüyor, PATCH'te tutuyor (canlı): parça açıldıktan sonra PATCH'le yazılır
    # önizleme başlangıcı API'de düzenlenebilir alan değil (parçada `preview_start_time` var ama PATCH yok sayıyor)
    return alanlar


def wav_hazirla(ses: Path, klasor: Path) -> Path:
    """Tunearo deposu sesi her zaman `…-audio.wav` adıyla saklıyor (uzantı ve tür ne verilirse verilsin, canlı):
    FLAC paket kayıpsız 16 bit WAV'a açılır."""
    import subprocess

    from yanki import ses as ses_araci

    hedef = klasor / f"{ses.stem}.wav"
    subprocess.run([ses_araci.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(ses),
                    "-c:a", "pcm_s16le", str(hedef)], check=True)
    return hedef


# ── yükleme ─────────────────────────────────────────────────
def _paket_dosyalari(p: Path) -> tuple[Path, Path]:
    gorunur = lambda desen: [x for x in p.glob(desen) if not x.name.startswith(".")]  # noqa: E731
    sesler = sorted([*gorunur("*.flac"), *gorunur("*.wav")])
    kapaklar = sorted(gorunur("*.jpg"))
    if len(sesler) != 1 or len(kapaklar) != 1:
        raise ValueError(f"pakette tek ses ve tek kapak olmalı ({p}): {len(sesler)} ses, {len(kapaklar)} kapak")
    return sesler[0], kapaklar[0]


def _meta_yaz(yol: Path, alan: str, deger: dict) -> None:
    meta = json.loads(yol.read_text(encoding="utf-8"))
    meta[alan] = deger
    dosya.json_yaz(yol, meta)


class Tunearo:
    ad, otomatik = "tunearo", True

    def __init__(self, kok: Path, istemci: Istemci | None = None, ayar: dict | None = None):
        self.kok = kok
        self._istemci = istemci
        self.ayar = ayar if ayar is not None else ayar_oku(kok / "config" / "yayin.toml")

    @property
    def api(self) -> Istemci:
        if self._istemci is None:
            self._istemci = Istemci.kokten(self.kok)
        return self._istemci

    def sanatci_id(self, ad: str) -> str:
        """Hesaptaki sanatçı (ada göre, büyük/küçük harf duyarsız); yoksa bir kez açılır."""
        for a in _liste(self.api.get("/artists"), "artists"):
            if (a.get("artist_name") or "").casefold() == ad.casefold():
                return a["id"]
        return self.api.post("/artists", {"artist_name": ad})["artist"]["id"]

    def yukle(self, calisma: Path, d: durum.Durum, yayin_tarihi: date, gonder: bool = True) -> dict:
        """Paketi yükler ve (gonder=True ise) incelemeye gönderir. Dönen sözlük `takip.yukleme_kaydet`'e gider.
        gonder=False: her şey yüklenir, yayın taslakta kalır (ilk deneme; gönderim sonra aynı çağrıyla)."""
        p = durum.klasor(calisma, d.kimlik) / "paket"
        meta_yolu = p / "metadata.json"
        meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
        if not meta.get("sanatci"):
            raise ValueError("pakette sanatçı adı yok (config/yayin.toml → sanatci_adi)")
        if not yazarlar(meta):  # cover'da orijinal yazarlar zorunlu (© ve composer bunlar)
            raise ValueError("pakette orijinal yazarlar yok: `yanki kunye <kimlik>` sonra `yanki paketle --yeniden`")
        ses, kapak = _paket_dosyalari(p)
        kayit = dict(meta.get("tunearo") or {})
        rid = kayit.get("release_id")
        if rid:
            try:
                st = self.api.get(f"/releases/{rid}/status")
            except ag.Bulunamadi:  # taslak panelden silinmiş: baştan
                rid, kayit = None, {}
            else:
                # önceki koşu göndermiş, sonucu kaydedememiş (`gonderiliyor`) ya da gönderim panelden yapılmış:
                # dokunma, olduğu gibi kaydet. Reddedilmişse de yeniden gönderme: kayda geçsin, yoklama reddi
                # bildirsin (red kaydedildikten sonra durum `gonderiliyor` değildir, düzeltilen yayın gönderilir)
                kaydedilmedi = kayit.get("durum") == "gonderiliyor"
                if st.get("status") not in DUZENLENEBILIR or (st.get("status") == "rejected" and kaydedilmedi):
                    kayit["durum"] = st.get("status")  # artık kayıtlı: red sonrası düzeltilen yayın gönderilebilir
                    _meta_yaz(meta_yolu, "tunearo", kayit)
                    return self._sonuc(kayit, rid, date.fromisoformat(kayit.get("yayin_tarihi")
                                                                      or yayin_tarihi.isoformat()), st)
        alanlar = yayin_alanlari(meta, d, yayin_tarihi, self.ayar, self.sanatci_id(meta["sanatci"]))
        if rid:
            self.api.patch(f"/releases/{rid}", alanlar)
        else:
            rid = self.api.post("/releases", alanlar)["release"]["id"]
            kayit = {"release_id": rid, "acildi": datetime.now().isoformat(timespec="seconds")}
            _meta_yaz(meta_yolu, "tunearo", kayit)
        # kapak: imzalı adres → PUT → yayına yol
        u = self.api.post(f"/releases/{rid}/artwork-upload-url", {"content_type": "image/jpeg"})
        self.api.dosya_yukle(u["upload_url"], kapak, "image/jpeg")
        self.api.patch(f"/releases/{rid}", {"cover_artwork_url": u["path"]})
        # parça: varsa düzelt (yeniden gönderim), yoksa aç (hesabın parça kotasından düşer)
        soz_yolu = durum.klasor(calisma, d.kimlik) / "soz.txt"
        soz = duz_soz(soz_yolu.read_text(encoding="utf-8")) if soz_yolu.exists() else None
        palan = parca_alanlari(meta, soz)
        parcalar = _liste(self.api.get(f"/releases/{rid}/tracks"), "tracks")
        tid = next((t["id"] for t in parcalar if t["id"] == kayit.get("track_id")), parcalar[0]["id"] if parcalar
                   else None)
        if not tid:
            tid = self.api.post(f"/releases/{rid}/tracks", palan)["track"]["id"]
            kayit["track_id"] = tid
            _meta_yaz(meta_yolu, "tunearo", kayit)
        self.api.patch(f"/releases/{rid}/tracks/{tid}", palan)
        kayit["track_id"] = tid
        # ses: depo WAV saklıyor; FLAC paket geçici WAV'a açılır
        with tempfile.TemporaryDirectory(prefix="yanki-tunearo-") as gecici:
            wav = ses if ses.suffix == ".wav" else wav_hazirla(ses, Path(gecici))
            u = self.api.post(f"/releases/{rid}/tracks/{tid}/audio-upload-url",
                              {"content_type": "audio/wav", "extension": "wav"})
            self.api.dosya_yukle(u["upload_url"], wav, "audio/wav")
        parca = self.api.get(f"/releases/{rid}/tracks/{tid}").get("track") or {}
        if parca.get("audio_file_url") != u["path"]:
            self.api.patch(f"/releases/{rid}/tracks/{tid}", {"audio_file_url": u["path"]})
            parca = self.api.get(f"/releases/{rid}/tracks/{tid}").get("track") or {}
            if parca.get("audio_file_url") != u["path"]:
                raise TunearoHatasi(None, f"ses yüklendi ama parçaya bağlanmadı ({u['path']})")
        kayit.update(kapak=kapak.name, ses=ses.name, yuklendi=datetime.now().isoformat(timespec="seconds"))
        if not gonder:
            kayit["durum"] = "draft"
            _meta_yaz(meta_yolu, "tunearo", kayit)
            return {}
        # gönderimden önce işaret: istek sunucuda başarılı olup burada düşerse takvim bunu incelemede sayar
        kayit.update(durum="gonderiliyor", yayin_tarihi=yayin_tarihi.isoformat())
        _meta_yaz(meta_yolu, "tunearo", kayit)
        st = self.api.post(f"/releases/{rid}/submit").get("release") or {"status": "pending"}
        kayit.update(durum=st.get("status", "pending"), gonderildi=datetime.now().isoformat(timespec="seconds"))
        _meta_yaz(meta_yolu, "tunearo", kayit)
        return self._sonuc(kayit, rid, yayin_tarihi, st)

    def _sonuc(self, kayit: dict, rid: str, yayin_tarihi: date, st: dict) -> dict:
        bilgi = {"release_id": rid, "track_id": kayit.get("track_id"), "yayin_tarihi": yayin_tarihi.isoformat(),
                 "dagitim_durumu": st.get("status", "pending")}
        if st.get("upc"):
            bilgi["upc"] = st["upc"]
        if self.ayar.get("haric_bolgeler"):
            bilgi["haric_bolgeler"] = list(self.ayar["haric_bolgeler"])
        if self.ayar.get("haric_magazalar"):
            bilgi["haric_magazalar"] = list(self.ayar["haric_magazalar"])
        return bilgi

    def geri_cek(self, calisma: Path, d: durum.Durum, neden: str) -> str:
        """Yüklenmiş yayını geri çeker (`dagitim.geri_cek`). API incelemedeki (`pending`) yayını geri çekemiyor
        (takedown 409, PATCH/DELETE yalnız taslak ve redde): yükleme `geri_cek` diye işaretlenir, yoklama sonuç
        gelince bitirir (red → aynı yayın kuyruğa; canlı → takedown). Dönen: "tamam" | "bekliyor"."""
        from yanki import takip

        rid = (takip.yukleme_bilgisi(calisma, d.kimlik) or {}).get("release_id")
        if not rid:
            raise ValueError("Tunearo yayın kimliği kayıtlı değil")
        takip.yukleme_kaydet(calisma, d.kimlik, {"geri_cek": {"neden": neden, "tarih": date.today().isoformat()}})
        try:
            st = self.api.get(f"/releases/{rid}/status")
        except ag.Bulunamadi:
            st = {"status": None}  # panelden silinmiş
        return self._geri_cek_ilerlet(calisma, d, rid, st)

    def _geri_cek_ilerlet(self, calisma: Path, d: durum.Durum, rid: str, st: dict) -> str:
        from yanki import dagitim

        s = st.get("status")
        if s == "draft":
            self.api.delete(f"/releases/{rid}")
        elif s in KABUL:
            try:
                self.api.post(f"/releases/{rid}/takedown")
            except TunearoHatasi as e:
                if e.kod != 409:  # approved: takedown yalnız canlıda; canlıya çıkınca yoklama yeniden dener
                    raise
                return "bekliyor"
        elif s not in (None, "rejected", *KALDIRMA):
            return "bekliyor"  # pending
        dagitim.geri_cekildi_kaydet(calisma, d.kimlik, yeni_yayin=s != "rejected", son_durum=s or "silindi")
        return "tamam"

    def yokla(self, calisma: Path, bildir=None) -> list[tuple[durum.Durum, str, str | None]]:
        """Tunearo'ya yüklenmiş şarkıların durumu. Değişeni kaydeder ve bildirir; red şarkıyı `paketlendi`ye döndürür
        (`dagitim.red_kaydet`). Dönen: (şarkı, durum, önceki durum)."""
        from yanki import dagitim, takip

        sonuc = []
        for d in durum.hepsi(calisma):
            y = takip.yukleme_bilgisi(calisma, d.kimlik) or {}
            if d.asama not in ("yuklendi", "yayinda") or y.get("dagitimci") != self.ad or not y.get("release_id"):
                continue
            rid = y["release_id"]
            try:  # bir yayının hatası diğerlerinin yoklamasını durdurmaz
                st = self.api.get(f"/releases/{rid}/status")
            except ag.Bulunamadi:
                if bildir:
                    bildir("kayip", f"Tunearo'da yok: {d.ad}", f"yayın {rid} bulunamadı (panelden silinmiş olabilir)",
                           f"tunearo:yok:{d.kimlik}:{rid}")
                sonuc.append((d, "bulunamadi", y.get("dagitim_durumu")))
                continue
            except TunearoHatasi as e:
                print(f"  {d.ad}: durum alınamadı: {e}")
                sonuc.append((d, "hata", y.get("dagitim_durumu")))
                continue
            yeni, eski = st.get("status"), y.get("dagitim_durumu")
            if y.get("geri_cek"):  # geri çekilmesi istenmiş yayın: incelemeden çıktıysa bitir
                try:
                    sonuc_ = self._geri_cek_ilerlet(calisma, d, rid, st)
                except TunearoHatasi as e:
                    print(f"  {d.ad}: geri çekilemedi: {e}")
                    sonuc.append((d, "hata", eski))
                    continue
                if sonuc_ == "tamam":
                    d = durum.oku(calisma, d.kimlik) or d
                if sonuc_ == "tamam" and bildir:
                    bildir("dagitim", f"Tunearo'dan geri çekildi: {d.ad}",
                           f"durum {yeni}: yayın kaldırıldı; gece koşusu yeniden paketleyip kuyruğa alır",
                           f"tunearo:geri:{d.kimlik}:{rid}")
                sonuc.append((d, "geri_cekildi" if sonuc_ == "tamam" else f"geri çekilecek ({yeni})", eski))
                continue
            guncel ={"dagitim_durumu": yeni, "dagitim_kontrol": datetime.now().isoformat(timespec="seconds")}
            if st.get("upc"):
                guncel["upc"] = st["upc"]
            if yeni in KABUL and not y.get("isrc") and y.get("track_id"):
                isrc = (self.api.get(f"/releases/{rid}/tracks/{y['track_id']}").get("track") or {}).get("isrc")
                if isrc:
                    guncel["isrc"] = isrc.replace("-", "").upper()
            if yeni == "rejected":
                neden = (st.get("rejection_reason") or "neden yazılmamış").strip()
                guncel["red_metni"] = neden
                takip.yukleme_kaydet(calisma, d.kimlik, guncel)
                ozet = neden.split("\n\n", 1)[0][:300]
                d = dagitim.red_kaydet(calisma, d.kimlik, f"Tunearo: {ozet}")
                if bildir:
                    bildir("red", f"Tunearo reddetti: {d.ad}", ozet,
                           f"tunearo:red:{d.kimlik}:{rid}:{st.get('updated_at')}")
                sonuc.append((d, yeni, eski))
                continue
            takip.yukleme_kaydet(calisma, d.kimlik, guncel)
            if bildir and yeni != eski:
                metin = {"approved": "kabul edildi, mağazalara gönderiliyor",
                         "live": f"mağazalarda canlı (UPC {st.get('upc') or '—'}); Spotify takibi ISRC'yle sürer",
                         }.get(yeni, f"durum: {yeni}" + (" — mağazalardan kaldırılıyor" if yeni in KALDIRMA else ""))
                tur = "kayip" if yeni in KALDIRMA else "dagitim"
                bildir(tur, f"Tunearo: {d.ad}", metin, f"tunearo:{d.kimlik}:{rid}:{yeni}")
            sonuc.append((d, yeni, eski))
        return sonuc


def ayar_oku(yayin_yolu: Path) -> dict:
    import tomllib

    try:
        with open(yayin_yolu, "rb") as f:
            t = tomllib.load(f).get("tunearo", {})
    except OSError:
        t = {}
    bilinmeyen = set(t.get("haric_magazalar", [])) - set(MAGAZALAR)
    if bilinmeyen:
        raise ValueError(f"tunearo.haric_magazalar bilinmeyen mağaza: {', '.join(sorted(bilinmeyen))}")
    return {"haric_bolgeler": [b.upper() for b in t.get("haric_bolgeler", [])],
            "haric_magazalar": list(t.get("haric_magazalar", []))}


KAZANC_TAZELIK_SN = 6 * 3600  # Tunearo kazancı aylık rapordan geliyor; sayfa her açılışta sormasın


def bizim_yayinlar(calisma: Path) -> dict[str, str]:
    """Hattın Tunearo'ya gönderdiği yayınlar: release_id → şarkı adı (reddedilip geçmişe taşınanlar dahil). Hesap
    paylaşımlı: hesap geneli toplam başkalarının kazancını da içerir, yalnız bunlar toplanır."""
    sonuc = {}
    for d in durum.hepsi(calisma):
        yol = durum.klasor(calisma, d.kimlik) / "paket" / "metadata.json"
        try:
            meta = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for y in [meta.get("yukleme") or {}, *(meta.get("yukleme_gecmisi") or [])]:
            if y.get("dagitimci") == "tunearo" and y.get("release_id"):
                sonuc[y["release_id"]] = d.ad
    return sonuc


def kazanc(calisma: Path, istemci: Istemci, zorla: bool = False) -> dict:
    """Bizim yayınların kazancı (GBP), `calisma/.kazanc.json`'da önbellekli."""
    import time

    yol = calisma / ".kazanc.json"
    try:
        eski = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        eski = None
    yayinlar = bizim_yayinlar(calisma)
    if eski and not zorla and time.time() - eski.get("zaman", 0) < KAZANC_TAZELIK_SN \
            and set(eski.get("yayinlar", [])) == set(yayinlar):
        return eski
    toplam, bu_ay, kaynak, sarkilar = 0.0, 0.0, {}, []
    for rid, ad in yayinlar.items():
        try:
            r = istemci.get(f"/releases/{rid}/royalties")
        except ag.Bulunamadi:
            continue
        toplam += r.get("lifetime_earnings") or 0
        bu_ay += r.get("this_month_earnings") or 0
        for x in r.get("by_source") or []:
            kaynak[x["source"]] = kaynak.get(x["source"], 0) + (x.get("amount") or 0)
        sarkilar.append({"ad": ad, "tutar": round(r.get("lifetime_earnings") or 0, 2)})
    veri = {"zaman": time.time(), "para": "GBP", "toplam": round(toplam, 2), "bu_ay": round(bu_ay, 2),
            "kaynaklar": sorted(({"kaynak": k, "tutar": round(v, 2)} for k, v in kaynak.items()),
                                key=lambda x: -x["tutar"]),
            "sarkilar": sorted(sarkilar, key=lambda x: -x["tutar"]), "yayinlar": list(yayinlar)}
    dosya.json_yaz(yol, veri)
    return veri


def profil_bagla(calisma: Path, istemci: Istemci, sanatci_adi: str, bildir=None) -> str | None:
    """Spotify'da görülen Orvane profilini Tunearo'daki sanatçıya bağlar (`spotify_id`): sonraki yayınlar aynı profile
    düşer, yeni profil açılmaz (RouteNote'ta her yükleme "yeni profil" açmıştı). Profil `yanki takip`'in kaydından;
    birden çok profil görüldüyse en çok parçalı olan seçilir ve bölünme bildirilir. Dönen: bağlanan kimlik."""
    from collections import Counter

    sayim = Counter(k for d in durum.hepsi(calisma) if (k := ((d.yayin or {}).get("son") or {}).get("sanatci_id")))
    if not sayim:
        return None
    kimlik = sayim.most_common(1)[0][0]
    if len(sayim) > 1 and bildir:
        bildir("kayip", "Spotify profili bölünmüş", f"Orvane parçaları {len(sayim)} ayrı profilde: "
               f"{', '.join(sayim)}. Spotify for Artists'ten birleştirme iste; yeni yayınlar {kimlik}'e bağlandı.",
               f"profil_bolunme:{'-'.join(sorted(sayim))}")
    sanatci = next((x for x in _liste(istemci.get("/artists"), "artists")
                    if (x.get("artist_name") or "").casefold() == sanatci_adi.casefold()), None)
    if sanatci is None or sanatci.get("spotify_id") == kimlik:
        return None
    if sanatci.get("spotify_id"):  # elle başka profile bağlanmış: ezme, bildir
        if bildir:
            bildir("kayip", "Tunearo sanatçısı başka profile bağlı",
                   f"Tunearo'da {sanatci_adi} → {sanatci['spotify_id']}, Spotify'da parçalar {kimlik}'te",
                   f"profil_fark:{sanatci['spotify_id']}:{kimlik}")
        return None
    istemci.patch(f"/artists/{sanatci['id']}", {"spotify_id": kimlik})
    if bildir:
        bildir("dagitim", "Spotify profili bağlandı", f"Tunearo'daki {sanatci_adi} artık Spotify profili {kimlik}'e "
               "bağlı: yeni yayınlar aynı profile düşer.", f"profil_bag:{kimlik}")
    return kimlik
