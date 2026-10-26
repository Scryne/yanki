"""RouteNote'un yayın e-postaları → hat: onay, "Action Needed" (düzeltme isteği), red (Scryne 2026-10-16: "e-postadan").

RouteNote paneli botla okunmaz (site şartları madde 2). RouteNote onay, düzeltme isteği ve red için hesabın
e-postasına otomatik ileti atıyor (çalışanın blog yorumu: "automated emails from us notifying you of approval, user
action or disapproval"); gönderen adresi ve konu satırları belgelenmemiş (`docs/arastirma/08`). Bu yüzden:
- IMAP ile yalnız gönderende "routenote" geçen iletiler okunur (`BODY.PEEK`: okunmadı işareti bozulmaz, hiçbir şey
  silinmez). Ayar `.env`: `EPOSTA_KULLANICI`, `EPOSTA_SIFRE` (Gmail: uygulama şifresi), `EPOSTA_SUNUCU`
  (varsayılan imap.gmail.com).
- Sınıf anahtar kelimeyle (red önce: "not been approved" onay sayılmasın); eşleşme UPC'yle, yoksa şarkının adıyla
  (tek aday). Sınıflanamayan ya da şarkısı bulunamayan ileti de bildirilir: Scryne görür, kural ilk örneklerle
  genişletilir. Her yeni iletinin metni `calisma/eposta/ornek/`'e yazılır (yalnız RouteNote'unkiler).
- Red: `dagitim.red_kaydet` (şarkı `paketlendi`ye döner, takvim düzeltilene kadar yeni yükleme açmaz); RouteNote
  kaydı geçmişe (reddedilen yayın katalogdan çıkıyor, yeniden gönderim yeni taslak ister). Onay ve düzeltme isteği:
  yükleme kaydına durum + bildirim.
"""

import email
import email.policy
import hashlib
import html
import imaplib
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email.utils import parsedate_to_datetime
from pathlib import Path

from yanki import dosya, durum

RED = re.compile(r"disapprov|declin|reject|not (been )?approved|unable to (approve|accept|distribute|release)|"
                 r"cannot be (approved|distributed)|removed from sale|taken down", re.I)
AKSIYON = re.compile(r"action needed|action required|sent (it |your release )?back|requires? (your )?attention|"
                     r"needs? (some )?changes|please (amend|update|correct|edit)|moderation (team )?comment", re.I)
ONAY = re.compile(r"\bapproved\b|has been accepted|on its way to (the )?stores|sent to (the )?stores|"
                  r"delivered to (the )?stores|is now live|congratulations", re.I)
UPC = re.compile(r"(?<!\d)\d{12,13}(?!\d)")
# yayınla ilgisi olmayan hesap iletileri: sessizce geçilir (2026-10-16 ilk okuma: "Welcome aboard! Activate your New
# Account.", "Profile Code" — ikisi de noreply@routenote.com)
ILGISIZ = re.compile(r"welcome aboard|activate your|access code|profile code|password|verify your|verification|"
                     r"newsletter|special offer|webinar|survey|referral", re.I)
ILGILI = re.compile(r"release|single|album|\btrack|moderat|distribut|\bstores?\b|\bupc\b|isrc|takedown|approv|"
                    r"declin|reject|action needed", re.I)
BASLIK_UZUNLUGU = 4000


@dataclass
class Ileti:
    kimlik: str  # Message-ID (yoksa içerik özeti)
    gonderen: str
    konu: str
    tarih: str
    metin: str


# Onaydan sonra mağazaya teslim süresi: tarihsiz ("onaylanınca") yayında takibin gecikme ölçütü gönderim + 14 gün
# yerine onay + bu kadar gün olur (+ `takip.GECIKME_GUN`). Erken onaylanan parçanın teslim sorunu bir hafta erken
# görünür, geç onaylanan parça teslim sürerken "yayın tarihi geçti" diye yanlış alarm vermez.
ONAY_SONRASI_GUN = 7


