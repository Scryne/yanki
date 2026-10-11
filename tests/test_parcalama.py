import numpy as np
import pytest

from yanki import parcalama


def test_kisa_sarki_bolunmez():
    assert parcalama.kesimler(100, [10, 20, 30]) == []
    p = parcalama.plan(100, [10, 20])
    assert len(p) == 1 and (p[0].bas, p[0].son) == (0.0, 100)


def test_kesim_en_uzun_bosluga_ve_sinirlara_uyar():
    # satır başları: 85'ten 97'ye 12 sn'lik boşluk; 60–110 aralığındaki en uzun boşluk o
    baslar = [5, 15, 25, 35, 45, 55, 65, 75, 85, 97, 105, 115, 125, 135, 145, 155, 165, 175, 185, 195, 205]
    k = parcalama.kesimler(230, baslar)
    assert k[0] == pytest.approx(97 - parcalama.KESIM_ONCESI)
    for a, b in zip([0, *k], [*k, 230], strict=True):
        assert b - a <= 110 + 60  # son parça birleştirilmiş olabilir
    assert all(60 <= b - a for a, b in zip([0, *k], k, strict=False))


def test_sozsuz_uzun_bolumde_duz_kesim():
    assert parcalama.kesimler(250, []) == [90, 180]


def test_cok_kisa_son_parca_birlestirilir():
    k = parcalama.kesimler(205, [])  # 90, 180 → son parça 25 sn (< 30) → 180 kalkar
    assert k == [90]


def test_bindirme_ve_cekirdek():
    p = parcalama.plan(250, [])
    assert [(x.cekirdek_bas, x.cekirdek_son) for x in p] == [(0, 90), (90, 180), (180, 250)]
    assert p[1].bas == 90 - parcalama.BINDIRME and p[1].son == 180 + parcalama.BINDIRME
    assert p[0].bas == 0 and p[-1].son == 250


def test_soz_dagitimi():
    p = parcalama.plan(250, [])
    satirlar = [(10.0, "bir"), (89.9, "iki"), (90.0, "üç"), (200.0, "dört"), (210.0, "")]
    assert parcalama.soz_dagit(p, satirlar) == ["[Intro]\n\n[Verse 1]\nbir\n\n[Instrumental]\n\n[Verse 2]\niki",
                                                "[Verse 2]\nüç\n\n[Instrumental]", "[Verse 3]\ndört"]
    assert parcalama.soz_dagit(parcalama.plan(250, []), []) == ["[Instrumental]"] * 3


def test_birlestirme_sabit_sinyali_korur():
    # her parça kaynağın kendi aralığındaki sabit sinyal olursa dikişte genlik bozulmamalı (eşit güç ≈ ±%30)
    sr = 100
    p = parcalama.plan(250, [])
    sesler = [np.ones((int(round((x.son - x.bas) * sr)), 2), np.float32) for x in p]
    c = parcalama.birlestir(sesler, p, sr)
    assert c.shape == (250 * sr, 2)
    assert np.allclose(c[: 80 * sr], 1.0) and np.allclose(c[-60 * sr:], 1.0)
    assert c.min() > 0.99 and c.max() < 1.45  # sin+cos ≤ √2


def test_birlestirme_konumlari_dogru():
    # her parça kendi numarasıyla dolu: çekirdek bölgelerin ortası o numarayı taşımalı
    sr = 100
    p = parcalama.plan(250, [])
    sesler = [np.full((int(round((x.son - x.bas) * sr)), 1), x.no, np.float32) for x in p]
    c = parcalama.birlestir(sesler, p, sr)[:, 0]
    assert c[45 * sr] == 1 and c[135 * sr] == 2 and c[215 * sr] == 3


def test_soz_dagitimi_nota_ve_nakarat():
    p = parcalama.plan(250, [10, 50, 90, 95, 130, 170, 210])
    satirlar = [(10, "bir"), (12, "bir b"), (50, "♪"), (90, "n"), (92, "n2"), (95, "♪"), (130, "iki"),
                (132, "iki b"), (170, "♪"), (210, "n"), (212, "n2"), (214, "")]
    sonuc = parcalama.soz_dagit(p, satirlar, 250)
    assert all("♪" not in s for s in sonuc)
    assert "[Chorus]\nn\nn2" in "\n".join(sonuc) and "[Verse 1]\nbir" in sonuc[0]
    assert "[Instrumental]" in "\n".join(sonuc) and sonuc[-1].endswith("[Outro]")
