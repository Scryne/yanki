"""Ses modeli eğitimi: ACE-Step 1.5 XL-SFT'ye tür LoRA'sı, kiralık GPU'da (Scryne 2026-10-11: "şarkı yapma modelini
ve beat'ini eğit, orijinal şarkılar gibi kaliteli olsun"; Roadmap Faz 8/12'deki "LoRA ihtiyacı" denemesi).

ACE-Step vokali ve eşliği (beat) tek parça üretiyor: tek LoRA ikisini birlikte öğrenir. Eğitim motor klasöründeki
Side-Step (`train.py fixed`: modelin kendi sürekli zaman adımı dağılımı, %15 CFG düşürme), iki aşama:

  1. veri (yerel, ücretsiz): `config/egitim.toml`'daki şarkılar → `calisma/egitim/veri/`: YouTube'dan Opus (tam bant),
     48 kHz FLAC, en çok `en_uzun_sn`; LRCLIB'in zaman damgalı sözü aynı yerden kesilir (söz-ses kayması öğretilmez),
     stil metni liste.toml'daki tanımlarla aynı kalıpta. Cover listesindeki sanatçılar veriye girmez.
  2. kiralık GPU (RunPod, `uzak` ile aynı altyapı): ACE-Step kurulur, veri gider, ön işleme (VAE + metin kodlayıcı),
     eğitim, ardından karşılaştırmalı deneme: `deneme_sarkilari` üretim tarifiyle (cover, aynı tohum) LoRA ölçeği
     0 / 0,5 / 1 ile üretilir. LoRA ve deneme sesleri iner, pod silinir, maliyet aylık bütçeye yazılır.

Kalite kararı kulakta (proje ilkesi): deneme sesleri `calisma/dinleme/lora/<tarih>/`'e, kapı ölçüleriyle (söz WER,
parmak izi) birlikte. Üretimde kullanmak `config/motor.toml` → `[motor] lora`.

Eğitim pod'u üretimden ayrı adla (`egitim-…`) ve kayıtla (`acik_pod_egitim`) açılır: saatler süren eğitim sürerken
başlayan üretim koşusu onu artık pod sanıp silmesin.
"""

import json
import re
import shlex
import subprocess
import tarfile
import time
import tomllib
from dataclasses import asdict, dataclass, field, replace
from datetime import datetime
from pathlib import Path

from yanki import dosya, durum, kaynak, liste, motor, runpod, ses, sozler, uzak
from yanki.ayarlar import Ayarlar

KLASOR = Path("calisma") / "egitim"
# Side-Step yolları çalışma klasörünün (ACE-Step kökü) içinde olmak zorunda (`path_safety.safe_path`; dışarıdaki
# tensör klasörü "Path escapes safe root" ile düşüyor, 2026-10-11 yerel denemede bulundu)
UZAK = f"{runpod.ACESTEP_DIZIN}/yanki_egitim"
POD_AD, POD_KAYIT = "egitim-yanki", "acik_pod_egitim"
SOZ_SONU_PAYI = 3.0  # kesitin son saniyelerinde başlayan satır yarım kalır: söze girmez
SONUS_SN = 2.0  # kesilen şarkının sonu yumuşak biter (ani kesik öğretilmesin)
KAPAK_BETIGI = Path(__file__).with_name("kapak_hazirla.py")
SOZ_BICIMI = "yapi-1"  # sözler yanki/yapi.py bölüm etiketleriyle (2026-10-12)
# A40'ın saatlik fiyatına pay (ölçülen ~0,67 $): uzun eğitim, en kötü durumda (zaman aşımı) bakiyesi yetecek hesapta
# başlar. Bakiye eğitim ortasında biterse RunPod pod'u kapatır, saatlerin emeği gider.
SAATLIK_USD_PAYI = 0.75


@dataclass(frozen=True)
class Ayar:
    model: str = "acestep-v15-xl-sft"
    gpu: str = "NVIDIA A40"
    rank: int = 64
    alpha: int = 128
    lr: float = 1e-4
    epoch: int = 60
    kaydet_her: int = 20
    en_uzun_sn: float = 240.0
    zaman_asimi_saat: float = 6.0
    deneme_sarkilari: tuple[str, ...] = ()
    deneme_olcekleri: tuple[float, ...] = (0.0, 0.5, 1.0)
    # son bağdaştırıcının yanında denenen ara kayıtlar (epoch; ölçek 1): kaç epoch'un iyi olduğunu kulak seçsin
    deneme_ara_kayitlar: tuple[int, ...] = ()
    # örneklerin stili, eğitimden önce pod'da ACE-Step betimleyicisiyle (acestep-captioner) yazılır: üretim de betimden
    # stil kullandığı için (config/motor.toml [motor] betim) eğitim ile üretim aynı dili konuşur; listedeki stil yedek
    betim: bool = True
    # LoRA cover görevinde de öğrenir (yanki/kapak_hazirla.py): her örneğin yanına bağlamı kendi kaynak kodlarından,
    # talimatı ve söz biçimi üretimdeki gibi bir kopyası. Side-Step yalnız metinden-müzik öğretiyordu; üretim cover.
    kapak: bool = True


@dataclass(frozen=True)
class VeriSarki:
    sanatci: str
    ad: str
    stil: str = ""  # betim düşerse kullanılır

    @property
    def kimlik(self) -> str:
        return liste.kimlik(self.sanatci, self.ad)


