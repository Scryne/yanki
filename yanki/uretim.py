"""Üretim: `analiz` şarkılarına cover adayları, bekleyen bölge onarımlarına repaint; ardından kapılar.

Parçalı üretim (yanki/parcalama.py): uzun şarkı vokal boşluklarından ~90 sn'lik parçalara bölünür. İki tur:
  1. tur: her adayın ilk parçası + bütün onarımlar
  2. tur: kalan parçalar, ilk parçanın çıktısı tını referansı olarak (ses parçadan parçaya değişmesin)
Sonra parçalar dikilir, kapılar tam şarkı üzerinde çalışır.

Onarım pencerelidir: işaretli aralığın ±PENCERE_PAYI sn'lik penceresi kesilir, repaint yalnız orada yapılır, pencere
şarkıya geri dikilir. Tam şarkıda repaint de tüm şarkıyı işler (290 sn'de ~57 dk, ACE-Step zaman aşımı).
Scryne iyi sürümü kabul eder → adayın dosyası o sürüm olur (dinleme testi 4: bir tohum düzeltti, öbürü düzeltmedi).

Stil değişince (dinleme sayfası) şarkı yeniden `analiz`e döner; yeni adaylar mevcutların ardından numaralanır, eskiler
dinlenebilir ve onaylanabilir kalır.

Betim (`betimle=True`, kiralık GPU'da): stili Scryne yazmamış ve betimi olmayan şarkıya aynı işçide önce "betimle"
işi gider (ACE-Step captioner şarkıyı dinler), adaylar o betimden kurulan stille üretilir; betim ve stil şarkının
analizine yazılır (sonraki üretimler aynı stili kullanır). Betim düşerse adaylar eski stille üretilir.
"""

import dataclasses
import json
import re
import subprocess
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import numpy as np
import soundfile as sf

from yanki import ag, durum, kapilar, liste, motor, parcalama, runpod, sozler
from yanki.ayarlar import Ayarlar
from yanki.motor_isci import betim_stili

SR = 48000
TEK_PARCA_SN = 110  # bundan kısa şarkı bölünmez
PENCERE_PAYI = 25.0
# 90–110 sn'lik parça XL INT8 100 adımda ~2,5–3 dk (Faz 2 ölçümü); iş başına cömert pay
ZAMAN_ASIMI_SN_IS_BASI = 15 * 60


def _soz(calisma: Path, d: durum.Durum) -> str:
    return (durum.klasor(calisma, d.kimlik) / d.soz["dosya"]).read_text(encoding="utf-8")


def _satirlar(calisma: Path, d: durum.Durum, lrclib: Callable | None = None) -> list[tuple[float, str]]:
    """Zaman damgalı söz satırları. Dosya yoksa (eski hazırlık) ve sözler LRCLIB'denyse bir kez çekip kaydeder."""
    yol = durum.klasor(calisma, d.kimlik) / "soz_zaman.json"
    if not yol.exists() and d.soz.get("kaynak") == "lrclib":
        try:
            satirlar = (lrclib or sozler.lrclib)(d.sanatci, d.ad).satirlar
            yol.write_text(json.dumps(satirlar, ensure_ascii=False), encoding="utf-8")
        except (ag.Bulunamadi, OSError, ValueError):
            pass
    return [tuple(x) for x in json.loads(yol.read_text(encoding="utf-8"))] if yol.exists() else []


def _ortak(d: durum.Durum) -> dict:
    return dict(stil=d.analiz["stil"], dil=d.analiz.get("dil", "en"), bpm=d.analiz.get("bpm"),
                ton=d.analiz.get("ton") or "")


