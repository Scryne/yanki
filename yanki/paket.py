"""Yükleme paketi: onaylanan aday → mastering + kapak + metadata + YUKLE.md (`calisma/<kimlik>/paket/`).

RouteNote ve DistroKid'de yükleme insanda (API yok; DistroKid ToS'u botu yasaklıyor): paket, formu kopyala-yapıştırla
doldurmaya yetecek her şeyi taşır. Tunearo'da hat paketi API ile kendisi yükler (`yanki/tunearo.py`). Eksik karar
(sanatçı adı, dağıtımcı) varsa paket yine hazırlanır, YUKLE.md en üstte eksikleri yazar.
"""

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from yanki import dosya, durum, ses, sozler

FONT_KALIN = Path("C:/Windows/Fonts/bahnschrift.ttf")
KAPAK_BOYUT = 3000
KUCUK_KAPAK = 1000  # bundan küçük özgün görsel 3000'e büyütülünce bulanıklaşır; YUKLE.md uyarır

# Dağıtımcıya özel ayrıntılar: docs/arastirma/02-dagitimci-karsilastirmasi.md (2026-10-07). RouteNote WAV almıyor
# (FLAC/MP3 44,1); bilgi 2023 tarihli, yükleme ekranında doğrulanır.
SES_BICIMI = {"routenote": "flac", "distrokid": "wav", "tunearo": "wav", "": "wav"}  # Tunearo depoda WAV
DAGITIMCI_ADI = {"distrokid": "DistroKid", "routenote": "RouteNote", "tunearo": "Tunearo"}
DAGITIMCI_NOTU = {
    "distrokid": [
        "Yapay zekâ sorusu (\"Is any part of this track AI-generated?\"): **all of the audio**. Ardından sanatçının"
        " insan mı AI persona mı olduğu sorulur.",
        "Cover adımı formun Songwriter bölümünde: cover seçilir, orijinal sanatçı ve şarkı adı girilir"
        " (DistroKid üzerinden, $12/yıl/şarkı; onay 14 iş gününe kadar sürebilir).",
    ],
    # RouteNote: formun tamamı ekrandaki sırayla `_routenote_formu`nda
}


# Dağıtımcı formundaki dil listesi İngilizce adlarla (kod `analiz.dil`, Whisper/ACE-Step kodu)
DIL_ADI = {"en": "English", "tr": "Turkish", "fr": "French", "es": "Spanish", "pt": "Portuguese", "de": "German",
           "it": "Italian", "nl": "Dutch", "ru": "Russian", "ja": "Japanese", "ko": "Korean", "zh": "Chinese",
           "ar": "Arabic", "pl": "Polish", "sv": "Swedish", "id": "Indonesian", "hi": "Hindi", "az": "Azerbaijani",
           "unknown": "Instrumental / Unknown"}


@dataclass(frozen=True)
class Yayin:
    sanatci_adi: str
    dagitimci: str
    etiket: str
    lufs: float
    gercek_tepe: float
    ornekleme: int
    kapak: str = "uretilen"  # "pinterest" (şarkının moduna göre görsel) | "uretilen" (dalga formundan tipografik)
    # cover'ın frekans dengesi orijinal kayda yaklaştırılır (yanki/ton.py; referans mastering)
    ton_eslesme: bool = True


def yayin_ayarlari(yol: Path) -> Yayin:
    with open(yol, "rb") as f:
        d = tomllib.load(f)
    y, m = d["yayin"], d["master"]
    if y["dagitimci"] not in ("", "routenote", "distrokid", "tunearo"):
        raise ValueError(f"dagitimci tunearo, routenote, distrokid ya da boş olmalı: {y['dagitimci']}")
    kapak_kaynagi = d.get("kapak", {}).get("kaynak", "uretilen")
    if kapak_kaynagi not in ("pinterest", "uretilen"):
        raise ValueError(f"kapak.kaynak pinterest ya da uretilen olmalı: {kapak_kaynagi}")
    return Yayin(y["sanatci_adi"].strip(), y["dagitimci"], y.get("etiket", "").strip(), float(m["lufs"]),
                 float(m["gercek_tepe_dbtp"]), int(m["ornekleme"]), kapak_kaynagi, bool(m.get("ton_eslesme", True)))


