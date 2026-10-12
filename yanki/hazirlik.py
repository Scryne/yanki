"""Hazırlık: listedeki şarkı için kaynak ses, sözler, künye; sonra motorla stil/BPM/ton analizi.

Söz ya da kaynak yoksa şarkı `hata` aşamasında durur (neden yazılı). Künye yoksa uyarı: üretim sürer,
paketlemeden önce Scryne'dan istenir.
"""

import json
from dataclasses import asdict
from pathlib import Path

from yanki import ag, durum, kapilar, kaynak, kunye, motor, sozler
from yanki.ayarlar import Ayarlar
from yanki.liste import VOKAL, Sarki

STIL_SONEKI = "clean modern studio recording"


def girdi_hazirla(a: Ayarlar, s: Sarki, calisma: Path, girdi: Path) -> durum.Durum:
    """Ağ işleri (LRCLIB, MusicBrainz, YouTube; dakikalar sürebilir) önce yapılır, sonuç kilit altında taze duruma
    yazılır. Beklenmedik hata (yt-dlp, ffmpeg, bozuk cevap) şarkıyı `hata`ya düşürür; listedeki diğer şarkılar ve
    gece koşusunun geri kalanı sürer."""
    k = durum.klasor(calisma, s.kimlik)
    baslangic = (durum.oku(calisma, s.kimlik) or durum.Durum(s.kimlik, s.sanatci, s.ad)).asama
    alanlar: dict = {}

    def yaz(asama: str, hata: str | None = None) -> durum.Durum:
        with durum.guncelle(calisma, s.kimlik, yoksa=durum.Durum(s.kimlik, s.sanatci, s.ad)) as d:
            for ad, deger in alanlar.items():
                setattr(d, ad, deger)
            if d.asama == baslangic:  # hazırlık sürerken dinleme odasında reddedildiyse aşama korunur
                d.gec(asama, hata)
        return d

    try:
        soz = sozler.bul(s.sanatci, s.ad, girdi / "sozler" / f"{s.kimlik}.txt")
    except Exception as e:  # noqa: BLE001 — Bulunamadi, ağ hatası ya da bozuk cevap: aynı çözüm yolu
        return yaz("hata", f"söz bulunamadı: {e}. `girdi/sozler/{s.kimlik}.txt` olarak bırakılabilir")
    k.mkdir(parents=True, exist_ok=True)
    (k / "soz.txt").write_text(soz.metin, encoding="utf-8")
    # parçalı üretim sözleri parçalara bu damgalarla dağıtır
    (k / "soz_zaman.json").write_text(json.dumps(soz.satirlar, ensure_ascii=False), encoding="utf-8")
    alanlar["soz"] = {"kaynak": soz.kaynak, "sure_sn": soz.sure_sn, "dosya": "soz.txt"}

    try:
        alanlar["kunye"] = asdict(kunye.bul(s.sanatci, s.ad))
    except Exception as e:  # noqa: BLE001 — künye paketlemeden önce elle de tamamlanabilir
        alanlar["kunye"] = {"uyari": f"künye bulunamadı: {e}"}
    if s.yazarlar:  # listedeki elle yazarlar esas (MusicBrainz'de kaydı olmayan şarkı)
        alanlar["kunye"] = kunye.elle_yazarlar(alanlar["kunye"], s.yazarlar)

    try:
        kyn = kaynak.hazirla(s.kimlik, s.sanatci, s.ad, soz.sure_sn, girdi / "kaynak", k, youtube=s.youtube)
    except Exception as e:  # noqa: BLE001 — KaynakYok, yt-dlp DownloadError, ffmpeg hatası
        neden = str(e) if isinstance(e, kaynak.KaynakYok | OSError) else f"{type(e).__name__}: {e}"
        return yaz("hata", f"kaynak ses: {neden}. `girdi/kaynak/{s.kimlik}.mp3` olarak bırakılabilir")
    alanlar["kaynak"] = {"dosya": kyn.wav.name, "nereden": kyn.nereden, "baslik": kyn.baslik, "sure_sn": kyn.sure_sn}
    return yaz("hazir")