def parca_plani(calisma: Path, d: durum.Durum, lrclib: Callable | None = None, tek_parca_sn: float = TEK_PARCA_SN
                ) -> tuple[list[parcalama.Parca], list[str]]:
    """Parçalar ve her parçanın sözü. Kısa şarkı ya da zaman damgası yoksa tek parça, tüm söz (sözü yanlış parçaya
    koymaktansa yavaş yol; uzun şarkıda bu durum durum.json'a uyarı olarak yazılır)."""
    sure = d.kaynak["sure_sn"]
    satirlar = _satirlar(calisma, d, lrclib) if sure > tek_parca_sn else []
    if sure <= tek_parca_sn or not satirlar:
        if sure > tek_parca_sn:
            d.notlar.append({"uyari": f"söz zaman damgası yok: {sure:.0f} sn tek parça üretildi (yavaş yol)"})
        return [parcalama.Parca(1, 0.0, sure, 0.0, sure)], [_soz(calisma, d)]
    plan = parcalama.plan(sure, [t for t, _ in satirlar])
    return plan, parcalama.soz_dagit(plan, satirlar, sure, d.ad)


def _kes(kaynak: Path, bas: float, son: float, hedef: Path) -> Path:
    bilgi = sf.info(str(kaynak))
    ses, sr = sf.read(str(kaynak), dtype="float32", always_2d=True,
                      start=int(bas * bilgi.samplerate), stop=int(son * bilgi.samplerate))
    hedef.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(hedef), ses, sr)
    return hedef


def onarim_iste(a: Ayarlar, d: durum.Durum, aday_no: int, bas: float, son: float) -> None:
    if not 0 <= bas < son:
        raise ValueError(f"geçersiz aralık: {bas}–{son}")
    aday = next(x for x in d.adaylar if x.no == aday_no)
    sira = len(aday.onarimlar)
    for i, tohum in enumerate(a.onarim.tohumlar):
        aday.onarimlar.append({"id": f"{aday_no}-{sira + i + 1}", "bolge": [bas, son], "tohum": tohum,
                               "temel": aday.dosya, "durum": "bekliyor", "dosya": None, "kapilar": {}, "hata": None})
    d.gec("onarim")


def _yeniden_uretilebilir(d: durum.Durum, asamalar: tuple[str, ...]) -> None:
    if d.asama not in asamalar or not d.analiz.get("stil"):
        raise ValueError(f"bu aşamada yeniden üretilemez: {d.asama}")
    if any(o["durum"] == "bekliyor" for a in d.adaylar for o in a.onarimlar):
        raise ValueError("bekleyen onarım var; önce üretilmesini bekle")


def yeniden_uretime_al(d: durum.Durum) -> None:
    """Hat iyileşince (ör. temiz söz, aday sayısı) onaylı şarkıya da yeni adaylar: mevcut adaylar, seçim ve paket
    yerinde kalır; yeni adaylar ardından eklenir, Scryne hangisini yükleyeceğini yeniden seçer. Yüklenmiş şarkı geri
    alınmaz."""
    _yeniden_uretilebilir(d, ("uretildi", "hata", "onaylandi", "paketlendi"))
    d.notlar.append({"yeniden_uretim": {"onceki_asama": d.asama, "onceki_secilen": d.secilen}})
    d.secilen = None
    d.gec("analiz")


def stil_degistir(d: durum.Durum, stil: str, bpm: int | None, ton: str) -> None:
    """Yeni stil tanımıyla yeniden üretim ister; eski tanım notlara yazılır (hangi stilin işe yaradığı izlensin)."""
    _yeniden_uretilebilir(d, ("uretildi", "hata"))
    stil = " ".join(stil.split())
    if not stil:
        raise ValueError("stil boş olamaz")
    eski = {k: d.analiz.get(k) for k in ("stil", "bpm", "ton")}
    d.notlar.append({"stil_degisti": {"eski": eski, "yeni": {"stil": stil, "bpm": bpm, "ton": ton}}})
    d.analiz.update(stil=stil, bpm=bpm, ton=ton, stil_kaynak="elle")
    d.gec("analiz")