def _loudnorm_olc(girdi: Path, y: Yayin, on_filtre: str = "") -> dict:
    cikti = subprocess.run(
        [ses.arac("ffmpeg"), "-hide_banner", "-nostats", "-i", str(girdi), "-af",
         (f"{on_filtre}," if on_filtre else "") + f"loudnorm=I={y.lufs}:TP={y.gercek_tepe}:LRA=11:print_format=json",
         "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
        timeout=ses.ARAC_SURESI).stderr
    return json.loads(cikti[cikti.rindex("{"): cikti.rindex("}") + 1])


# Alçak geçiren temizlik: ACE-Step çıktısında DC kayması (+0,001…+0,0035) ve orijinal kayda göre 30–60 Hz'te 10–20 dB
# fazla uğultu var (2026-10-11, Someone Like You / Fix You / Perfect ölçümü); boşa tepe payı yiyor, hoparlörde boğuk.
# İki kat 2 kutuplu = 24 dB/oktav, 28 Hz: baladın en alt bas notası (E1 41 Hz) etkilenmez.
ALT_KESIM_HZ = 28.0
SINIRLAYICI_ORNEKLEME = 176400  # 4× aşırı örnekleme: örnekler arası (gerçek) tepeler de yakalanır
TAVAN_PAYI_DB = 0.3  # sınırlayıcı tavanı gerçek tepe hedefinin altında (son yeniden örnekleme ara tepeleri)


def master(girdi: Path, hedef: Path, y: Yayin, deneme: int = 3, referans: Path | None = None) -> dict:
    """Alçak kesim → kazanç → 4× aşırı örneklenmiş tepe sınırlayıcı → 44,1 kHz 16 bit (üçgen dither), WAV ya da FLAC.

    Önce iki geçişli `loudnorm` doğrusal istenirdi ama tepe/ses yüksekliği oranı (PLR) −14 LUFS ve −1,2 dBTP'ye
    sığmayınca (ACE-Step çıktısında PLR 15–16 dB, sığan en çok 12,8) ffmpeg sessizce dinamik moda düşüyordu
    (2026-10-11: yüklenen paketlerin hepsi `normalization_type: dynamic`): zamanla değişen kazanç, nakaratta pompalama.
    Şimdi tepeler kontrollü sınırlanır, kazanç tüm şarkıda sabit kalır; sonuç ölçülür, hedeften sapma kazanca
    yansıtılıp yeniden çıkarılır. `referans` (orijinal kayıt) verilirse ve `ton_eslesme` açıksa frekans dengesi ona
    yaklaştırılır (`yanki/ton.py`). Dönen: son ölçüm + uygulanan sınırlama ve ton eğrisi."""
    from yanki import ton

    temiz = f"highpass=f={ALT_KESIM_HZ:g}:poles=2,highpass=f={ALT_KESIM_HZ:g}:poles=2"
    ton_bilgi: dict = {}
    if referans is not None and y.ton_eslesme:
        orijinal, cover = ton.bant_spektrumu(referans), ton.bant_spektrumu(girdi)
        noktalar = ton.egri(cover, orijinal)
        temiz += "," + ton.ffmpeg_filtresi(noktalar)
        ton_bilgi = {"ton_egrisi": noktalar, "ton_sapma_once_db": round(ton.sapma(cover, orijinal), 2),
                     "_orijinal": orijinal}
    o = _loudnorm_olc(girdi, y, temiz)
    kazanc = y.lufs - float(o["input_i"])
    tavan_db = y.gercek_tepe - TAVAN_PAYI_DB
    hedef.parent.mkdir(parents=True, exist_ok=True)
    for _ in range(deneme):
        zincir = (f"{temiz},volume={kazanc:.2f}dB,aresample={SINIRLAYICI_ORNEKLEME},"
                  f"alimiter=limit={10 ** (tavan_db / 20):.5f}:attack=1:release=80:level=0:latency=1,"
                  f"aresample={y.ornekleme}:osf=s16:dither_method=triangular")
        subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(girdi), "-af",
                        zincir, "-ac", "2", *_kodlayici(hedef), str(hedef)], check=True, timeout=ses.ARAC_SURESI)
        son = _loudnorm_olc(hedef, y)
        lufs, tepe = float(son["input_i"]), float(son["input_tp"])
        if abs(y.lufs - lufs) <= 0.2 and tepe <= y.gercek_tepe + 0.05:
            break
        kazanc += y.lufs - lufs
        if tepe > y.gercek_tepe:
            tavan_db -= tepe - y.gercek_tepe + 0.1
    orijinal = ton_bilgi.pop("_orijinal", None)
    if orijinal is not None:  # eşleme ölçülür: master'ın orijinale uzaklığı (önce/sonra)
        ton_bilgi["ton_sapma_sonra_db"] = round(ton.sapma(ton.bant_spektrumu(hedef), orijinal), 2)
    sonuc = {"lufs": lufs, "gercek_tepe_dbtp": tepe, "alt_kesim_hz": ALT_KESIM_HZ,
             "sinirlama_db": round(max(0.0, float(o["input_tp"]) + kazanc - tavan_db), 1),
             "giris_plr_db": round(float(o["input_tp"]) - float(o["input_i"]), 1), **ton_bilgi}
    return sonuc


