"""RouteNote kazanç raporu: Scryne'ın panelden indirdiği satış raporları (`girdi/kazanc/*.csv`) → şarkı başına kazanç.

RouteNote paneli botla okunmaz (site şartları madde 2; `yanki/performans.py`). Rapor ayda bir gelir; Scryne panelden
indirip klasöre bırakır, hat her açılışta okur. Sütun adları sabit değil (rapor türüne göre değişebiliyor): başlıklar
eş anlamlılarından tanınır, satır şarkıya ISRC (yoksa UPC) ile bağlanır. Aynı satır iki dosyada geçerse (aylık rapor
+ tüm geçmiş) bir kez sayılır.
"""

import csv
import io
import re
from collections import Counter
from pathlib import Path

# başlık (küçük harf, sade) → alan; ilk eşleşen kazanır
ESANLAMLI = {
    "isrc": ("isrc",),
    "upc": ("upc", "ean", "barcode", "upc ean"),
    "parca": ("track title", "track name", "track", "song title", "song", "title"),
    "sanatci": ("track artist", "artist name", "artist", "release artist"),
    "magaza": ("store", "dsp", "retailer", "service", "platform", "shop", "store name", "outlet"),
    "ulke": ("country", "territory", "country code", "region"),
    "ay": ("sale month", "sales month", "reporting month", "statement month", "month", "period", "reporting period",
           "sale period", "date", "sales date", "transaction date"),
    "adet": ("quantity", "units", "streams", "plays", "qty", "unit count", "downloads"),
    "tutar": ("net revenue", "net earnings", "earnings", "revenue", "royalty", "royalties", "net amount", "amount",
              "payable", "income", "net", "total"),
    "para": ("currency", "currency code"),
}
PARA_SIMGE = {"£": "GBP", "$": "USD", "€": "EUR"}


def klasor(kok: Path) -> Path:
    return kok / "girdi" / "kazanc"


