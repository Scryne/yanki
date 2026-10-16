"""Denetim 6 (dağıtım): geri alınamaz RouteNote gönderimine giden yolun kenar durumları, paket bütünlüğü, e-postanın
yanlış şarkıya yazılması, elle taslak profili, Pinterest kapağının yarım yazımı. Ağ ve tarayıcı yok."""

import io
import json
from datetime import date, timedelta
from email.message import EmailMessage

import numpy as np
import pytest
import soundfile as sf

from yanki import dagitim, durum, elle, eposta, kilit, paket, pinterest, routenote, sanatci, ses

try:
    ses.arac("ffmpeg")
    FFMPEG = True
except FileNotFoundError:
    FFMPEG = False

ffmpeg_gerekli = pytest.mark.skipif(not FFMPEG, reason="ffmpeg gerekli")

ASAMALAR = ("yeni", "hazir", "analiz", "uretildi", "onaylandi", "paketlendi", "yuklendi", "yayinda")


def _paket(p, **meta_ek):
    from PIL import Image

    p.mkdir(parents=True, exist_ok=True)
    (p / "Orvane_-_Song.flac").write_bytes(b"fLaC" + b"\0" * 64)
    Image.new("RGB", (3000, 3000)).save(p / "Orvane_-_Song.jpg")
    meta = {"sanatci": "Orvane", "baslik": "Song", "dil": "en", "acik_icerik": False,
            "orijinal_yazar_adlari": [["Adele", "Adkins"]], **meta_ek}
    (p / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def _tarayicisiz(monkeypatch):
    monkeypatch.setattr(routenote, "baglam", lambda *a, **k: pytest.fail("tarayıcı açıldı"))


# ── RouteNote yükleyicisi ────────────────────────────────────


def test_paket_dosyalari_yarim_ve_gizli_dosyayi_saymaz(tmp_path):
    """Yarıda kalmış yeniden paketlemenin `.yaziliyor` FLAC'ı ya da noktalı eski küçük resim RouteNote'a gitmez;
    iki asıl FLAC varsa hangisinin gideceği belirsiz: yükleme durur."""
    p = tmp_path / "paket"
    _paket(p)
    (p / ".Orvane_-_Song.yaziliyor.flac").write_bytes(b"yarim")
    (p / "ses.yaziliyor.flac").write_bytes(b"yarim")  # elle taslağın eski geçici adı
    (p / ".kucuk.jpg").write_bytes(b"x")
    ses, kapak = routenote.paket_dosyalari(p)
    assert (ses.name, kapak.name) == ("Orvane_-_Song.flac", "Orvane_-_Song.jpg")
    (p / "Orvane_-_Eski.flac").write_bytes(b"fLaC")
    with pytest.raises(ValueError, match="birden çok .flac"):
        routenote.paket_dosyalari(p)


def test_gonderilmis_taslak_tarayici_acmadan_bilgi_doner(tmp_path, monkeypatch):
    """Distribute'tan sonra yükleme kaydı yazılamadıysa (koşu düştü) sonraki deneme yeniden göndermez, tarayıcıyı da
    açmaz (oturum düşmüş olsa da kayıt tamamlanır)."""
    _tarayicisiz(monkeypatch)
    p = tmp_path / "s" / "paket"
    _paket(p, routenote={"upc": "5064150239784", "adim": "gonderildi", "isrc": "ZZA192606238",
                         "gonderim": "2026-10-16"})
    bilgi = routenote.RouteNote(tmp_path).yukle_klasor(tmp_path, p, "s", None, "Pop")
    assert bilgi["upc"] == "5064150239784" and bilgi["isrc"] == "ZZA192606238"
    assert bilgi["dagitim_durumu"] == "gonderildi" and bilgi["en_gec_yayin"] == "2026-10-30"


def test_tarayici_baska_iste_acikken_mesgul(tmp_path, monkeypatch):
    _tarayicisiz(monkeypatch)
    p = tmp_path / "s" / "paket"
    _paket(p)
    with kilit.tek_kosu(tmp_path / routenote.TARAYICI_KILIDI) as alindi:
        assert alindi
        with pytest.raises(routenote.Mesgul, match="başka bir işte"):
            routenote.RouteNote(tmp_path).yukle_klasor(tmp_path, p, "s", None, "Pop")
    with kilit.tek_kosu(paket.yukleme_kilidi(p)) as alindi:  # paket o an yeniden hazırlanıyor
        assert alindi
        with pytest.raises(routenote.Mesgul, match="yeniden hazırlanıyor"):
            routenote.RouteNote(tmp_path).yukle_klasor(tmp_path, p, "s", None, "Pop")
    with kilit.tek_kosu(tmp_path / routenote.TARAYICI_KILIDI) as alindi:
        with pytest.raises(routenote.Mesgul):
            routenote.giris(tmp_path, bekle_sn=0)


def test_on_kontrol_sanatcisiz_paketi_durdurur(tmp_path):
    """Sanatçı adı boş paket (config'te sanatci_adi yok) taslak açılmadan durur: aksi halde UPC alınır, albüm
    adımında düşer, panelde yarım taslak kalır."""
    p = tmp_path / "paket"
    meta = _paket(p)
    ses, kapak = routenote.paket_dosyalari(p)
    for bozuk in ({"sanatci": None}, {"sanatci": " "}, {"baslik": ""}):
        with pytest.raises(ValueError, match="sanatçı adı ya da şarkı adı"):
            routenote.on_kontrol({**meta, **bozuk}, ses, kapak)


def test_gonderilmedi_mesaji_otomasyonun_gonderemeyecegini_soyler(tmp_path):
    c = tmp_path / "c"
    d = durum.Durum("a-b", "A", "B")
    for a in ASAMALAR[:ASAMALAR.index("paketlendi") + 1]:
        d.gec(a)
    durum.yaz(c, d)
    _paket(durum.klasor(c, "a-b") / "paket", routenote={"upc": "5064150000001", "adim": "gonderiliyor"})
    mesaj = routenote.gonderim_sonucu(c, "a-b", False)
    assert "gönderemez" in mesaj and "taslak-silindi a-b" in mesaj and "gonderildi a-b" in mesaj


# ── takvim ───────────────────────────────────────────────────


def _paketli(c, kimlik, **meta_ek):
    d = durum.Durum(kimlik, "A", kimlik.upper())
    for a in ASAMALAR[:ASAMALAR.index("paketlendi") + 1]:
        d.gec(a)
    durum.yaz(c, d)
    _paket(durum.klasor(c, kimlik) / "paket", orijinal_yazarlar=["Adele Adkins"], **meta_ek)


def test_insanin_elindeki_taslak_gece_kuyruguna_girmez(tmp_path):
    """Önceki oturumda hazırlanmış taslak (`hazir`) ve son tıktan sonra yarıda kalan gönderim (`gonderiliyor`)
    otomasyonla bitmez: kuyrukta kalsalar her 30 dakikada bir tarayıcı açılıp aynı hatayla düşüyordu."""
    c = tmp_path / "c"
    _paketli(c, "kuyruk")
    _paketli(c, "yarim", routenote={"upc": "5064150000002", "adim": "kapak"})  # kaldığı adımdan sürer
    _paketli(c, "hazir", routenote={"upc": "5064150000003", "adim": "hazir"})
    _paketli(c, "kontrol", routenote={"upc": "5064150000004", "adim": "gonderiliyor"})
    _paketli(c, "kayitsiz", routenote={"upc": "5064150000005", "adim": "gonderildi"})  # kayıt tamamlanacak
    p = dagitim.plan(c, dagitim.Takvim(haftada=0, yayin_on_gun=0, baslangic="surekli"), puanlar={},
                     dagitimci="routenote")
    assert sorted(x.kimlik for x in p.sira) == ["kayitsiz", "kuyruk", "yarim"]
    assert sorted(p.elle_bekleyen) == ["hazir", "kontrol"]
    ilk = dagitim.plan(c, dagitim.Takvim(baslangic="ilk_kabul"), puanlar={}, dagitimci="routenote")
    assert ilk.beklemede and "KONTROL" in ilk.beklemede  # gönderilmiş olabilir: ilk kabul kapısı onu bekler


def test_sanatci_hali_gonderilmis_ama_kaydedilmemis_incelemede(tmp_path):
    d = durum.Durum("a", "A", "B", asama="paketlendi")
    assert sanatci.hal(d, {"routenote": {"adim": "gonderildi"}}) == "inceleme"
    assert sanatci.hal(d, {"routenote": {"adim": "kapak"}}) == "taslak_yarim"


# ── paket bütünlüğü ──────────────────────────────────────────


def _muzik(yol, sure=4, sr=48000):
    t = np.arange(int(sure * sr)) / sr
    x = 0.05 * np.sin(2 * np.pi * 220 * t)
    sf.write(str(yol), np.stack([x, x], 1).astype("float32"), sr)


def _yayin(tmp_path):
    yol = tmp_path / "yayin.toml"
    yol.write_text('[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "routenote"\netiket = ""\n'
                   "[master]\nlufs = -14.0\ngercek_tepe_dbtp = -1.0\nornekleme = 44100\nton_eslesme = false\n",
                   encoding="utf-8")
    return yol


def _onayli(c, kimlik="a-b"):
    k = c / kimlik
    (k / "adaylar" / "1").mkdir(parents=True)
    _muzik(k / "adaylar" / "1" / "tam.flac")
    d = durum.Durum(kimlik, "A", "B", kunye={"yazarlar": ["Adele Adkins"]}, analiz={"dil": "en"})
    d.adaylar = [durum.Aday(1, "adaylar/1/tam.flac", 42, {}, True)]
    d.secilen = 1
    for a in ASAMALAR[:ASAMALAR.index("onaylandi") + 1]:
        d.gec(a)
    durum.yaz(c, d)
    return k


@ffmpeg_gerekli
def test_yarida_kalan_yeniden_paketleme_eski_sesi_bozmaz(tmp_path, monkeypatch):
    """Yeniden paketleme ffmpeg sürerken düşerse (güç, çökme) asıl adlı FLAC yarım kalmaz: aşama `paketlendi`
    kaldığı için o dosya RouteNote'a gönderilirdi."""
    c = tmp_path / "c"
    k = _onayli(c)
    paket.paketle(c, _yayin(tmp_path))
    p = k / "paket"
    ses_yolu = p / "Orvane_-_B.flac"
    once = ses_yolu.read_bytes()

    def yarim_master(girdi, hedef, y, **_k):
        hedef.write_bytes(b"fLaC yarim")
        raise RuntimeError("güç gitti")

    asil = paket.master
    monkeypatch.setattr(paket, "master", yarim_master)
    with pytest.raises(RuntimeError, match="güç gitti"):
        paket.paketle(c, _yayin(tmp_path), yeniden=True)
    assert ses_yolu.read_bytes() == once
    assert routenote.paket_dosyalari(p)[0] == ses_yolu  # yarım geçici dosya yükleyiciye görünmez
    monkeypatch.setattr(paket, "master", asil)
    paket.paketle(c, _yayin(tmp_path), yeniden=True)  # sonraki paketleme geçici artığı da siler
    assert sorted(x.name for x in p.iterdir()) == ["Orvane_-_B.flac", "Orvane_-_B.jpg", "YUKLE.md", "metadata.json"]


def test_yukleme_surerken_paket_yenilenmez(tmp_path):
    c = tmp_path / "c"
    _onayli(c)
    with kilit.tek_kosu(paket.yukleme_kilidi(durum.klasor(c, "a-b") / "paket")) as alindi:
        assert alindi
        hatalar = []
        assert paket.paketle(c, _yayin(tmp_path), hatalar=hatalar) == []
        assert "yükleniyor" in hatalar[0][1]
    assert durum.oku(c, "a-b").asama == "onaylandi"


# ── e-posta ──────────────────────────────────────────────────


def _ileti(konu, govde, mid="<1@rn>"):
    m = EmailMessage()
    m["From"], m["Subject"], m["Message-ID"], m["Date"] = ("RouteNote <noreply@routenote.com>", konu, mid,
                                                           "Fri, 16 Oct 2026 10:00:00 +0000")
    m.set_content(govde)
    return eposta.ayristir(m.as_bytes())


LISTE = [{"kimlik": "lovely", "ad": "lovely", "upc": "5064149247325", "asama": "yuklendi"},
         {"kimlik": "numb", "ad": "Numb", "upc": "5064150546080", "asama": "yuklendi"},
         {"kimlik": "shape", "ad": "Shape of You", "upc": "", "asama": "yuklendi"}]


def test_eposta_gundelik_sozcuk_sarkiya_baglanmaz():
    """Tek sözcüklü ad ("lovely") gövdede yalnız yayın bağlamında sayılır: "have a lovely day" diyen red iletisi
    lovely'yi kuyruğa döndürmesin."""
    red = _ileti("Release update", "Unfortunately your release was declined. Have a lovely day!")
    assert eposta.eslestir(red, LISTE) is None
    assert eposta.eslestir(_ileti("Release update", 'Your release "lovely" was declined'), LISTE)["kimlik"] == "lovely"
    assert eposta.eslestir(_ileti("Update", "lovely has been approved"), LISTE)["kimlik"] == "lovely"
    assert eposta.eslestir(_ileti("lovely approved", "Good news"), LISTE)["kimlik"] == "lovely"  # konuda
    assert eposta.eslestir(_ileti("Update", "We think shape of you is approved"), LISTE)["kimlik"] == "shape"


def test_eposta_baska_upc_adla_eslesmez():
    """Arşivdeki eski yayın, panelden silinmiş taslak ya da elle taslak hakkındaki ileti (UPC'si adaylarda yok) aynı
    adlı başka şarkıya yazılmaz."""
    ileti = _ileti("Release declined", "Numb (UPC 5064150546099) was declined")
    assert eposta.eslestir(ileti, LISTE) is None
    assert eposta.eslestir(_ileti("Release declined", "UPC 5064150546080 declined"), LISTE)["kimlik"] == "numb"


def test_eposta_duzeltme_istegi_red_sayilmaz():
    i = _ileti("Your release", "Your release cannot be approved until you amend the artwork. Please update it.")
    assert eposta.sinif(i) == "aksiyon"
    assert eposta.sinif(_ileti("Release declined", "Your release has not been approved")) == "red"


def test_eposta_hesap_iletisi_onay_sayilmaz(tmp_path):
    c = tmp_path / "c"
    sonuc = eposta.isle(c, [_ileti("Welcome aboard! Activate your New Account.",
                                   "Congratulations! Click to activate: https://x/abc123")])
    assert sonuc[0]["sinif"] is None and sonuc[0]["eylem"].startswith("ilgisiz")
    assert not (c / "eposta" / "ornek").exists()  # etkinleştirme bağlantısı diske yazılmaz


def test_eposta_her_iletiden_sonra_kaydedilir(tmp_path, monkeypatch):
    """İkinci iletide hata çıksa da ilki işlenmiş sayılır (red ikinci kez işlenmez, bildirim yinelenmez)."""
    c = tmp_path / "c"
    bildirimler = []

    def bildir(*a):
        bildirimler.append(a)
        if len(bildirimler) == 2:
            raise OSError("disk dolu")

    iletiler = [_ileti("Update", "News about your release", mid="<a>"),
                _ileti("Update 2", "More news about your release", mid="<b>")]
    with pytest.raises(OSError):
        eposta.isle(c, iletiler, bildir=bildir)
    kayit = json.loads(eposta.kayit_yolu(c).read_text(encoding="utf-8"))
    assert list(kayit) == ["<a>"]


# ── elle taslak ──────────────────────────────────────────────


def _elle(tmp_path, sid="AAAAAAAAAAAAAAAAAAAAAA"):
    kok = tmp_path / "kok"
    (kok / "config").mkdir(parents=True)
    (kok / "config" / "yayin.toml").write_text(
        f'[yayin]\nsanatci_adi = "Orvane"\ndagitimci = "routenote"\netiket = ""\n[master]\nlufs = -14.0\n'
        f'gercek_tepe_dbtp = -1.2\nornekleme = 44100\n[routenote]\nspotify_sanatci_id = "{sid}"\n', encoding="utf-8")
    c = kok / "calisma"
    return kok, c, elle.yeni(c, kok, "Kendi Şarkım")["kimlik"]


def test_elle_baska_sanatciya_kayitli_profil_baglanmaz(tmp_path):
    """Yeni taslağın profil kutusu Orvane'in profiliyle dolu gelir; sanatçı değiştirilip kutu öyle kaldıysa yayın
    Orvane'in Spotify profiline bağlanmaz."""
    kok, c, k = _elle(tmp_path)
    m = elle.oku(c, k)
    assert m["spotify_sanatci_id"] == "AAAAAAAAAAAAAAAAAAAAAA" == m["varsayilan_spotify_id"]
    assert elle.routenote_meta(m)["rn_spotify_id"] == "AAAAAAAAAAAAAAAAAAAAAA"  # Orvane: kayıtlı profil
    elle.guncelle(c, k, {"sanatci": "Başka Ad"})
    assert any("profile bağlanmaz" in u for u in elle.kontrol(c, k)["uyari"])
    m = json.loads((elle.routenote_hazirla(c, k) / "metadata.json").read_text(encoding="utf-8"))
    assert m["rn_spotify_id"] is None and m["yeni_profil"] is True
    elle.guncelle(c, k, {"spotify_sanatci_id": "BBBBBBBBBBBBBBBBBBBBBB"})  # o sanatçının kendi profili
    assert elle.routenote_meta(elle.oku(c, k))["rn_spotify_id"] == "BBBBBBBBBBBBBBBBBBBBBB"


def test_elle_ilk_yayin_tarihi_gelecekte_olamaz(tmp_path):
    _, c, k = _elle(tmp_path)
    elle.guncelle(c, k, {"orijinal_tarih": (date.today() + timedelta(days=3)).isoformat()})
    assert any("gelecekte" in e for e in elle.kontrol(c, k)["eksik"])
    elle.guncelle(c, k, {"orijinal_tarih": "2020-01-01", "yayin_tarihi": "2019-01-01"})
    assert any("yayın tarihinden sonra" in e for e in elle.kontrol(c, k)["eksik"])
    elle.guncelle(c, k, {"yayin_tarihi": ""})
    assert not any("tarih" in e.casefold() for e in elle.kontrol(c, k)["eksik"])


@ffmpeg_gerekli
def test_elle_okunamayan_ses_yarim_flac_birakmaz(tmp_path):
    _, c, k = _elle(tmp_path)
    with pytest.raises(elle.Hata, match="okunamadı"):
        elle.ses_kaydet(c, k, "bozuk.wav", b"RIFF bozuk")
    kl = elle.klasor(c, k)
    assert not list(kl.glob("*.flac")) and not list(kl.glob(".*.flac"))


# ── Pinterest ────────────────────────────────────────────────


def _jpeg(renk=(30, 60, 90), boyut=(900, 1200)):
    from PIL import Image

    b = io.BytesIO()
    Image.new("RGB", boyut, renk).save(b, "JPEG")
    return b.getvalue()


def _pin(no):
    return {"id": str(no), "type": "pin", "seo_alt_text": "calm ocean at dusk", "image_signature": f"imza{no}",
            "images": {"orig": {"url": f"https://i.pinimg.com/{no}.jpg", "width": 1200, "height": 1200}}}


def test_pinterest_kaynaksiz_gorsel_yeniden_secilir_basarisiz_yeni_eskiyi_bozmaz(tmp_path):
    c = tmp_path / "c"
    d = durum.Durum("a", "X", "A", asama="onaylandi", analiz={"stil": "melancholic ballad"})
    durum.yaz(c, d)
    k = durum.klasor(c, "a")
    (k / "kapak_pinterest.jpg").write_bytes(b"yarim")  # kaynak yazılmadan düşmüş
    yol = pinterest.getir(c, d, arayici=lambda q: [_pin(1)], indirici=lambda u: _jpeg())
    assert yol.read_bytes() != b"yarim" and (k / "kapak_kaynak.json").exists()
    once = yol.read_bytes()

    def bozuk(_u):
        raise OSError("bağlantı kesildi")

    with pytest.raises(pinterest.Bulunamadi):
        pinterest.getir(c, d, yeni=True, arayici=lambda q: [_pin(2)], indirici=bozuk)
    assert yol.read_bytes() == once and not list(k.glob(".*yaziliyor*"))


def test_onay_epostasi_gecikme_olcutunu_onay_tarihine_baglar(tmp_path):
    """Tarihsiz yayında gecikme ölçütü gönderim + 14 gündü: erken onaylanan parçanın teslim sorunu geç, geç onaylanan
    parça teslim sürerken yanlış "yayın tarihi geçti" alarmı veriyordu."""
    from tests.test_performans import _ileti as ham
    from tests.test_performans import _sarki
    from yanki import takip

    c = tmp_path / "calisma"
    _sarki(c, "numb", "Numb", asama="yuklendi", routenote={"upc": "5064149827466", "adim": "gonderildi"},
           yukleme={"upc": "5064149827466", "dagitimci": "routenote", "en_gec_yayin": "2026-10-30"})
    _sarki(c, "tarihli", "Tarihli", asama="yuklendi", routenote={"upc": "5064149827467", "adim": "gonderildi"},
           yukleme={"upc": "5064149827467", "dagitimci": "routenote", "yayin_tarihi": "2026-11-20"})
    eposta.isle(c, [eposta.ayristir(ham("Release approved", "Numb has been approved", mid="<a>")),
                    eposta.ayristir(ham("Release approved", "Tarihli has been approved", mid="<b>"))])
    numb = takip.yukleme_bilgisi(c, "numb")
    assert numb["dagitim_durumu"] == "approved" and numb["en_gec_yayin"] == "2026-10-23"  # 16 Eki + 7
    tarihli = takip.yukleme_bilgisi(c, "tarihli")
    assert tarihli["dagitim_durumu"] == "approved" and "en_gec_yayin" not in tarihli


def _secimli(c, kimlik, adaylar, secilen, oto=None):
    """adaylar: (no, söz WER'i, CFG); CFG farkı tarifi ayırır (2026-10-15: CFG 7 → 10 yeniden üretimi)."""
    d = durum.Durum(kimlik, "A", kimlik)
    d.adaylar = [durum.Aday(no, f"adaylar/{no}.flac", no, {"soz_wer": {"deger": w}}, True,
                            tarif={"model": "xl", "lora": "ep20", "ek": {"cfg": cfg},
                                   "tarih": "2026-10-15T18:47" if cfg == 10 else "2026-10-13T16:14"})
                 for no, w, cfg in adaylar]
    d.secilen = secilen
    if oto is not None:
        d.notlar.append({"otomatik_onay": {"aday": oto}})
    d.gec("onaylandi")
    durum.yaz(c, d)


def test_isabet_kulak_secimlerini_olcer(tmp_path):
    """Faz 12 ölçütü: öneri kuralı kulak seçimini ne sıklıkla tutuyor; otomatik onaylar ölçüme girmez."""
    from yanki import onay

    c = tmp_path / "calisma"
    _secimli(c, "tutan", [(1, 0.05, 10), (2, 0.02, 10)], secilen=2)
    _secimli(c, "kacan", [(1, 0.05, 10), (2, 0.02, 10), (3, 0.09, 10)], secilen=3)
    # eski tarifin adayını kulakla seçmiş: kural en yeni tarife bakar, ıska sayılır
    _secimli(c, "eski", [(1, 0.01, 7), (5, 0.04, 10), (6, 0.03, 10)], secilen=1)
    _secimli(c, "oto", [(1, 0.05, 10), (2, 0.02, 10)], secilen=2, oto=2)  # otomatik onay: ölçülmez
    _secimli(c, "tek", [(1, 0.05, 10)], secilen=1)  # karar yok
    o = onay.isabet(c)
    assert o["sarki"] == 3 and o["isabet"] == 1 and o["yalniz_wer"] == 2
    assert abs(o["rastgele"] - (1 / 2 + 1 / 3 + 1 / 3)) < 1e-9
    assert {s["kimlik"]: s["oneri"] for s in o["satirlar"]} == {"tutan": 2, "kacan": 2, "eski": 6}


def test_isabet_komutu_olcumu_bir_kez_kaydeder(tmp_path, monkeypatch, capsys):
    import argparse
    from dataclasses import replace

    from yanki import ayarlar, cli

    c = tmp_path / "calisma"
    _secimli(c, "tutan", [(1, 0.05, 10), (2, 0.02, 10)], secilen=2)
    asil = ayarlar.yukle
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda *a, **k: replace(asil(), kok=tmp_path))
    for _ in range(2):
        assert cli._isabet(argparse.Namespace(json=False, ayrinti=True)) == 0
    cikti = capsys.readouterr().out
    assert "1 şarkıda 1 isabet" in cikti and "✓ tutan" in cikti
    seri = json.loads((c / "dinleme" / "isabet.json").read_text(encoding="utf-8"))
    assert len(seri) == 1 and seri[0]["oran"] == 1.0