def oku(yol: Path) -> tuple[Ayar, list[VeriSarki]]:
    d = tomllib.loads(yol.read_text(encoding="utf-8"))
    e = d.get("egitim", {})
    bilinmeyen = set(e) - set(Ayar.__dataclass_fields__)
    if bilinmeyen:
        raise ValueError(f"egitim: bilinmeyen alan: {', '.join(sorted(bilinmeyen))}")
    ayar = Ayar(**{k: tuple(v) if isinstance(v, list) else v for k, v in e.items()})
    if ayar.epoch < 1 or ayar.kaydet_her < 1 or not 30 <= ayar.en_uzun_sn <= 480:
        raise ValueError("egitim: epoch ≥ 1, kaydet_her ≥ 1, 30 ≤ en_uzun_sn ≤ 480 olmalı")
    sarkilar, gorulen = [], set()
    for i, s in enumerate(d.get("sarki", []), 1):
        gerekli = ("sanatci", "ad") if ayar.betim else ("sanatci", "ad", "stil")  # betimle stil pod'da yazılır
        if not all(str(s.get(k, "")).strip() for k in gerekli):
            raise ValueError(f"egitim: {i}. şarkıda {', '.join(gerekli)} gerekli")
        v = VeriSarki(s["sanatci"].strip(), s["ad"].strip(), " ".join(str(s.get("stil", "")).split()))
        if v.kimlik in gorulen:
            raise ValueError(f"egitim: aynı şarkı iki kez: {v.sanatci} — {v.ad}")
        gorulen.add(v.kimlik)
        sarkilar.append(v)
    return ayar, sarkilar


def veri(kok: Path) -> list[VeriSarki]:
    """Eğitim verisindeki şarkılar (`config/egitim.toml`; yoksa boş). Üretim ve keşif buna bakar: popüler keşif
    (2026-10-13) eğitim sanatçılarını listeye almaya başladı, ikisi eğitimdeki kaydın ta kendisiydi (Do I Wanna Know?,
    Californication); modelin öğrendiği kaydın cover'ı ezberden gelir."""
    yol = kok / "config" / "egitim.toml"
    return oku(yol)[1] if yol.exists() else []


# ── 1. veri ─────────────────────────────────────────────────
# Eğitimde kayıt stüdyo sürümü olmalı: söz zaman damgaları albüm sürümüne göre ve stil metni o kaydı anlatıyor.
# "(Acoustic)" sürümü ya da fragman kurgusu ("… // Project Hail Mary") ilk denemede seçildi (2026-10-11).
EGITIMDE_ISTENMEYEN = re.compile(r"[(\[]\s*acoustic|//|trailer|mashup|tiktok", re.I)


def _tercih(a: kaynak.Aday) -> int:
    """Küçük önce: YouTube'un kendiliğinden açtığı "- Topic" kanalı (albüm sesi) > "audio" başlığı > söz videosu >
    diğerleri (klipte giriş/ses efekti olabilir)."""
    b = a.baslik.casefold()
    if a.kanal.endswith(" - Topic"):
        return 0
    if "audio" in b:
        return 1
    return 2 if "lyric" in b else 3


def sec(adaylar: list[kaynak.Aday], beklenen_sn: float | None) -> kaynak.Aday:
    """Süresi tutan adaylar arasından en tercihli katmandaki, katman içinde süresi en yakın olan."""
    temiz = [a for a in adaylar if not EGITIMDE_ISTENMEYEN.search(a.baslik)]
    for katman in range(4):
        try:
            return kaynak.sec([a for a in temiz if _tercih(a) == katman], beklenen_sn)
        except kaynak.KaynakYok:
            continue
    return kaynak.sec(temiz, beklenen_sn)  # uygun yok: kaynak.sec'in hata metni


def veri_klasoru(kok: Path) -> Path:
    return kok / KLASOR / "veri"


def ornek_dili(ses_yolu: Path, metin: str, tespit=None) -> str:
    """Söz dili: sesten (Whisper); ses emin değilse söz İngilizce değilse sesin dili (hazirlik.dil_bul ile aynı kural).
    Önce hep "en" yazılıyordu; çok türlü veride İspanyolca/Korece şarkı yanlış etiketlenirdi."""
    from yanki import hazirlik, kapilar

    try:
        dil, olasilik = (tespit or kapilar.dil_tespit)(ses_yolu)
    except Exception:  # noqa: BLE001 — dil tespiti örneği düşürmez
        return "en"
    if olasilik >= hazirlik.DIL_ESIGI:
        return dil if dil != "unknown" else "en"
    oran = kapilar.ingilizce_orani(metin)
    return dil if oran is not None and oran < hazirlik.INGILIZCE_ESIGI and dil not in ("en", "unknown") else "en"


