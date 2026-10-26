"""Gündem keşfi (yanki/trend.py, 2026-10-26)."""

from datetime import date, timedelta

from yanki import kesif, trend


def _g(liste, sira, sanatci, ad, toplam=100, kaynak=None, dinlenme=None, isrc=None):
    return trend.Giris(kaynak or liste.split(":")[0], liste, sira, toplam, sanatci, ad, isrc, dinlenme)


def test_ana_sanatci():
    assert trend.ana_sanatci("Tame Impala & JENNIE") == "Tame Impala"
    assert trend.ana_sanatci("Sabrina Carpenter feat. X") == "Sabrina Carpenter"
    assert trend.ana_sanatci("Rosé, Bruno Mars") == "Rosé"
    assert trend.ana_sanatci("Earth, Wind & Fire".split(",")[0]) == "Earth"  # virgüllü grup adı ilk parçayı verir


def test_puan_liste_sayisi_ve_sirasi():
    g = [_g("deezer:USA", 1, "A", "Bir"), _g("apple:us", 2, "A", "Bir"), _g("deezer:USA", 90, "B", "Iki")]
    p = trend.puanla(g)
    bir, iki = p[kesif.liste.kimlik("A", "Bir")], p[kesif.liste.kimlik("B", "Iki")]
    assert bir["skor"] > iki["skor"] and bir["en_iyi"] == 1 and len(bir["listeler"]) == 2
    # global liste ve Spotify daha ağır
    p2 = trend.puanla([_g("deezer:Worldwide", 1, "C", "Uc"), _g("spotify:Top 50 - USA", 1, "D", "Dort", 50)])
    c, d = p2[kesif.liste.kimlik("C", "Uc")], p2[kesif.liste.kimlik("D", "Dort")]
    assert c["skor"] == d["skor"] == round(1.5 * 1.3, 3)


def test_yukselis_yeni_giris_ve_gunluk_dinlenme():
    bugun = date(2026, 10, 26)
    sp = "spotify:Top 50 - Global"
    onceki = {(bugun - timedelta(days=5)).isoformat(): [_g("deezer:USA", 60, "A", "Eski"),
                                                          _g(sp, 40, "S", "Hit", 50, dinlenme=1_000_000)],
              (bugun - timedelta(days=1)).isoformat(): [_g(sp, 30, "S", "Hit", 50, dinlenme=9_000_000)]}
    g = [_g("deezer:USA", 10, "A", "Eski"), _g("deezer:USA", 10, "Y", "Yeni"),
         _g("spotify:Top 50 - Global", 5, "S", "Hit", 50, dinlenme=11_000_000)]
    p = trend.puanla(g, onceki, bugun)
    eski, yeni, hit = (p[kesif.liste.kimlik(*x)] for x in (("A", "Eski"), ("Y", "Yeni"), ("S", "Hit")))
    assert eski["yukselis"] == 50 and eski["skor"] > 0.91 * 1.4  # 50 sıra yükseldi: +%50
    assert yeni["ilk_gorulme"] == bugun.isoformat() and yeni["skor"] == round(0.91 * 1.3, 3)
    assert hit["gunluk_dinlenme"] == 2_000_000  # en yakın önceki görüntüyle fark


def test_adaylar_duzenleme_ve_esik_atilir():
    p = trend.puanla([_g("deezer:USA", 1, "A", "Song"), _g("deezer:USA", 2, "B", "Song (Sped Up)"),
                      _g("deezer:USA", 100, "C", "Dip")])
    a = trend.adaylar(p, trend.Ayar(en_az_puan=0.5), set())
    assert [x.ad for x in a] == ["Song"] and a[0].neden == "trend" and a[0].geri_geldi is False


def test_trend_adayi_puani_gundemle_ve_bayatlar():
    ortak = dict(youtube_izlenme=10**6, sanatci_uyusuyor=True, soz_var=True, ingilizce=True, turler=["pop"],
                 sure_sn=200, geri_geldi=False, neden="trend")
    a = kesif.Aday("A", "B", "trend:x", trend={"skor": 10, "tarih": date.today().isoformat()}, **ortak)
    b = kesif.Aday("C", "D", "trend:x", trend={"skor": 2, "tarih": date.today().isoformat()}, **ortak)
    assert a.puan > b.puan > 0 and kesif.hal(a) == "gündemde" and a.populer and not kesif.spotifya_sorulur(a)
    a.trend["tarih"] = (date.today() - timedelta(days=10)).isoformat()
    assert a.trend_skoru == 0 and kesif.hal(a) == "gündemden düştü" and a.puan < b.puan
    a.trend["tarih"], a.ingilizce = date.today().isoformat(), False  # yabancı ama İngilizce olmayan: listeye girmez
    assert a.puan == 0


def test_kaynak_hatasi_digerlerini_durdurmaz(tmp_path):
    def json_al(url, p=None):
        if "user/" in url:
            return {"data": [{"title": "Top USA", "id": 7, "nb_tracks": 100}]}
        if "playlist/7" in url:
            return {"data": [{"title": "Hit", "artist": {"name": "A"}, "isrc": "USAAA2600001"}]}
        raise OSError("apple düştü")

    satirlar = []
    g = trend.topla(tmp_path, trend.Ayar(deezer=("USA", "Mars"), apple=("us",)), json_al, yaz=satirlar.append)
    assert [(x.liste, x.isrc) for x in g] == [("deezer:USA", "USAAA2600001")]
    assert any("Mars" in s for s in satirlar) and any("apple" in s.lower() for s in satirlar)


def test_spotify_kopruden_okunur():
    class Kopru:
        def degerlendir(self, ifade, sn):
            assert "Stillmore.playlist.scan" in ifade
            return [{"n": 1, "name": "Hit", "artist": "S", "isrc": "X", "plays": 5},
                    {"n": 2, "name": "", "artist": "Z"}]

    g = trend.spotify_cek(Kopru(), "Top 50 - Global", "37i9")
    assert [(x.liste, x.sira, x.toplam, x.dinlenme) for x in g] == [("spotify:Top 50 - Global", 1, 1, 5)]


def test_anlik_goruntu_yazilir_ve_eskisi_silinir(tmp_path):
    bugun = date(2026, 10, 26)
    eski = trend.klasor(tmp_path) / "2026-09-01.json"
    eski.parent.mkdir(parents=True)
    eski.write_text('{"girisler": []}', encoding="utf-8")
    trend.anlik_yaz(tmp_path, [_g("deezer:USA", 1, "A", "B")], bugun)
    assert not eski.exists()
    assert list(trend.anliklar(tmp_path, bugun + timedelta(days=1))) == ["2026-10-26"]