def _onay_bilgisi(calisma: Path, kimlik: str, ileti_tarihi: str | None) -> dict:
    from yanki import takip

    bilgi: dict = {"dagitim_durumu": "approved", "onay_tarihi": (ileti_tarihi or "")[:10] or None}
    y = takip.yukleme_bilgisi(calisma, kimlik) or {}
    if not y.get("yayin_tarihi"):  # tarihli yayında ölçüt yayın tarihinin kendisi
        try:
            gun = date.fromisoformat(bilgi["onay_tarihi"] or date.today().isoformat())
        except ValueError:
            gun = date.today()
        bilgi["en_gec_yayin"] = (gun + timedelta(days=ONAY_SONRASI_GUN)).isoformat()
    return bilgi

def ayar(kok: Path) -> dict | None:
    from yanki import spotify

    env = spotify.env_oku(kok)
    import os

    al = lambda k: os.environ.get(k) or env.get(k)  # noqa: E731
    if not (al("EPOSTA_KULLANICI") and al("EPOSTA_SIFRE")):
        return None
    return {"kullanici": al("EPOSTA_KULLANICI"), "sifre": al("EPOSTA_SIFRE").replace(" ", ""),
            "sunucu": al("EPOSTA_SUNUCU") or "imap.gmail.com"}


def _metin(mesaj) -> str:
    """Düz metin parça varsa o, yoksa HTML'den etiketsiz metin."""
    parca = mesaj.get_body(preferencelist=("plain", "html")) if mesaj.is_multipart() else mesaj
    if parca is None:
        return ""
    # baytlar önce UTF-8 denenir: RouteNote'un HTML'i charset bildirmeden ya da yanlış bildirip UTF-8 gönderiyor
    # (2026-10-16: "weâll"); geçerli UTF-8 Latin metinde yanlışlıkla tutmaz
    ham = parca.get_payload(decode=True) or b""
    for kod in ("utf-8", parca.get_content_charset(), "cp1252"):
        try:
            icerik = ham.decode(kod) if kod else None
        except (UnicodeDecodeError, LookupError):
            icerik = None
        if icerik is not None:
            break
    else:
        icerik = ham.decode("utf-8", "replace")
    if parca.get_content_type() == "text/html":
        icerik = re.sub(r"(?s)<!--.*?-->", " ", icerik)
        icerik = re.sub(r"(?is)<(script|style|head|title).*?</\1>", " ", icerik)
        icerik = re.sub(r"(?i)<br\s*/?>|</p>|</div>|</tr>", "\n", icerik)
        icerik = html.unescape(re.sub(r"<[^>]+>", " ", icerik))
    return re.sub(r"[ \t\xa0]+", " ", re.sub(r"\n\s*\n+", "\n", icerik)).strip()


def ayristir(ham: bytes) -> Ileti:
    m = email.message_from_bytes(ham, policy=email.policy.default)
    metin = _metin(m)
    try:
        tarih = parsedate_to_datetime(m["Date"]).isoformat(timespec="seconds") if m["Date"] else ""
    except (TypeError, ValueError):
        tarih = ""
    kimlik = (m["Message-ID"] or "").strip() or hashlib.sha1(ham).hexdigest()
    return Ileti(kimlik=kimlik, gonderen=str(m["From"] or ""), konu=str(m["Subject"] or ""), tarih=tarih,
                 metin=metin[:BASLIK_UZUNLUGU * 4])


def _tum_postalar(baglanti) -> str:
    """Gmail'in "Tüm Postalar"ı (arşivlenen de içinde; adı dile göre değişir: `\\All` bayrağından), yoksa INBOX."""
    try:
        _, kutular = baglanti.list()
    except (OSError, imaplib.IMAP4.error, AttributeError):
        return "INBOX"
    for k in kutular or []:
        s = k.decode(errors="replace") if isinstance(k, bytes) else str(k)
        if "\\All" in s and (ad := re.search(r'"([^"]+)"\s*$|(\S+)\s*$', s)):
            return f'"{ad[1] or ad[2]}"'
    return "INBOX"


