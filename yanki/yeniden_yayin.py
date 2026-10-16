"""Kendi kalkmış yayınını yeniden yayınla: Bulucu'daki kalkmış parça → FreshTunes taslağı (Scryne 2026-10-16: "kendi
yayınladığım kaldırılmış şarkıları playlistimde topladım; tıklayınca Yükle'de kendi şarkım FreshTunes taslağı dolsun,
aynı saniyedeki şarkıyı bulup indirsin, kapağı bulsun, aynı ISRC'yi girsin").

Yalnız Scryne'ın kendi kataloğu: parçanın sanatçısı kayıtlı kendi sanatçı adlarından biri olmalı
(`elle.kendi_sanatcilar`; oda Yükle'den kaydeder). Kayıt onun olduğu için ISRC ve UPC aynen girilir (FreshTunes daha
önce yayınlanmış kaydın kodlarını kabul ediyor, docs/arastirma/09) ve ilk yayın tarihi eski çıkış tarihidir.

İki adım:
- `taslak_kur` (ağsız, anında): Bulucu'nun parça ayrıntısından (`calisma/bulucu/parca-<id>.json`) künye.
- `kaynak_doldur` (oda işi `yanki elle-kaynak <kimlik>`, ağ): ses YouTube'dan, süresi Spotify'daki süreye en çok
  `SURE_TOLERANS_SN` uzak kayıt; önce sanatçının "- Topic" kanalı (dağıtımcının yüklediği kayıt), sonra resmî ses. Kapak
  iTunes'tan 3000×3000 (Spotify'ın kapağı 640 px, FreshTunes en az 1400 istiyor). Bulunamayan elle sürüklenir.
"""

import re
import urllib.request
from datetime import date, timedelta
from pathlib import Path

from yanki import ag, elle

SURE_TOLERANS_SN = 2.0  # "aynı saniyede": Spotify süresinden en çok bu kadar farklı kayıt
ISO_DIL = {"en": "English", "tr": "Turkish", "de": "German", "fr": "French", "es": "Spanish", "it": "Italian",
           "pt": "Portuguese", "ru": "Russian", "ar": "Arabic", "ja": "Japanese", "ko": "Korean", "nl": "Dutch",
           "sv": "Swedish", "pl": "Polish", "el": "Greek", "he": "Hebrew", "hi": "Hindi", "fa": "Persian",
           "id": "Indonesian", "az": "Azerbaijani", "uk": "Ukrainian", "ro": "Romanian", "hu": "Hungarian",
           "cs": "Czech", "da": "Danish", "fi": "Finnish", "no": "Norwegian"}
BELGESIZ = {"not documented", "unknown", ""}


class Hata(ValueError):
    pass


def _sade(ad: str) -> str:
    return re.sub(r"\s+", " ", (ad or "").casefold().replace("ı", "i")).strip()


def sanatci_adlari(metin: str | None, sanatcilar: list | None = None) -> list[str]:
    """Parçanın sanatçıları: Bulucu satırında virgüllü tek metin, parça ayrıntısında liste."""
    if sanatcilar:
        return [x.get("name", "") for x in sanatcilar if isinstance(x, dict) and x.get("name")]
    return [x.strip() for x in (metin or "").split(",") if x.strip()]


def kendi_sanatci(adlar: list[str], kendi: list[str]) -> str | None:
    """Parçanın sanatçılarından Scryne'ın kayıtlı adlarından biri (yazıldığı haliyle); yoksa None."""
    kayitli = {_sade(k): k for k in kendi if k.strip()}
    for ad in adlar:
        if _sade(ad) in kayitli:
            return kayitli[_sade(ad)]
    return None


def _kisi(ad: str) -> list[str]:
    """"Ad Soyad" → [ad, soyad] (son sözcük soyad; tek sözcüklüde soyad boş kalır, denetim ister)."""
    p = ad.split()
    return [" ".join(p[:-1]), p[-1]] if len(p) > 1 else [ad.strip(), ""]


def _telif(metin: str | None) -> tuple[int | None, str]:
    """"(P) 2013 Ultra Records, LLC" → (2013, "Ultra Records, LLC")."""
    m = re.match(r"^\s*(?:\(?[cp℗©]\)?\s*)?(\d{4})?\s*(.*)$", metin or "", re.I)
    if not m:
        return None, ""
    return (int(m[1]) if m[1] else None), m[2].strip()


def _tarih(t: str | None) -> str:
    return t if t and re.fullmatch(r"\d{4}-\d{2}-\d{2}", t) else ""


