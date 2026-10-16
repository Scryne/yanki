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
from datetime import datetime, timedelta
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


HARCAMA_EN_AZ_KAYIT = 500


def _harcama_kirp(liste: list[dict], simdi: datetime | None = None) -> list[dict]:
    """Eski kayıtlar atılır ama bu ayın ve geçen ayın hepsi kalır: önce düz son 500 kayıt tutuluyordu; stok yokken
    her 30 dk'da bir 0 $'lık deneme yazılırsa ayın başındaki ödemeler düşer, aylık bütçe eksik görünürdü."""
    simdi = simdi or datetime.now()
    gecen_ay = (simdi.replace(day=1) - timedelta(days=1)).strftime("%Y-%m")
    if len(liste) <= HARCAMA_EN_AZ_KAYIT:
        return liste
    bas = len(liste) - HARCAMA_EN_AZ_KAYIT
    return [x for i, x in enumerate(liste) if i >= bas or str(x.get("zaman", ""))[:7] >= gecen_ay]


def harcama_yaz(kok: Path, kayit: dict) -> None:
    """Kilitli oku-ekle-yaz: eğitim pod'u ile üretim pod'u aynı anda bitip birbirinin kaydını ezmesin."""
    from yanki import kilit

    yol = harcama_yolu(kok)
    yol.parent.mkdir(parents=True, exist_ok=True)
    with kilit.bekleyerek(yol.with_name(".runpod.kilit")):
        try:
            liste = json.loads(yol.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            liste = []
        dosya.json_yaz(yol, _harcama_kirp([*liste, kayit]), indent=1)


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


def baslatma_betigi(hedef: str, dizin: str = UZAK_DIZIN) -> str:
    """İşçiyi arka planda başlatan kabuk betiği; SSH komutu hemen döner.

    Arka plana yalnız işçi komutu gider (`;` ile ayrı). Önce `cd … && export … && setsid … &` idi: `&` bütün `&&`
    zincirini arka plana atıyor, zinciri koşan alt kabuk SSH'ın stdout/stderr'ini işçi bitene kadar açık tutuyor, SSH
    kanalı kapanmıyordu. Her uzak koşuda başlatma 120 sn'de zaman aşımına düşüyor, iş yalnız pid yoklamasıyla
    sürüyordu (2026-10-10, runpod.log'da beş koşunun beşi). `setsid` yoksa (test kabuğu) yalnız `nohup`."""
    return (f"cd {hedef} || exit 1; export PATH=$HOME/.local/bin:$PATH ACESTEP_GENERATION_TIMEOUT=3600 PYTHONUTF8=1; "
            f"$(command -v setsid) nohup uv run python {dizin}/motor_isci.py {dizin}/motor_is.json "
            f"{dizin}/motor_sonuc.json > {dizin}/motor.log 2>&1 < /dev/null & "
            f"echo $! > {dizin}/motor.pid")


# İşçinin günlüğü (ACE-Step adım çubuğu, indirme) ve biten iş sayısı bu kadar süre hiç değişmezse işçi takılmış sayılır
# ve durdurulur. Zaman aşımı iş başına 15 dk × iş sayısı (40 iş = 10 saat): asılı bir CUDA/indirme A40'ı o kadar boşa
# yakardı (~4,4 $). Evdeki motorun 20 dk ilerlemesizlik sınırının uzaktaki karşılığı.
SESSIZ_SN = 1800


def isci_kos(p: runpod.Pod, hedef: str, zaman_asimi_sn: float, aralik_sn: float = 20, toplam: int | None = None,
             bildir: Callable[[str], None] = print, sessiz_sn: float = SESSIZ_SN) -> list[dict]:
    """İşçiyi arka planda başlatır (SSH kopsa da sürer), bitene kadar bekler; sonuç listesini döner. Süreç pid
    dosyasından izlenir: `pgrep -f motor_isci.py` kendi `bash -lc` satırını eşleştirip hep "sürüyor" diyordu (S19).
    Biten iş sayısı değiştikçe bir satır yazılır (günlükte saatlik koşunun nerede olduğu görünsün). Günlük ve sonuç
    `sessiz_sn` boyunca değişmezse işçi durdurulur, o ana kadarki sonuçlar döner."""
    try:
        p.komut(baslatma_betigi(hedef), tekrar=False)
    except runpod.RunPodHatasi:
        # komut kanalı koptu ama işçi başlamış olabilir: başlamadıysa hata, başladıysa izlemeye devam (iki kez başlatma)
        if "VAR" not in p.komut(f"kill -0 $(cat {UZAK_DIZIN}/motor.pid 2>/dev/null) 2>/dev/null && echo VAR || "
                                "echo YOK"):
            raise
    bitis, bas = time.monotonic() + zaman_asimi_sn, time.monotonic()
    sonuc: list[dict] = []
    iz, son_degisim = None, time.monotonic()
    while time.monotonic() < bitis:
        time.sleep(aralik_sn)
        try:
            cikti = p.komut(f"cat {UZAK_DIZIN}/motor_sonuc.json 2>/dev/null || echo '[]'; echo; echo '#DURUM#'; "
                            f"kill -0 $(cat {UZAK_DIZIN}/motor.pid) 2>/dev/null && echo SURUYOR || echo BITTI; "
                            f"echo '#GUNLUK#'; stat -c %s {UZAK_DIZIN}/motor.log 2>/dev/null || echo 0")
        except runpod.RunPodHatasi as e:
            # evdeki ağ koptu (2026-10-14, S33: ~10 dk "No route to host"); işçi podda sürüyor, yoklamaya devam
            bildir(f"  yoklama kopuk: {str(e)[-120:]}")
            continue
        govde, ayrac, hal = cikti.partition("#DURUM#")
        if not ayrac:  # yarım çıktı (bağlantı çıktı ortasında kesildi): işçi sürüyor, kopuk yoklama gibi
            bildir("  yoklama yarım geldi")
            continue
        hal, _, gunluk = hal.partition("#GUNLUK#")
        if (yeni_iz := (len(govde), gunluk.strip())) != iz:
            iz, son_degisim = yeni_iz, time.monotonic()
        elif time.monotonic() - son_degisim >= sessiz_sn:
            bildir(f"  uzak motor {sessiz_sn / 60:.0f} dk'dır ilerlemiyor (günlük ve sonuç aynı): durduruluyor")
            break
        try:
            yeni = json.loads(govde.strip() or "[]")
        except ValueError:  # işçi o an yazıyor
            continue
        if toplam and len(yeni) != len(sonuc):
            hatali = sum(not x.get("basari") for x in yeni)
            bildir(f"  uzak motor: {len(yeni)}/{toplam} iş bitti ({(time.monotonic() - bas) / 60:.0f} dk"
                   + (f", {hatali} hatalı" if hatali else "") + ")")
        sonuc = yeni
        if hal.strip() == "BITTI":
            return sonuc
    try:
        p.komut(f"kill $(cat {UZAK_DIZIN}/motor.pid) 2>/dev/null || true")
    except runpod.RunPodHatasi:
        pass  # pod zaten silinecek
    return sonuc


POD_DENEME = 2  # hazır olmayan pod silinip başka bir makinede yeniden denenir


class PodAcici:
    """Hazır (SSH'a açık) bir pod; açılamazsa silinip `POD_DENEME` kez yeniden (başka makine). Açılan her pod
    `acilan`'a eklenir: hazır olmayanın süresi de ödendi."""

    def __init__(self, a: Ayarlar, pod_sinifi, acilan: list, gpu: str | None = None, **pod_ayar):
        self.a, self.pod_sinifi, self.acilan, self.pod = a, pod_sinifi, acilan, None
        self.gpu, self.pod_ayar = gpu or a.uzak.gpu, pod_ayar or {"ad": "yanki-motor"}

    def __enter__(self):
        son: Exception | None = None
        for _ in range(POD_DENEME):
            aday = self.pod_sinifi(self.a.kok, gpu=self.gpu, **self.pod_ayar)
            self.acilan.append(aday)
            try:
                self.pod = aday.__enter__()  # hazır olmazsa kendi __exit__'iyle silinir
                return self.pod
            except runpod.RunPodHatasi as e:
                son = e
                print(f"pod hazır olmadı, yeniden deneniyor: {e}")
        raise son or runpod.RunPodHatasi("pod açılamadı")

    def __exit__(self, *bilgi):
        if self.pod is not None:
            self.pod.__exit__(*bilgi)


def calistir(a: Ayarlar, isler: list[motor.Is], klasor: Path, zaman_asimi_sn: float, gpu_bekleme_sn: float = 0,
             pod_sinifi=runpod.Pod, kur=runpod.acestep_kur, commit: str | None = None,
             bakiye: Callable[[str], float] = runpod.bakiye, kapat=runpod.kapat_artiklari) -> list[motor.Sonuc]:
    """`motor.calistir` ile aynı sözleşme: işlerin sonuçları (yerel çıktı yollarıyla). `gpu_bekleme_sn` yok sayılır
    (sunucunun GPU'su bizim). Bütçe yoksa ya da pod açılamazsa `RunPodHatasi` (çağıran evdeki motora döner)."""
    if not isler:
        return []
    api = runpod.anahtar(a.kok, a.uzak.en_az_bakiye, bakiye)
    butce_kontrol(a, api, bakiye)
    # önceki koşudan açık kalan pod (bilgisayar koşu ortasında kapandı/uyudu) saatlik yanmasın: bu koşu kilitli, başka
    # bir koşunun pod'u olamaz. Her hesapta bakılır (pod önceki koşuda öbür hesapta açılmış olabilir).
    if artik := [p for k in dict.fromkeys([api, *runpod.anahtarlar(a.kok)])
                 for p in kapat(k, a.kok / "calisma" / ".runpod", harcama=lambda r: harcama_yaz(a.kok, r))]:
        print(f"önceki koşudan açık kalan pod silindi: {', '.join(artik)}")
    klasor = klasor.resolve()
    klasor.mkdir(parents=True, exist_ok=True)
    commit = commit or acestep_commit(a)
    # girdi sesleri: aynı dosya bir kez gider (aynı şarkının adayları aynı kaynağı kullanır)
    girdiler: dict[str, str] = {}
    for i in isler:
        for yol in (i.kaynak, i.referans, i.puanlanan):
            if yol and yol not in girdiler:
                girdiler[yol] = f"{UZAK_DIZIN}/girdi/{len(girdiler)}{Path(yol).suffix}"
    kayit: dict = {"zaman": datetime.now().isoformat(timespec="seconds"), "is": len(isler), "gpu": a.uzak.gpu}
    sonuclar: list[motor.Sonuc] = []
    ham: list[dict] = []
    acilan: list = []  # açılan her pod (hazır olmayan dahil): maliyeti kayda
    try:
        with PodAcici(a, pod_sinifi, acilan) as p:
            kayit["pod"] = p.id
            t = time.time()
            hedef = kur(p, commit, (a.motor.model,))
            kayit["kurulum_sn"] = round(time.time() - t)
            p.komut(f"mkdir -p {UZAK_DIZIN}/girdi {UZAK_DIZIN}/cikti")
            for yerel, uzak in girdiler.items():
                p.gonder(Path(yerel), uzak)
            p.gonder(motor.ISCI, f"{UZAK_DIZIN}/motor_isci.py")
            if a.motor.lora is not None:  # eğitilmiş LoRA (yanki/egitim.py): bağdaştırıcı dosyaları
                p.komut(f"mkdir -p {UZAK_DIZIN}/lora")
                for f in ("adapter_config.json", "adapter_model.safetensors"):
                    p.gonder(a.motor.lora / f, f"{UZAK_DIZIN}/lora/{f}")
            uzak_isler = []
            for n, i in enumerate(isler):
                d = {**i.__dict__, "kaynak": girdiler[i.kaynak], "referans": girdiler.get(i.referans or ""),
                     "puanlanan": girdiler.get(i.puanlanan or ""),
                     "cikti_klasor": f"{UZAK_DIZIN}/cikti/{n}", "bolge": list(i.bolge) if i.bolge else None}
                uzak_isler.append(d)
            is_yolu = klasor / "motor_is.json"
            dosya.json_yaz(is_yolu, {"motor": {
                "klasor": hedef, "model": a.motor.model, "niceleme": None, "cpu_offload": False,
                "dit_offload": False, "lm_model": a.motor.lm_model, "lm_backend": a.motor.lm_backend,
                **({"vae": a.motor.vae} if a.motor.vae else {}),
                **({"lora": f"{UZAK_DIZIN}/lora", "lora_olcek": a.motor.lora_olcek} if a.motor.lora else {})},
                "isler": uzak_isler})
            p.gonder(is_yolu, f"{UZAK_DIZIN}/motor_is.json")
            t = time.time()
            ham = isci_kos(p, hedef, zaman_asimi_sn, toplam=len(uzak_isler))
            kayit["uretim_sn"] = round(time.time() - t)
            dosya.json_yaz(klasor / "motor_sonuc.json", ham)  # ham işçi kaydı (puanlar, süreler) yerelde de kalsın
            try:
                p.al(f"{UZAK_DIZIN}/motor.log", klasor / "motor.log")
            except (runpod.RunPodHatasi, subprocess.SubprocessError, OSError):
                pass
            yerel_is = {i.id: i for i in isler}
            for r in ham:
                if r.get("id") is None or r["id"] not in yerel_is:
                    continue
                if r.get("basari") and r.get("cikti"):
                    hedef_yol = Path(yerel_is[r["id"]].cikti_klasor) / Path(r["cikti"]).name
                    try:
                        r["cikti"] = str(p.al(r["cikti"], hedef_yol))
                    except (runpod.RunPodHatasi, subprocess.SubprocessError, OSError) as e:
                        r.update(basari=False, hata=f"çıktı indirilemedi: {e}", cikti=None)
                sonuclar.append(motor.Sonuc.okunan(r))
    except Exception as e:
        kayit["hata"] = f"{type(e).__name__}: {str(e)[:300]}"
        raise
    finally:
        # hata olsa da açık kalınan süre ödendi: bütçe hesabı eksik kalmasın (önce düşen koşuya 0 $ yazılıyordu)
        kayit["usd"] = round(sum(x.maliyet() for x in acilan), 3)
        kayit.setdefault("pod", ",".join(str(x.id) for x in acilan if x.id) or None)
        kayit["basarili"] = sum(s.basari for s in sonuclar)
        harcama_yaz(a.kok, kayit)
    gelen = {s.id for s in sonuclar}
    # işçinin genel hatası (model/LoRA yüklenemedi) sonuçsuz kalan işlere: "sonuç yazmadı" nedenini söylemiyordu
    genel = next((r.get("hata") for r in reversed(ham) if r.get("id") is None and r.get("hata")), None)
    return sonuclar + [motor.Sonuc(i.id, False, genel or "uzak işçi sonuç yazmadı") for i in isler if i.id not in gelen]


def artik_temizle(kok: Path, kapat=runpod.kapat_artiklari) -> list[str]:
    """Her koşunun başında, iş olsun olmasın: açık kalmış üretim ve eğitim pod'ları (önce yalnız üretim işi varken ve
    bütçe yerindeyken bakılıyordu; kuyruk boşsa ya da artık pod bütçeyi doldurduysa pod bakiye bitene kadar yanardı).
    Eğitim pod'u da: eğitim ortasında kapanan bilgisayarın pod'u yalnız bir sonraki `yanki egit`te siliniyordu (günlerce
    yanabilirdi). Sahibi yaşayan pod'a (süren eğitim, deney) dokunulmaz (`runpod.kapat_artiklari`). Dönen: silinenler;
    hata günlüğe, koşu sürer."""
    from yanki import egitim

    silinen = []
    for k in runpod.anahtarlar(kok):
        for kayit_adi, on_ek in (("acik_pod", "yanki-"), (egitim.POD_KAYIT, "egitim-")):
            try:
                silinen += kapat(k, kok / "calisma" / ".runpod", kayit_adi, on_ek,
                                 harcama=lambda r: harcama_yaz(kok, r))
            except (runpod.RunPodHatasi, OSError) as e:
                print(f"kiralık GPU artık denetimi yapılamadı: {e}")
                break  # bu hesapta ikinci sorgu da düşer
    return silinen


# sunucu koşu ortasında düşerse bu kadar saat yeniden denenmez (evde üretim kapalıysa üretim o kadar bekler; tek bir
# geçici bağlantı kopması 3 saat üretimsiz bırakıyordu)
DURMA_SAAT = 1


def durma_yolu(kok: Path) -> Path:
    return kok / "calisma" / ".uzak_durdu"


# Üretimin kiralık GPU'yu açamadığı son neden (bakiye, aylık sınır, stok, ağ, devre dışı): pano, `yanki durum` ve
# `yanki ozet` ağa çıkmadan gösterir. Sürekli koşu 30 dk'da bir yazar; bu kadar eski kayıt bayat sayılır.
ENGEL_GECERLI_SAAT = 2


def engel_yolu(kok: Path) -> Path:
    return kok / "calisma" / ".uretim_engeli.json"


def _engel_yaz(kok: Path, tur: str, neden: str) -> None:
    try:
        dosya.yaz(engel_yolu(kok), json.dumps({"tur": tur, "neden": neden,
                                               "zaman": datetime.now().isoformat(timespec="seconds")},
                                              ensure_ascii=False))
    except OSError:
        pass  # gösterim için; üretim kararını etkilemez


def uretim_engeli(calisma: Path) -> dict | None:
    """Üretimi bekleten son kiralık GPU engeli ({"tur", "neden", "zaman"}); yoksa ya da bayatsa None. Ağa çıkmaz."""
    yol = calisma / engel_yolu(Path()).name
    try:
        if time.time() - yol.stat().st_mtime > ENGEL_GECERLI_SAAT * 3600:
            return None
        e = json.loads(yol.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return e if isinstance(e, dict) and e.get("neden") else None


def ag_engeli_bildir(kok: Path, neden: str) -> None:
    """SSH'ı kapatan ağ günde bir bildirilir (sürekli koşu her 30 dk'da yeniden bildirmesin)."""
    from yanki import olay

    olay.bildir(kok / "calisma", "kayip", "üretim bekliyor: ağ SSH'a kapalı",
                f"{neden}. Kiralık GPU açılmadı (ücret yok); 22 ve 22xxx portlarına açık bir ağa geçince üretim "
                "kendiliğinden sürer.", f"ag-ssh:{datetime.now():%Y-%m-%d}")


def butce_yok_bildir(kok: Path, neden: str) -> None:
    """Bakiye bitti ya da aylık sınır doldu: günde bir bildirilir. Önce yalnız günlüğe yazılıyordu; 2026-10-16'da
    bakiye 0,80 $'da kaldı, 50 şarkı bütün gün sessizce bekledi."""
    from yanki import olay

    olay.bildir(kok / "calisma", "kayip", "üretim bekliyor: kiralık GPU bütçesi",
                f"{neden}. Kiralık GPU açılmıyor; RunPod'a kredi yükleyince (ya da config/motor.toml → [uzak] sınırı) "
                "üretim kendiliğinden sürer.", f"gpu-butce:{datetime.now():%Y-%m-%d}")


def motor_sec(a: Ayarlar, kayit: Callable[[str], None] = print, stok=runpod.stok,
              bakiye: Callable[[str], float] = runpod.bakiye, ssh_engeli: Callable[[], str | None] | None = None,
              ag_bildir: Callable[[Path, str], None] = ag_engeli_bildir,
              butce_bildir: Callable[[Path, str], None] = butce_yok_bildir
              ) -> tuple[Callable[..., list[motor.Sonuc]] | None, float, bool]:
    """Üretimin motoru ve tek parça eşiği, işler planlanmadan önce: uzak açık, son 3 saatte düşmemiş, ağ SSH'a açık,
    anahtar ve bütçe yerinde, GPU stokta ise sunucu (tek parça); değilse evdeki kart (INT8, parçalı). Karar sonradan
    değişmez: sunucu için tek parça planlanan iş evde 8 GB'a ve motorun iç zaman aşımına sığmaz. Sunucu koşu
    ortasında düşerse hata yükselir (şarkılar sırada kalır) ve uzak motor `DURMA_SAAT` devre dışı kalır.
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
        neden = durdu.read_text(encoding="utf-8")[:200]
        kayit(f"uzak GPU {DURMA_SAAT} saat devre dışı ({neden}); {nerede}")
        _engel_yaz(a.kok, "durdu", f"sunucu düştü, {DURMA_SAAT} saat devre dışı ({neden})")
        return yedek
    if engel := (ssh_engeli or runpod.ssh_engeli)():
        kayit(f"uzak GPU kullanılmıyor ({engel}); {nerede}")
        ag_bildir(a.kok, engel)
        _engel_yaz(a.kok, "ag", engel)
        return yedek
    try:
        api = runpod.anahtar(a.kok, a.uzak.en_az_bakiye, bakiye)
        butce_kontrol(a, api, bakiye)
        # "Low" da denenir (2026-10-12: A40 saatlerce Low kaldı, üretim hiç başlamadı); açılamazsa ücret yok
        if (durum_ := stok(api, a.uzak.gpu)) in (None, "None"):
            raise runpod.RunPodHatasi(f"{a.uzak.gpu} stok: {durum_}")
    except (runpod.RunPodHatasi, OSError) as e:
        kayit(f"uzak GPU kullanılmıyor ({e}); {nerede}")
        if isinstance(e, ButceYok):
            butce_bildir(a.kok, str(e))
        _engel_yaz(a.kok, "butce" if isinstance(e, ButceYok) else "sunucu", str(e))
        return yedek
    engel_yolu(a.kok).unlink(missing_ok=True)

    def uzak_calistir(a_, isler, klasor, zaman_asimi_sn, **_k):
        try:
            return calistir(a_, isler, klasor, zaman_asimi_sn)
        except runpod.StokYok:
            raise  # pod açılmadı: şarkılar sırada kalır, sonraki koşu yine dener (devre dışı bırakılmaz)
        except (runpod.RunPodHatasi, OSError, subprocess.SubprocessError) as e:
            dosya.yaz(durma_yolu(a_.kok), f"{datetime.now():%Y-%m-%d %H:%M} {type(e).__name__}: {e}")
            raise

    return uzak_calistir, a.uzak.tek_parca_sn, True