def stil_kur(s: Sarki, lm_caption: str | None = None, kunye: dict | None = None,
             yedek_turler: list[str] | None = None) -> str:
    """Scryne'ın stili esastır. Yoksa: (LM tanımı ya da sanatçının ilk iki MusicBrainz türü; MusicBrainz boşsa Deezer
    türleri) + vokal cinsiyeti (liste; yoksa solo sanatçının cinsiyeti, grupta söylenmez) + temiz kayıt soneki."""
    if s.stil:
        return s.stil
    kunye = kunye or {}
    parcalar = []
    if lm_caption:
        parcalar.append(lm_caption.strip().rstrip("."))
    elif turler := list(kunye.get("sanatci_turleri") or [])[:2] or list(yedek_turler or [])[:2]:
        parcalar.append(", ".join(turler) + " song")
    vokal = VOKAL.get(s.vokal or "") or (
        {"Female": "female", "Male": "male"}.get(kunye.get("sanatci_cinsiyeti") or "")
        if kunye.get("sanatci_tipi") == "Person" else None)
    if vokal:
        parcalar.append(f"{vokal} lead vocal")
    parcalar.append(STIL_SONEKI)
    return ", ".join(parcalar)


def analiz_et(a: Ayarlar, sarkilar: list[Sarki], calisma: Path, zaman_asimi_sn: float = 1800) -> None:
    """`hazir` şarkıları tek motor çağrısıyla analiz eder (LM bir kez yüklenir)."""
    hedef = [(s, d) for s in sarkilar if (d := durum.oku(calisma, s.kimlik)) and d.asama == "hazir"]
    if not hedef:
        return
    if a.motor.analiz_yontemi == "musicbrainz":
        for s, d in hedef:
            k = durum.klasor(calisma, s.kimlik)
            dil = dil_bul(d, k)
            if hata := soz_dili_uyumu(d, k, dil["dil"]):
                _hataya(calisma, s.kimlik, hata)
                continue
            # BPM/ton yalnız listeden: yanlış değer modeli detone eder, tahmin göndermek göndermemekten kötü
            _analizi_yaz(calisma, s.kimlik, {
                "stil": stil_kur(s, kunye=d.kunye, yedek_turler=_yedek_turler(s, d)), "bpm": s.bpm,
                "ton": s.ton or "", **dil, "kaynak": "musicbrainz"})
        return
    isler = []
    for s, d in hedef:
        k = durum.klasor(calisma, s.kimlik)
        kesit = _kesit(k / d.kaynak["dosya"], k / "analiz_kesit.wav", a.motor.analiz_kesit_sn)
        isler.append(motor.Is(id=s.kimlik, gorev="anla", kaynak=str(kesit)))
    sonuclar = {r.id: r for r in motor.calistir(a, isler, calisma / "_motor" / "analiz", zaman_asimi_sn,
                                                model=a.motor.analiz_model)}
    for s, d in hedef:
        r = sonuclar[s.kimlik]
        lm = r.analiz if r.basari else {}
        _analizi_yaz(calisma, s.kimlik, {
            "stil": stil_kur(s, lm.get("caption"), d.kunye),
            "bpm": s.bpm or _tam(lm.get("bpm")),
            "ton": s.ton or (lm.get("keyscale") or ""),
            **dil_bul(d, durum.klasor(calisma, s.kimlik)),
            "lm": lm,
            "lm_hata": None if r.basari else r.hata,
        })


INGILIZCE_UYUMSUZ = 0.30  # ses İngilizce dışıyken söz bu kadar İngilizceyse çeviri sürümü gelmiştir


def soz_dili_uyumu(d: durum.Durum, k: Path, dil: str, surumler=None) -> str | None:
    """Ses İngilizce dışı (emin), söz İngilizce ise LRCLIB çeviri sürümünü vermiştir (YOASOBI "Idol": Japonca ses,
    İngilizce sürümün sözü; 2026-10-12). Dili ve süresi tutan zaman damgalı sürüm aranır; bulunursa söz dosyaları
    değişir. Dönen: düzeltilemezse hata metni (yanlış dilde söz söyletilmez)."""
    soz_yolu = k / (d.soz or {}).get("dosya", "soz.txt")
    if dil in ("en", "unknown") or (d.soz or {}).get("kaynak") != "lrclib" or not soz_yolu.exists():
        return None
    oran = kapilar.ingilizce_orani(soz_yolu.read_text(encoding="utf-8"))
    if oran is None or oran < INGILIZCE_UYUMSUZ:
        return None
    sure = (d.kaynak or {}).get("sure_sn")
    try:
        adaylar = (surumler or sozler.lrclib_surumleri)(d.sanatci, d.ad)
    except Exception:  # noqa: BLE001 — arama düşerse hata metni kalır
        adaylar = []
    for alt in adaylar:
        o = kapilar.ingilizce_orani(alt.metin)
        if o is not None and o < INGILIZCE_ESIGI and (sure is None or alt.sure_sn is None
                                                     or abs(alt.sure_sn - sure) <= SURUM_SURE_PAYI_SN):
            soz_yolu.write_text(alt.metin, encoding="utf-8")
            (k / "soz_zaman.json").write_text(json.dumps(alt.satirlar, ensure_ascii=False), encoding="utf-8")
            return None
    return (f"söz İngilizce (pay {oran:.2f}) ama ses {dil}: LRCLIB çeviri sürümünü vermiş, dili tutan sürüm yok; "
            f"doğru söz `girdi/sozler/{d.kimlik}.txt` olarak bırakılabilir")


