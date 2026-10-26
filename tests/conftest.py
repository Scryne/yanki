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
    """Gerçek `calisma/` ve `girdi/` testte yazılmaz. Denetim 7'de bir test `ayarlar.yukle().kok`'la sahte motoru gerçek
    kuyrukta koşturdu, 86 şarkıyı `hata`ya düşürdü (elle geri alındı); bu kapı aynısını hemen düşürür."""
    from yanki import ayarlar, dosya

    korunan = [(ayarlar.KOK / ad).resolve() for ad in ("calisma", "girdi")]
    asil = dosya.yaz

    def yaz(yol, metin):
        tam = Path(yol).resolve()
        if any(tam.is_relative_to(k) for k in korunan):
            raise AssertionError(f"test gerçek veriye yazıyor: {tam}")
        return asil(yol, metin)

    monkeypatch.setattr(dosya, "yaz", yaz)


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
