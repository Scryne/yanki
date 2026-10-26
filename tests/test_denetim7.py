"""Denetim 7 (2026-10-26): ayar okuma, arşiv temizliği."""

from datetime import datetime

from yanki import ayarlar, temizlik


def test_operasyon_her_alan_kendi_anahtarindan(tmp_path):
    """Alanlar konumla veriliyordu; 95b61be bir alan ekleyince hepsi kaydı (arsiv_gun = 1, gunduz_bosta_dk = 1,
    surekli_uretim = 7). Her değer farklı yazılır, her biri kendi alanında okunmalı."""
    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "operasyon.toml").write_text(
        '[yedek]\nklasor = "y"\ngun = 3\nsakla = 4\n[temizlik]\ngun = 5\narsiv_gun = 6\n'
        '[gunduz]\nacik = false\nbosta_dk = 33\nsarki = 2\nsaatler = [9, 23]\n'
        '[surekli]\nuretim = false\nuretim_sarki = 3\nbosta_bekle = true\n', encoding="utf-8")
    o = ayarlar.operasyon_oku(tmp_path)
    assert (o.yedek_klasor, o.yedek_gun, o.yedek_sakla, o.temizlik_gun, o.arsiv_gun) == (tmp_path / "y", 3, 4, 5, 6)
    assert (o.gunduz_acik, o.gunduz_bosta_dk, o.gunduz_sarki, o.gunduz_saatler) == (False, 33, 2, (9, 23))
    assert (o.surekli_uretim, o.surekli_uretim_sarki, o.surekli_bosta_bekle) == (False, 3, True)


def test_arsiv_temizligi_yayin_kayitlarini_birakir(tmp_path):
    """`_arsiv` bütünüyle siliniyordu (canlı RouteNote yayınlarının UPC'si yalnız orada)."""
    k = tmp_path / "_arsiv" / "2026-10-10" / "adele-someone-like-you"
    (k / "paket").mkdir(parents=True)
    (k / "paket" / "metadata.json").write_text("{}", encoding="utf-8")
    (k / "paket" / "kapak.jpg").write_bytes(b"jpg")
    (k / "durum.json").write_text("{}", encoding="utf-8")
    (k / "adaylar").mkdir()
    (k / "adaylar" / "tam.flac").write_bytes(b"x" * 100)
    simdi = datetime(2026, 10, 26)
    plan = temizlik.arsiv_plani(tmp_path, 7, simdi)
    assert len(plan) == 1 and temizlik.arsiv_sil(plan[0]) == 100
    assert all((k / f).exists() for f in ("paket/metadata.json", "durum.json", "paket/kapak.jpg"))
    assert not (k / "adaylar").exists() and temizlik.arsiv_plani(tmp_path, 7, simdi) == []
