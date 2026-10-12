from pathlib import Path

import numpy as np
import pytest

from yanki import ayarlar, kapilar

KOK = Path(__file__).resolve().parents[1]
GERCEK_KAYNAK = KOK / "calisma" / "adele-someone-like-you" / "kaynak.wav"
FPCALC = ayarlar.yukle().fpcalc


def test_dalga_ayni_ve_kaydirilmis_sinyal_yuksek():
    rng = np.random.default_rng(0)
    a = rng.standard_normal(8000 * 10).astype(np.float32)
    assert kapilar.dalga_korelasyonu(a, a, 8000) > 0.99
    kaymis = np.concatenate([np.zeros(1600, np.float32), a[:-1600]])  # 0,2 sn gecikme
    assert kapilar.dalga_korelasyonu(a, kaymis, 8000) > 0.95


def test_dalga_bagimsiz_sinyal_dusuk():
    rng = np.random.default_rng(0)
    a, b = rng.standard_normal((2, 8000 * 10)).astype(np.float32)
    assert kapilar.dalga_korelasyonu(a, b, 8000) < 0.05


def test_dalga_kapisi_kick_ortusmesini_saymaz_kopyayi_yakalar():
    # EDM: cover kaynağın zamanlamasını izler, dört vuruşlu kick üst üste biner (Avicii tam bantta 0,26 düşüyordu)
    sr = 8000
    t_ = np.arange(sr * 20) / sr
    kick = (np.sin(2 * np.pi * 55 * t_) * np.exp(-((t_ % 0.5) * 30))).astype(np.float32)
    rng = np.random.default_rng(0)
    orijinal = kick + 0.15 * rng.standard_normal(len(t_)).astype(np.float32)
    cover = kick + 0.15 * rng.standard_normal(len(t_)).astype(np.float32)  # aynı kick, başka üst bantlar
    assert kapilar.dalga_korelasyonu(orijinal, cover, sr) > 0.25
    assert kapilar.dalga_korelasyonu(kapilar.alcak_kes(orijinal, sr), kapilar.alcak_kes(cover, sr), sr) < 0.05
    kopya = orijinal + 0.05 * rng.standard_normal(len(t_)).astype(np.float32)
    assert kapilar.dalga_korelasyonu(kapilar.alcak_kes(orijinal, sr), kapilar.alcak_kes(kopya, sr), sr) > 0.9


def test_dalga_sessizlik_sifir():
    assert kapilar.dalga_korelasyonu(np.zeros(800, np.float32), np.ones(800, np.float32), 8000) == 0.0


def test_parmak_izi_benzerligi():
    rng = np.random.default_rng(0)
    a = rng.integers(0, 2**32, 500, dtype=np.uint64).astype(np.uint32)
    b = rng.integers(0, 2**32, 500, dtype=np.uint64).astype(np.uint32)
    assert kapilar.parmak_izi_benzerligi(a, a) == 1.0
    assert kapilar.parmak_izi_benzerligi(a[5:], a) == 1.0  # kayma
    assert 0.45 < kapilar.parmak_izi_benzerligi(a, b) < 0.6


def test_soz_wer():
    assert kapilar.soz_wer("[verse]\nHello, World!", "hello world") == 0.0
    assert kapilar.soz_wer("hello world", "") == 1.0
    assert kapilar.soz_wer("a b c d", "a b x d") == 0.25
    with pytest.raises(ValueError):
        kapilar.soz_wer("[verse]", "x")


def test_hepsi_gecti():
    assert kapilar.hepsi_gecti({"a": {"gecti": True}, "b": {"gecti": True}})
    assert not kapilar.hepsi_gecti({"a": {"gecti": True}, "b": {"gecti": False}})


@pytest.mark.skipif(not (GERCEK_KAYNAK.exists() and FPCALC.exists()), reason="gerçek kaynak ve fpcalc gerekli")
def test_bozuk_aday_orijinalin_kendisi_kapidan_dusmeli(tmp_path):
    # pozitif kontrol: kaynağın kendisi "cover" diye verilirse kopya kapıları yakalamalı
    k = kapilar.degerlendir(GERCEK_KAYNAK, GERCEK_KAYNAK, "irrelevant", FPCALC, dokumcu=lambda *_: "irrelevant")
    assert not k["parmak_izi"]["gecti"] and k["parmak_izi"]["deger"] > 0.9
    assert not k["dalga"]["gecti"] and k["dalga"]["deger"] > 0.9
    assert not kapilar.hepsi_gecti(k)


def test_kesme_isareti_bicimi_wer_artirmaz():
    assert kapilar.soz_wer("[verse]\nI don’t know\n'Cause we're kids", "i don't know cause were kids") == 0.0


def test_normalle_unicode_harfleri_korur():
    assert kapilar.normalle("[Nakarat]\nGülümse, kaderine, Gülümse!") == "gülümse kaderine gülümse"
    assert kapilar.normalle("İstanbul'u ÇOK seviyorum") == "istanbulu çok seviyorum"
    assert kapilar.normalle("Je t’aime, ça va?") == "je taime ça va"
    assert kapilar.normalle("Don't stop") == "dont stop"  # İngilizce davranış değişmedi
    assert kapilar.soz_wer("Gülümse kaderine", "gülümse kaderine") == 0.0


def test_soz_kapisi_orijinal_kayda_gore():
    # Whisper orijinal rap kaydını da 0,49 anlıyor; cover 0,52 ile orijinal kadar anlaşılır ama 0,50'den düşüyordu
    assert kapilar.soz_esigi(None) == 0.50 and kapilar.soz_esigi(0.06) == 0.50
    assert kapilar.soz_esigi(0.49) == pytest.approx(0.59)
    assert kapilar.soz_esigi(0.95) == kapilar.SOZ_TAVAN  # anlamsız vokal her durumda düşer