def getir(a: dict, gun: int = 21, imap=imaplib.IMAP4_SSL) -> list[Ileti]:
    """Son `gun` günde gönderende "routenote" geçen iletiler (salt okunur, `BODY.PEEK`)."""
    baglanti = imap(a["sunucu"])
    try:
        baglanti.login(a["kullanici"], a["sifre"])
        baglanti.select(_tum_postalar(baglanti), readonly=True)
        once = (date.today() - timedelta(days=gun)).strftime("%d-%b-%Y")
        _, veri = baglanti.search(None, "FROM", '"routenote"', "SINCE", once)
        iletiler = []
        for no in (veri[0] or b"").split():
            _, parcalar = baglanti.fetch(no, "(BODY.PEEK[])")
            ham = next((p[1] for p in parcalar if isinstance(p, tuple)), None)
            if ham:
                iletiler.append(ayristir(ham))
        return iletiler
    finally:
        try:
            baglanti.logout()
        except (OSError, imaplib.IMAP4.error):
            pass


def sinif(i: Ileti) -> str | None:
    """Red önce ("not been approved" onay sayılmasın); ama düzeltme isteyen ileti ("cannot be approved until you
    amend…") red değil: ikisi birden tutarsa düzeltme (şarkıyı kuyruğa döndürmez, Scryne'a metniyle bildirir)."""
    metin = f"{i.konu}\n{i.metin[:BASLIK_UZUNLUGU]}"
    if RED.search(metin):
        return "aksiyon" if AKSIYON.search(metin) else "red"
    for ad, kalip in (("aksiyon", AKSIYON), ("onay", ONAY)):
        if kalip.search(metin):
            return ad
    return None