def kapak(baslik: str, tepe: list[float], hedef: Path, sanatci: str = "", boyut: int = 3000) -> Path:
    """Şarkının kendi dalga formundan tipografik kapak. Orijinal sanatçı adı/logosu yok (dağıtımcı kuralı)."""
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (boyut, boyut))
    y = np.linspace(0, 1, boyut)[:, None]
    x = np.linspace(0, 1, boyut)[None, :]
    zemin = np.array([11, 10, 26]) * (1 - y)[..., None] + np.array([26, 15, 46]) * y[..., None]
    parilti = np.exp(-(((x - 0.15) ** 2 + (y - 0.12) ** 2) / 0.08))[..., None] * np.array([18, 59, 74])
    img = Image.fromarray(np.clip(zemin + parilti * 0.9, 0, 255).astype("uint8"))
    ciz = ImageDraw.Draw(img)
    # dalga: dikey çubuklar, ortada bir bant (DESIGN.md: punch-in bandı) amber
    n = 96
    t = np.array(tepe or [0.5])
    kova = np.array_split(t, n)
    kenar, orta = int(boyut * 0.1), int(boyut * 0.52)
    genislik = (boyut - 2 * kenar) / n
    for i, k in enumerate(kova):
        h = max(0.04, float(k.max() if len(k) else 0)) * boyut * 0.22
        x0 = kenar + i * genislik
        renk = (242, 169, 59) if 0.42 <= i / n <= 0.58 else (185, 180, 230)
        ciz.rounded_rectangle([x0 + genislik * 0.18, orta - h, x0 + genislik * 0.82, orta + h],
                              radius=int(genislik * 0.3), fill=renk)
    font = ImageFont.truetype(str(FONT_KALIN), int(boyut * 0.075)) if FONT_KALIN.exists() else ImageFont.load_default()
    satirlar = _sar(baslik, font, ciz, boyut - 2 * kenar)
    yy = int(boyut * 0.78)
    for s in satirlar[:2]:
        ciz.text((kenar, yy), s, font=font, fill=(236, 234, 246))
        yy += int(boyut * 0.085)
    if sanatci:
        kucuk = ImageFont.truetype(str(FONT_KALIN), int(boyut * 0.035)) if FONT_KALIN.exists() else font
        ciz.text((kenar, int(boyut * 0.1)), sanatci, font=kucuk, fill=(169, 165, 196))
    hedef.parent.mkdir(parents=True, exist_ok=True)
    img.save(hedef, "JPEG", quality=92)
    return hedef


def _sar(metin: str, font, ciz, en: int) -> list[str]:
    kelimeler, satirlar, s = metin.split(), [], ""
    for k in kelimeler:
        aday = f"{s} {k}".strip()
        if ciz.textlength(aday, font=font) <= en:
            s = aday
        else:
            satirlar.append(s)
            s = k
    return satirlar + [s] if s else satirlar


# Mağazaların "explicit" saydığı sözcükler; damn/hell gibi hafifler sayılmaz (drivers license: "fucking", 2026-10-08)
ACIK_SOZ = re.compile(r"\b((?:mother)?fuck\w*|shit\w*|bitch\w*|cunt\w*|pussy|dick|cock|nigga\w*)\b", re.I)


def acik_sozler(metin: str) -> list[str]:
    """Sözlerde geçen açık içerikli sözcükler (küçük harf, tekrarsız, ilk geçiş sırasıyla)."""
    return list(dict.fromkeys(m.group(1).lower() for m in ACIK_SOZ.finditer(metin)))


def nakarat_baslangici(satirlar: list) -> float | None:
    """Önizleme (preview) başlangıcı: nakaratın ilk satırı (`sozler.nakarat_gecisleri`). Zaman damgası kaynağın;
    parçalı üretim kaynağın zamanlamasını izlediği için cover'da da tutar."""
    return next(iter(sozler.nakarat_gecisleri(satirlar)), None)


