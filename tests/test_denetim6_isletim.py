"""Denetim 6 (2026-10-16) işletim bulgularının testleri: günlükte bekleme hâlleri, CLI ve işletim uçları."""

import io
import sys
from dataclasses import replace

from yanki import ayarlar


def _calistir_bekleyen(tmp_path, monkeypatch, satirlar: list[str]):
    """Sürekli koşu, üretimden başka adımı iş yapmadan; üretim verilen satırları basar. Dönen: günlüğe yazılan."""
    from yanki import cli

    a = replace(ayarlar.yukle(), kok=tmp_path)
    a = replace(a, uzak=replace(a.uzak, acik=False))
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: a)
    monkeypatch.setattr(cli, "_kesif_ayarlari", lambda _k: {"kesif": {"gece_ekle": 0}})
    for ad in ("_hazirla", "_otomatik_onay", "_paketle", "_dagitim_durum", "_takvim_hatirlat", "_temizle",
               "_yedekle", "_eposta"):
        monkeypatch.setattr(cli, ad, lambda *_a: print("paketlenecek onaylı şarkı yok") or 0)
    monkeypatch.setattr(cli, "_uret_surekli", lambda *_: [print(s) for s in satirlar] and 0)
    gunluk = io.StringIO()
    monkeypatch.setattr(sys, "stdout", gunluk)
    assert cli._calistir(cli.argparse.Namespace(liste=None, analizsiz=False)) == 0
    monkeypatch.setattr(sys, "stdout", sys.__stdout__)
    return gunluk.getvalue()


def test_ayni_bekleme_hali_gunluge_bir_kez_yazilir(tmp_path, monkeypatch):
    """2026-10-16: RunPod bakiyesi 0,80 $ iken her 30 dk'da "üretim bekliyor … (50 şarkı sırada)" + "koşu bitti" +
    "dış servisler" bloğu günlüğe yazılıyordu; README "iş yapılmayan koşu günlüğe yazmaz" diyor."""
    bekleme = ["uzak GPU kullanılmıyor (RunPod bakiyesi 0.80 $ (en az 1.00 $): kredi yükle); üretim sunucu "
               "açılabilene kadar bekliyor",
               "üretim bekliyor: kiralık GPU kullanılamıyor, evde üretim kapalı (50 şarkı sırada)"]
    ilk = _calistir_bekleyen(tmp_path, monkeypatch, bekleme)
    assert "── üretim (" in ilk and "50 şarkı sırada" in ilk and "── koşu bitti" in ilk  # hâl ilk kez: yazılır
    # aynı hâl, yalnız sayılar farklı (bakiye, sıradaki şarkı): hiçbir şey yazılmaz
    sayisi_farkli = [bekleme[0].replace("0.80", "0.75"), bekleme[1].replace("50", "51")]
    assert _calistir_bekleyen(tmp_path, monkeypatch, sayisi_farkli) == ""
    # hâl değişti (GPU stokta yok): bir kez yazılır
    stok = ["uzak GPU kullanılmıyor (A40 stok: None); üretim sunucu açılabilene kadar bekliyor", bekleme[1]]
    assert "A40 stok" in _calistir_bekleyen(tmp_path, monkeypatch, stok)
    assert _calistir_bekleyen(tmp_path, monkeypatch, stok) == ""
    # üretim iş yaptı, sonra aynı bekleme hâline döndü: yeniden bir kez yazılır (araya giren iş hâli sıfırlar)
    uretti = ["uretildi  A — B: 3/4 aday kapıdan geçti"]
    assert "aday kapıdan geçti" in _calistir_bekleyen(tmp_path, monkeypatch, uretti)
    assert "A40 stok" in _calistir_bekleyen(tmp_path, monkeypatch, stok)
    # bekleme kalktı (sırada şarkı yok): iş yok satırı yazılmaz, hâl sıfırlanır
    assert _calistir_bekleyen(tmp_path, monkeypatch, ["üretilecek bir şey yok (analiz ya da onarım bekleyen)"]) == ""
    assert "A40 stok" in _calistir_bekleyen(tmp_path, monkeypatch, stok)