def onarim_kabul(d: durum.Durum, aday_no: int, onarim_id: str) -> None:
    aday = next(x for x in d.adaylar if x.no == aday_no)
    secilen = next(o for o in aday.onarimlar if o["id"] == onarim_id)
    if secilen["durum"] != "hazir":
        raise ValueError(f"onarım {onarim_id} kabul edilemez: {secilen['durum']}")
    if secilen.get("temel") and secilen["temel"] != aday.dosya:
        # aynı turda iki aralık işaretlendiyse ikisi de eski dosyaya dikildi: ikincisini kabul etmek ilkinin
        # düzeltmesini sessizce geri alırdı
        raise ValueError("bu onarım adayın önceki haline dikildi, arada başka bir onarım kabul edildi; aralığı "
                         "yeniden işaretle (yeni onarım güncel dosyaya dikilir)")
    for o in aday.onarimlar:
        if o["bolge"] == secilen["bolge"] and o["temel"] == secilen["temel"] and o["durum"] == "hazir":
            o["durum"] = "ret"
    secilen["durum"] = "kabul"
    aday.dosya = secilen["dosya"]
    aday.kapilar, aday.gecti = secilen["kapilar"], kapilar.hepsi_gecti(secilen["kapilar"])


def _goreli(k: Path, yol: Path | str) -> str:
    return Path(yol).resolve().relative_to(k.resolve()).as_posix()


def _dik_pencere(temel: Path, pencere: Path, bas: float, hedef: Path, gecis_sn: float = 0.5) -> Path:
    """Onarılmış pencereyi temel dosyaya geri koyar; kenarlarda kısa eşit güçlü geçiş."""
    t, sr = sf.read(str(temel), dtype="float32", always_2d=True)
    p, _ = sf.read(str(pencere), dtype="float32", always_2d=True)
    i = int(round(bas * sr))
    p = p[: max(0, len(t) - i)]
    n = min(int(gecis_sn * sr), len(p) // 4)
    kazanc = np.ones(len(p), dtype=np.float32)
    if n:
        kazanc[:n] = np.sin(np.linspace(0, np.pi / 2, n))
        kazanc[-n:] = np.cos(np.linspace(0, np.pi / 2, n))
    cikti = t.copy()
    cikti[i: i + len(p)] = t[i: i + len(p)] * (1 - kazanc[:, None] ** 2) ** 0.5 + p * kazanc[:, None]
    hedef.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(hedef), cikti, sr)
    return hedef


def _cover_isleri(a: Ayarlar, calisma: Path, d: durum.Durum, tek_parca_sn: float = TEK_PARCA_SN
                  ) -> tuple[tuple, list[motor.Is]]:
    """Cover adaylarının planı ve ilk tur işleri (her adayın ilk parçası)."""
    k = durum.klasor(calisma, d.kimlik)
    plan, sozler_ = parca_plani(calisma, d, tek_parca_sn=tek_parca_sn)
    # stil değişikliğinden sonra yeni adaylar eskilerin ardından (geçmiş adaylar dinlenebilir kalır)
    ilk_no = max((x.no for x in d.adaylar if x.dosya), default=0)
    numaralar = [(ilk_no + n, a.cover.tohumlar[n - 1]) for n in range(1, a.cover.aday_sayisi + 1)]
    kaynak = k / d.kaynak["dosya"]
    if len(plan) > 1:
        for p in plan:
            _kes(kaynak, p.bas, p.son, k / "parcalar" / f"kaynak_{p.no}.wav")
    ilk = k / "parcalar" / "kaynak_1.wav" if len(plan) > 1 else kaynak
    isler = [motor.Is(id=f"{d.kimlik}|cover|{n}|1", gorev="cover", kaynak=str(ilk),
                      cikti_klasor=str(k / "adaylar" / str(n) / "p1"), soz=sozler_[0],
                      adim=a.cover.adim, tohum=tohum, guc=a.cover.guc,
                      referans=str(ilk) if a.cover.referans else None, ek=dict(a.cover.ek), **_ortak(d))
             for n, tohum in numaralar]
    return (plan, sozler_, numaralar), isler