def metadata(d: durum.Durum, y: Yayin, master_olcum: dict, sure_sn: float, onizleme_sn: float | None = None,
             acik: list[str] | None = None) -> dict:
    k = d.kunye or {}
    return {
        "baslik": d.ad,  # dağıtımcı kuralı: orijinal başlıkla aynı, "(Cover)" eki yok, orijinal sanatçı adı yok
        "sanatci": y.sanatci_adi or None,
        "etiket": y.etiket or y.sanatci_adi or None,
        "tur": "cover",
        "orijinal_sanatci": d.sanatci,  # formda yalnız cover bilgisi alanına (başlık/sanatçı alanlarına değil)
        "orijinal_yazarlar": list(k.get("yazarlar") or []),
        # künyeden ad + soyad (eski künyede yok → ad boşluktan bölünür)
        "orijinal_yazar_adlari": [list(x) for x in k.get("yazar_adlari") or []],
        "orijinal_isrc": list(k.get("isrc") or []),
        "orijinal_eser_mbid": k.get("eser_mbid"),
        "orijinal_yil": (k.get("ilk_yayin") or "")[:4] or None,  # © satırı (besteci telifi) bu yılla
        "dil": d.analiz.get("dil", "en"),
        "sure_sn": round(sure_sn, 2),
        "onizleme_sn": onizleme_sn,
        "yapay_zeka": {"kullanildi": True, "arac": "ACE-Step 1.5 (XL-SFT)", "kapsam": "vokal ve enstrümantal üretim",
                       "baglanti": "https://github.com/ace-step/ACE-Step-1.5"},
        # sözler tarandıysa (acik bir liste) karar ondan; taranmadıysa None → formda elle bakılır
        "acik_icerik": None if acik is None else bool(acik),
        "acik_sozcukler": acik or [],
        "master": master_olcum,
        # hangi adaydan paketlendi (yeniden üretimden sonra eski/yeni ayırt edilsin)
        "kaynak_aday": next(({"no": x.no, "tohum": x.tohum, "dosya": x.dosya} for x in d.adaylar if x.no == d.secilen),
                            None),
        "hazirlanma": date.today().isoformat(),
    }


def _kodlayici(hedef: Path) -> list[str]:
    return ["-c:a", "flac", "-sample_fmt", "s16"] if hedef.suffix == ".flac" else ["-c:a", "pcm_s16le"]


def yukle_md(meta: dict, y: Yayin, dosyalar: dict[str, str]) -> str:
    eksik = []
    if not y.sanatci_adi:
        eksik.append("Sanatçı adı: `config/yayin.toml` → `sanatci_adi` "
                     "(kapak da yeniden üretilmeli: `yanki paketle --yeniden`)")
    if not y.dagitimci:
        eksik.append("Dağıtımcı: `config/yayin.toml` → `dagitimci` (tunearo | routenote | distrokid)")
    if not meta["orijinal_yazarlar"]:
        eksik.append("Orijinal yazarlar bulunamadı: dağıtımcının cover formunda zorunlu")
    satir = [f"# Yükleme: {meta['baslik']}", ""]
    if eksik:
        satir += ["> **Eksik karar — yüklemeden önce:**", *[f"> - {e}" for e in eksik], ""]
    if y.dagitimci == "routenote":
        return "\n".join(satir + _routenote_formu(meta, dosyalar)) + "\n"
    if y.dagitimci == "tunearo":
        return "\n".join(satir + _tunearo_notu(meta, dosyalar)) + "\n"
    satir += [
        "Form alanları yukarıdan aşağı, kopyala-yapıştır:", "",
        f"1. **Başlık (Title):** `{meta['baslik']}`",
        f"2. **Sanatçı (Primary artist):** `{meta['sanatci'] or 'EKSİK'}`",
        "3. **Sürüm türü:** Single",
        "4. **Cover mı?** Evet (cover / remake). Orijinal sanatçı yalnız bu bölümde: "
        f"`{meta['orijinal_sanatci']}`",
        f"5. **Söz yazarı / besteci (Songwriters / Publishing):** `{', '.join(meta['orijinal_yazarlar']) or 'EKSİK'}`",
        f"6. **Dil:** `{meta['dil']}`",
        "7. **Açık içerik (Explicit):** sözlere bakıp işaretle",
        f"8. **Yapay zekâ beyanı:** Evet — {meta['yapay_zeka']['kapsam']}; araç: {meta['yapay_zeka']['arac']} "
        f"({meta['yapay_zeka']['baglanti']})",
        f"9. **Ses dosyası:** `{dosyalar['ses']}` (44,1 kHz / 16 bit {Path(dosyalar['ses']).suffix[1:].upper()}, "
        f"{meta['master']['lufs']:.1f} LUFS, "
        f"{meta['master']['gercek_tepe_dbtp']:.1f} dBTP, {_mmss(meta['sure_sn'])})",
        f"10. **Kapak:** `{dosyalar['kapak']}` (3000×3000 JPG){_kapak_notu(meta)}",
        "",
        "Kurallar (dağıtımcı yönergelerinden): başlığa `(Cover)` ya da orijinal sanatçı adı eklenmez; kapakta orijinal",
        "sanatçının adı, fotoğrafı ya da logosu yoktur.",
        "",
    ]
    if notlar := DAGITIMCI_NOTU.get(y.dagitimci):
        satir += [f"{DAGITIMCI_ADI[y.dagitimci]} formuna özel:", "", *[f"- {n}" for n in notlar], ""]
    satir += [
        "Yükledikten sonra: `yanki yuklendi <kimlik>`",
    ]
    return "\n".join(satir) + "\n"