def test_bekleme_hali_hepside_her_zaman_yazilir():
    from yanki.cli import _AdimCiktisi

    hedef = io.StringIO()
    c = _AdimCiktisi("── üretim (03:00:00)", hedef, "üretim bekliyor: pilde (# şarkı sırada)")
    c.write("üretim bekliyor: pilde (4 şarkı sırada)\n")
    assert c.bitir() is False and hedef.getvalue() == "" and c.bekleme == "üretim bekliyor: pilde (# şarkı sırada)"
    assert c.bitir(zorla=True) and "pilde" in hedef.getvalue()


def test_dusen_otomatik_yukleme_seyreklesir_basarida_sifirlanir(tmp_path, monkeypatch):
    """2026-10-16: bir paketin RouteNote formu gece 01:00'den beri her 30 dk'da aynı zaman aşımıyla düştü; her deneme
    tarayıcı açıp 75 sn sürdü ve koşuyu "sorunlu" bitirdi."""
    from datetime import date, datetime, timedelta
    from types import SimpleNamespace

    from yanki import cli, dagitim, paket

    s = dagitim.Sira("a-b", "A", "B", date.today(), date.today(), 0.0)
    monkeypatch.setattr(dagitim, "takvim_oku", lambda _y: None)
    monkeypatch.setattr(dagitim, "plan", lambda *_a, **_k: dagitim.Plan([s], None, None, []))
    monkeypatch.setattr(paket, "yayin_ayarlari", lambda _y: SimpleNamespace(dagitimci="routenote"))
    monkeypatch.setattr(dagitim, "sec", lambda *_a: SimpleNamespace(ad="routenote", otomatik=True, gece=True))
    denemeler = []

    def yukle(*_a):
        denemeler.append(1)
        if hata["var"]:
            raise RuntimeError("Timeout 45000ms exceeded")
        return {"upc": "5064"}

    hata = {"var": True}
    monkeypatch.setattr(dagitim, "otomatik_yukle", yukle)
    assert cli._takvim_hatirlat(tmp_path) == 1 and cli._takvim_hatirlat(tmp_path) == 1  # ilk düşüşten sonra bir kez
    assert cli._takvim_hatirlat(tmp_path) == 0 and len(denemeler) == 2  # sonra 2 saat beklenir, koşu sorunlu değil
    yol = tmp_path / "calisma" / ".yukleme_hatalari.json"
    kayit = cli._yukleme_hatalari(tmp_path / "calisma", {"a-b"})
    assert kayit["a-b"]["sayi"] == 2 and "Timeout" in kayit["a-b"]["hata"]
    assert cli._yukleme_sonraki_deneme({"sayi": 9, "son": "2026-10-16T01:00:00"}) == \
        datetime(2026, 10, 16, 1) + timedelta(hours=24)  # en çok günde bir
    kayit["a-b"]["son"] = (datetime.now() - timedelta(hours=3)).isoformat(timespec="seconds")
    cli._yukleme_hatalari_yaz(tmp_path / "calisma", kayit)
    hata["var"] = False
    assert cli._takvim_hatirlat(tmp_path) == 0 and len(denemeler) == 3  # süresi doldu: denendi, yüklendi
    assert cli._yukleme_hatalari(tmp_path / "calisma", {"a-b"}) == {} and yol.exists()
    # kuyruktan çıkan paketin kaydı atılır
    assert cli._yukleme_hatalari(tmp_path / "calisma", set()) == {}


