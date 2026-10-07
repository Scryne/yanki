"""Yükleme paketi: onaylanan aday → mastering + kapak + metadata + YUKLE.md (`calisma/<kimlik>/paket/`).

Yükleme insanda kalır (dağıtımcılarda API yok; DistroKid ToS'u botu yasaklıyor). Paket, formu kopyala-yapıştırla
doldurmaya yetecek her şeyi taşır. Eksik karar (sanatçı adı, dağıtımcı) varsa paket yine hazırlanır, YUKLE.md en
üstte eksikleri yazar.
"""

import json
import re
import subprocess
import tomllib
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

from yanki import durum, ses

FONT_KALIN = Path("C:/Windows/Fonts/bahnschrift.ttf")

# Dağıtımcıya özel ayrıntılar: docs/arastirma/02-dagitimci-karsilastirmasi.md (2026-10-07). RouteNote WAV almıyor
# (FLAC/MP3 44,1); bilgi 2023 tarihli, yükleme ekranında doğrulanır.
SES_BICIMI = {"routenote": "flac", "distrokid": "wav", "": "wav"}
DAGITIMCI_ADI = {"distrokid": "DistroKid", "routenote": "RouteNote"}
DAGITIMCI_NOTU = {
    "distrokid": [
        "Yapay zekâ sorusu (\"Is any part of this track AI-generated?\"): **all of the audio**. Ardından sanatçının"
        " insan mı AI persona mı olduğu sorulur.",
        "Cover adımı formun Songwriter bölümünde: cover seçilir, orijinal sanatçı ve şarkı adı girilir"
        " (DistroKid üzerinden, $12/yıl/şarkı; onay 14 iş gününe kadar sürebilir).",
    ],
    "routenote": [
        "Yapay zekâ aracı kredi ya da sanatçı alanına yazılmaz; RouteNote isterse aracın bağlantısı verilir.",
        "Mekanik lisans alınmıyor (Scryne, 2026-10-07): mağaza bölgelerinden ABD, Kanada, Meksika, Hindistan ve"
        " Pakistan çıkarılır (RouteNote'un lisanssız cover kuralı).",
        "Kore mağazaları (Melon, Genie, Bugs, Flo, Vibe) ve Amazon AI içeriği almaz; seçiliyse kaldır.",
    ],
}


@dataclass(frozen=True)
class Yayin:
    sanatci_adi: str
    dagitimci: str
    etiket: str
    lufs: float
    gercek_tepe: float
    ornekleme: int


def yayin_ayarlari(yol: Path) -> Yayin:
    with open(yol, "rb") as f:
        d = tomllib.load(f)
    y, m = d["yayin"], d["master"]
    if y["dagitimci"] not in ("", "routenote", "distrokid"):
        raise ValueError(f"dagitimci routenote, distrokid ya da boş olmalı: {y['dagitimci']}")
    return Yayin(y["sanatci_adi"].strip(), y["dagitimci"], y.get("etiket", "").strip(), float(m["lufs"]),
                 float(m["gercek_tepe_dbtp"]), int(m["ornekleme"]))


def _loudnorm_olc(girdi: Path, y: Yayin) -> dict:
    cikti = subprocess.run(
        [ses.arac("ffmpeg"), "-hide_banner", "-nostats", "-i", str(girdi), "-af",
         f"loudnorm=I={y.lufs}:TP={y.gercek_tepe}:LRA=11:print_format=json", "-f", "null", "-"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True).stderr
    return json.loads(cikti[cikti.rindex("{"): cikti.rindex("}") + 1])


def master(girdi: Path, hedef: Path, y: Yayin) -> dict:
    """İki geçişli EBU R128 loudnorm (doğrusal mod) → 44,1 kHz 16 bit WAV ya da FLAC (hedefin uzantısına göre).
    Ölçülen son değerleri döner."""
    o = _loudnorm_olc(girdi, y)
    filtre = (f"loudnorm=I={y.lufs}:TP={y.gercek_tepe}:LRA=11:measured_I={o['input_i']}:measured_TP={o['input_tp']}"
              f":measured_LRA={o['input_lra']}:measured_thresh={o['input_thresh']}:offset={o['target_offset']}"
              ":linear=true")
    hedef.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(girdi), "-af", filtre,
                    "-ar", str(y.ornekleme), "-ac", "2", *_kodlayici(hedef), str(hedef)], check=True)
    son = _loudnorm_olc(hedef, y)
    return {"lufs": float(son["input_i"]), "gercek_tepe_dbtp": float(son["input_tp"])}


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