def _kapak_notu(meta: dict) -> str:
    k = meta.get("kapak") or {}
    en, boy = k.get("ozgun_boyut") or (KAPAK_BOYUT, KAPAK_BOYUT)
    if k.get("kaynak") in ("ozel", "pinterest") and min(en, boy) < KUCUK_KAPAK:
        return f". **Dikkat:** özgün görsel {en}×{boy} px, {KAPAK_BOYUT}'e büyütüldü; bulanıksa dağıtımcı reddedebilir"
    return ""


def _acik_satiri(meta: dict) -> str:
    if meta.get("acik_icerik") is True:
        return f"**Explicit** (sözlerde: {', '.join(meta['acik_sozcukler'])})"
    temiz = "Not Explicit" + (" (sözlerde küfür yok)" if meta.get("acik_icerik") is False else " (sözlere bak)")
    return temiz + "; \"Clean\" seçme, o açık içeriğin temizlenmiş sürümü demek"


SOYAD_YOK = "SOYAD? (yasal soyadı, ör. albüm künyesi)"


def _ad_soyad(ad: str) -> tuple[str, str]:
    """Künyede ad + soyad yoksa (eski paket): son boşluktan böl."""
    parca = ad.rsplit(" ", 1)
    return (parca[0], parca[1]) if len(parca) == 2 else (ad, SOYAD_YOK)


def _yazarlar(meta: dict) -> list[tuple[str, str]]:
    """RouteNote yazar alanı ad + soyad ister. Künye sıralama adından ("Del Rey, Lana") ya da tek sözcüklü sahne
    adında yasal addan ("Adele" → Adele Adkins) bölmüş olur; bilinmeyen soyad elle girilir."""
    if adlar := meta.get("orijinal_yazar_adlari"):
        return [(a, s or SOYAD_YOK) for a, s in adlar]
    return [_ad_soyad(a) for a in meta["orijinal_yazarlar"]]


def _routenote_formu(meta: dict, dosyalar: dict[str, str]) -> list[str]:
    """RouteNote formu, ekrandaki sırayla (ilk gerçek yükleme, Adele, 2026-10-08)."""
    sanatci = meta["sanatci"] or "EKSİK"
    yazarlar = _yazarlar(meta) or [("EKSİK", "")]
    yazar_satiri = "; ".join(f"First `{a}` · Last `{s}`" for a, s in yazarlar)
    yazar_metni = ", ".join(f"{a} {s}" for a, s in yazarlar)
    yil = meta.get("orijinal_yil") or "ORİJİNAL YIL"
    on = meta.get("onizleme_sn")
    onizleme = f"`{_mmss(on)}` (ilk nakarat; Visually Select Clip ile dinleyip doğrula)" if on else "ilk nakarat, elle"
    ses_bilgi = (f"44,1 kHz / 16 bit {Path(dosyalar['ses']).suffix[1:].upper()}, {meta['master']['lufs']:.1f} LUFS, "
                 f"{meta['master']['gercek_tepe_dbtp']:.1f} dBTP, {_mmss(meta['sure_sn'])}")
    return [
        "RouteNote formu, ekrandaki sırayla (doğrulandı: ilk yükleme, 2026-10-08). Kopyala-yapıştır:", "",
        "## 1. Album Details",
        f"1. **Language:** {DIL_ADI.get(meta['dil'], meta['dil'])}",
        f"2. **Album/Single/EP Title:** `{meta['baslik']}`",
        "3. **Album Version:** boş",
        "4. **Does this release contain cover versions?:** Yes",
        "5. **Compilation Album:** No",
        f"6. **Artist Name (Primary):** `{sanatci}`: listeden seç ya da yeni sanatçı olarak oluştur. Yalnız yazmak "
        "yetmez (\"Primary Artist field is required\"). Var olan bir Spotify profiline bağlama.",
        f"7. **Writers (Composer):** her yazar bir satır (Add Composer): {yazar_satiri}",
        f"8. **Does this release contain lyrics?:** Yes → **Lyricist** satırları aynı isimlerle: {yazar_satiri}",
        f"9. **Contributors (zorunlu):** Producer · `{sanatci}`. Yapay zekâ aracı buraya yazılmaz.",
        "10. **Primary Genre:** şarkının türü (Alternative varsayılanını bırakma) · **Secondary:** None",
        f"11. **Composition Copyright (©):** yıl `{yil}` · `{yazar_metni}` (beste orijinal yazarların)",
        f"12. **Sound Recording Copyright (℗):** yıl `{date.today().year}` · `{sanatci}`",
        f"13. **Record Label Name:** `{meta['etiket'] or sanatci}`",
        "14. **Originally Released** = **Sales Start Date**: aynı gün, en az 2–3 hafta sonrası (ücretsiz inceleme "
        "günler sürüyor; Spotify pitch için ≥7 gün). **Pre Order Date:** boş.",
        f"15. **Explicit Content:** {_acik_satiri(meta)}",
        "",
        "## 2. Add Audio",
        f"16. **Ses dosyası:** `{dosyalar['ses']}` ({ses_bilgi})",
        f"17. **Track Name:** `{meta['baslik']}` · **Title Version:** boş",
        "18. **Is this track a cover version?:** Yes (varsayılan No!) → **Do you have a mechanical license?:** No",
        "19. **Writers / Lyricist / Contributors:** 7–9 ile aynı; ad yazımını kontrol et",
        f"20. **Set Preview Start Time:** {onizleme}",
        "21. **ISRC:** RouteNote'un atadığı kalır; orijinal kaydın ISRC'si girilmez",
        "22. **Explicit Content / Audio Language:** 15 ve 1 ile aynı",
        "",
        "## 3. Add Artwork",
        f"23. **Kapak:** `{dosyalar['kapak']}` (3000×3000 JPG; orijinal sanatçının adı, fotoğrafı, logosu yok)"
        f"{_kapak_notu(meta)}",
        "",
        "## 4. Manage Stores",
        "24. **İşareti kaldır:** Amazon (yapay zekâ içeriği almıyor); Melon, Bugs!, VIBE, FLO, Genie Music (Kore: AI "
        "içerik almıyor, cover için orijinal sanatçının yazılı izni); YouTube Content ID (cover orijinalle eşleşir; "
        "YouTube Music işaretli kalır)",
        "25. **Pricing:** Standard",
        "26. **Managing Territories:** Exclude → United States, Canada, Mexico, India, Pakistan (mekanik lisans yok, "
        "Scryne 2026-10-07); mağaza listesi olduğu gibi kalır",
        "",
        "## Yapay zekâ beyanı",
        f"Formun 1–4. adımlarında sorulmadı (2026-10-08). Sorulursa: Evet, {meta['yapay_zeka']['kapsam']}; araç "
        f"{meta['yapay_zeka']['arac']} ({meta['yapay_zeka']['baglanti']}). Araç kredi ya da sanatçı alanına yazılmaz.",
        "",
        "Kurallar: başlığa `(Cover)` ya da orijinal sanatçı adı eklenmez.",
        "",
        "Yükledikten sonra: `yanki yuklendi <kimlik>`",
    ]


