import json
from pathlib import Path

from yanki import durum, estetik, onay


def _es(ort: float) -> dict:
    return {"songeval": {k: ort for k in ("Coherence", "Musicality", "Memorability", "Clarity", "Naturalness")},
            "audiobox": {"CE": 7.0, "CU": 7.0, "PC": 7.0, "PQ": 7.0}, "surum": estetik.SURUM}


def _secimli(c: Path, kimlik: str, adaylar, secilen: int):
    """adaylar: (no, söz WER'i, estetik ortalaması | None)."""
    d = durum.Durum(kimlik, "A", kimlik)
    d.adaylar = [durum.Aday(no, f"adaylar/{no}.flac", no, {"soz_wer": {"deger": w}}, True,
                            estetik=_es(e) if e is not None else None) for no, w, e in adaylar]
    d.secilen = secilen
    d.gec("onaylandi")
    durum.yaz(c, d)


def test_estetik_secici_en_yuksek_puan_eksikse_kural():
    d = durum.Durum("a-b", "A", "B")
    d.adaylar = [durum.Aday(1, "1.flac", 1, {"soz_wer": {"deger": 0.02}}, True, estetik=_es(3.1)),
                 durum.Aday(2, "2.flac", 2, {"soz_wer": {"deger": 0.09}}, True, estetik=_es(3.6)),
                 durum.Aday(3, "", 3, {}, False, estetik=_es(4.9))]  # kapıdan geçmemiş: seçilmez
    assert onay.oneri(d, "estetik").no == 2 and onay.oneri(d).no == 1
    d.adaylar[0].estetik = None  # bir adayın puanı yok: eksik bilgiyle seçilmez, kural
    assert onay.oneri(d, "estetik").no == 1
    assert onay.oneri(d, "otomatik").no == 1  # çözülmemiş otomatik = kural


def test_isabet_estetigi_yan_yana_olcer_ve_otomatik_esikte_gecer(tmp_path, monkeypatch):
    c = tmp_path / "calisma"
    # kural en düşük WER'i (1) seçer, Scryne 2'yi seçti, estetik 2'yi tutar
    for i in range(9):
        _secimli(c, f"s{i}", [(1, 0.02, 3.0), (2, 0.05, 3.5)], secilen=2)
    _secimli(c, "puansiz", [(1, 0.02, None), (2, 0.05, 3.5)], secilen=2)  # estetik ölçümüne girmez
    o = onay.isabet(c)
    assert o["sarki"] == 10 and o["isabet"] == 0
    assert o["estetik"] == {"sarki": 9, "isabet": 9, "oran": 1.0, "kural_isabet": 0, "rastgele": 4.5}
    assert onay.secici_coz(c, "otomatik") == "kural"  # 9 < ESTETIK_EN_AZ
    _secimli(c, "s9", [(1, 0.02, 3.0), (2, 0.05, 3.5)], secilen=2)
    assert onay.secici_coz(c, "otomatik") == "estetik"
    assert onay.secici_coz(c, "kural") == "kural"


def test_ayar_secici_okunur_ve_dogrulanir(tmp_path):
    import pytest

    yol = tmp_path / "yayin.toml"
    yol.write_text('[otomatik_onay]\nacik = true\nsecici = "otomatik"\n', encoding="utf-8")
    assert onay.ayar_oku(yol).secici == "otomatik"
    assert onay.ayar_oku(yol, tmp_path / "calisma").secici == "kural"  # ölçü yok: kural
    yol.write_text('[otomatik_onay]\nsecici = "rastgele"\n', encoding="utf-8")
    with pytest.raises(ValueError):
        onay.ayar_oku(yol)


def test_puanla_dinlemedeki_adaylari_yazar_digerlerine_dokunmaz(tmp_path):
    c = tmp_path / "calisma"
    d = durum.Durum("a-b", "A", "B", asama="uretildi")
    d.gecmis = [{"zaman": "2026-10-18T10:00:00", "asama": "uretildi", "hata": None}]
    d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, {}, True), durum.Aday(2, "adaylar/2/tam.flac", 7, {}, True),
                 durum.Aday(3, "adaylar/3/tam.flac", 9, {}, False)]  # kapıdan geçmemiş: puanlanmaz
    durum.yaz(c, d)
    y = durum.Durum("y-z", "Y", "Z", asama="yuklendi", adaylar=[durum.Aday(1, "adaylar/1/tam.flac", 1, {}, True)])
    durum.yaz(c, y)  # yüklenmiş: dinlemede değil
    for k, no in (("a-b", 1), ("a-b", 2), ("a-b", 3), ("y-z", 1)):
        (c / k / f"adaylar/{no}/tam.flac").parent.mkdir(parents=True, exist_ok=True)
        (c / k / f"adaylar/{no}/tam.flac").write_bytes(b"x")
    assert [(x.kimlik, a.no) for x, a in estetik.bekleyenler(c)] == [("a-b", 1), ("a-b", 2)]
    gorulen = {}

    def calistir(komut, **k):
        gorulen.update(komut=komut, **k)
        girdi = json.loads(Path(komut[-2]).read_text(encoding="utf-8"))
        assert girdi["cpu"] is True and len(girdi["dosyalar"]) == 2
        ilk, ikinci = girdi["dosyalar"]
        Path(komut[-1]).write_text(json.dumps({ilk: _es(3.4), ikinci: {"hata": "bozuk ses"}}), encoding="utf-8")

        class R:
            returncode, stderr = 0, ""
        return R()

    mesajlar = []
    assert estetik.puanla(tmp_path, c, calistir=calistir, bildir=mesajlar.append) == 1
    assert gorulen["komut"][1] == "-I" and gorulen["timeout"] > 0
    d = durum.oku(c, "a-b")
    assert estetik.puan(d.adaylar[0].estetik) == 3.4 and d.adaylar[1].estetik is None
    assert any("bozuk ses" in m for m in mesajlar)
    assert [a.no for _, a in estetik.bekleyenler(c)] == [2]  # puanlanan tekrar sorulmaz