def test_dusen_adim_gunde_bir_kez_bildirilir(tmp_path):
    from yanki import cli, olay

    for _ in range(3):
        cli._adim_hatasi_bildir(tmp_path, "takvim", ["A — lovely: TimeoutError: Timeout 45000ms exceeded."])
    cli._adim_hatasi_bildir(tmp_path, "takvim", ["A — lovely: TimeoutError: Timeout 30000ms exceeded."])  # sayı farkı
    cli._adim_hatasi_bildir(tmp_path, "takvim", ["A — lovely: oturum düştü"])  # başka hata: ayrıca
    assert [o["baslik"] for o in olay.oku(tmp_path)] == ["takvim adımı düştü", "takvim adımı düştü"]


def test_yedek_arsivi_elle_taslaklari_eski_paketi_ve_raporlari_icerir(tmp_path):
    """Önce `yanki bastan` arşivindeki canlı RouteNote yayınlarının UPC/ISRC'si, eski paketin açık taslak UPC'si,
    odadaki elle yayın taslakları ve RouteNote satış raporları yedeğe girmiyordu."""
    import zipfile

    from yanki import yedek

    girecek = ["calisma/_arsiv/2026-10-10/a-b/durum.json", "calisma/_arsiv/2026-10-10/a-b/paket/metadata.json",
               "calisma/a-b/paket_onceki/metadata.json", "calisma/elle/benim/metadata.json",
               "calisma/elle/benim/kapak.jpg", "calisma/eposta/routenote.json", "girdi/kazanc/2026-08.csv",
               "girdi/kesif/bulucu.csv"]
    girmeyecek = ["calisma/_arsiv/2026-10-10/a-b/paket/x.flac", "calisma/elle/benim/ses.flac", ".env",
                  "calisma/.spotify.json"]
    for yol in girecek + girmeyecek:
        (tmp_path / yol).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / yol).write_text("x", encoding="utf-8")
    op = ayarlar.Operasyon(tmp_path / "calisma" / "yedek")
    zip_yolu, n = yedek.yedekle(tmp_path, op)
    with zipfile.ZipFile(zip_yolu) as z:
        assert sorted(z.namelist()) == sorted(girecek) and n == len(girecek)


def test_uretimdeki_lora_bir_kez_yedeklenir(tmp_path):
    from yanki import yedek

    lora = tmp_path / "calisma" / "egitim" / "lora" / "20261012-1702" / "checkpoints" / "epoch_20"
    lora.mkdir(parents=True)
    (lora / "adapter_config.json").write_text("{}", encoding="utf-8")
    (lora / "adapter_model.safetensors").write_bytes(b"agirlik")
    op = ayarlar.Operasyon(tmp_path / "yedek")
    hedef = yedek.lora_yedekle(lora, op)
    assert hedef == tmp_path / "yedek" / "lora" / "20261012-1702-epoch_20"
    assert (hedef / "adapter_model.safetensors").read_bytes() == b"agirlik"
    assert yedek.lora_yedekle(lora, op) is None  # ikinci kez kopyalanmaz
    assert yedek.lora_yedekle(None, op) is None and yedek.lora_yedekle(tmp_path / "yok", op) is None


def test_stillmore_configteki_bozuk_playlist_kimligi_kesfi_dusurmez(tmp_path, monkeypatch, capsys):
    """Önce `kimlik_ayikla` try'sızdı: config'teki tek bozuk kimlik bütün keşif adımını ValueError'la düşürüyordu."""
    from types import SimpleNamespace

    from yanki import cli, stillmore

    monkeypatch.setattr(stillmore, "havuz_oku", lambda _c: {})
    yazilan = {}
    monkeypatch.setattr(stillmore, "havuz_yaz", lambda _c, h: yazilan.update(h))
    monkeypatch.setattr(stillmore, "sec", lambda *_a: [])
    st = {"acik": True, "playlistler": ["https://open.spotify.com/", "37i9dQZF1DXcBWIGoYBM5M"]}
    cli._stillmore_tara(SimpleNamespace(), tmp_path, tmp_path / "calisma", st, None, False, [])
    assert "37i9dQZF1DXcBWIGoYBM5M" in yazilan and "atlandı" in capsys.readouterr().out


