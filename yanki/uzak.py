"""Uzak motor: üretim işlerini kiralık GPU'da (RunPod, `yanki/runpod.py`) çalıştırır, `motor.calistir` ile aynı imza.

S19 (2026-10-10, A40 48 GB): nicelemesiz bf16 XL-SFT, 45 sn kesit 21 sn, 285 sn tam şarkı tek parça 140 sn, VRAM tepe
14,4 GB; evde INT8 ile parçalı üretim aday başı ~8 dk. Kapılar aynı düzeyde (söz WER kesitte 0,042/0,056).

Bir koşu = bir pod: açılır, ACE-Step yereldeki commit'le kurulur (~1 dk; model veri merkezinden ~40 sn), girdi sesleri
gider, işçi `motor_isci.py` nicelemesiz ve offload'suz koşar, çıktılar işin yerel `cikti_klasor`'una iner, pod silinir.
Hattın geri kalanı (kapılar, dinleme, paket) yerel dosyalarla çalışır; uzak olduğunu bilmez.

Bütçe: bakiye `en_az_bakiye`'nin altındaysa ya da bu ayın harcaması `aylik_butce`'ye ulaştıysa açılmaz (`ButceYok`);
her pod'un maliyeti `calisma/gunluk/runpod.json`'a yazılır. Açılamazsa çağıran evdeki motora döner (`motor_sec`).
"""

import json
import subprocess
import time
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from yanki import dosya, motor, runpod
from yanki.ayarlar import Ayarlar

UZAK_DIZIN = "/root/is"


class ButceYok(runpod.RunPodHatasi):
    pass


def harcama_yolu(kok: Path) -> Path:
    return kok / "calisma" / "gunluk" / "runpod.json"