def taslak_kur(calisma: Path, kok: Path, parca: dict, kendi: list[str]) -> dict:
    """Parça ayrıntısından (Bulucu `parca` sonucu) FreshTunes taslağı. Sanatçı kayıtlı kendi adlarından biri değilse
    Hata (yalnız kendi kataloğun yeniden yayınlanır)."""
    adlar = sanatci_adlari(parca.get("sanatci"), parca.get("sanatcilar"))
    sanatci = kendi_sanatci(adlar, kendi)
    if not kendi:
        raise Hata("önce kendi sanatçı adını kaydet (Yükle → FreshTunes → Kendi sanatçı adların)")
    if sanatci is None:
        raise Hata(f"{', '.join(adlar) or 'sanatçı'} kayıtlı kendi sanatçı adların arasında değil; yalnız kendi "
                   "kalkmış yayınların yeniden yayınlanır")
    if not parca.get("sure_ms"):
        raise Hata("parçanın süresi okunamadı (Bulucu'da parçayı yeniden oku)")
    m = elle.yeni(calisma, kok, parca.get("ad") or "", sablon="freshtunes")
    k = m["kimlik"]
    sid = next((x.get("id") for x in parca.get("sanatcilar") or []
                if isinstance(x, dict) and _sade(x.get("name", "")) == _sade(sanatci)), None)
    yazarlar = [_kisi(x) for x in parca.get("yazarlar") or [] if _sade(x) not in BELGESIZ]
    yapimci = next((x for x in parca.get("yapimcilar") or [] if _sade(x) not in BELGESIZ), "")
    p_yil, p_sahibi = _telif(parca.get("telif_p"))
    c_yil, c_sahibi = _telif(parca.get("telif_c"))
    ilk = _tarih(parca.get("ilk_yayin")) or _tarih(parca.get("cikis"))
    dil = next((ISO_DIL[x] for x in parca.get("diller") or [] if ISO_DIL.get(x) in elle.routenote.RN_DILLER), None)
    alanlar = {"sanatci": sanatci, "isrc": parca.get("isrc") or "", "upc": parca.get("upc") or "",
               "acik_icerik": bool(parca.get("acik_icerik")), "orijinal_tarih": ilk if ilk and ilk <= str(date.today())
               else "", "etiket": (parca.get("label") or "")[:120], "uretici": yapimci[:120],
               "yayin_tarihi": (date.today() + timedelta(days=elle.FRESHTUNES_YAYIN_ONERI_GUN)).isoformat()}
    if sid:
        alanlar["spotify_sanatci_id"] = sid
    if yazarlar:
        alanlar["yazar_adlari"] = yazarlar[:20]
    if dil:
        alanlar["dil"] = dil
    if p_yil:
        alanlar |= {"p_yil": p_yil, "p_sahibi": p_sahibi[:200]}
    if c_yil:
        alanlar |= {"c_yil": c_yil, "c_sahibi": c_sahibi[:200]}
    # © ya da ℗ satırı yoksa yılı ilk çıkış yılı (yeniden yayında bugünün yılı yanlış olurdu)
    if yil := (int(ilk[:4]) if ilk else None) or p_yil or c_yil:
        alanlar.setdefault("c_yil", yil)
        alanlar.setdefault("p_yil", yil)
    try:
        elle.guncelle(calisma, k, alanlar)
    except elle.Hata:  # biçimi tutmayan tek alan (ör. tuhaf ISRC) bütün taslağı düşürmesin: alan alan
        for ad, deger in alanlar.items():
            try:
                elle.guncelle(calisma, k, {ad: deger})
            except elle.Hata:
                pass
    meta = elle.oku(calisma, k)
    meta["kaynak_parca"] = {"spotify_id": parca.get("id"), "sure_sn": parca["sure_ms"] / 1000,
                            "ad": parca.get("ad"), "sanatci": sanatci, "isrc": parca.get("isrc"),
                            "resim": parca.get("resim"), "cikis": parca.get("cikis"), "label": parca.get("label"),
                            "distributor": parca.get("distributor")}
    meta["notlar"] = (f"Kalkmış yayının yeniden yayını (Bulucu): spotify:track:{parca.get('id')} · "
                      f"{parca.get('distributor') or 'distribütör ?'} · {parca.get('label') or 'label ?'}")
    return elle._yaz(calisma, k, meta)


