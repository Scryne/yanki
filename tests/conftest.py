"""Test izolasyonu: testler ağa çıkmaz, Whisper modeli yüklemez, Windows bildirimi göstermez.

Önce `analiz_et` testleri dil tespiti için gerçek Whisper `small`'u yüklüyor (CI'da indirme), türü olmayan sanatçıda
Deezer'a gerçek istek atıyordu. Ağ gerektiren her yol sahte istemciyle ayrıca sınanıyor.
"""

import urllib.error
import urllib.request
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def _agsiz(monkeypatch):
    def yok(*_a, **_k):
        raise urllib.error.URLError("testte ağ yok")

    monkeypatch.setattr(urllib.request, "urlopen", yok)
    import yt_dlp
    from curl_cffi import requests as curl_istek

    from yanki import runpod

    # YouTube urllib kullanmıyor (yt-dlp, curl_cffi): ayrıca kapatılır; kendi sahtesini kuran test bunu ezer
    monkeypatch.setattr(yt_dlp, "YoutubeDL", yok)
    monkeypatch.setattr(curl_istek, "Session", yok)

    monkeypatch.setattr(runpod, "ssh_engeli", lambda: None)  # pod öncesi port denemesi (gerçek TCP bağlantısı)


@pytest.fixture(autouse=True)
def _gercek_veriye_yazmaz(monkeypatch):
    """Gerçek `calisma/`, `girdi/` ve `config/` testte yazılmaz, silinmez, taşınmaz. Denetim 7'de bir test
    `ayarlar.yukle().kok`'la sahte motoru gerçek kuyrukta koşturdu, 86 şarkıyı `hata`ya düşürdü (elle geri alındı).
    İlk kapı yalnız `dosya.yaz`'ı tutuyordu; `write_text`, `open(.., "w")`, `unlink`, `shutil` gibi 60'ı aşkın doğrudan
    yazma yolu ondan geçmiyordu (2026-10-26 denetimi). Kapı artık alttaki yazma işlevlerinde: hangi yoldan gelirse
    gelsin gerçek veriye dokunan test hemen düşer (`test_izolasyon.py` kapının kendisini sınar)."""
    import builtins
    import os
    import shutil

    from yanki import ayarlar

    korunan = [(ayarlar.KOK / ad).resolve() for ad in ("calisma", "girdi", "config")]

    def denetle(yol):
        if isinstance(yol, int):  # dosya tanımlayıcısı: yolu zaten açılırken denetlendi
            return
        try:
            tam = Path(os.fspath(yol)).resolve()
        except (TypeError, ValueError, OSError):
            return
        if any(tam.is_relative_to(k) for k in korunan):
            raise AssertionError(f"test gerçek veriye yazıyor: {tam}")

    def yazma_kipi(mode) -> bool:
        return any(c in str(mode) for c in "wax+")

    asil_open = builtins.open

    def open_(file, mode="r", *a, **k):
        if yazma_kipi(mode):
            denetle(file)
        return asil_open(file, mode, *a, **k)

    monkeypatch.setattr(builtins, "open", open_)

    asil_path_open = Path.open

    def path_open(self, mode="r", *a, **k):
        if yazma_kipi(mode):
            denetle(self)
        return asil_path_open(self, mode, *a, **k)

    monkeypatch.setattr(Path, "open", path_open)

    def sar_path(ad, *, hedef=False):
        asil = getattr(Path, ad)

        def sarili(self, *a, **k):
            denetle(self)
            if hedef and a:
                denetle(a[0])
            return asil(self, *a, **k)

        monkeypatch.setattr(Path, ad, sarili)

    for ad in ("write_text", "write_bytes", "unlink", "touch", "mkdir", "rmdir"):
        sar_path(ad)
    for ad in ("rename", "replace"):
        sar_path(ad, hedef=True)

    def sar_modul(modul, ad, *, konumlar=(0,)):
        asil = getattr(modul, ad)

        def sarili(*a, **k):
            for i in konumlar:
                if i < len(a):
                    denetle(a[i])
            return asil(*a, **k)

        monkeypatch.setattr(modul, ad, sarili)

    for ad in ("remove", "unlink", "rmdir", "makedirs", "mkdir"):
        sar_modul(os, ad)
    for ad in ("rename", "replace"):
        sar_modul(os, ad, konumlar=(0, 1))
    sar_modul(shutil, "rmtree")
    for ad in ("copy", "copy2", "copyfile", "copytree"):
        sar_modul(shutil, ad, konumlar=(1,))
    sar_modul(shutil, "move", konumlar=(0, 1))


@pytest.fixture(autouse=True)
def _bildirimsiz(monkeypatch):
    monkeypatch.setenv("YANKI_BILDIRIMSIZ", "1")  # Windows bildirimi gösterilmez, yalnız kayıt


@pytest.fixture(autouse=True)
def _whispersiz(monkeypatch):
    from yanki import kapilar

    monkeypatch.setattr(kapilar, "dil_tespit", lambda _yol: ("en", 0.99))
    # göreli söz kapısının orijinal kayıt ölçümü (gerçekte Whisper, ~1 dk); testte ölçülmez (mutlak eşik)
    monkeypatch.setattr(kapilar, "orijinal_wer", lambda *a, **k: None)


@pytest.fixture(autouse=True)
def _tur_listesi_varsayilan(monkeypatch):
    # keşfin tür süzgeci testlerde gerçek config'e bağlı olmasın (config/kesif.toml türleri açtıkça değişiyor)
    from yanki import kesif, onay

    monkeypatch.setattr(kesif, "haric_kalip", lambda: onay.tur_kalibi(onay.DENENMEMIS_VARSAYILAN))


@pytest.fixture(autouse=True)
def _lora_klasorsuz(monkeypatch):
    # config/motor.toml eğitilmiş LoRA'yı gösteriyor (calisma/, repoda yok): üretim testleri o klasöre bağlı olmasın.
    # Denetimin kendisi test_egitim.py'de modül yüklenirken alınan asıl işlevle sınanıyor.
    from yanki import ayarlar

    monkeypatch.setattr(ayarlar, "lora_denetle", lambda a: None)


@pytest.fixture(autouse=True)
def _gorevsiz(monkeypatch):
    # dinleme odası zamanlanmış görevlerin hâlini PowerShell'le soruyor: testte makinenin görevlerine bakılmaz
    from yanki import sistem

    monkeypatch.setattr(sistem, "gorev_durumlari", lambda *_a, **_k: {})