def _onarim_isleri(a: Ayarlar, calisma: Path, d: durum.Durum, pencere_bas: dict[str, float]) -> list[motor.Is]:
    """Bekleyen onarımların işleri: işaretli aralığın ±PENCERE_PAYI penceresi kesilir, repaint yalnız orada."""
    k = durum.klasor(calisma, d.kimlik)
    satirlar = _satirlar(calisma, d)
    isler = []
    for aday in d.adaylar:
        for o in aday.onarimlar:
            if o["durum"] != "bekliyor":
                continue
            temel = k / o["temel"]
            sure = sf.info(str(temel)).duration
            bas, son = o["bolge"]
            pb, ps = max(0.0, bas - PENCERE_PAYI), min(sure, son + PENCERE_PAYI)
            pencere = _kes(temel, pb, ps, k / "onarimlar" / o["id"] / "pencere_temel.wav")
            soz = sozler.aralik_sozu(satirlar, pb, ps, d.kaynak.get("sure_sn"), d.ad) or _soz(calisma, d)
            pencere_bas[o["id"]] = pb
            isler.append(motor.Is(
                id=f"{d.kimlik}|onarim|{aday.no}|{o['id']}", gorev="repaint", kaynak=str(pencere),
                cikti_klasor=str(k / "onarimlar" / o["id"]), soz=soz, adim=a.onarim.adim, tohum=o["tohum"],
                bolge=(max(0.0, bas - a.onarim.pay_sn - pb), min(ps - pb, son + a.onarim.pay_sn - pb)),
                **_ortak(d)))
    return isler


def _kapilardan_gecir(degerlendir: Callable[..., dict], tam: Path, kaynak: Path, soz: str, dil: str,
                      orijinal_wer: float | None = None) -> dict:
    """Kapı ölçümü düşerse (Whisper, fpcalc, ffmpeg) aday düşmüş sayılır; saatlik koşunun geri kalanı sürer."""
    try:
        return degerlendir(tam, kaynak, soz, dil, orijinal_wer)
    except Exception as e:  # noqa: BLE001
        return {"degerlendirme": {"gecti": False, "hata": f"{type(e).__name__}: {e}"}}


def _aday_kur(k: Path, d: durum.Durum, plan, n: int, tohum: int, sonuclar: dict, degerlendir, kaynak: Path,
              soz: str, dil: str, orijinal_wer: float | None = None, tarif: dict | None = None) -> durum.Aday:
    rs = [sonuclar.get(f"{d.kimlik}|cover|{n}|{p.no}") for p in plan]
    aday = durum.Aday(n, "", tohum, stil=d.analiz["stil"])
    if tarif is not None:
        olcek = rs[0].lora_olcek if rs[0] else None
        aday.tarif = {**tarif, "lora": tarif.get("lora") if olcek else None, "lora_olcek": olcek,
                      "stil_kaynak": d.analiz.get("stil_kaynak")}
    hatali = [f"parça {p.no}: {r.hata if r else 'üretilmedi'}" for p, r in zip(plan, rs, strict=True)
              if not (r and r.basari)]
    if hatali:
        aday.kapilar = {"motor": {"gecti": False, "hata": "; ".join(hatali)}}
        return aday
    aday.hizalama = [r.hizalama for r in rs] if any(r.hizalama for r in rs) else None
    tam = k / "adaylar" / str(n) / "tam.flac"
    try:
        if len(plan) == 1:
            ses, sr = sf.read(rs[0].cikti, dtype="float32", always_2d=True)
        else:
            sesler = [sf.read(r.cikti, dtype="float32", always_2d=True)[0] for r in rs]
            ses, sr = parcalama.birlestir(sesler, plan, SR), SR
        sf.write(str(tam), ses, sr)
    except Exception as e:  # noqa: BLE001 — bozuk motor çıktısı tek adayı düşürür
        aday.kapilar = {"birlestirme": {"gecti": False, "hata": f"{type(e).__name__}: {e}"}}
        return aday
    aday.dosya = _goreli(k, tam)
    aday.kapilar = _kapilardan_gecir(degerlendir, tam, kaynak, soz, dil, orijinal_wer)
    aday.gecti = kapilar.hepsi_gecti(aday.kapilar)
    return aday