SURUM_SURE_PAYI_SN = 5.0


def _hataya(calisma: Path, kimlik: str, hata: str) -> None:
    with durum.guncelle(calisma, kimlik) as d:
        if d.asama == "hazir":
            d.gec("hata", hata)


def _analizi_yaz(calisma: Path, kimlik: str, analiz: dict) -> None:
    with durum.guncelle(calisma, kimlik) as d:
        if d.asama == "hazir":  # analiz sürerken reddedildiyse dokunma
            d.analiz = analiz
            d.gec("analiz")


DIL_ESIGI = 0.5
INGILIZCE_ESIGI = 0.15  # İngilizce şarkı sözünde sık kelimelerin payı ~0,3–0,5; başka dilde ~0


def _yedek_turler(s: Sarki, d: durum.Durum) -> list[str]:
    if s.stil or (d.kunye or {}).get("sanatci_turleri"):
        return []
    from yanki import katalog

    try:
        return katalog.sanatci_turleri(s.sanatci)
    except (OSError, ag.Bulunamadi, katalog.DeezerHatasi):
        return []


def dil_bul(d: durum.Durum, k: Path, tespit=None) -> dict:
    """Söz dili kaynak sesten (keşif global: Fransızca, Türkçe… şarkılar geliyor; önce hep "en" yazılıyordu).
    Whisper emin değilse ya da ses okunamazsa "en" (hattın kalibre olduğu dil) ve neden kayıtlı."""
    tespit = tespit or kapilar.dil_tespit
    try:
        dil, olasilik = tespit(k / d.kaynak["dosya"])
    except Exception as e:  # noqa: BLE001 — dil tespiti üretimi durdurmaz
        return {"dil": "en", "dil_tespit": f"başarısız: {e}"}
    if olasilik < DIL_ESIGI:
        # Ses emin değilse söz metni karar verir: İngilizce değilse sesin en olası dili. Nyoy Volante (Tagalogca, ses
        # "tl 0,25") "en" sayılmış, model Tagalog sözü İngilizce diye söylemiş, İngilizce Whisper'la ölçülen söz WER'i
        # üç adayda da ~1,0 çıkmıştı (2026-10-11).
        soz = k / (d.soz or {}).get("dosya", "soz.txt")
        oran = kapilar.ingilizce_orani(soz.read_text(encoding="utf-8")) if soz.exists() else None
        if oran is not None and oran < INGILIZCE_ESIGI and dil not in ("en", "unknown"):
            return {"dil": dil, "dil_tespit": f"ses belirsiz ({dil} {olasilik:.2f}), söz İngilizce değil ({oran:.2f})"}
        return {"dil": "en", "dil_tespit": f"belirsiz ({dil} {olasilik:.2f})"}
    return {"dil": dil, "dil_tespit": f"{dil} {olasilik:.2f}"}


def _kesit(kaynak: Path, hedef: Path, sure_sn: float) -> Path:
    """Şarkının ~%40'ından başlayan kesit (çoğu şarkıda nakarat bölgesi; giriş sessizliği değil)."""
    import soundfile as sf

    bilgi = sf.info(str(kaynak))
    bas = max(0.0, min(bilgi.duration * 0.4, bilgi.duration - sure_sn))
    ses, sr = sf.read(str(kaynak), dtype="float32", always_2d=True, start=int(bas * bilgi.samplerate),
                      stop=int(min(bilgi.duration, bas + sure_sn) * bilgi.samplerate))
    sf.write(str(hedef), ses, sr)
    return hedef


def _tam(x) -> int | None:
    try:
        return round(float(x)) if x not in (None, "", "N/A") else None
    except (TypeError, ValueError):
        return None