def _takvim_sahnesi(tmp_path, monkeypatch, sira, elle_bekleyen=()):
    from types import SimpleNamespace

    from yanki import dagitim, paket

    monkeypatch.setattr(dagitim, "takvim_oku", lambda _y: None)
    monkeypatch.setattr(dagitim, "plan", lambda *_a, **_k: dagitim.Plan(sira, None, None, [],
                                                                       elle_bekleyen=tuple(elle_bekleyen)))
    monkeypatch.setattr(paket, "yayin_ayarlari", lambda _y: SimpleNamespace(dagitimci="routenote"))
    monkeypatch.setattr(dagitim, "sec", lambda *_a: SimpleNamespace(ad="routenote", otomatik=True, gece=True))


def test_tarayici_mesgulken_takvim_durur_hata_saymaz(tmp_path, monkeypatch):
    """Oda işi RouteNote tarayıcısını tutarken her paket aynı kilide takılıp 'düştü' sayılıyor, seyrekleşiyordu."""
    from datetime import date

    from yanki import cli, dagitim, routenote

    sira = [dagitim.Sira(k, "A", k, date.today(), date.today(), 0.0) for k in ("a-b", "a-c")]
    _takvim_sahnesi(tmp_path, monkeypatch, sira)
    denemeler = []

    def yukle(_c, _d, kimlik, _t):
        denemeler.append(kimlik)
        raise routenote.TarayiciMesgul("RouteNote tarayıcısı başka bir işte açık")

    monkeypatch.setattr(dagitim, "otomatik_yukle", yukle)
    assert cli._takvim_hatirlat(tmp_path) == 0 and denemeler == ["a-b"]  # ikinci paket denenmez
    assert cli._yukleme_hatalari(tmp_path / "calisma", {"a-b", "a-c"}) == {}  # seyrekleştirmeye girmez


def test_paket_yenilenirken_sonraki_pakete_gecer(tmp_path, monkeypatch):
    from datetime import date

    from yanki import cli, dagitim, routenote

    sira = [dagitim.Sira(k, "A", k, date.today(), date.today(), 0.0) for k in ("a-b", "a-c")]
    _takvim_sahnesi(tmp_path, monkeypatch, sira)

    def yukle(_c, _d, kimlik, _t):
        if kimlik == "a-b":
            raise routenote.Mesgul("a-b: paket şu an yeniden hazırlanıyor")
        return {"upc": "5064"}

    monkeypatch.setattr(dagitim, "otomatik_yukle", yukle)
    assert cli._takvim_hatirlat(tmp_path) == 0
    assert cli._yukleme_hatalari(tmp_path / "calisma", {"a-b", "a-c"}) == {}


def test_elindeki_taslak_bir_kez_bildirilir(tmp_path, monkeypatch):
    """Gece kuyruğundan çıkarılan (önceki oturumun hazır taslağı, yarım son tık) paket sessizce beklemesin."""
    from yanki import cli, durum, olay

    durum.yaz(tmp_path / "calisma", durum.Durum("billie-eilish-lovely", "Billie Eilish", "lovely", asama="paketlendi"))
    _takvim_sahnesi(tmp_path, monkeypatch, [], elle_bekleyen=["billie-eilish-lovely"])
    assert cli._takvim_hatirlat(tmp_path) == 0 and cli._takvim_hatirlat(tmp_path) == 0
    basliklar = [o["baslik"] for o in olay.oku(tmp_path / "calisma")]
    assert basliklar == ["RouteNote'ta seni bekliyor: lovely"]


def test_kesif_listesiz_kurulumda_dusmez(tmp_path):
    from yanki import kesif

    (tmp_path / "calisma" / "a-b").mkdir(parents=True)
    assert kesif.listedekiler(tmp_path / "liste.toml", tmp_path / "calisma") == {"a-b"}