# ── ses ve kapak (ağ) ────────────────────────────────────────
# Spotify'daki adda geçmiyorsa başka sürüm: hazırlığın `kaynak.ISTENMEYEN`'ine ek (2026-10-16 canlı deneme: Mt. Eden'in
# kendi kanalında 292 sn'lik "Orchestral Version" Spotify süresine en yakın adaydı)
FARKLI_SURUM = re.compile(r"\b(orchestral|acoustic|unplugged|extended|radio edit|edit|dubstep|bass boosted|"
                          r"rework|vip|demo|version|ver\.?|mix)\b", re.I)


def _harfler(s: str) -> str:
    return re.sub(r"[^\w]+", " ", _sade(s)).strip()


def ses_sec(adaylar: list, sanatci: str, beklenen_sn: float, ad: str = ""):
    """Süresi Spotify'dakine en çok `SURE_TOLERANS_SN` uzak aday. Kanal sırası: sanatçının "- Topic" kanalı
    (dağıtımcının yüklediği kayıt), sanatçının ya da VEVO'nun kanalı, diğerleri; her kademede en yakın süre (canlı
    denemede en yakın süre bir hayran yüklemesiydi). Canlı/cover/remix ve Spotify adında geçmeyen sürüm sözcükleri
    elenir. Yoksa None."""
    from yanki import kaynak

    def farkli(baslik: str) -> bool:
        return any(m.group(0).casefold() not in _sade(ad) for m in FARKLI_SURUM.finditer(baslik or ""))

    uygun = [a for a in adaylar if a.sure_sn and abs(a.sure_sn - beklenen_sn) <= SURE_TOLERANS_SN
             and not kaynak.ISTENMEYEN.search(a.baslik or "") and not farkli(a.baslik)]
    if not uygun:
        return None
    s = _harfler(sanatci)

    def kademe(a) -> int:
        kanal = _harfler(a.kanal or "")
        if kanal == f"{s} topic":
            return 0
        return 1 if s and (s in kanal or "vevo" in kanal) else 2

    return min(uygun, key=lambda a: (kademe(a), abs(a.sure_sn - beklenen_sn)))


def ses_indir(calisma: Path, kimlik: str, adaylar=None, indir=None) -> str:
    from yanki import kaynak

    meta = elle.oku(calisma, kimlik)
    kp = meta.get("kaynak_parca") or {}
    sanatci, ad, sure = kp.get("sanatci") or meta.get("sanatci"), kp.get("ad") or meta.get("baslik"), kp["sure_sn"]
    adaylar_ = adaylar or kaynak.youtube_adaylari
    gorulen, secilen = {}, None
    for sorgu in (f"{sanatci} {ad}", f"{sanatci} {ad} official audio"):
        for a in adaylar_(sorgu):
            gorulen.setdefault(a.id, a)
        if secilen := ses_sec(list(gorulen.values()), sanatci, sure, ad):
            break
    if secilen is None:
        yakin = sorted(gorulen.values(), key=lambda a: abs((a.sure_sn or 0) - sure))[:3]
        raise Hata(f"YouTube'da {int(sure) // 60}:{int(sure) % 60:02d} süreli kayıt bulunamadı (en yakınlar: "
                   + ", ".join(f"{a.baslik[:40]} {int(a.sure_sn or 0) // 60}:{int(a.sure_sn or 0) % 60:02d}"
                               for a in yakin) + "); sesi kendin sürükle")
    gecici = elle.klasor(calisma, kimlik) / ".youtube.indirilen"
    try:
        (indir or kaynak.youtube_indir)(secilen.id, gecici)
        veri = gecici.read_bytes()
    finally:
        gecici.unlink(missing_ok=True)
    bilgi = elle.ses_kaydet(calisma, kimlik, "youtube.m4a", veri)  # ffmpeg biçimi içerikten tanır (opus/m4a)
    ek = ""
    if bilgi.get("kirpik", 0) > KIRPIK_ESIGI:
        bilgi = {**bilgi, **_tepe_indir(elle.klasor(calisma, kimlik) / "ses.flac")}
        ek = f", tepe {TEPE_PAYI_DB:+.0f} dB (kırpılma)"
    meta = elle.oku(calisma, kimlik)
    meta["ses"] = {**bilgi, "ad": f"YouTube: {secilen.baslik[:80]}", "youtube": secilen.id, "kanal": secilen.kanal}
    elle._yaz(calisma, kimlik, meta)
    fark = (bilgi.get("sure") or 0) - sure
    return f"ses: {secilen.kanal} — {secilen.baslik} ({bilgi.get('sure')} sn, Spotify'dan {fark:+.1f} sn{ek})"


