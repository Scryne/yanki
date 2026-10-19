"""`yanki durum`: hattın çalışması için gerekenler yerinde mi."""

import shutil
import subprocess
from dataclasses import dataclass

from yanki.ayarlar import Ayarlar


@dataclass(frozen=True)
class Kontrol:
    ad: str
    tamam: bool
    ayrinti: str


def gpu_kullanilan_mib() -> int | None:
    """nvidia-smi'den kullanılan VRAM; GPU ya da sürücü yoksa None."""
    if not shutil.which("nvidia-smi"):
        return None
    try:
        cikti = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.used", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=15, check=True,
        ).stdout
        return int(cikti.strip().splitlines()[0])
    except (subprocess.SubprocessError, ValueError, IndexError):
        return None


def _arac_kontrol(ad: str) -> Kontrol:
    """Hattın kullandığı yolla (`ses.arac`: PATH, yoksa winget kurulum yeri); yalnız PATH'e bakınca winget'le
    kurulmuş ffmpeg yeni kabuk açılana kadar ✗ görünüyordu, oysa hat onu buluyordu."""
    from yanki import ses

    try:
        return Kontrol(ad, True, ses.arac(ad))
    except FileNotFoundError as e:
        return Kontrol(ad, False, str(e))


def kontroller(a: Ayarlar) -> list[Kontrol]:
    sonuc = [
        Kontrol("motor venv", a.motor.python.exists(), str(a.motor.python)),
        Kontrol(f"model {a.motor.model}", (a.motor.checkpoints / a.motor.model).is_dir(),
                str(a.motor.checkpoints / a.motor.model)),
        Kontrol("VAE", (a.motor.checkpoints / "vae").is_dir(), str(a.motor.checkpoints / "vae")),
        _arac_kontrol("ffmpeg"),
        _arac_kontrol("ffprobe"),
        Kontrol("fpcalc", a.fpcalc.exists(), str(a.fpcalc)),
    ]
    if a.motor.lora is not None:
        yol = a.motor.lora.relative_to(a.kok) if a.motor.lora.is_relative_to(a.kok) else a.motor.lora
        sonuc.append(Kontrol("LoRA", (a.motor.lora / "adapter_config.json").is_file(),
                             f"{yol.as_posix()} (ölçek {a.motor.lora_olcek:g})"))
    sonuc += [*anahtar_kontrolleri(a), disk_kontrolu(a)]
    from yanki import sistem

    if gorevler := sistem.gorev_durumlari():  # kurulu değilse (CI, başka makine) satır yok
        kapali = sistem.kapali_gorevler(gorevler)
        sonuc.append(Kontrol("otomatik koşu", not kapali, f"{', '.join(kapali)} devre dışı (Görev Zamanlayıcı → Yanki)"
                             if kapali else ", ".join(f"{k} {v}" for k, v in sorted(gorevler.items()))))
    if a.uzak.acik:
        sonuc.append(uzak_kontrolu(a))
    kullanilan = gpu_kullanilan_mib()
    # evde üretim kapalıyken (kiralık GPU, yerel_yedek = false) evdeki kartın dolu olması hattı durdurmaz: bilgi
    # satırı; önce oyun açıkken `yanki durum` hep 1 dönüp ✗ gösteriyordu
    evde = not (a.uzak.acik and not a.uzak.yerel_yedek)
    ek = "" if evde else " (evde üretim kapalı, üretim kiralık GPU'da)"
    if kullanilan is None:
        sonuc.append(Kontrol("GPU", not evde, "nvidia-smi okunamadı" + ek))
    else:
        bos = kullanilan < a.gpu.bos_esik_mib
        sonuc.append(Kontrol("GPU boş", bos or not evde,
                             f"{kullanilan} MiB kullanımda (eşik {a.gpu.bos_esik_mib})" + ek))
    return sonuc


DISK_EN_AZ_GB = 20  # şarkı başı ~300–450 MB ara ses; gece iki şarkıyla haftada ~6 GB (temizlik yüklenince ve retten
# sonra siler)


def disk_kontrolu(a: Ayarlar) -> Kontrol:
    bos = shutil.disk_usage(a.kok).free / 1e9
    return Kontrol("disk", bos >= DISK_EN_AZ_GB, f"{bos:,.0f} GB boş (en az {DISK_EN_AZ_GB})")