def bu_ay_harcama(kok: Path, simdi: datetime | None = None) -> float:
    ay = (simdi or datetime.now()).strftime("%Y-%m")
    try:
        kayit = json.loads(harcama_yolu(kok).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0.0
    return round(sum(x.get("usd", 0) for x in kayit if str(x.get("zaman", "")).startswith(ay)), 3)


def harcama_yaz(kok: Path, kayit: dict) -> None:
    yol = harcama_yolu(kok)
    try:
        liste = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        liste = []
    dosya.json_yaz(yol, [*liste, kayit][-500:], indent=1)


def butce_kontrol(a: Ayarlar, api_anahtari: str, bakiye: Callable[[str], float] = runpod.bakiye) -> float:
    harcanan = bu_ay_harcama(a.kok)
    if harcanan >= a.uzak.aylik_butce:
        raise ButceYok(f"bu ay {harcanan:.2f} $ harcandı (sınır {a.uzak.aylik_butce:.2f} $)")
    b = bakiye(api_anahtari)
    if b < a.uzak.en_az_bakiye:
        raise ButceYok(f"RunPod bakiyesi {b:.2f} $ (en az {a.uzak.en_az_bakiye:.2f} $): kredi yükle")
    return b


def acestep_commit(a: Ayarlar) -> str:
    """Sunucuya yereldeki ACE-Step commit'i kurulur: aynı kod, sonuçlar karşılaştırılabilir."""
    return subprocess.run(["git", "-C", str(a.motor.klasor), "rev-parse", "--short", "HEAD"], capture_output=True,
                          text=True, check=True).stdout.strip()


def isci_kos(p: runpod.Pod, hedef: str, zaman_asimi_sn: float, aralik_sn: float = 20) -> list[dict]:
    """İşçiyi arka planda başlatır (SSH kopsa da sürer), bitene kadar bekler; sonuç listesini döner. Süreç pid
    dosyasından izlenir: `pgrep -f motor_isci.py` kendi `bash -lc` satırını eşleştirip hep "sürüyor" diyordu (S19)."""
    p.komut(f"cd {hedef} && export PATH=$HOME/.local/bin:$PATH ACESTEP_GENERATION_TIMEOUT=3600 PYTHONUTF8=1 && "
            f"nohup uv run python {UZAK_DIZIN}/motor_isci.py {UZAK_DIZIN}/motor_is.json {UZAK_DIZIN}/motor_sonuc.json "
            f"> {UZAK_DIZIN}/motor.log 2>&1 & echo $! > {UZAK_DIZIN}/motor.pid", tekrar=False)
    bitis = time.monotonic() + zaman_asimi_sn
    sonuc: list[dict] = []
    while time.monotonic() < bitis:
        time.sleep(aralik_sn)
        cikti = p.komut(f"cat {UZAK_DIZIN}/motor_sonuc.json 2>/dev/null || echo '[]'; echo; echo '#DURUM#'; "
                        f"kill -0 $(cat {UZAK_DIZIN}/motor.pid) 2>/dev/null && echo SURUYOR || echo BITTI")
        govde, hal = cikti.split("#DURUM#")
        try:
            sonuc = json.loads(govde.strip() or "[]")
        except ValueError:  # işçi o an yazıyor
            continue
        if hal.strip() == "BITTI":
            return sonuc
    p.komut(f"kill $(cat {UZAK_DIZIN}/motor.pid) 2>/dev/null || true")
    return sonuc


def calistir(a: Ayarlar, isler: list[motor.Is], klasor: Path, zaman_asimi_sn: float, gpu_bekleme_sn: float = 0,
             pod_sinifi=runpod.Pod, kur=runpod.acestep_kur, commit: str | None = None,
             bakiye: Callable[[str], float] = runpod.bakiye, kapat=runpod.kapat_artiklari) -> list[motor.Sonuc]:
    """`motor.calistir` ile aynı sözleşme: işlerin sonuçları (yerel çıktı yollarıyla). `gpu_bekleme_sn` yok sayılır
    (sunucunun GPU'su bizim). Bütçe yoksa ya da pod açılamazsa `RunPodHatasi` (çağıran evdeki motora döner)."""
    if not isler:
        return []
    api = runpod.anahtar(a.kok)
    butce_kontrol(a, api, bakiye)
    # önceki koşudan açık kalan pod (bilgisayar koşu ortasında kapandı/uyudu) saatlik yanmasın: bu koşu kilitli, başka
    # bir koşunun pod'u olamaz
    if artik := kapat(api, a.kok / "calisma" / ".runpod"):
        print(f"önceki koşudan açık kalan pod silindi: {', '.join(artik)}")
    klasor = klasor.resolve()
    klasor.mkdir(parents=True, exist_ok=True)
    commit = commit or acestep_commit(a)
    # girdi sesleri: aynı dosya bir kez gider (aynı şarkının adayları aynı kaynağı kullanır)
    girdiler: dict[str, str] = {}
    for i in isler:
        for yol in (i.kaynak, i.referans):
            if yol and yol not in girdiler:
                girdiler[yol] = f"{UZAK_DIZIN}/girdi/{len(girdiler)}{Path(yol).suffix}"
    kayit: dict = {"zaman": datetime.now().isoformat(timespec="seconds"), "is": len(isler), "gpu": a.uzak.gpu}
    sonuclar: list[motor.Sonuc] = []
    pod = None
    try:
        with pod_sinifi(a.kok, gpu=a.uzak.gpu, ad="yanki-motor") as p:
            pod = p
            kayit["pod"] = p.id
            t = time.time()
            hedef = kur(p, commit, (a.motor.model,))
            kayit["kurulum_sn"] = round(time.time() - t)
            p.komut(f"mkdir -p {UZAK_DIZIN}/girdi {UZAK_DIZIN}/cikti")
            for yerel, uzak in girdiler.items():
                p.gonder(Path(yerel), uzak)
            p.gonder(motor.ISCI, f"{UZAK_DIZIN}/motor_isci.py")
            uzak_isler = []
            for n, i in enumerate(isler):
                d = {**i.__dict__, "kaynak": girdiler[i.kaynak], "referans": girdiler.get(i.referans or ""),
                     "cikti_klasor": f"{UZAK_DIZIN}/cikti/{n}", "bolge": list(i.bolge) if i.bolge else None}
                uzak_isler.append(d)
            is_yolu = klasor / "motor_is.json"
            dosya.json_yaz(is_yolu, {"motor": {
                "klasor": hedef, "model": a.motor.model, "niceleme": None, "cpu_offload": False,
                "dit_offload": False, "lm_model": a.motor.lm_model, "lm_backend": a.motor.lm_backend},
                "isler": uzak_isler})
            p.gonder(is_yolu, f"{UZAK_DIZIN}/motor_is.json")
            t = time.time()
            ham = isci_kos(p, hedef, zaman_asimi_sn)
            kayit["uretim_sn"] = round(time.time() - t)
            try:
                p.al(f"{UZAK_DIZIN}/motor.log", klasor / "motor.log")
            except (subprocess.SubprocessError, OSError):
                pass
            yerel_is = {i.id: i for i in isler}
            for r in ham:
                if r.get("id") is None or r["id"] not in yerel_is:
                    continue
                if r.get("basari") and r.get("cikti"):
                    hedef_yol = Path(yerel_is[r["id"]].cikti_klasor) / Path(r["cikti"]).name
                    try:
                        r["cikti"] = str(p.al(r["cikti"], hedef_yol))
                    except (subprocess.SubprocessError, OSError) as e:
                        r.update(basari=False, hata=f"çıktı indirilemedi: {e}", cikti=None)
                sonuclar.append(motor.Sonuc(**{k: r.get(k) for k in motor.Sonuc.__dataclass_fields__}))
    except Exception as e:
        kayit["hata"] = f"{type(e).__name__}: {str(e)[:300]}"
        raise
    finally:
        # hata olsa da açık kalınan süre ödendi: bütçe hesabı eksik kalmasın (önce düşen koşuya 0 $ yazılıyordu)
        kayit["usd"] = pod.maliyet() if pod is not None else 0.0
        kayit["basarili"] = sum(s.basari for s in sonuclar)
        harcama_yaz(a.kok, kayit)
    gelen = {s.id for s in sonuclar}
    return sonuclar + [motor.Sonuc(i.id, False, "uzak işçi sonuç yazmadı") for i in isler if i.id not in gelen]


# sunucu koşu ortasında düşerse bu kadar saat yeniden denenmez (evde üretim kapalıysa üretim o kadar bekler; tek bir
# geçici bağlantı kopması 3 saat üretimsiz bırakıyordu)
DURMA_SAAT = 1


def durma_yolu(kok: Path) -> Path:
    return kok / "calisma" / ".uzak_durdu"


def motor_sec(a: Ayarlar, kayit: Callable[[str], None] = print, stok=runpod.stok,
              bakiye: Callable[[str], float] = runpod.bakiye
              ) -> tuple[Callable[..., list[motor.Sonuc]] | None, float, bool]:
    """Üretimin motoru ve tek parça eşiği, işler planlanmadan önce: uzak açık, son 3 saatte düşmemiş, anahtar ve
    bütçe yerinde, GPU stokta ise sunucu (tek parça); değilse evdeki kart (INT8, parçalı). Karar sonradan değişmez:
    sunucu için tek parça planlanan iş evde 8 GB'a ve motorun iç zaman aşımına sığmaz. Sunucu koşu ortasında düşerse
    hata yükselir (şarkılar sırada kalır) ve uzak motor `DURMA_SAAT` devre dışı kalır.
    Dönen: (calistir, tek_parca_sn, uzak_mi); calistir None: sunucu yok ve evde üretim kapalı (`yerel_yedek`)."""
    from yanki import uretim

    yerel = (motor.calistir, uretim.TEK_PARCA_SN, False)
    if not a.uzak.acik:
        return yerel
    # sunucu yoksa: evde üretim açıksa evdeki kart, kapalıysa üretim yok (çağıran bekler)
    yedek = yerel if a.uzak.yerel_yedek else (None, uretim.TEK_PARCA_SN, False)
    nerede = "üretim evde" if a.uzak.yerel_yedek else "üretim sunucu açılabilene kadar bekliyor"
    durdu = durma_yolu(a.kok)
    if durdu.exists() and time.time() - durdu.stat().st_mtime < DURMA_SAAT * 3600:
        kayit(f"uzak GPU {DURMA_SAAT} saat devre dışı ({durdu.read_text(encoding='utf-8')[:200]}); {nerede}")
        return yedek
    try:
        api = runpod.anahtar(a.kok)
        butce_kontrol(a, api, bakiye)
        if (durum_ := stok(api, a.uzak.gpu)) in (None, "None", "Low"):
            raise runpod.RunPodHatasi(f"{a.uzak.gpu} stok: {durum_}")
    except (runpod.RunPodHatasi, OSError) as e:
        kayit(f"uzak GPU kullanılmıyor ({e}); {nerede}")
        return yedek

    def uzak_calistir(a_, isler, klasor, zaman_asimi_sn, **_k):
        try:
            return calistir(a_, isler, klasor, zaman_asimi_sn)
        except (runpod.RunPodHatasi, OSError, subprocess.SubprocessError) as e:
            dosya.yaz(durma_yolu(a_.kok), f"{datetime.now():%Y-%m-%d %H:%M} {type(e).__name__}: {e}")
            raise

    return uzak_calistir, a.uzak.tek_parca_sn, True