def adaylar(calisma: Path) -> list[dict]:
    """RouteNote'a gönderilmiş şarkılar: kimlik, ad, UPC (paketin RouteNote kaydı ya da yükleme bilgisi)."""
    sonuc = []
    for d in durum.hepsi(calisma):
        if d.asama not in ("yuklendi", "yayinda", "paketlendi"):
            continue
        try:
            meta = json.loads((durum.klasor(calisma, d.kimlik) / "paket" / "metadata.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        upc = (meta.get("routenote") or {}).get("upc") or (meta.get("yukleme") or {}).get("upc")
        if upc or d.asama != "paketlendi":
            sonuc.append({"kimlik": d.kimlik, "ad": meta.get("baslik") or d.ad, "upc": str(upc or ""),
                          "asama": d.asama})
    return sonuc


# Gövdede tek sözcüklü ad yalnız yayın bağlamında sayılır: "lovely" bir şarkımızın adı, "have a lovely day" değil.
# Bağlam: tırnak/ayraç içinde, "release/single/track/titled …" sonrasında ya da "… was/has/is" öncesinde.
BAGLAM_ONCE = re.compile(r"(?:release|single|track|album|\bep|titled|called|for|:|[\"“'‘«(\[])\s*$")
BAGLAM_SONRA = re.compile(r"^\s*(?:[\"”'’»)\]]|was\b|has\b|is\b|have\b|-|–|—|by\b|upc\b)")


def _geciyor(ad: str, metin: str, baglamli: bool) -> bool:
    for m in re.finditer(rf"(?<!\w){re.escape(ad)}(?!\w)", metin):
        if (not baglamli or BAGLAM_ONCE.search(metin[max(0, m.start() - 20):m.start()])
                or BAGLAM_SONRA.search(metin[m.end():m.end() + 12])):
            return True
    return False


def eslestir(i: Ileti, liste: list[dict]) -> dict | None:
    """UPC iletide geçiyorsa o. İletide UPC var ama hiçbir adayın değilse (geçmişe alınmış taslak, arşivdeki yayın,
    elle taslak, başkasının yayını) adla eşleştirilmez: ileti başka bir yayın hakkında. Yoksa adı konuda geçen ya da
    gövdede (tek sözcüklü adda yayın bağlamında) geçen tek şarkı. Eşleşmeyen ileti yalnız bildirilir."""
    metin = f"{i.konu}\n{i.metin}"
    upcler = set(UPC.findall(metin))
    if hit := [x for x in liste if x["upc"] and (x["upc"] in upcler or x["upc"].lstrip("0") in upcler)]:
        return hit[0]
    if upcler:
        return None
    konu, govde = i.konu.casefold(), i.metin.casefold()
    adlilar = [x for x in liste if (ad := (x["ad"] or "").casefold())
               and (_geciyor(ad, konu, False) or _geciyor(ad, govde, len(ad.split()) < 2))]
    adlilar.sort(key=lambda x: -len(x["ad"]))  # "Numb" ile "Numb (Acoustic)" ikisi tutarsa uzun ad
    if len(adlilar) == 1 or (len(adlilar) > 1 and len(adlilar[0]["ad"]) > len(adlilar[1]["ad"])):
        return adlilar[0]
    return None


def _ozet(i: Ileti, uzunluk: int = 400) -> str:
    return re.sub(r"\s+", " ", i.metin)[:uzunluk]


def kayit_yolu(calisma: Path) -> Path:
    return calisma / "eposta" / "routenote.json"


def isle(calisma: Path, iletiler: list[Ileti], bildir=None) -> list[dict]:
    """Yeni iletileri hatta işler (her ileti bir kez). Dönen: [{ileti, sinif, kimlik, eylem}]."""
    from yanki import dagitim, takip

    bildir = bildir or (lambda *a, **k: None)
    yol = kayit_yolu(calisma)
    kayit = json.loads(yol.read_text(encoding="utf-8")) if yol.exists() else {}
    liste = adaylar(calisma)
    sonuc = []
    for i in sorted(iletiler, key=lambda x: x.tarih):
        if i.kimlik in kayit:
            continue
        ozet_kimlik = hashlib.sha1(i.kimlik.encode()).hexdigest()
        tur, sarki = sinif(i), eslestir(i, liste)
        bas = f"{i.konu}\n{i.metin[:BASLIK_UZUNLUGU]}"
        # hesap iletisi konusundan tanınır ("Welcome aboard", "Password"): gövdesinde "congratulations" geçse de
        # onay sayılmaz, gövdesi (etkinleştirme bağlantısı, kod) diske yazılmaz
        hesap = bool(ILGISIZ.search(i.konu)) and not ILGILI.search(i.konu)
        ilgisiz = hesap or (tur is None and not ILGILI.search(bas))
        if ilgisiz:
            tur = sarki = None
        if not ilgisiz:  # hesap iletilerinin gövdesi (giriş kodu, etkinleştirme bağlantısı) diske yazılmaz
            ornek = calisma / "eposta" / "ornek" / f"{(i.tarih or 'tarihsiz')[:10]}-{ozet_kimlik[:8]}.txt"
            ornek.parent.mkdir(parents=True, exist_ok=True)
            dosya.yaz(ornek, f"Kimden: {i.gonderen}\nKonu: {i.konu}\nTarih: {i.tarih}\n\n{i.metin}")
        eylem = "bildirildi"
        anahtar = f"eposta:{ozet_kimlik[:12]}"
        if tur in ("onay", "aksiyon") and sarki and sarki["asama"] == "paketlendi":
            # onay/düzeltme yalnız gönderilmiş yayına gelir: Scryne panelden elle göndermiş, hat kaydetmemiş
            from yanki import routenote

            try:
                routenote.gonderim_sonucu(calisma, sarki["kimlik"], True)
                sarki = {**sarki, "asama": "yuklendi"}
            except ValueError:
                pass  # RouteNote kaydı hazır değil (eski taslak): yalnız bildirilir
        if ilgisiz:
            eylem = "ilgisiz (hesap iletisi)"  # hoş geldin, giriş kodu: bildirilmez
        elif tur is None or sarki is None:
            neden = "türü anlaşılmadı" if tur is None else "hangi şarkı olduğu bulunamadı"
            bildir("dagitim", f"RouteNote e-postası ({neden})", f"Konu: {i.konu}. {_ozet(i, 300)}", anahtar)
        elif tur == "onay":
            if sarki["asama"] in ("yuklendi", "yayinda"):
                takip.yukleme_kaydet(calisma, sarki["kimlik"], _onay_bilgisi(calisma, sarki["kimlik"], i.tarih))
                eylem = "onay kaydedildi"
            bildir("dagitim", f"RouteNote onayladı: {sarki['ad']}",
                   f"Mağazalara teslim ediliyor; onaydan {ONAY_SONRASI_GUN} gün sonra hâlâ Spotify'da yoksa takip "
                   "bildirir.", anahtar)
        elif tur == "aksiyon":
            if sarki["asama"] in ("yuklendi", "yayinda"):
                takip.yukleme_kaydet(calisma, sarki["kimlik"], {"dagitim_durumu": "action_needed"})
                eylem = "düzeltme isteği kaydedildi"
            bildir("dagitim", f"RouteNote düzeltme istiyor: {sarki['ad']}",
                   f"Moderasyon yayını geri gönderdi; RouteNote panelinde yayının yorumuna bak, düzelt ve yeniden "
                   f"gönder. E-posta: {_ozet(i)}", anahtar)
        else:  # red
            neden = _ozet(i, 300)
            # red geri alınması zor bir kayıt (yükleme geçmişe, şarkı kuyruğa): yalnız iletide UPC'si geçen ve henüz
            # canlı olmayan şarkıda kendiliğinden; adla eşleşen ya da yayındaki şarkıda Scryne doğrular (alt bilgi
            # metnindeki "declined"/"taken down" yanlış red üretebiliyordu — Denetim 7)
            upc_ile = bool(sarki["upc"]) and sarki["upc"].lstrip("0") in {
                u.lstrip("0") for u in UPC.findall(f"{i.konu}\n{i.metin}")}
            if sarki["asama"] == "yuklendi" and upc_ile:
                try:
                    dagitim.red_kaydet(calisma, sarki["kimlik"], f"RouteNote: {neden}")
                    eylem = "red kaydedildi (paketlendi'ye döndü)"
                except ValueError as e:
                    eylem = f"red kaydedilemedi: {e}"
                bildir("kayip", f"RouteNote reddetti: {sarki['ad']}",
                       f"Şarkı paketlendi'ye döndü; takvim sebep anlaşılıp düzeltilene kadar yeni yükleme açmaz. "
                       f"E-posta: {neden}", anahtar)
            else:
                eylem = "red olabilir, doğrulama bekliyor"
                bildir("kayip", f"RouteNote reddetmiş olabilir: {sarki['ad']}",
                       f"E-posta {'UPC içermiyor' if not upc_ile else 'yayındaki şarkı hakkında'}: kendiliğinden "
                       f"işlenmedi. Panelde bak; red ise `yanki dagitim-red {sarki['kimlik']}`. E-posta: {neden}",
                       anahtar)
        kayit[i.kimlik] = {"tarih": i.tarih, "konu": i.konu, "sinif": tur, "sarki": sarki and sarki["kimlik"],
                           "eylem": eylem, "islendi": datetime.now().isoformat(timespec="seconds")}
        sonuc.append({"konu": i.konu, "sinif": tur, "kimlik": sarki and sarki["kimlik"], "eylem": eylem})
        # her iletiden sonra: sonraki iletide hata çıksa da işlenen (red kaydı, bildirim) ikinci kez işlenmez
        dosya.json_yaz(yol, kayit, indent=1)
    return sonuc