def _onarim_sonucu(k: Path, o: dict, r: motor.Sonuc, pencere_bas: float, degerlendir, kaynak: Path, soz: str,
                   dil: str, orijinal_wer: float | None = None) -> dict:
    if not r.basari:
        return {"durum": "hata", "hata": r.hata}
    try:
        tam = _dik_pencere(k / o["temel"], Path(r.cikti), pencere_bas, k / "onarimlar" / o["id"] / "tam.flac")
    except Exception as e:  # noqa: BLE001
        return {"durum": "hata", "hata": f"dikiş: {type(e).__name__}: {e}"}
    return {"durum": "hazir", "dosya": _goreli(k, tam),
            "kapilar": _kapilardan_gecir(degerlendir, tam, kaynak, soz, dil, orijinal_wer)}


def _sonuclari_isle(calisma: Path, baslangic: str, yeni_adaylar: list[durum.Aday], onarimlar: dict[str, dict],
                    kimlik: str, notlar: list | None = None, analiz: dict | None = None) -> durum.Durum:
    """Üretim sonuçlarını diskteki taze duruma işler (kilit altında, birkaç milisaniye). Üretim sürerken Scryne
    dinleme odasında karar verdiyse (ret, başka adaya onay) onun aşaması korunur; yeni onarım istediyse şarkı
    `onarim`da kalır, sonraki koşu onları üretir."""
    with durum.guncelle(calisma, kimlik) as d:
        d.notlar += notlar or []
        d.analiz.update(analiz or {})  # betimden gelen stil (sonraki üretimler de kullanır)
        for aday in yeni_adaylar:
            d.adaylar = [x for x in d.adaylar if x.no != aday.no] + [aday]
        for x in d.adaylar:
            for o in x.onarimlar:
                if o["durum"] == "bekliyor" and o["id"] in onarimlar:
                    o.update(onarimlar[o["id"]])
        d.adaylar.sort(key=lambda x: x.no)
        if d.asama != baslangic:
            d.notlar.append({"uretim": f"sonuçlar eklendi; aşama {d.asama} kaldı (üretim sürerken değişti)"})
        elif any(o["durum"] == "bekliyor" for x in d.adaylar for o in x.onarimlar):
            d.gec("onarim")
        elif any(x.gecti for x in d.adaylar):
            d.gec("uretildi")
        elif baslangic == "analiz" and yeni_adaylar and _yalniz_motor_dustu(yeni_adaylar) and (
                sum("motor_tekrar" in n for n in d.notlar) < MOTOR_TEKRAR):
            # işçi çöktü / zaman aşımı (geçici): aynı tohumlarla sonraki koşuda yeniden; kapıdan düşen aday
            # aynı tohumla yine düşeceği için o durum `hata`da Scryne'ı bekler
            d.notlar.append({"motor_tekrar": "; ".join(x.kapilar["motor"].get("hata") or "" for x in yeni_adaylar)})
            d.gec("analiz")
        else:
            nedenler = "; ".join(f"aday {x.no}: " + ", ".join(n for n, v in x.kapilar.items() if not v.get("gecti"))
                                 for x in d.adaylar)
            d.gec("hata", f"hiçbir aday kapıdan geçmedi ({nedenler}); yeniden denemek için stili değiştir ya da "
                          f"`yanki yeniden {kimlik}`")
    return d


MOTOR_TEKRAR = 2  # yalnız motor hatasıyla düşen üretim kaç kez kendiliğinden yeniden denensin


def _yalniz_motor_dustu(adaylar: list[durum.Aday]) -> bool:
    return all(set(x.kapilar) == {"motor"} for x in adaylar)


def lora_adi(yol: Path | None) -> str | None:
    """Eğitimin adı (calisma/egitim/lora/<zaman>/final → <zaman>; ara kayıt …/<zaman>/checkpoints/epoch_20_… →
    <zaman>/ep20): adayın tarifinde hangi LoRA."""
    if yol is None:
        return None
    if yol.parent.name == "checkpoints" and (m := re.match(r"epoch_(\d+)_", yol.name)):
        return f"{yol.parent.parent.name}/ep{m.group(1)}"
    return yol.parent.name if yol.name == "final" else yol.name


