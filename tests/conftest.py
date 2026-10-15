"""Test izolasyonu: testler ağa çıkmaz, Whisper modeli yüklemez, Windows bildirimi göstermez.

Önce `analiz_et` testleri dil tespiti için gerçek Whisper `small`'u yüklüyor (CI'da indirme), türü olmayan sanatçıda
Deezer'a gerçek istek atıyordu. Ağ gerektiren her yol sahte istemciyle ayrıca sınanıyor.
"""

import urllib.error
import urllib.request

import pytest


@pytest.fixture(autouse=True)
def _agsiz(monkeypatch):
    def yok(*_a, **_k):
        raise urllib.error.URLError("testte ağ yok")

    monkeypatch.setattr(urllib.request, "urlopen", yok)
    from yanki import runpod

    monkeypatch.setattr(runpod, "ssh_engeli", lambda: None)  # pod öncesi port denemesi (gerçek TCP bağlantısı)


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