def uzak_kontrolu(a: Ayarlar) -> Kontrol:
    """Kiralık GPU'nun bu ayki harcaması (yerel kayıttan, ağa çıkmaz) ve devre dışı olup olmadığı. Sınır dolunca ya
    da sunucu düşünce üretim durur; `yanki durum` bunu göstermiyordu."""
    import time

    from yanki import uzak

    harcanan = uzak.bu_ay_harcama(a.kok)
    durdu = uzak.durma_yolu(a.kok)
    if durdu.exists() and time.time() - durdu.stat().st_mtime < uzak.DURMA_SAAT * 3600:
        return Kontrol("kiralık GPU", False, f"devre dışı ({durdu.read_text(encoding='utf-8')[:120]})")
    if e := uzak.uretim_engeli(a.kok / "calisma"):  # son koşu sunucuyu açamadı (bakiye, stok, ağ): üretim bekliyor
        return Kontrol("kiralık GPU", False, f"üretim bekliyor: {e['neden'][:160]} · bu ay {harcanan:.2f} $ / "
                                             f"{a.uzak.aylik_butce:.2f} $")
    return Kontrol("kiralık GPU", harcanan < a.uzak.aylik_butce,
                   f"bu ay {harcanan:.2f} $ / {a.uzak.aylik_butce:.2f} $ ({a.uzak.gpu.replace('NVIDIA ', '')})")


def dagitimci_kontrolu(a: Ayarlar, tunearo_anahtari: bool = False) -> Kontrol:
    """Seçili dağıtımcının ön koşulu (ağa çıkmaz). RouteNote: kalıcı tarayıcı profili var mı (oturum bir kez elle;
    düşüp düşmediği ancak sayfa açılınca anlaşılır). Tunearo 2026-10-12'de kapandı: yalnız seçiliyse anahtarına
    bakılır."""
    from yanki import paket, routenote

    try:
        ad = paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").dagitimci
    except (OSError, ValueError, KeyError) as e:
        return Kontrol("dağıtımcı", False, f"config/yayin.toml okunamadı: {e}")
    if ad == "routenote":
        profil = a.kok / "calisma" / routenote.PROFIL
        return Kontrol("RouteNote oturumu", profil.is_dir(),
                       "tarayıcı profili var (oturum düştüyse: yanki routenote giris)" if profil.is_dir()
                       else "profil yok: bir kez `yanki routenote giris`")
    if ad == "tunearo":
        return Kontrol("Tunearo anahtarı", tunearo_anahtari, "yükleme ve durum yoklaması" if tunearo_anahtari
                       else ".env → TUNEARO_API_KEY yok: yükleme otomatik değil")
    return Kontrol("dağıtımcı", True, f"{ad or 'seçilmedi'}: yükleme elle (YUKLE.md)")


def anahtar_kontrolleri(a: Ayarlar) -> list[Kontrol]:
    """Dış servis anahtarları yerinde mi (ağa çıkmaz; değer yazılmaz). Yoksa ilgili adım atlanır, hat yine çalışır."""
    import os

    from yanki import spotify

    # .env'nin tamamı (spotify.env_oku Spotify dışındakileri de okur) + ortam değişkenleri (Tunearo ve TypeSafe orada
    # da olabilir)
    e = {**spotify.env_oku(a.kok),
         **{k: v for k, v in os.environ.items() if k.startswith(("TUNEARO_", "TYPESAFE_", "RUNPOD_", "EPOSTA_"))}}
    var = lambda *adlar: all(e.get(x) for x in adlar)  # noqa: E731
    return [
        dagitimci_kontrolu(a, var("TUNEARO_API_KEY")),
        Kontrol("Spotify anahtarı", var("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET"),
                "keşif doğrulaması ve takip" if var("SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET")
                else ".env → SPOTIFY_CLIENT_ID/SECRET yok: keşif doğrulanmaz, takip yok"),
        Kontrol("TypeSafe anahtarı", var("TYPESAFE_API_KEY"), "keşif özgünlük kararı (Jev)" if var("TYPESAFE_API_KEY")
                else ".env → TYPESAFE_API_KEY yok: özgünlük regex yedeğiyle"),
        Kontrol("e-posta", var("EPOSTA_KULLANICI", "EPOSTA_SIFRE"),
                "RouteNote onay/red e-postaları okunuyor" if var("EPOSTA_KULLANICI", "EPOSTA_SIFRE")
                else ".env → EPOSTA_KULLANICI/EPOSTA_SIFRE yok: RouteNote kararları elle işlenir"),
        *([Kontrol("RunPod anahtarı", var("RUNPOD_API_KEY"), "üretim kiralık GPU'da" if var("RUNPOD_API_KEY")
                   else ".env → RUNPOD_API_KEY yok: kiralık GPU kullanılamaz")] if a.uzak.acik else []),
    ]