def betim_gerekli(d: durum.Durum, elle_stil: set[str]) -> bool:
    """Betimi yok ve stilini Scryne yazmamış (listede `stil`, dinleme odasında stil değişikliği)."""
    return (not d.analiz.get("betim") and d.analiz.get("stil_kaynak") != "elle" and d.kimlik not in elle_stil)


def _elle_stil(kok: Path) -> set[str]:
    try:
        return {s.kimlik for s in liste.yukle(kok / "girdi" / "liste.toml") if s.stil}
    except (OSError, ValueError):
        return set()


def egitimde(kok: Path) -> set[str]:
    """Eğitim verisindeki şarkıların kimlikleri: cover'ı üretilmez (`egitim.veri`)."""
    from yanki import egitim

    return {s.kimlik for s in egitim.veri(kok)}


def tur_disi(d: durum.Durum) -> str | None:
    """Şarkının stili keşfin dışladığı türdense (`config/kesif.toml` → `haric_turler`: kör testlerde en iyi aday bile
    yayınlanamaz bulunan caz, blues, reggae, rap, drill, grunge, folk…) o tür. Stili Scryne yazdıysa (elle) üretilir."""
    from yanki import kesif

    if d.analiz.get("stil_kaynak") == "elle" or not (kalip := kesif.haric_kalip()):
        return None
    m = kalip.search(d.analiz.get("stil") or "")
    return m.group(0) if m else None


def uretilecek(a: Ayarlar, calisma: Path) -> list[durum.Durum]:
    """Üretim sırası: analiz ve onarım bekleyenler; eğitim verisindeki şarkılar ve hattın iyi yapmadığı türler hariç
    (Scryne, 2026-10-15: "müzik üretiminin en iyi olduğu türlerde üretsin"; keşif bu türleri süzüyordu ama listeye
    önceden girenler üretiliyordu)."""
    haric = egitimde(a.kok)
    return [d for d in durum.hepsi(calisma) if d.asama == "onarim" or (
        d.asama == "analiz" and d.kimlik not in haric and not tur_disi(d))]