def _tunearo_notu(meta: dict, dosyalar: dict[str, str]) -> list[str]:
    """Tunearo'da form yok, hat API ile yükler: YUKLE.md ne gönderileceğini söyler (`yanki/tunearo.py` ile aynı)."""
    from yanki import tunearo

    yazarlar = tunearo.yazarlar(meta) or "EKSİK"
    return [
        "Tunearo'ya hat API ile kendisi yükler: yayın takviminde sırası gelince gece koşusu, ya da elle "
        "`yanki yukle <kimlik>`. Form doldurma yok.", "",
        "Gönderilenler:",
        f"- **Yayın:** Single · `{meta['baslik']}` · sanatçı `{meta['sanatci'] or 'EKSİK'}` · etiket "
        f"`{meta['etiket'] or meta['sanatci']}` · dil {DIL_ADI.get(meta['dil'], meta['dil'])} · "
        f"{'Explicit' if meta.get('acik_icerik') else 'Not Explicit'}",
        f"- **©** {meta.get('orijinal_yil') or '—'} {yazarlar} · **℗** {date.today().year} {meta['sanatci']}",
        f"- **Parça:** composer/songwriter/lyricist `{yazarlar}`, producer `{meta['sanatci']}`, düz söz",
        f"- **Dosyalar:** `{dosyalar['ses']}` ({meta['master']['lufs']:.1f} LUFS, {_mmss(meta['sure_sn'])}) · "
        f"`{dosyalar['kapak']}` (3000×3000 JPG){_kapak_notu(meta)}",
        "- **Bölge ve mağaza:** `config/yayin.toml` → `[tunearo]`",
        "",
        "Durum gece koşusunda yoklanır (`yanki dagitim-durum`): kabulde UPC/ISRC `metadata.json` → `yukleme`'ye "
        "yazılır; red gelirse şarkı `paketlendi`ye döner, neden bildirilir.",
        "",
        "Kurallar: başlığa `(Cover)` ya da orijinal sanatçı adı eklenmez; kapakta orijinal sanatçının adı, fotoğrafı "
        "ya da logosu yoktur.",
    ]


def _mmss(sn: float) -> str:
    dk, s = divmod(round(sn), 60)
    return f"{dk}:{s:02d}"