def metadata(d: durum.Durum, y: Yayin, master_olcum: dict, sure_sn: float) -> dict:
    k = d.kunye or {}
    return {
        "baslik": d.ad,  # dağıtımcı kuralı: orijinal başlıkla aynı, "(Cover)" eki yok, orijinal sanatçı adı yok
        "sanatci": y.sanatci_adi or None,
        "etiket": y.etiket or y.sanatci_adi or None,
        "tur": "cover",
        "orijinal_sanatci": d.sanatci,  # formda yalnız cover bilgisi alanına (başlık/sanatçı alanlarına değil)
        "orijinal_yazarlar": list(k.get("yazarlar") or []),
        "orijinal_isrc": list(k.get("isrc") or []),
        "orijinal_eser_mbid": k.get("eser_mbid"),
        "dil": d.analiz.get("dil", "en"),
        "sure_sn": round(sure_sn, 2),
        "yapay_zeka": {"kullanildi": True, "arac": "ACE-Step 1.5 (XL-SFT)", "kapsam": "vokal ve enstrümantal üretim",
                       "baglanti": "https://github.com/ace-step/ACE-Step-1.5"},
        "acik_icerik": None,  # Scryne işaretler; sözlerde küfür taraması yapılmadı
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
        eksik.append("Dağıtımcı: `config/yayin.toml` → `dagitimci` (routenote | distrokid)")
    if not meta["orijinal_yazarlar"]:
        eksik.append("Orijinal yazarlar bulunamadı: dağıtımcının cover formunda zorunlu")
    satir = [f"# Yükleme: {meta['baslik']}", ""]
    if eksik:
        satir += ["> **Eksik karar — yüklemeden önce:**", *[f"> - {e}" for e in eksik], ""]
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
        f"10. **Kapak:** `{dosyalar['kapak']}` (3000×3000 JPG)",
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


def _mmss(sn: float) -> str:
    dk, s = divmod(round(sn), 60)
    return f"{dk}:{s:02d}"


def guvenli_ad(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s).strip("_")


def paketle(calisma: Path, yayin_yolu: Path, kimlikler: list[str] | None = None,
            yeniden: bool = False) -> list[durum.Durum]:
    """`onaylandi` (yeniden=True ise `paketlendi` de) şarkıları paketler."""
    from yanki import sunucu

    y = yayin_ayarlari(yayin_yolu)
    asamalar = ("onaylandi", "paketlendi") if yeniden else ("onaylandi",)
    islenen = []
    for d in durum.hepsi(calisma):
        if d.asama not in asamalar or (kimlikler and d.kimlik not in kimlikler):
            continue
        k = durum.klasor(calisma, d.kimlik)
        aday = next(x for x in d.adaylar if x.no == d.secilen)
        kaynak = k / aday.dosya
        p = k / "paket"
        ad = guvenli_ad(f"{y.sanatci_adi or 'SANATCI'} - {d.ad}")
        ses_yolu, kapak_yolu = p / f"{ad}.{SES_BICIMI[y.dagitimci]}", p / f"{ad}.jpg"
        olcum = master(kaynak, ses_yolu, y)
        kapak(d.ad, sunucu.dalga(kaynak)["tepe"], kapak_yolu, y.sanatci_adi)
        meta = metadata(d, y, olcum, ses.sure(ses_yolu))
        (p / "metadata.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (p / "YUKLE.md").write_text(yukle_md(meta, y, {"ses": ses_yolu.name, "kapak": kapak_yolu.name}),
                                    encoding="utf-8")
        d.gec("paketlendi")
        durum.yaz(calisma, d)
        islenen.append(d)
    return islenen