def uret(a: Ayarlar, calisma: Path, kimlikler: list[str] | None = None,
         calistir: Callable[..., list[motor.Sonuc]] = motor.calistir,
         degerlendir: Callable[..., dict] | None = None, tek_parca_sn: float = TEK_PARCA_SN,
         betimle: bool = False, orijinal_wer: Callable[..., float | None] | None = None) -> list[durum.Durum]:
    """`tek_parca_sn`: bundan kısa şarkı tek parça üretilir (evde 110 sn; kiralık GPU'da 480, `uzak.motor_sec`).
    `betimle`: betimi olmayan şarkının stili önce dinlenip betimden kurulur (yalnız kiralık GPU'da)."""
    degerlendir = degerlendir or (lambda aday, kaynak, soz, dil="en", orijinal_wer=None:
                                  kapilar.degerlendir(aday, kaynak, soz, a.fpcalc, dil=dil, orijinal_wer=orijinal_wer))
    orijinal_wer = orijinal_wer or kapilar.orijinal_wer
    hedef = [d for d in uretilecek(a, calisma) if kimlikler is None or d.kimlik in kimlikler]
    if not hedef:
        return []
    from yanki import ayarlar

    ayarlar.lora_denetle(a)  # bağdaştırıcısız üretim sessizce başka tarif olurdu

    def motor_turu(isler: list[motor.Is], ad: str) -> dict[str, motor.Sonuc]:
        if not isler:
            return {}
        return {r.id: r for r in calistir(a, isler, calisma / "_motor" / ad, ZAMAN_ASIMI_SN_IS_BASI * len(isler))}

    planlar, tur1, pencere_bas, islenen, notlar = {}, [], {}, [], {}
    tarif = {"model": a.motor.model, "lora": lora_adi(a.motor.lora), "ek": dict(a.cover.ek),
             "tarih": datetime.now().isoformat(timespec="minutes")}  # ek: CFG vb. (Sanatçı görünümü eski tarifi ayırır)
    elle_stil = _elle_stil(a.kok) if betimle else set()
    for d in hedef:
        n0 = len(d.notlar)
        try:  # bir şarkının hazırlığı (eksik dosya, bozuk söz zamanı) diğerlerini durdurmaz
            if d.asama == "analiz":
                planlar[d.kimlik], isler = _cover_isleri(a, calisma, d, tek_parca_sn)
                if betimle and betim_gerekli(d, elle_stil):
                    betim = f"{d.kimlik}|betim"
                    kaynak = durum.klasor(calisma, d.kimlik) / d.kaynak["dosya"]
                    isler = [motor.Is(id=betim, gorev="betimle", kaynak=str(kaynak)),
                             *(dataclasses.replace(i, stil_betimden=betim) for i in isler)]
            else:
                isler = _onarim_isleri(a, calisma, d, pencere_bas)
        except Exception as e:  # noqa: BLE001
            planlar.pop(d.kimlik, None)
            with durum.guncelle(calisma, d.kimlik) as taze:
                if taze.asama == d.asama:
                    taze.gec("hata", f"üretim hazırlığı: {type(e).__name__}: {e}")
            islenen.append(taze)
            continue
        tur1 += isler
        notlar[d.kimlik] = d.notlar[n0:]  # planlamanın uyarıları (ör. söz zaman damgası yok)
        islenen.append(d)
    s1 = motor_turu(tur1, "tur1")
    analizler: dict[str, dict] = {}
    for d in islenen:
        r = s1.get(f"{d.kimlik}|betim")
        if r is None:
            continue
        if r.basari and (betim := (r.analiz or {}).get("betim")):
            analizler[d.kimlik] = {"betim": betim, "stil": betim_stili(betim), "stil_kaynak": "betim"}
            notlar.setdefault(d.kimlik, []).append({"stil_betimden": {"eski": d.analiz.get("stil"),
                                                                      "yeni": analizler[d.kimlik]["stil"]}})
            d.analiz.update(analizler[d.kimlik])  # ikinci tur ve adayların kaydı yeni stille
        else:
            notlar.setdefault(d.kimlik, []).append({"uyari": f"betim alınamadı ({r.hata}); eski stille üretildi"})

    tur2 = []
    for d in islenen:
        if d.kimlik not in planlar:
            continue
        k = durum.klasor(calisma, d.kimlik)
        plan, sozler_, numaralar = planlar[d.kimlik]
        for n, tohum in numaralar:
            ilk = s1.get(f"{d.kimlik}|cover|{n}|1")
            if not (ilk and ilk.basari):
                continue
            for p in plan[1:]:
                tur2.append(motor.Is(id=f"{d.kimlik}|cover|{n}|{p.no}", gorev="cover",
                                     kaynak=str(k / "parcalar" / f"kaynak_{p.no}.wav"),
                                     cikti_klasor=str(k / "adaylar" / str(n) / f"p{p.no}"), soz=sozler_[p.no - 1],
                                     adim=a.cover.adim, tohum=tohum, guc=a.cover.guc,
                                     referans=ilk.cikti, ek=dict(a.cover.ek), **_ortak(d)))
    try:
        s2 = motor_turu(tur2, "tur2")
    except (runpod.RunPodHatasi, OSError, subprocess.SubprocessError) as e:
        # ikinci turun sunucusu açılamadı (stok, ağ): ilk turun ödenmiş tek parça şarkıları kaybolmasın, yalnız
        # parçalı şarkıların kalan parçaları başarısız sayılır (motor tekrarı yolundan yeniden üretilir)
        print(f"ikinci tur ({len(tur2)} iş) yapılamadı: {type(e).__name__}: {e}")
        s2 = {i.id: motor.Sonuc(i.id, False, f"ikinci tur yapılamadı: {e}") for i in tur2}
    sonuclar = {**s1, **s2}

    sonuc = []
    for d in islenen:
        if d.asama not in ("analiz", "onarim"):  # hazırlıkta hataya düştü
            sonuc.append(d)
            continue
        k = durum.klasor(calisma, d.kimlik)
        kaynak, soz, dil = k / d.kaynak["dosya"], _soz(calisma, d), d.analiz.get("dil", "en")
        # göreli söz kapısı: orijinal kaydın söz WER'i şarkı başı bir kez ölçülür, analize yazılır
        if "orijinal_wer" not in d.analiz:
            analizler.setdefault(d.kimlik, {})["orijinal_wer"] = d.analiz["orijinal_wer"] = orijinal_wer(
                kaynak, soz, dil)
        owr = d.analiz.get("orijinal_wer")
        yeni_adaylar, onarimlar = [], {}
        if d.kimlik in planlar:
            plan, _, numaralar = planlar[d.kimlik]
            yeni_adaylar = [_aday_kur(k, d, plan, n, tohum, sonuclar, degerlendir, kaynak, soz, dil, owr, tarif)
                            for n, tohum in numaralar]
        else:
            for aday in d.adaylar:
                for o in aday.onarimlar:
                    r = sonuclar.get(f"{d.kimlik}|onarim|{aday.no}|{o['id']}")
                    if o["durum"] == "bekliyor" and r is not None:
                        onarimlar[o["id"]] = _onarim_sonucu(k, o, r, pencere_bas[o["id"]], degerlendir, kaynak, soz,
                                                            dil, owr)
        sonuc.append(_sonuclari_isle(calisma, d.asama, yeni_adaylar, onarimlar, d.kimlik, notlar.get(d.kimlik),
                                     analizler.get(d.kimlik)))
    return sonuc