def _sade(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").strip().lower()).strip()


def sutunlar(baslik: list[str]) -> dict[str, int]:
    """Başlık satırı → {alan: sütun no}. Tam eşleşme önce, sonra içerme ("Earnings (GBP)")."""
    sade = [_sade(b) for b in baslik]
    sonuc: dict[str, int] = {}
    for alan, adlar in ESANLAMLI.items():
        for ad in adlar:
            i = next((i for i, b in enumerate(sade) if b == ad and i not in sonuc.values()), None)
            if i is None:
                i = next((i for i, b in enumerate(sade) if re.search(rf"\b{re.escape(ad)}\b", b)
                          and i not in sonuc.values()), None)
            if i is not None:
                sonuc[alan] = i
                break
    return sonuc


def _para(metin: str, baslik: str = "") -> tuple[float | None, str | None]:
    """'£1,234.56' / '1.234,56' / '0.0123' → (sayı, para birimi). Para birimi başlıktan da ("Earnings (GBP)")."""
    m = (metin or "").strip()
    birim = next((k for s, k in PARA_SIMGE.items() if s in m), None)
    if birim is None and (b := re.search(r"\b(GBP|USD|EUR)\b", baslik.upper())):
        birim = b[1]
    m = re.sub(r"[^\d,.\-]", "", m)
    if not m:
        return None, birim
    if "," in m and "." in m:  # binlik ayırıcı hangisi: sondaki ondalık
        m = m.replace(",", "") if m.rfind(".") > m.rfind(",") else m.replace(".", "").replace(",", ".")
    elif "," in m:
        # tek virgül: 1–2 ya da 4+ hane ondalık, tam kısmı 0 ise her zaman ondalık ("0,003" akış başı kazanç; önce
        # binlik sanılıp 3 sayılıyordu); "1,234" binlik
        ondalik = re.search(r",\d{1,2}$|,\d{3,}\d$", m) or re.fullmatch(r"-?0,\d+", m)
        m = m.replace(",", ".") if ondalik and m.count(",") == 1 else m.replace(",", "")
    try:
        return float(m), birim
    except ValueError:
        return None, birim


def _adet(metin: str) -> int | None:
    """Dinlenme/indirme adedi tam sayı: '1.234' ve '1,234' binlik ayırıcı; '1200.00' ondalık sıfır."""
    m = re.sub(r"[^\d.,]", "", metin or "")
    m = re.sub(r"[.,]0+$", "", m)
    m = re.sub(r"\D", "", m)
    return int(m) if m else None


def _ay(metin: str) -> str | None:
    """'2026-10', '10/2026', 'Oct 2026', '2026-10-31' → 'YYYY-MM'."""
    m = (metin or "").strip()
    if r := re.search(r"(\d{4})[-/.](\d{1,2})", m):
        return f"{r[1]}-{int(r[2]):02d}"
    if r := re.search(r"(\d{1,2})[-/.](\d{4})", m):
        return f"{r[2]}-{int(r[1]):02d}"
    aylar = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
    if (r := re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", m)) and r[1].lower() in aylar:
        return f"{r[2]}-{aylar.index(r[1].lower()) + 1:02d}"
    return None


def oku_dosya(yol: Path) -> list[dict]:
    """Bir rapor dosyası → satırlar {isrc, upc, parca, magaza, ulke, ay, adet, tutar, para}. Başlık ilk satırda
    olmayabilir (üstte rapor bilgisi): ISRC ya da tutar sütunu bulunan ilk satır başlık sayılır."""
    metin = yol.read_text(encoding="utf-8-sig", errors="replace")
    ayirici = max((",", ";", "\t"), key=lambda a: metin[:4000].count(a))
    satirlar = list(csv.reader(io.StringIO(metin), delimiter=ayirici))
    bulunan = next(((i, sutunlar(b)) for i, b in enumerate(satirlar[:30])
                    if {"tutar"} <= sutunlar(b).keys() and {"isrc", "upc"} & sutunlar(b).keys()), None)
    if bulunan is None:
        ilk = satirlar[0][:8] if satirlar else "—"
        raise ValueError(f"{yol.name}: ISRC/UPC ve kazanç sütunu bulunamadı (ilk satır: {ilk})")
    bas, s = bulunan
    baslik = satirlar[bas]
    sonuc = []
    for r in satirlar[bas + 1:]:
        if not any(x.strip() for x in r):
            continue

        def al(alan: str, r: list[str] = r) -> str:
            return r[s[alan]].strip() if alan in s and s[alan] < len(r) else ""

        tutar, birim = _para(al("tutar"), baslik[s["tutar"]])
        adet = _adet(al("adet"))
        sonuc.append({"isrc": re.sub(r"[^A-Z0-9]", "", al("isrc").upper()) or None,
                      "upc": re.sub(r"\D", "", al("upc")) or None, "parca": al("parca") or None,
                      "magaza": al("magaza") or None, "ulke": al("ulke") or None, "ay": _ay(al("ay")),
                      "adet": adet, "tutar": tutar,
                      "para": (al("para") or birim or None)})
    return sonuc


def sarki_kazanclari(kok: Path, calisma: Path) -> dict:
    """{"sarkilar": {kimlik: {tutar, akis, para}}, "ozet": {...}}. Dosya yoksa boş özet (oda "rapor yok" der)."""
    from yanki import durum, takip

    dosyalar = sorted(p for p in klasor(kok).glob("*.csv")) if klasor(kok).exists() else []
    ozet: dict = {"dosya": len(dosyalar), "toplam": {}, "aylar": [], "eslesmeyen": 0, "hatalar": [], "magazalar": {}}
    sarkilar: dict[str, dict] = {}
    if not dosyalar:
        return {"sarkilar": sarkilar, "ozet": ozet}
    isrc_kimlik, upc_kimlik = {}, {}
    for d in durum.hepsi(calisma):
        y = takip.yukleme_bilgisi(calisma, d.kimlik) or {}
        if y.get("isrc"):
            isrc_kimlik[y["isrc"].upper()] = d.kimlik
        if y.get("upc"):
            upc_kimlik[str(y["upc"]).lstrip("0")] = d.kimlik
    # Aynı satır iki dosyada (aylık rapor + tüm geçmiş) bir kez sayılır; aynı dosyada birebir aynı iki satır ise ayrı
    # kayıtlardır (ör. aynı mağaza/ülke/ayda iki satış türü) ve ikisi de sayılır: satır, bir dosyada görüldüğü en çok
    # adet kadar sayılır (önce dosya içindeki ikinci satır da atılıyordu)
    sayilan: Counter = Counter()
    aylar = set()
    for yol in dosyalar:
        try:
            satirlar = oku_dosya(yol)
        except (OSError, ValueError) as e:
            ozet["hatalar"].append(str(e)[:200])
            continue
        bu_dosya: Counter = Counter()
        for r in satirlar:
            if r["tutar"] is None:
                continue
            anahtar = (r["ay"], r["magaza"], r["ulke"], r["isrc"], r["upc"], r["adet"], r["tutar"])
            bu_dosya[anahtar] += 1
            if bu_dosya[anahtar] <= sayilan[anahtar]:
                continue
            sayilan[anahtar] = bu_dosya[anahtar]
            para = r["para"] or "?"
            ozet["toplam"][para] = ozet["toplam"].get(para, 0) + r["tutar"]
            if r["magaza"]:
                ozet["magazalar"][r["magaza"]] = ozet["magazalar"].get(r["magaza"], 0) + r["tutar"]
            if r["ay"]:
                aylar.add(r["ay"])
                ay = ozet.setdefault("aylik", {}).setdefault(r["ay"], {})
                ay[para] = ay.get(para, 0) + r["tutar"]
            k = isrc_kimlik.get(r["isrc"] or "") or upc_kimlik.get((r["upc"] or "").lstrip("0"))
            if k is None:
                ozet["eslesmeyen"] += 1
                continue
            s = sarkilar.setdefault(k, {"tutar": 0.0, "akis": 0, "para": para})
            s["tutar"] += r["tutar"]
            s["akis"] += r["adet"] or 0
    # yuvarlama en sonda: satır başına kazanç çoğu zaman 0,0001'in altında, toplarken her adımda yuvarlamak küçük
    # satırları sıfırlıyordu (round(0 + 0.00004, 4) == 0)
    ozet["toplam"] = {k: round(v, 4) for k, v in ozet["toplam"].items()}
    ozet["magazalar"] = {k: round(v, 4) for k, v in ozet["magazalar"].items()}
    if "aylik" in ozet:
        ozet["aylik"] = {ay: {k: round(v, 4) for k, v in t.items()} for ay, t in ozet["aylik"].items()}
    for s in sarkilar.values():
        s["tutar"] = round(s["tutar"], 4)
    ozet["aylar"] = sorted(aylar)
    return {"sarkilar": sarkilar, "ozet": ozet}