def guvenli_ad(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def ozel_kapak(kaynak: Path, hedef: Path, boyut: int = KAPAK_BOYUT) -> dict:
    """Scryne'ın seçtiği kapak. Zaten kare, `boyut` px, RGB JPEG ise bayt bayt kopyalanır; değilse ortadan kare
    kırpılır ve `boyut`'a getirilir (dağıtımcı en az 3000×3000 kare istiyor; 2026-10-08'de üç kapak elle böyle
    hazırlanmıştı). Görsel açılamazsa hata: bozuk kapakla paket çıkmaz."""
    from PIL import Image

    with Image.open(kaynak) as img:
        en, boy = img.size
        hazir = img.format == "JPEG" and img.mode == "RGB" and en == boy == boyut
        hedef.parent.mkdir(parents=True, exist_ok=True)
        if hazir:
            hedef.write_bytes(kaynak.read_bytes())
            return {"kaynak": "ozel", "ozgun_boyut": [en, boy], "islem": None}
        kenar = min(en, boy)
        sol, ust = (en - kenar) // 2, (boy - kenar) // 2
        kare = img.convert("RGB").crop((sol, ust, sol + kenar, ust + kenar))
        kare.resize((boyut, boyut), Image.Resampling.LANCZOS).save(hedef, "JPEG", quality=95)
    kirpma = f"ortadan kare kırpıldı ({en}×{boy} → {kenar}×{kenar}), " if en != boy else ""
    islem = f"{kirpma}{boyut}×{boyut}'e getirildi"
    return {"kaynak": "ozel", "ozgun_boyut": [en, boy], "islem": islem}


def paketle(calisma: Path, yayin_yolu: Path, kimlikler: list[str] | None = None,
            yeniden: bool = False, hatalar: list | None = None) -> list[durum.Durum]:
    """`onaylandi` (yeniden=True ise `paketlendi` de) şarkıları paketler. Bir şarkının hatası (ffmpeg, bozuk kapak)
    diğerlerini durdurmaz: şarkı aşamasında kalır, hata `hatalar`a eklenir, sonraki koşu yeniden dener."""
    y = yayin_ayarlari(yayin_yolu)
    asamalar = ("onaylandi", "paketlendi") if yeniden else ("onaylandi",)
    islenen = []
    for d in durum.hepsi(calisma):
        if d.asama not in asamalar or (kimlikler and d.kimlik not in kimlikler):
            continue
        try:
            islenen.append(_paketle_bir(calisma, d, y))
        except Exception as e:  # noqa: BLE001
            if hatalar is None:
                raise
            hatalar.append((d, f"{type(e).__name__}: {e}"))
    return islenen


KALICI_ALANLAR = ("yukleme", "yukleme_gecmisi", "routenote", "routenote_gecmisi", "tunearo", "tunearo_gecmisi")


def yukleme_kilidi(paket_klasoru: Path) -> Path:
    """Paketin kilidi (`kilit.tek_kosu`): dağıtımcıya yükleme sürerken paket yenilenmesin, yenilenirken yüklenmesin.
    Klasörün dışında: `yanki yeniden` paket klasörünü taşıyabilsin (Windows açık dosyalı klasörü taşımıyor)."""
    return paket_klasoru.parent / f".{paket_klasoru.name}.yukleme.kilit"


def acik_taslak(paket_klasoru: Path) -> dict | None:
    """Paketin RouteNote'ta açılmış ama gönderilmemiş taslağı (kayıt), yoksa None."""
    try:
        rn = json.loads((paket_klasoru / "metadata.json").read_text(encoding="utf-8")).get("routenote") or {}
    except (OSError, ValueError):
        return None
    return rn if rn.get("adim") and rn.get("adim") != "gonderildi" else None


def _paketle_bir(calisma: Path, d: durum.Durum, y: Yayin) -> durum.Durum:
    from yanki import kilit

    p = durum.klasor(calisma, d.kimlik) / "paket"
    with kilit.tek_kosu(yukleme_kilidi(p)) as alindi:
        if not alindi:
            raise ValueError("paket şu an dağıtımcıya yükleniyor; yükleme bitince yeniden dene")
        return _paketle_kilitli(calisma, d, y)


def _gecici(hedef: Path) -> Path:
    """Paketin yanında yarım yazılabilecek dosyanın adı: noktalı ve `.yaziliyor` (yükleyici saymaz, sonraki paketleme
    siler), uzantı aynı (ffmpeg biçimi uzantıdan seçiyor)."""
    return hedef.with_name(f".{hedef.stem}.yaziliyor{hedef.suffix}")


def _paketle_kilitli(calisma: Path, d: durum.Durum, y: Yayin) -> durum.Durum:
    from yanki import sunucu

    k = durum.klasor(calisma, d.kimlik)
    aday = next((x for x in d.adaylar if x.no == d.secilen), None)
    if aday is None or not aday.dosya:
        raise ValueError(f"seçilen aday ({d.secilen}) ya da dosyası yok")
    kaynak = k / aday.dosya
    p = k / "paket"
    if (acik := acik_taslak(p)):
        # taslaktaki ses/kapak RouteNote'ta kayıtlı: paket değişirse taslak eski dosyalarla gönderilirdi
        raise ValueError(f"RouteNote'ta açık taslak var (UPC {acik.get('upc')}, adım {acik.get('adim')}): taslağı "
                         f"panelden sil, sonra `yanki routenote taslak-silindi {d.kimlik}`")
    ad = guvenli_ad(f"{y.sanatci_adi or 'SANATCI'} - {d.ad}")
    ses_yolu, kapak_yolu = p / f"{ad}.{SES_BICIMI[y.dagitimci]}", p / f"{ad}.jpg"
    orijinal = k / d.kaynak["dosya"] if d.kaynak.get("dosya") else None
    # ses ve kapak önce geçici adla yazılır, bitince yerine konur: yeniden paketleme yarıda kesilirse (güç, çökme)
    # eski metadata.json'un yanında yarım bir FLAC kalmaz (aşama `paketlendi` kaldığı için o dosya yüklenirdi)
    gecici_ses, gecici_kapak = _gecici(ses_yolu), _gecici(kapak_yolu)
    olcum = master(kaynak, gecici_ses, y, referans=orijinal if orijinal and orijinal.exists() else None)
    # Scryne'ın elle koyduğu kapak her zaman önce; yoksa ayara göre Pinterest (şarkının modu) ya da dalga formundan
    # üretilen. Görsel 3000×3000 kareye getirilir. Pinterest bulamazsa hata: şarkı onaylı kalır, sonraki koşu dener.
    if (ozel := k / "kapak_ozel.jpg").exists():
        kapak_bilgi = ozel_kapak(ozel, gecici_kapak)
    elif y.kapak == "pinterest":
        from yanki import olay, pinterest

        yeni_secim = not (k / "kapak_pinterest.jpg").exists()
        kapak_bilgi = {**ozel_kapak(pinterest.getir(calisma, d), gecici_kapak), "kaynak": "pinterest"}
        kaynak_yolu = k / "kapak_kaynak.json"
        pin = json.loads(kaynak_yolu.read_text(encoding="utf-8")) if kaynak_yolu.exists() else {}
        kapak_bilgi["pin"] = pin.get("pin")
        if yeni_secim:  # açıklama süzgeci her yazıyı/insanı yakalamıyor (11'de 2 kaçtı): göz atılsın
            olay.bildir(calisma, "kapak", f"kapak seçildi: {d.ad}",
                        f"{pin.get('aciklama')} — calisma/{d.kimlik}/kapak_pinterest.jpg. Beğenmezsen: "
                        f"yanki kapak {d.kimlik} --yeni", f"kapak:{d.kimlik}:{pin.get('pin_id')}")
    else:
        kapak(d.ad, sunucu.dalga(kaynak)["tepe"], gecici_kapak, y.sanatci_adi)
        kapak_bilgi = {"kaynak": "uretilen", "ozgun_boyut": [KAPAK_BOYUT, KAPAK_BOYUT], "islem": None}
    zaman = k / "soz_zaman.json"
    onizleme = nakarat_baslangici(json.loads(zaman.read_text(encoding="utf-8"))) if zaman.exists() else None
    soz = k / "soz.txt"
    acik = acik_sozler(soz.read_text(encoding="utf-8")) if soz.exists() else None
    meta = metadata(d, y, olcum, ses.sure(gecici_ses), onizleme, acik)
    meta["kapak"] = kapak_bilgi
    # yeniden paketlemede dağıtım geçmişi kalır: reddedilen yayın aynı kayıtla yeniden gönderilir (Tunearo), red
    # geçmişi takvimin ilk_kabul kapısını tutar
    if (eski_yol := p / "metadata.json").exists():
        eski = json.loads(eski_yol.read_text(encoding="utf-8"))
        meta.update({a: eski[a] for a in KALICI_ALANLAR if a in eski})
    gecici_ses.replace(ses_yolu)
    gecici_kapak.replace(kapak_yolu)
    # başka biçimde ya da adla kalmış eski ses/kapak (FLAC → WAV, sanatçı adı değişti), yarım kalmış geçici dosya:
    # yükleyici tek dosya bekler
    for eski_dosya in [*p.glob("*.flac"), *p.glob("*.wav"), *p.glob("*.jpg")]:  # noktalılar dahil (eski küçük resim)
        if eski_dosya not in (ses_yolu, kapak_yolu):
            eski_dosya.unlink()
    dosya.json_yaz(p / "metadata.json", meta)  # atomik: yükleyici ve dinleme odası yarım dosya görmesin
    dosya.yaz(p / "YUKLE.md", yukle_md(meta, y, {"ses": ses_yolu.name, "kapak": kapak_yolu.name}))
    with durum.guncelle(calisma, d.kimlik) as taze:
        # paketleme sürerken seçim değiştiyse (yeniden üretim, ret) paket eskidir: aşamaya dokunma
        if taze.asama == d.asama and taze.secilen == d.secilen:
            taze.gec("paketlendi")
    return taze
