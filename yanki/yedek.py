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
    "calisma/kesif/*.json",
    "girdi/liste.toml",
    "girdi/sozler/*.txt",
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
    liste = dosyalar(kok)
    with zipfile.ZipFile(gecici, "w", zipfile.ZIP_DEFLATED) as z:
        for p in liste:
            z.write(p, p.relative_to(kok).as_posix())
    gecici.replace(hedef)
    for eski in yedekler(op.yedek_klasor)[: -op.yedek_sakla]:
        eski.unlink(missing_ok=True)
    return hedef, len(liste)
