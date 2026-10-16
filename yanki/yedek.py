"""Yedek: hattın yeniden üretilemeyen durumu tek zip'te (Roadmap Faz 13).

Ses yok (adaylar yeniden üretilebilir, paket sesi seçilen adaydan yeniden çıkar; dosya başı onlarca MB), sır yok
(`.env`, Spotify token'ı). Kalan her şey kararların kendisi: şarkı başına `durum.json` (hangi aday seçildi, onarımlar,
yayın takibi), söz dosyaları, paketin `metadata.json`/`YUKLE.md`'si (yükleme bilgisi: UPC, ISRC, yayın tarihi),
Scryne'ın seçtiği kapaklar, keşif kaydı, liste ve ayarlar. Boyut birkaç MB.

Gece koşusu son yedek `gun`'den eskiyse alır, en yeni `sakla` tanesi kalır. Klasör `config/operasyon.toml`'da;
varsayılan `calisma/yedek` aynı diskte (yanlışlıkla silmeye ve bozuk yazıma karşı). Disk arızasına karşı başka bir
disk ya da eşitlenen bir klasör yazılabilir.
"""

import zipfile
from datetime import datetime, timedelta
from pathlib import Path

from yanki.ayarlar import Operasyon

DESENLER = (
    "calisma/*/durum.json",
    "calisma/*/soz.txt",
    "calisma/*/soz_zaman.json",
    "calisma/*/kapak_ozel.jpg",
    "calisma/*/kapak_pinterest.jpg",
    "calisma/*/kapak_kaynak.json",
    "calisma/*/paket/metadata.json",
    "calisma/*/paket/YUKLE.md",
    # yeniden paketlenen şarkının eski paketi: RouteNote'ta açık kalan taslağın UPC'si burada
    "calisma/*/paket_onceki/metadata.json",
    # `yanki bastan` arşivi: geri çekilmiş/yayındaki eski RouteNote yayınlarının UPC/ISRC'si (oda → Sanatçı bunu okur)
    "calisma/_arsiv/*/*/durum.json",
    "calisma/_arsiv/*/*/paket/metadata.json",
    "calisma/_arsiv/*/*/paket/YUKLE.md",
    # odada elle doldurulan yayın taslakları (form + dağıtıcı kayıtları, kapak; ses büyük ve Scryne'da var)
    "calisma/elle/*/metadata.json",
    "calisma/elle/*/kapak.jpg",
    "calisma/eposta/*.json",  # işlenmiş RouteNote e-postaları (karar bir kez uygulanır)
    "calisma/kesif/*.json",
    "calisma/olaylar.jsonl",  # bildirimlerin tekrar anahtarları: geri yüklemede eski olaylar yeniden bildirilmesin
    "calisma/gunluk/runpod.json",  # kiralık GPU harcaması: aylık bütçe sınırı bundan hesaplanıyor
    "girdi/liste.toml",
    "girdi/sozler/*.txt",
    "girdi/kazanc/*",  # RouteNote aylık satış raporları (Scryne'ın indirdiği)
    "girdi/kesif/*.csv",  # STILLMORE ve odadaki Bulucu'nun keşfe gönderdikleri
    "config/*.toml",
)
AD_BICIMI = "yanki-%Y-%m-%d-%H%M%S.zip"


def dosyalar(kok: Path) -> list[Path]:
    return sorted({p for desen in DESENLER for p in kok.glob(desen) if p.is_file()})


def yedekler(klasor: Path) -> list[Path]:
    return sorted(klasor.glob("yanki-*.zip")) if klasor.exists() else []


def son_yedek_zamani(klasor: Path) -> datetime | None:
    for p in reversed(yedekler(klasor)):
        try:
            return datetime.strptime(p.name, AD_BICIMI)
        except ValueError:
            continue
    return None


def gerekli_mi(op: Operasyon, simdi: datetime | None = None) -> bool:
    son = son_yedek_zamani(op.yedek_klasor)
    return son is None or son <= (simdi or datetime.now()) - timedelta(days=op.yedek_gun)


def yedekle(kok: Path, op: Operasyon, simdi: datetime | None = None) -> tuple[Path, int]:
    """Zip'i yazar (önce geçici ad: yarım yedek "son yedek" sayılmasın), eskileri budar. (yol, dosya sayısı)."""
    simdi = simdi or datetime.now()
    op.yedek_klasor.mkdir(parents=True, exist_ok=True)
    hedef = op.yedek_klasor / simdi.strftime(AD_BICIMI)
    gecici = hedef.with_name(hedef.name + ".tmp")
    yazilan = 0
    with zipfile.ZipFile(gecici, "w", zipfile.ZIP_DEFLATED) as z:
        for p in dosyalar(kok):
            try:  # tarama ile yazım arasında silinen/taşınan dosya (oda o an paketi yeniliyor) yedeği düşürmesin
                z.write(p, p.relative_to(kok).as_posix())
            except FileNotFoundError:
                continue
            yazilan += 1
    gecici.replace(hedef)
    for eski in yedekler(op.yedek_klasor)[: -op.yedek_sakla]:
        eski.unlink(missing_ok=True)
    return hedef, yazilan


def lora_yedekle(lora: Path | None, op: Operasyon) -> Path | None:
    """Üretimdeki LoRA (kiralık GPU'da saatlerce eğitildi, ~160 MB) yedek klasörüne bir kez kopyalanır; zip'e girmez
    (her yedekte yeniden yazılmasın). Dönen: yeni kopyalandıysa hedef, zaten varsa ya da LoRA yoksa None."""
    import shutil

    if lora is None or not (lora / "adapter_config.json").is_file():
        return None
    hedef = op.yedek_klasor / "lora" / "-".join(x for x in lora.parts[-3:] if x != "checkpoints")  # <eğitim>-<epoch>
    if (hedef / "adapter_config.json").is_file():
        return None
    gecici = hedef.with_name(hedef.name + ".tmp")
    shutil.rmtree(gecici, ignore_errors=True)
    shutil.copytree(lora, gecici)
    gecici.replace(hedef)
    return hedef