ARSIV_KLASORLER = ("adaylar", "onarimlar", "parcalar", "paket", "paket_onceki")
BASTAN_ASAMALAR = ("analiz", "uretildi", "onarim", "onaylandi", "paketlendi", "hata")


def bastan(calisma: Path, kimlik: str, neden: str, arsiv: Path | None = None) -> durum.Durum:
    """Şarkıyı baştan üretime alır (Scryne, 2026-10-10: "makinede tam sürümüyle üreticez, 0'dan başlayalım"): adaylar,
    onarımlar, parçalar ve paket `calisma/_arsiv/<tarih>/<kimlik>/`'e taşınır, seçim silinir, aşama `analiz`. Kaynak
    ses, sözler, künye, stil ve kapak kalır (donanımdan bağımsız). Paketteki dağıtım geçmişi arşivde kalır. Analizi
    olmayan (hazırlıkta düşmüş) ya da yüklenmiş şarkı alınmaz: önce hazırlık / geri çekme."""
    import shutil
    from datetime import date

    k = durum.klasor(calisma, kimlik)
    arsiv = arsiv or calisma / "_arsiv" / date.today().isoformat() / kimlik
    with durum.guncelle(calisma, kimlik) as d:
        if d.asama not in BASTAN_ASAMALAR or not d.analiz.get("stil"):
            raise ValueError(f"baştan alınamaz (aşama {d.asama}" + ("" if d.analiz.get("stil") else ", analiz yok")
                             + ")")
        tasinan = []
        for ad in ARSIV_KLASORLER:
            if (k / ad).exists():
                hedef = arsiv / ad
                if hedef.exists():  # aynı gün ikinci kez: öncekinin yanına
                    hedef = arsiv / f"{ad}_{len(list(arsiv.glob(ad + '*')))}"
                hedef.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(k / ad), str(hedef))
                tasinan.append(ad)
        d.notlar.append({"bastan": {"neden": neden, "onceki_asama": d.asama, "onceki_secilen": d.secilen,
                                    "aday": len(d.adaylar), "arsiv": str(arsiv), "tasinan": tasinan}})
        d.adaylar, d.secilen, d.yayin = [], None, {}
        d.gec("analiz")
    return d