# YouTube'dan çözülen ses çoğu zaman 0 dBFS'e dayanıyor (canlı deneme 2026-10-16: tepe 0,0 dBFS); FreshTunes kırpılmış
# sesi reddediyor. Yalnız otomatik indirilen seste kazanç bu kadar düşürülür (Scryne'ın sürüklediği dosyaya dokunulmaz).
TEPE_PAYI_DB = -1.0
KIRPIK_ESIGI = 1e-5


def _tepe_indir(yol: Path) -> dict:
    import subprocess

    from yanki import ses

    gecici = yol.with_name(".ses.yaziliyor.flac")
    r = subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(yol), "-af",
                        f"volume={TEPE_PAYI_DB}dB", "-ac", "2", "-ar", "44100", "-c:a", "flac", "-sample_fmt", "s16",
                        str(gecici)], capture_output=True, text=True, timeout=ses.ARAC_SURESI)
    if r.returncode or not gecici.exists():
        gecici.unlink(missing_ok=True)
        raise OSError(f"kazanç düşürülemedi: {(r.stderr or '').strip()[:200]}")
    gecici.replace(yol)
    return {**elle.ses_olcumu(yol), "flac_boyut": yol.stat().st_size, "kazanc_db": TEPE_PAYI_DB}


def _bayt_al(url: str, en_cok: int = 30 * 2**20) -> bytes:
    istek = urllib.request.Request(url, headers={"User-Agent": ag.KIMLIK})
    with urllib.request.urlopen(istek, timeout=60) as r:
        veri = r.read(en_cok + 1)
    if len(veri) > en_cok:
        raise OSError("kapak çok büyük")
    return veri


def kapak_bul(sanatci: str, ad: str, sure_sn: float, ara=None) -> str | None:
    """iTunes'ta aynı parça (sanatçı, ad, süre ±3 sn): kapağın 3000×3000 adresi. Bulunamazsa None."""
    ara = ara or (lambda p: ag.json_al("https://itunes.apple.com/search", p))
    try:
        sonuc = ara({"term": f"{sanatci} {ad}", "entity": "song", "limit": 25}).get("results") or []
    except (OSError, ValueError, ag.Bulunamadi):
        return None
    temiz = lambda s: re.sub(r"\s*[\(\[].*?[\)\]]", "", _sade(s))  # noqa: E731 — "(feat. …)", "[Remastered]"
    for x in sonuc:
        if (_sade(x.get("artistName", "")).find(_sade(sanatci)) >= 0 and temiz(x.get("trackName", "")) == temiz(ad)
                and abs((x.get("trackTimeMillis") or 0) / 1000 - sure_sn) <= 3 and x.get("artworkUrl100")):
            return re.sub(r"/\d+x\d+bb\.", "/3000x3000bb.", x["artworkUrl100"])
    return None


def kapak_indir(calisma: Path, kimlik: str, bul=None, al=None) -> str:
    meta = elle.oku(calisma, kimlik)
    kp = meta.get("kaynak_parca") or {}
    url = (bul or kapak_bul)(kp.get("sanatci") or meta.get("sanatci"), kp.get("ad") or meta.get("baslik"),
                             kp.get("sure_sn") or 0)
    if not url:
        raise Hata("kapak iTunes'ta bulunamadı (Spotify'ınki 640 px, FreshTunes en az 1400 istiyor); kapağı kendin "
                   "sürükle")
    elle.kapak_kaydet(calisma, kimlik, "itunes.jpg", (al or _bayt_al)(url))
    return f"kapak: iTunes ({url.rsplit('/', 2)[-2] if '/' in url else url})"


def kaynak_doldur(calisma: Path, kimlik: str, ses=ses_indir, kapak=kapak_indir) -> list[str]:
    """Oda işi: ses ve kapak (biri düşerse öbürü yine denenir). Dönen: yapılan/bulunamayan satırları; ikisi de
    düşerse Hata."""
    satirlar, hatalar = [], []
    for ad, adim in (("ses", ses), ("kapak", kapak)):
        try:
            satirlar.append(adim(calisma, kimlik))
        except (Hata, elle.Hata, OSError, LookupError) as e:
            hatalar.append(f"✗ {ad}: {e}")
    if len(hatalar) == 2:
        raise Hata("; ".join(hatalar))
    return satirlar + hatalar
