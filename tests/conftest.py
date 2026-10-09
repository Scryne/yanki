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


@pytest.fixture(autouse=True)
def _bildirimsiz(monkeypatch):
    monkeypatch.setenv("YANKI_BILDIRIMSIZ", "1")  # Windows bildirimi gösterilmez, yalnız kayıt


@pytest.fixture(autouse=True)
def _whispersiz(monkeypatch):
    from yanki import kapilar

    monkeypatch.setattr(kapilar, "dil_tespit", lambda _yol: ("en", 0.99))
