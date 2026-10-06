"""Hazırlık: listedeki şarkı için kaynak ses, sözler, künye; sonra motorla stil/BPM/ton analizi.

Söz ya da kaynak yoksa şarkı `hata` aşamasında durur (neden yazılı). Künye yoksa uyarı: üretim sürer,
paketlemeden önce Scryne'dan istenir.
"""

import json
from dataclasses import asdict
from pathlib import Path

from yanki import ag, durum, kaynak, kunye, motor, sozler
from yanki.ayarlar import Ayarlar
from yanki.liste import VOKAL, Sarki

STIL_SONEKI = "clean modern studio recording"


def girdi_hazirla(a: Ayarlar, s: Sarki, calisma: Path, girdi: Path) -> durum.Durum:
    d = durum.oku(calisma, s.kimlik) or durum.Durum(s.kimlik, s.sanatci, s.ad)
    k = durum.klasor(calisma, s.kimlik)
    try:
        soz = sozler.bul(s.sanatci, s.ad, girdi / "sozler" / f"{s.kimlik}.txt")
    except (ag.Bulunamadi, OSError) as e:
        d.gec("hata", f"söz bulunamadı: {e}. `girdi/sozler/{s.kimlik}.txt` olarak bırakılabilir")
        durum.yaz(calisma, d)
        return d
    (k / "soz.txt").parent.mkdir(parents=True, exist_ok=True)
    (k / "soz.txt").write_text(soz.metin, encoding="utf-8")
    # parçalı üretim sözleri parçalara bu damgalarla dağıtır
    (k / "soz_zaman.json").write_text(json.dumps(soz.satirlar, ensure_ascii=False), encoding="utf-8")
    d.soz = {"kaynak": soz.kaynak, "sure_sn": soz.sure_sn, "dosya": "soz.txt"}

    try:
        kn = kunye.bul(s.sanatci, s.ad)
        d.kunye = asdict(kn)
    except (ag.Bulunamadi, OSError) as e:
        d.kunye = {"uyari": f"künye bulunamadı: {e}"}

    try:
        kyn = kaynak.hazirla(s.kimlik, s.sanatci, s.ad, soz.sure_sn, girdi / "kaynak", k, youtube=s.youtube)
    except (kaynak.KaynakYok, OSError) as e:
        d.gec("hata", f"kaynak ses: {e}. `girdi/kaynak/{s.kimlik}.mp3` olarak bırakılabilir")
        durum.yaz(calisma, d)
        return d
    d.kaynak = {"dosya": kyn.wav.name, "nereden": kyn.nereden, "baslik": kyn.baslik, "sure_sn": kyn.sure_sn}
    d.gec("hazir")
    durum.yaz(calisma, d)
    return d


def stil_kur(s: Sarki, lm_caption: str | None = None, kunye: dict | None = None) -> str:
    """Scryne'ın stili esastır. Yoksa: (LM tanımı ya da sanatçının ilk iki MusicBrainz türü) + vokal cinsiyeti
    (liste; yoksa solo sanatçının cinsiyeti, grupta söylenmez) + temiz kayıt soneki."""
    if s.stil:
        return s.stil
    kunye = kunye or {}
    parcalar = []
    if lm_caption:
        parcalar.append(lm_caption.strip().rstrip("."))
    elif turler := list(kunye.get("sanatci_turleri") or [])[:2]:
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
            # BPM/ton yalnız listeden: yanlış değer modeli detone eder, tahmin göndermek göndermemekten kötü
            d.analiz = {"stil": stil_kur(s, kunye=d.kunye), "bpm": s.bpm, "ton": s.ton or "", "dil": "en",
                        "kaynak": "musicbrainz"}
            d.gec("analiz")
            durum.yaz(calisma, d)
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
        d.analiz = {
            "stil": stil_kur(s, lm.get("caption"), d.kunye),
            "bpm": s.bpm or _tam(lm.get("bpm")),
            "ton": s.ton or (lm.get("keyscale") or ""),
            "dil": "en",
            "lm": lm,
            "lm_hata": None if r.basari else r.hata,
        }
        d.gec("analiz")
        durum.yaz(calisma, d)


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