def ornek_hazirla(s: VeriSarki, ayar: Ayar, klasor: Path, lrclib=sozler.lrclib,
                  adaylar=kaynak.youtube_adaylari, indir=kaynak.youtube_indir, dil_tespit=None,
                  surumler=sozler.lrclib_surumleri) -> dict:
    """Bir eğitim örneği: `<kimlik>.flac` + `<kimlik>.json` (Side-Step örnek alanları + kaynak). Varsa yeniden
    indirilmez."""
    ses_yolu, meta_yolu = klasor / f"{s.kimlik}.flac", klasor / f"{s.kimlik}.json"
    if ses_yolu.exists() and meta_yolu.exists():
        meta = json.loads(meta_yolu.read_text(encoding="utf-8"))
        stil = meta.get("betim_stil") or s.stil  # betim (pod'da yazıldıysa) listedeki stilden önce
        degisti = meta.get("caption") != stil  # stil metni düzeltildiyse ses yeniden inmez
        meta["caption"] = stil
        if meta.get("soz_bicimi") != SOZ_BICIMI:  # eski biçimli söz (bölüm yapısından önce): yeniden kurulur
            soz = lrclib(s.sanatci, s.ad)
            tam = meta.get("tam_sn") or (soz.sure_sn if meta["duration"] >= ayar.en_uzun_sn - 1 else meta["duration"])
            meta.update(lyrics=kesit_sozu(soz, meta["duration"], tam or meta["duration"], s.ad), soz_bicimi=SOZ_BICIMI)
            degisti = True
        if degisti:
            dosya.json_yaz(meta_yolu, meta)
        return meta
    soz = lrclib(s.sanatci, s.ad)
    videolar = adaylar(f"{s.sanatci} {s.ad} official audio")
    try:
        if not soz.satirlar:
            raise LookupError("LRCLIB'de zaman damgalı söz yok: söz-ses hizası kurulamaz")
        secilen = sec(videolar, soz.sure_sn)
    except LookupError as ilk:  # KaynakYok dahil: `/get` başka sürümü vermiş olabilir (çok türlü veride 10'da 7)
        for alt in surumler(s.sanatci, s.ad):
            try:
                secilen, soz = sec(videolar, alt.sure_sn), alt
                break
            except kaynak.KaynakYok:
                continue
        else:
            raise ilk
    klasor.mkdir(parents=True, exist_ok=True)
    ham = indir(secilen.id, klasor / f"{s.kimlik}.indirilen")
    try:
        tam = ses.sure(ham)
        kesit = min(ayar.en_uzun_sn, tam)
        filtre = ["-af", f"afade=t=out:st={kesit - SONUS_SN:.2f}:d={SONUS_SN}"] if kesit < tam - 1 else []
        subprocess.run([ses.arac("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(ham), "-t",
                        f"{kesit:.2f}", *filtre, "-ar", "48000", "-ac", "2", "-sample_fmt", "s16", "-c:a", "flac",
                        str(ses_yolu)], check=True)
    finally:
        ham.unlink(missing_ok=True)
    metin = kesit_sozu(soz, kesit, tam, s.ad)
    if not metin.strip():
        ses_yolu.unlink(missing_ok=True)
        raise LookupError("kesitte söz yok")
    meta = {"audio_path": ses_yolu.name, "filename": ses_yolu.name, "caption": s.stil, "lyrics": metin,
            "language": ornek_dili(ses_yolu, metin, dil_tespit), "is_instrumental": False, "duration": round(kesit, 2),
            "sanatci": s.sanatci, "ad": s.ad, "kaynak": f"youtube:{secilen.id}", "baslik": secilen.baslik,
            "tam_sn": round(tam, 2), "soz_bicimi": SOZ_BICIMI,
            "hazirlandi": datetime.now().isoformat(timespec="seconds")}
    dosya.json_yaz(meta_yolu, meta)
    return meta


def _soz_satiri(m: str) -> bool:
    return not sozler._ara_mi(m) and not (m.strip().startswith("[") and m.strip().endswith("]"))


def kirp(metin: str, satir_sayisi: int) -> str:
    """Etiketli sözün ilk `satir_sayisi` söz satırı; kıta etiketleri korunur, içi boşalan son kıta atılır."""
    cikti, sayi = [], 0
    for satir in metin.split("\n"):
        if _soz_satiri(satir):
            if sayi >= satir_sayisi:
                break
            sayi += 1
        cikti.append(satir)
    while cikti and not _soz_satiri(cikti[-1]):
        cikti.pop()
    return "\n".join(cikti).strip()


def kesit_sozu(soz: sozler.Soz, kesit: float, tam: float, ad: str = "") -> str:
    """Eğitim kesitinin sözü, üretimdeki `soz.txt` ile aynı biçimde (`yapi` bölüm etiketleri). Şarkı kesildiyse
    zaman damgasıyla kesitte başlayan satırlar; zaman damgası yoksa düz sözden kesitin oranı kadar satır."""
    if kesit >= tam - 1:
        return soz.metin
    sinir = kesit - SOZ_SONU_PAYI
    if soz.satirlar:
        return sozler.aralik_sozu(list(soz.satirlar), 0.0, sinir, tam, ad)
    toplam = sum(_soz_satiri(x) for x in soz.metin.split("\n"))
    return kirp(soz.metin, int(toplam * sinir / tam))


ORNEK_ALANLARI = ("audio_path", "filename", "caption", "lyrics", "language", "is_instrumental", "duration")


def veri_hazirla(kok: Path, ayar: Ayar, sarkilar: list[VeriSarki], bildir=print, **bagimlilik
                 ) -> tuple[list[dict], list[tuple[VeriSarki, str]]]:
    """Örnekleri hazırlar, `dataset.json`'u (Side-Step'in tam ACE-Step biçimi) yazar. Dönen: (örnekler, düşenler)."""
    klasor = veri_klasoru(kok)
    try:
        cover = {s.sanatci.casefold() for s in liste.yukle(kok / "girdi" / "liste.toml")}
    except OSError:
        cover = set()
    ornekler, dusen = [], []
    for s in sarkilar:
        if s.sanatci.casefold() in cover:
            dusen.append((s, "cover listesindeki sanatçı (kaydını ezberlemesin)"))
            continue
        try:
            ornekler.append(ornek_hazirla(s, ayar, klasor, **bagimlilik))
            bildir(f"  ✓ {s.sanatci} — {s.ad} ({ornekler[-1]['duration']:.0f} sn)")
        except (LookupError, OSError, ValueError, subprocess.SubprocessError) as e:
            dusen.append((s, f"{type(e).__name__}: {e}"))
            bildir(f"  ✗ {s.sanatci} — {s.ad}: {e}")
    dosya.json_yaz(klasor / "dataset.json", {
        "metadata": {"name": "orvane-balad", "custom_tag": "", "tag_position": "prepend", "genre_ratio": 0,
                     "all_instrumental": False, "num_samples": len(ornekler),
                     "created_at": datetime.now().isoformat(timespec="seconds")},
        "samples": [{k: o[k] for k in ORNEK_ALANLARI} for o in ornekler]})
    return ornekler, dusen


def paketle(kok: Path, ornekler: list[dict]) -> Path:
    """Veri tek tar'da gider (dosya başına SSH el sıkışması yok)."""
    klasor = veri_klasoru(kok)
    hedef = kok / KLASOR / "veri.tar"
    with tarfile.open(hedef, "w") as t:
        t.add(klasor / "dataset.json", "dataset.json")
        for o in ornekler:
            t.add(klasor / o["audio_path"], o["audio_path"])
    return hedef


# ── 2. kiralık GPU ──────────────────────────────────────────
def arka_plan_betigi(hedef: str, komut: str, ad: str, dizin: str = UZAK) -> str:
    """Komutu pod'da arka planda başlatır; SSH hemen döner (uzak.baslatma_betigi'deki kabuk önceliği dersi: arka plana
    yalnız komut gider). Bitince çıkış kodu `<ad>.kod`'a yazılır (pid yeniden kullanımına bakılmaz)."""
    ic = f"{komut}; echo $? > {dizin}/{ad}.kod"
    return (f"cd {hedef} || exit 1; export PATH=$HOME/.local/bin:$PATH PYTHONUTF8=1 PYTHONUNBUFFERED=1; "
            f"rm -f {dizin}/{ad}.kod; $(command -v setsid) nohup bash -c {shlex.quote(ic)} > {dizin}/{ad}.log 2>&1 "
            f"< /dev/null & echo $! > {dizin}/{ad}.pid")


def bekle(p, ad: str, zaman_asimi_sn: float, aralik_sn: float = 60, bildir=print, dizin: str = UZAK) -> int:
    """Arka plandaki komutun bitmesini bekler; günlüğün son satırı değiştikçe yazar. Dönen: çıkış kodu."""
    bitis, son = time.monotonic() + zaman_asimi_sn, ""
    while time.monotonic() < bitis:
        time.sleep(aralik_sn)
        try:
            cikti = p.komut(f"cat {dizin}/{ad}.kod 2>/dev/null || echo SURUYOR; echo '#'; "
                            f"tail -c 2000 {dizin}/{ad}.log | tr '\\r' '\\n' | grep -v '^\\s*$' | tail -n 1")
        except runpod.RunPodHatasi as e:  # tek kopuk yoklama eğitimi düşürmez
            bildir(f"  yoklama kopuk: {str(e)[-120:]}")
            continue
        kod, _, satir = cikti.partition("#")
        satir = satir.strip()[-200:]
        if satir and satir != son:
            bildir(f"  [{ad}] {satir}")
            son = satir
        if kod.strip() != "SURUYOR":
            return int(kod.strip() or 1)
    p.komut(f"kill $(cat {dizin}/{ad}.pid) 2>/dev/null || true")
    raise runpod.RunPodHatasi(f"{ad} {zaman_asimi_sn / 3600:.1f} saatte bitmedi")


def sidestep(ayar: Ayar, ek: str) -> str:
    """`--yes`: onay sorusu sorulmaz (stdin yok, soru "Aborted" ile bitiyordu); `--plain`: günlükte renk kodu yok.
    `--dataset-dir`/`--output-dir` ön işlemede de zorunlu (argparse)."""
    return (f"uv run --with rich python train.py --yes --plain fixed --checkpoint-dir ./checkpoints "
            f"--model-variant {ayar.model} --dataset-dir {UZAK}/tensor --output-dir {UZAK}/cikti {ek}")


def on_isleme_komutu(ayar: Ayar) -> str:
    return sidestep(ayar, f"--preprocess --dataset-json {UZAK}/veri/dataset.json --audio-dir {UZAK}/veri "
                          f"--tensor-output {UZAK}/tensor --max-duration {ayar.en_uzun_sn:g}")


def egitim_komutu(ayar: Ayar) -> str:
    # SFT: çıkarım kaydırması 1.0, 50 adım (Side-Step bunu bağdaştırıcıya üst veri olarak yazar; eğitimi etkilemez)
    return sidestep(ayar, f"--epochs {ayar.epoch} "
                          f"--lr {ayar.lr:g} --rank {ayar.rank} --alpha {ayar.alpha} --save-every {ayar.kaydet_her} "
                          "--shift 1.0 --num-inference-steps 50 --gradient-checkpointing")


@dataclass
class Sonuc:
    klasor: Path  # calisma/egitim/lora/<zaman>/
    dinleme: Path  # calisma/dinleme/lora/<zaman>/
    lora: Path | None = None
    deneme: list[dict] = field(default_factory=list)
    usd: float = 0.0
    sureler: dict = field(default_factory=dict)


REFERANS = "_referans"


def deneme_kok(calisma: Path, kimlik: str) -> Path:
    """Deneme şarkısının durum kökü: hattaki şarkı ya da `calisma/_referans/` (yayından silinen şarkıların kaynağı ve
    sözü, karşılaştırma için kalır; 2026-10-12'de yayınlananlar silinince S20 şarkıları oraya alındı)."""
    return calisma if durum.oku(calisma, kimlik) is not None else calisma / REFERANS


def deneme_isleri(a: Ayarlar, calisma: Path, ayar: Ayar, ses_yolu, ara: dict[int, str] | None = None,
                  son: str | None = None) -> list[tuple[motor.Is, durum.Durum, float | str | None]]:
    """Karşılaştırmalı deneme: üretim tarifiyle (cover, güç, adım, ilk tohum) tek parça, her ölçek için bir iş; `ara`
    (epoch → pod'daki bağdaştırıcı) verilirse her ara kayıt için de bir iş (ölçek 1, kol `ep<N>`). `son`: son
    bağdaştırıcının pod'daki yolu (ara kayıt varken işçi bağdaştırıcıları değiştirir). `ses_yolu(yerel) → uzak yol`.
    Sıra: önce betimler, sonra bağdaştırıcı başına işler (işçi her bağdaştırıcıyı bir kez takar)."""
    from yanki import uretim

    isler, kollar = [], []
    for kimlik in ayar.deneme_sarkilari:
        kok = deneme_kok(calisma, kimlik)
        d = durum.oku(kok, kimlik)
        if d is None or not d.analiz.get("stil") or not d.kaynak.get("dosya"):
            continue
        k = durum.klasor(kok, kimlik)
        betim = None
        if ayar.betim:  # üretim tarifi: stil şarkıyı dinleyen betimden (ölçek None: betim işi)
            betim = f"{kimlik}|betim"
            isler.append((motor.Is(id=betim, gorev="betimle", kaynak=ses_yolu(k / d.kaynak["dosya"])), d, None))
        ortak = dict(gorev="cover", kaynak=ses_yolu(k / d.kaynak["dosya"]),
                     soz=(k / d.soz["dosya"]).read_text(encoding="utf-8"), adim=a.cover.adim,
                     tohum=a.cover.tohumlar[0], guc=a.cover.guc, stil_betimden=betim, **uretim._ortak(d))
        for olcek in ayar.deneme_olcekleri:
            i = motor.Is(id=f"{kimlik}|{olcek:g}", cikti_klasor=f"{UZAK}/deneme/{kimlik}/{olcek:g}", lora_olcek=olcek,
                         lora=son if ara else None, **ortak)
            kollar.append((son or "", i, d, olcek))
        for ep, yol in sorted((ara or {}).items()):
            kollar.append((yol, motor.Is(id=f"{kimlik}|ep{ep}", cikti_klasor=f"{UZAK}/deneme/{kimlik}/ep{ep}",
                                         lora_olcek=1.0, lora=yol, **ortak), d, f"ep{ep}"))
    return isler + [(i, d, kol) for _, i, d, kol in sorted(kollar, key=lambda x: (x[0] != (son or ""), x[0]))]


def egit(a: Ayarlar, ayar: Ayar, veri_tar: Path, bildir=print, pod_sinifi=runpod.Pod, kur=runpod.acestep_kur,
         bakiye=runpod.bakiye, kapat=runpod.kapat_artiklari, commit: str | None = None) -> Sonuc:
    """Kiralık GPU'da ön işleme + eğitim + karşılaştırmalı deneme. LoRA `calisma/egitim/lora/<zaman>/`'e iner."""
    kok, calisma = a.kok, a.kok / "calisma"
    # en kötü durumda (zaman aşımına kadar) bakiyesi yetecek hesap; yoksa en az bakiyeli kural (bütçe denetimi durdurur)
    gereken = max(a.uzak.en_az_bakiye, ayar.zaman_asimi_saat * SAATLIK_USD_PAYI)
    api = runpod.anahtar(kok, gereken, bakiye)
    if bakiye(api) < gereken:
        api = runpod.anahtar(kok, a.uzak.en_az_bakiye, bakiye)
        bildir(f"uyarı: hiçbir hesapta {gereken:.1f} $ yok; eğitim bakiye biterse yarıda kalabilir")
    uzak.butce_kontrol(a, api, bakiye)
    if artik := [p for k in dict.fromkeys([api, *runpod.anahtarlar(kok)])
                 for p in kapat(k, calisma / ".runpod", POD_KAYIT, "egitim-")]:
        bildir(f"önceki eğitimden açık kalan pod silindi: {', '.join(artik)}")
    commit = commit or uzak.acestep_commit(a)
    zaman = datetime.now().strftime("%Y%m%d-%H%M")
    yerel = kok / KLASOR / "lora" / zaman
    sonuc, acilan = Sonuc(yerel, calisma / "dinleme" / "lora" / zaman), []
    kayit: dict = {"zaman": datetime.now().isoformat(timespec="seconds"), "gpu": ayar.gpu, "not": "egitim",
                   "is": 0}
    zaman_asimi = ayar.zaman_asimi_saat * 3600
    try:
        with uzak.PodAcici(a, pod_sinifi, acilan, gpu=ayar.gpu, ad=POD_AD, kayit_adi=POD_KAYIT) as p:
            kayit["pod"] = p.id
            t = time.time()
            hedef = kur(p, commit, (ayar.model,))
            sonuc.sureler["kurulum"] = round(time.time() - t)
            p.komut(f"mkdir -p {UZAK}/veri {UZAK}/girdi")
            t = time.time()
            p.gonder(veri_tar, f"{UZAK}/veri.tar", zaman_asimi=3600)
            p.komut(f"tar xf {UZAK}/veri.tar -C {UZAK}/veri && rm {UZAK}/veri.tar")
            sonuc.sureler["yukleme"] = round(time.time() - t)
            if ayar.betim:
                t = time.time()
                veri_betimle(a, ayar, p, hedef, kok, yerel, zaman_asimi, bildir)
                sonuc.sureler["betim"] = round(time.time() - t)
            adimlar = [("on_isleme", on_isleme_komutu(ayar))]
            if ayar.kapak:
                p.gonder(KAPAK_BETIGI, f"{UZAK}/kapak_hazirla.py")
                adimlar.append(("kapak", kapak_komutu(ayar)))
            for ad, komut in (*adimlar, ("egitim", egitim_komutu(ayar))):
                t = time.time()
                p.komut(arka_plan_betigi(hedef, komut, ad), tekrar=False)
                kod = bekle(p, ad, zaman_asimi, bildir=bildir)
                sonuc.sureler[ad] = round(time.time() - t)
                if kod != 0:
                    try:
                        p.al(f"{UZAK}/{ad}.log", kok / KLASOR / f"{zaman}-{ad}.log")
                    except (runpod.RunPodHatasi, OSError):
                        pass
                    raise runpod.RunPodHatasi(f"{ad} {kod} koduyla bitti (günlük: {KLASOR}/{zaman}-{ad}.log)")
            # bağdaştırıcı: son sürüm + ara kayıtlar (hangi epoch daha iyi, kulak seçebilsin)
            # yalnız bağdaştırıcı (training_state.* iyileyici durumu: büyük, çıkarımda gereksiz)
            liste_ = p.komut(f"cd {UZAK}/cikti && find . -name 'adapter_config.json' -o -name "
                             "'adapter_model.safetensors' | sort").split()
            for goreli in liste_:
                p.al(f"{UZAK}/cikti/{goreli[2:]}", yerel / goreli[2:])
            for ad in ("on_isleme", "egitim"):
                try:
                    p.al(f"{UZAK}/{ad}.log", yerel / f"{ad}.log")
                except (runpod.RunPodHatasi, OSError):
                    pass
            final = yerel / "final"
            if not (final / "adapter_config.json").exists():
                raise runpod.RunPodHatasi(f"eğitim bitti ama son bağdaştırıcı inmedi: {liste_[:10]}")
            sonuc.lora = final
            sonuc.deneme = _deneme(a, ayar, p, hedef, calisma, sonuc.dinleme, zaman_asimi, bildir,
                                   ara_kayitlar(liste_, ayar.deneme_ara_kayitlar))
    except Exception as e:
        kayit["hata"] = f"{type(e).__name__}: {str(e)[:300]}"
        raise
    finally:
        kayit["usd"] = sonuc.usd = round(sum(x.maliyet() for x in acilan), 3)
        kayit.setdefault("pod", ",".join(str(x.id) for x in acilan if x.id) or None)
        kayit["sureler"] = sonuc.sureler
        uzak.harcama_yaz(kok, kayit)
    kaydet(sonuc, ayar, commit)
    return sonuc


def yerel_ara_kayitlar(yerel: Path, epochlar) -> dict[int, Path]:
    """İnmiş ara kayıtlar (`<lora>/checkpoints/epoch_<N>_loss_<x>/`) → {epoch: klasör}; yalnız istenenler."""
    bulunan = {}
    for d in sorted((yerel / "checkpoints").glob("epoch_*")):
        m = re.match(r"epoch_(\d+)_", d.name)
        if m and int(m.group(1)) in epochlar and (d / "adapter_config.json").is_file():
            bulunan[int(m.group(1))] = d
    return bulunan


def deneme_yeniden(a: Ayarlar, ayar: Ayar, yerel: Path, epochlar, bildir=print, pod_sinifi=runpod.Pod,
                   kur=runpod.acestep_kur, bakiye=runpod.bakiye, commit: str | None = None) -> Sonuc:
    """Biten bir eğitimin ara kayıtlarıyla deneme, eğitimsiz: bağdaştırıcılar yerelden pod'a gider, yalnız ara kayıt
    kolları üretilir (son bağdaştırıcının kayıtları zaten var). Dördüncü eğitimde ara kayıt denemesi bağdaştırıcı adı
    yüzünden düşmüştü (2026-10-13; `motor_isci.lora_adi`)."""
    kok, calisma = a.kok, a.kok / "calisma"
    ara_yerel = yerel_ara_kayitlar(yerel, epochlar)
    if not ara_yerel:
        raise ValueError(f"{yerel.name}: istenen ara kayıt yok ({', '.join(map(str, epochlar))})")
    api = runpod.anahtar(kok, a.uzak.en_az_bakiye, bakiye)
    uzak.butce_kontrol(a, api, bakiye)
    commit = commit or uzak.acestep_commit(a)
    sonuc, acilan = Sonuc(yerel, calisma / "dinleme" / "lora" / yerel.name, lora=yerel / "final"), []
    kayit: dict = {"zaman": datetime.now().isoformat(timespec="seconds"), "gpu": ayar.gpu, "not": "egitim-deneme",
                   "is": 0}
    try:
        with uzak.PodAcici(a, pod_sinifi, acilan, gpu=ayar.gpu, ad=POD_AD, kayit_adi=POD_KAYIT) as p:
            kayit["pod"] = p.id
            t = time.time()
            hedef = kur(p, commit, (ayar.model,))
            sonuc.sureler["kurulum"] = round(time.time() - t)
            ara = {}
            for ep, d in ara_yerel.items():
                ara[ep] = f"{UZAK}/cikti/checkpoints/{d.name}"
            for yerel_k, uzak_k in [(yerel / "final", f"{UZAK}/cikti/final"),
                                    *((d, ara[ep]) for ep, d in ara_yerel.items())]:
                p.komut(f"mkdir -p {uzak_k} {UZAK}/girdi")
                for f in ("adapter_config.json", "adapter_model.safetensors"):
                    p.gonder(yerel_k / f, f"{uzak_k}/{f}", zaman_asimi=1800)
            t = time.time()
            sonuc.deneme = _deneme(a, replace(ayar, deneme_olcekleri=()), p, hedef, calisma, sonuc.dinleme,
                                   ayar.zaman_asimi_saat * 3600, bildir, ara)
            sonuc.sureler["deneme"] = round(time.time() - t)
    except Exception as e:
        kayit["hata"] = f"{type(e).__name__}: {str(e)[:300]}"
        raise
    finally:
        kayit["usd"] = sonuc.usd = round(sum(x.maliyet() for x in acilan), 3)
        kayit.setdefault("pod", ",".join(str(x.id) for x in acilan if x.id) or None)
        kayit["sureler"] = sonuc.sureler
        uzak.harcama_yaz(kok, kayit)
    return sonuc


def deneme_birlestir(yerel: Path, yeni: list[dict], usd: float) -> Sonuc:
    """Yeniden üretilen kolları eğitimin kaydına katar (aynı şarkı+kolun eskisi düşer, maliyet eklenir)."""
    yol = yerel / "egitim.json"
    eski = json.loads(yol.read_text(encoding="utf-8"))
    anahtar = {(x["kimlik"], x.get("kol")) for x in yeni}
    deneme = [x for x in eski.get("deneme", []) if (x["kimlik"], x.get("kol")) not in anahtar] + yeni
    eski.update(deneme=deneme, usd=round(eski.get("usd", 0.0) + usd, 3))
    dosya.json_yaz(yol, eski)
    return Sonuc(yerel, yerel.parents[2] / "dinleme" / "lora" / yerel.name, yerel / "final", deneme, eski["usd"],
                 eski.get("sureler", {}))


def veri_betimle(a: Ayarlar, ayar: Ayar, p, hedef: str, kok: Path, yerel: Path, zaman_asimi: float,
                 bildir=print) -> dict[str, str]:
    """Eğitim örneklerinin stili pod'da betimleyiciyle (üretimle aynı dil: `motor_isci.betim_stili`). Betimi düşen
    örnek listedeki stilini korur. `dataset.json` pod'da ve yerelde güncellenir; betimler `yerel/betimler.json`."""
    from yanki.motor_isci import betim_stili

    veri = veri_klasoru(kok)
    dataset = json.loads((veri / "dataset.json").read_text(encoding="utf-8"))
    betimler = {o["audio_path"]: b for o in dataset["samples"]
                if (b := _ornek_meta(veri, o["audio_path"]).get("betim"))}  # önceki eğitimden (örnek kaydında)
    eksik = [o for o in dataset["samples"] if o["audio_path"] not in betimler]
    if eksik:
        is_yolu = yerel / "betim_is.json"
        dosya.json_yaz(is_yolu, {"motor": {"klasor": hedef, "model": ayar.model},
                                 "isler": [{"id": o["audio_path"], "gorev": "betimle",
                                            "kaynak": f"{UZAK}/veri/{o['audio_path']}"} for o in eksik]})
        p.gonder(motor.ISCI, f"{UZAK}/motor_isci.py")
        p.gonder(is_yolu, f"{UZAK}/betim_is.json")
        p.komut(arka_plan_betigi(hedef, f"uv run python {UZAK}/motor_isci.py {UZAK}/betim_is.json "
                                        f"{UZAK}/betim_sonuc.json", "betim"), tekrar=False)
        bekle(p, "betim", zaman_asimi, aralik_sn=30, bildir=bildir)
        ham = json.loads(p.komut(f"cat {UZAK}/betim_sonuc.json 2>/dev/null || echo '[]'") or "[]")
        yeni = {r["id"]: r["analiz"]["betim"] for r in ham
                if r.get("basari") and r.get("id") and (r.get("analiz") or {}).get("betim")}
        for ad, b in yeni.items():  # örnek kaydına: sonraki eğitim yeniden betimlemez
            meta = _ornek_meta(veri, ad)
            if meta:
                dosya.json_yaz(veri / (Path(ad).stem + ".json"), {**meta, "betim": b, "betim_stil": betim_stili(b)})
        betimler.update(yeni)
    for o in dataset["samples"]:
        if o["audio_path"] in betimler:
            o["caption"] = betim_stili(betimler[o["audio_path"]])
    # betimi düşen ve listede stili olmayan örnek boş stille öğretilmesin
    if bos := [o["audio_path"] for o in dataset["samples"] if not o.get("caption", "").strip()]:
        bildir(f"betimsiz ve stilsiz {len(bos)} örnek çıkarıldı: {', '.join(bos[:5])}")
        dataset["samples"] = [o for o in dataset["samples"] if o.get("caption", "").strip()]
        dataset.get("metadata", {})["num_samples"] = len(dataset["samples"])
    dosya.json_yaz(veri / "dataset.json", dataset)
    dosya.json_yaz(yerel / "betimler.json", betimler)
    p.gonder(veri / "dataset.json", f"{UZAK}/veri/dataset.json")
    bildir(f"betim: {len(betimler)}/{len(dataset['samples'])} örnek")
    if not betimler:
        raise runpod.RunPodHatasi("betimleyici hiçbir örneği betimleyemedi (eğitim listedeki stillerle yapılmasın)")
    return betimler


def _ornek_meta(veri: Path, ses_adi: str) -> dict:
    try:
        return json.loads((veri / (Path(ses_adi).stem + ".json")).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ara_kayitlar(dosyalar: list[str], epochlar) -> dict[int, str]:
    """Side-Step'in ara kayıtları (`./checkpoints/epoch_<N>_loss_<x>/adapter_config.json`) → {epoch: pod'daki klasör};
    yalnız istenen epoch'lar."""
    bulunan = {}
    for f in dosyalar:
        m = re.search(r"checkpoints/(epoch_(\d+)_[^/]*)/adapter_config\.json$", f)
        if m and int(m.group(2)) in epochlar:
            bulunan[int(m.group(2))] = f"{UZAK}/cikti/checkpoints/{m.group(1)}"
    return bulunan


def kapak_komutu(ayar: Ayar) -> str:
    return (f"uv run python {UZAK}/kapak_hazirla.py {runpod.ACESTEP_DIZIN} {ayar.model} {UZAK}/tensor "
            f"{UZAK}/veri/dataset.json")


def kaydet(sonuc: Sonuc, ayar: Ayar, commit: str | None = None, ornek: int | None = None) -> None:
    yol = sonuc.klasor / "egitim.json"
    try:
        eski = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        eski = {}
    dosya.json_yaz(yol, {**eski, "ayar": asdict(ayar), "usd": sonuc.usd, "sureler": sonuc.sureler,
                         "deneme": sonuc.deneme, **({"commit": commit} if commit else {}),
                         **({"ornek": ornek} if ornek is not None else {})})


def rapor(sonuc: Sonuc, ornek: int, dusen: int) -> str:
    """Dinleme notu (`calisma/dinleme/lora/<zaman>/OKU.md`): hangi dosya ne, kapı ölçüleri."""
    satirlar = [f"# LoRA karşılaştırması ({sonuc.klasor.name})", "",
                f"Eğitim: {ornek} şarkı ({dusen} düştü), maliyet {sonuc.usd:.2f} $, süreler "
                + ", ".join(f"{k} {v / 60:.0f} dk" for k, v in sonuc.sureler.items()) + ".", "",
                "Aynı şarkı, aynı tohum ve üretim tarifi; yalnız LoRA ölçeği değişiyor. `lora_0` = bugünkü üretim "
                "(LoRA yok). Dinle: hangisi orijinal kayda daha yakın prodüksiyon, vokal daha net, mırıldanma/nefes "
                "kusuru daha az.", "",
                "| şarkı | ölçek | dosya | söz WER | parmak izi | kapı |", "|---|---|---|---|---|---|"]
    for x in sonuc.deneme:
        k = x.get("kapilar") or {}
        wer = (k.get("soz_wer") or {}).get("deger")
        pi = (k.get("parmak_izi") or {}).get("deger")
        gecti = all(v.get("gecti") for v in k.values()) if k and "hata" not in k else None
        kol = x.get("kol") or format(x["olcek"], "g")
        satirlar.append(f"| {x['ad']} | {kol} | {Path(x['dosya']).name if x.get('dosya') else '—'} | "
                        f"{wer if wer is not None else '—'} | {pi if pi is not None else '—'} | "
                        f"{'geçti' if gecti else 'düştü' if gecti is False else x.get('hata') or '—'} |")
    if sonuc.lora:
        satirlar += ["", f"Üretimde kullanmak için: `config/motor.toml` → `[motor] lora = \"{sonuc.lora.as_posix()}\"`"]
    return "\n".join(satirlar) + "\n"


def _deneme(a: Ayarlar, ayar: Ayar, p, hedef: str, calisma: Path, dinleme: Path, zaman_asimi: float,
            bildir, ara: dict[int, str] | None = None) -> list[dict]:
    girdiler: dict[str, str] = {}

    def ses_yolu(yerel: Path) -> str:
        return girdiler.setdefault(str(yerel), f"{UZAK}/girdi/{len(girdiler)}{yerel.suffix}")

    isler = deneme_isleri(a, calisma, ayar, ses_yolu, ara, f"{UZAK}/cikti/final")
    if not isler:
        return []
    for yerel_yol, uzak_yol in girdiler.items():
        p.gonder(Path(yerel_yol), uzak_yol)
    p.gonder(motor.ISCI, f"{UZAK}/motor_isci.py")
    is_yolu = dinleme / "motor_is.json"
    dosya.json_yaz(is_yolu, {"motor": {
        "klasor": hedef, "model": ayar.model, "niceleme": None, "cpu_offload": False, "dit_offload": False,
        "lm_model": a.motor.lm_model, "lm_backend": a.motor.lm_backend, "lora": f"{UZAK}/cikti/final",
        "lora_olcek": 1.0}, "isler": [{**asdict(i), "bolge": None} for i, _, _ in isler]})
    p.gonder(is_yolu, f"{UZAK}/motor_is.json")
    komut = (f"ACESTEP_GENERATION_TIMEOUT=3600 uv run python {UZAK}/motor_isci.py {UZAK}/motor_is.json "
             f"{UZAK}/motor_sonuc.json")
    p.komut(arka_plan_betigi(hedef, komut, "deneme"), tekrar=False)
    bekle(p, "deneme", zaman_asimi, aralik_sn=30, bildir=bildir)
    ham = json.loads(p.komut(f"cat {UZAK}/motor_sonuc.json 2>/dev/null || echo '[]'") or "[]")
    sonuclar = []
    for r in ham:
        eslesen = next(((i, d, o) for i, d, o in isler if i.id == r.get("id")), None)
        if eslesen is None:
            continue
        i, d, kol = eslesen
        if kol is None:  # betim işi
            continue
        ara_mi = isinstance(kol, str)  # "ep20": ara kayıt (ölçek 1)
        satir = {"kimlik": d.kimlik, "ad": d.ad, "olcek": 1.0 if ara_mi else kol, "kol": kol if ara_mi else f"{kol:g}",
                 "basari": bool(r.get("basari")), "hata": r.get("hata"), "sure_sn": r.get("sure_sn")}
        if r.get("basari") and r.get("cikti"):
            ad = f"lora_{kol}.flac" if ara_mi else f"lora_{kol:g}.flac"
            satir["dosya"] = str(p.al(r["cikti"], dinleme / d.kimlik / ad))
        sonuclar.append(satir)
    bildir(f"deneme: {sum(x['basari'] for x in sonuclar)}/{sum(o is not None for _, _, o in isler)} iş")
    return sonuclar


def degerlendir(a: Ayarlar, calisma: Path, deneme: list[dict], degerlendirici=None) -> list[dict]:
    """Deneme seslerini üretimin kapılarından geçirir (söz WER, parmak izi, dalga, süre): LoRA sözü bozuyor mu,
    orijinal kaydı taşıyor mu. "İyi"yi yine kulak seçer."""
    from yanki import kapilar

    degerlendirici = degerlendirici or (lambda aday, kaynak, soz, dil: kapilar.degerlendir(aday, kaynak, soz,
                                                                                            a.fpcalc, dil=dil))
    for x in deneme:
        if not x.get("dosya"):
            continue
        kok = deneme_kok(calisma, x["kimlik"])
        d = durum.oku(kok, x["kimlik"])
        k = durum.klasor(kok, x["kimlik"])
        try:
            x["kapilar"] = degerlendirici(Path(x["dosya"]), k / d.kaynak["dosya"],
                                          (k / d.soz["dosya"]).read_text(encoding="utf-8"), d.analiz.get("dil", "en"))
        except Exception as e:  # noqa: BLE001 — ölçüm düşerse ses yine dinlenebilir
            x["kapilar"] = {"hata": f"{type(e).__name__}: {e}"}
    return deneme
