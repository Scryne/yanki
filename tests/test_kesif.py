import json

import pytest

from yanki import durum, kesif, liste, spotify, takip

# STILLMORE v12.1 `csv.playlist` başlığı birebir (spicetify/stillmore-finder.js → toCsv: BOM, virgül, tırnak)
STILLMORE_BASLIK = ("#,Parça,Sanatçı,Spotify ID,Çalınabilir,Durum,ISRC,Distribütör,Label,Çıkış,Spotify'a ilk çıkış,"
                    "Dinlenme,Sanatçı aylık dinleyici,Sanatçının son çıkışı,Yeniden yüklenmiş,Eklenme")


def _parca(id_, ad, sanatci, oynar=True, isrc=None, neden=None):
    t = {"id": id_, "name": ad, "type": "track", "artists": [{"id": "a-" + sanatci, "name": sanatci}],
         "album": {"name": ad, "release_date": "2015-01-01"}, "is_playable": oynar,
         "external_ids": {"isrc": isrc} if isrc else {}}
    if neden:
        t["restrictions"] = {"reason": neden}
    return t


class SahteSpotify:
    def __init__(self, isrc=None, arama=None, playlist=None):
        self.isrc, self.arama, self.pl = isrc or {}, arama or {}, playlist or []
        self.sorgular = []

    def isrc_ara(self, isrc, market):
        return self.isrc.get(isrc, [])

    def ara(self, sorgu, market, adet=10):
        self.sorgular.append(sorgu)
        return self.arama.get(sorgu, [])[:adet]

    def playlist_parcalari(self, pid, market):
        self.tam_tarama = getattr(self, "tam_tarama", 0) + 1
        yield from self.pl

    def playlist(self, pid):
        return {"snapshot_id": getattr(self, "snapshot", "s1")}

    def parca(self, pid, market):
        return {"id": pid, "is_playable": pid in getattr(self, "baska_yerde_acik", set())}


def test_sade_ad():
    assert kesif.sade_ad("Mr. Brightside - Remastered 2011") == "mr brightside"
    assert kesif.sade_ad("Yalnızlık Senfonisi (feat. X) [Live]") == "yalnizlik senfonisi"
    assert kesif.sade_ad_gorunur("Song (2011 Remaster)") == "Song"
    assert kesif.sade_ad_gorunur("Song (Interlude)") == "Song (Interlude)"


def test_stillmore_csv_yalniz_calinamayan_ve_geri_gelmemis(tmp_path):
    satirlar = [
        STILLMORE_BASLIK,
        '1,Açık Şarkı,Biri,AAAAAAAAAAAAAAAAAAAAAA,Evet,,TR1,,,,,100,,,,',
        '2,"Kayıp, Şarkı",Sanatçı A,BBBBBBBBBBBBBBBBBBBBBB,Hayır,Kaldırılmış,trx001,DistroKid,L,2019-03-01,,'
        '"1234567",5000,,,2024-01-01',
        '3,Geri Gelen,Sanatçı B,CCCCCCCCCCCCCCCCCCCCCC,Hayır,Kaldırılmış,TRX002,,,,,10,,,DDDDDDDDDDDDDDDDDDDDDD,',
        '4,Ülke Şarkısı,"Sanatçı C, Konuk",EEEEEEEEEEEEEEEEEEEEEE,Hayır,Ülkende kapalı (Türkiye),,,,,,,,,,',
    ]
    yol = tmp_path / "stillmore-playlist.csv"
    yol.write_text("﻿" + "\n".join(satirlar), encoding="utf-8")
    a = kesif.stillmore_csv(yol)
    assert [(x.sanatci, x.ad, x.neden) for x in a] == [("Sanatçı A", "Kayıp, Şarkı", "kaldirildi"),
                                                       ("Sanatçı C", "Ülke Şarkısı", "kismi")]
    assert a[0].isrc == "TRX001" and a[0].spotify_dinlenme == 1234567 and a[0].kaynak == "stillmore:" + yol.name


def test_playlist_tara_calinamayanlari_alir():
    # ikisinin de nedeni "market" (Spotify ikisini ayırmıyor); ayrım başka pazarlara bakarak
    sp = SahteSpotify(playlist=[_parca("1" * 22, "Var", "X"), _parca("2" * 22, "Yok", "Y", False, "ISRC1", "market"),
                                _parca("3" * 22, "Kapalı", "Z", False, neden="market")])
    sp.baska_yerde_acik = {"3" * 22}
    from collections import Counter

    sayac = Counter()
    a = kesif.playlist_tara(sp, "p" * 22, ("TR", "US"), sayac)
    assert [(x.ad, x.isrc, x.kapali_pazarlar) for x in a] == [("Yok", "ISRC1", ["TR"]), ("Kapalı", None, ["TR"])]
    # pazarlar doğrulamada sorulur: biri her yerde kapalı, öteki yalnız ana pazarda
    a = [kesif.bosluk_dogrula(sp, x, ("TR", "US")) for x in a]
    assert [(x.neden, x.kapali_pazarlar) for x in a] == [("kaldirildi", ["TR", "US"]), ("kismi", ["TR"])]
    assert sayac == Counter({"X": 1, "Y": 1, "Z": 1})


def test_bosluk_dogrula_isrc_ile_geri_gelmis():
    a = kesif.Aday("Sanatçı", "Şarkı", "x", spotify_id="old", isrc="I1")
    sp = SahteSpotify(isrc={"I1": [_parca("old", "Şarkı", "Sanatçı", False), _parca("new", "Şarkı", "Sanatçı")]})
    kesif.bosluk_dogrula(sp, a, "TR")
    assert a.geri_geldi is True and a.geri_gelen[0]["neden"] == "isrc" and a.puan == 0


def test_bosluk_dogrula_ayni_sanatci_ayni_ad_ve_rakip_sayimi():
    a = kesif.Aday("Sanatçı", "Şarkı - Remastered", "x", spotify_id="old")
    arama = {'track:"Şarkı"': [
        _parca("c1", "Şarkı", "Başka Biri"),             # rakip cover
        _parca("c2", "Şarkı (Cover)", "Üçüncü"),         # sade ad aynı → rakip
        _parca("c3", "Şarkı", "Orvane"),                 # bizim: sayılmaz
        _parca("c4", "Şarkı", "Dördüncü", oynar=False),  # çalınamıyor: sayılmaz
        _parca("c5", "Başka Şarkı", "Beşinci"),          # ad farklı
    ]}
    kesif.bosluk_dogrula(SahteSpotify(arama=arama), a, "TR", kendi_sanatci="Orvane")
    assert a.geri_geldi is False and a.rakip_cover == 2
    arama['track:"Şarkı"'].append(_parca("c6", "Şarkı", "Sanatçı"))
    kesif.bosluk_dogrula(SahteSpotify(arama=arama), a, "TR")
    assert a.geri_geldi is True and a.geri_gelen == [{"id": "c6", "sanatci": "Sanatçı", "ad": "Şarkı", "neden": "ad"}]


def test_talep_istenmeyen_surumleri_atar():
    a = kesif.Aday("Sanatçı", "Şarkı", "x")
    sonuc = [("Sanatçı - Şarkı (Live at Harbiye)", 9_000_000), ("Şarkı karaoke", 8_000_000),
             ("Sanatçı - Şarkı (Official Video)", 2_000_000), ("Sanatçı - Şarkı (lyrics)", 300_000),
             ("Bambaşka video", 50_000_000), ("Sanatçı - Şarkı", None)]
    kesif.talep_olc(a, arama=lambda q: sonuc)
    assert a.youtube_izlenme == 2_000_000 and "Official" in a.youtube_baslik


def test_puan_ve_siralama():
    x = kesif.Aday("A", "1", "k", youtube_izlenme=1000, rakip_cover=1, geri_geldi=False, sanatci_uyusuyor=True)
    y = kesif.Aday("B", "2", "k", youtube_izlenme=900, rakip_cover=0, geri_geldi=False, sanatci_uyusuyor=True)
    z = kesif.Aday("C", "3", "k", youtube_izlenme=10**9, geri_geldi=True)
    assert [a.sanatci for a in kesif.sirala({a.kimlik: a for a in (x, y, z)})] == ["B", "A", "C"]


def test_birlestir_ilk_gorulmeyi_ve_olcumleri_korur(tmp_path):
    a = kesif.Aday("A", "Ş", "stillmore:x.csv", spotify_dinlenme=50, youtube_izlenme=10, geri_geldi=False)
    kesif.birlestir(tmp_path, [a])
    ilk = kesif.oku(tmp_path)[a.kimlik].ilk_gorulme
    b = kesif.Aday("A", "Ş", "playlist:p")
    k = kesif.birlestir(tmp_path, [b])[a.kimlik]
    assert (k.ilk_gorulme, k.spotify_dinlenme, k.youtube_izlenme, k.kaynak) == (ilk, 50, 10, "playlist:p")


def test_listeye_ekle_dogrulanmisi_ekler_mevcudu_atlar(tmp_path):
    lyol = tmp_path / "liste.toml"
    lyol.write_text('# açıklama korunur\n[[sarki]]\nsanatci = "Var"\nad = "Olan"\n', encoding="utf-8")
    calisma = tmp_path / "calisma"
    (calisma / "zaten-uretilmis").mkdir(parents=True)
    adaylar = [
        kesif.Aday("Var", "Olan", "k", youtube_izlenme=10**6, geri_geldi=False),            # listede
        kesif.Aday("Zaten", "Üretilmiş", "k", youtube_izlenme=10**6, geri_geldi=False),     # calisma'da
        kesif.Aday("Geri", "Gelen", "k", youtube_izlenme=10**6, geri_geldi=True),
        kesif.Aday("Doğrulanmamış", "X", "k", youtube_izlenme=10**6),
        kesif.Aday("Yeni \"Tırnak\"", "Şarkı (2011 Remaster)", "k", youtube_izlenme=5000, geri_geldi=False),
        kesif.Aday("İkinci", "Y", "k", youtube_izlenme=4000, geri_geldi=False),
    ]
    for x in adaylar:
        x.sanatci_uyusuyor = True
    eklenen = kesif.listeye_ekle(adaylar, lyol, calisma, adet=1)
    assert [x.sanatci for x in eklenen] == ['Yeni "Tırnak"']
    metin = lyol.read_text(encoding="utf-8")
    assert metin.startswith("# açıklama korunur") and "YouTube 5,000 izlenme" in metin
    assert liste.yukle(lyol)[-1] == liste.Sarki('Yeni "Tırnak"', "Şarkı")
    assert kesif.listeye_ekle(adaylar, lyol, calisma, adet=5)[0].sanatci == "İkinci"


# ── Spotify istemcisi ───────────────────────────────────────
class KayitliSpotify(spotify.Spotify):
    def __init__(self, tmp_path, yanitlar):
        super().__init__(tmp_path, "cid", "sec")
        self.yanitlar, self.istekler, self.aralik_sn = list(yanitlar), [], 0

    def _http(self, yontem, url, basliklar, veri=None):
        self.istekler.append((yontem, url))
        kod, govde, *bas = self.yanitlar.pop(0)
        return kod, (bas[0] if bas else {}), json.dumps(govde).encode()


TOKEN = (200, {"access_token": "t", "expires_in": 3600})


def test_ara_sayfa_basi_10_ve_offset(tmp_path):
    sayfa = {"tracks": {"items": [{"id": str(i)} for i in range(10)]}}
    sp = KayitliSpotify(tmp_path, [TOKEN, (200, sayfa), (200, {"tracks": {"items": [{"id": "x"}]}})])
    assert len(sp.ara("q", "TR", adet=20)) == 11
    assert "limit=10" in sp.istekler[1][1] and "offset=0" in sp.istekler[1][1] and "offset=10" in sp.istekler[2][1]


def test_429_uzun_bekleme_kalici_kilit(tmp_path):
    sp = KayitliSpotify(tmp_path, [TOKEN, (429, {"error": {"reason": "QUOTA_EXCEEDED"}}, {"Retry-After": "83595"})])
    with pytest.raises(spotify.Sinirli) as e:
        sp.ara("q", "TR")
    assert e.value.sn == 83595 and "QUOTA_EXCEEDED" in str(e.value)
    # yeni süreç (gece koşusu) kilidi dosyadan okur ve hiç istek atmaz
    sp2 = KayitliSpotify(tmp_path, [])
    with pytest.raises(spotify.Sinirli):
        sp2.ara("q", "TR")
    assert sp2.istekler == []


def test_gunluk_tavan(tmp_path):
    sp = KayitliSpotify(tmp_path, [TOKEN] + [(200, {"tracks": {"items": []}})] * 3)
    sp.gunluk_butce = 2
    sp.ara("a", "TR")
    sp.ara("b", "TR")
    with pytest.raises(spotify.KotaDoldu):
        sp.ara("c", "TR")
    assert len([i for i in sp.istekler if "/search" in i[1]]) == 2


def test_playlist_403_aciklayici(tmp_path):
    sp = KayitliSpotify(tmp_path, [(403, {"error": "forbidden"})])
    sp.token_yolu.parent.mkdir(parents=True)
    sp.token_yolu.write_text(json.dumps({"access_token": "u", "refresh_token": "r", "bitis": 9e12}))
    with pytest.raises(spotify.SpotifyHatasi, match="kendi ya da ortak"):
        list(sp.playlist_parcalari("p" * 22, "TR"))
    assert "/items" in sp.istekler[0][1]


def test_playlist_item_ve_track_alanlari(tmp_path):
    s1 = {"items": [{"item": {"id": "1", "type": "track"}}, {"track": {"id": "2", "type": "track"}},
                    {"item": {"id": "3", "type": "episode"}}, {"is_local": True, "item": {"id": "4", "type": "track"}}],
          "next": "https://api.spotify.com/v1/playlists/p/items?offset=50"}
    sp = KayitliSpotify(tmp_path, [(200, s1), (200, {"items": [{"item": {"id": "5", "type": "track"}}], "next": None})])
    sp.token_yolu.parent.mkdir(parents=True)
    sp.token_yolu.write_text(json.dumps({"access_token": "u", "refresh_token": "r", "bitis": 9e12}))
    assert [t["id"] for t in sp.playlist_parcalari("p" * 22, "TR")] == ["1", "2", "5"]


def test_env_dosyasi_ve_ortam(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text('# yorum\nSPOTIFY_CLIENT_ID="abc"\nSPOTIFY_CLIENT_SECRET=def\n', encoding="utf-8")
    monkeypatch.delenv("SPOTIFY_CLIENT_ID", raising=False)
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "ortam")
    sp = spotify.Spotify(tmp_path)
    assert (sp.client_id, sp.client_secret, sp.yonlendirme) == ("abc", "ortam", spotify.YONLENDIRME)


def test_pkce_adresi(tmp_path):
    adres, dogrulayici, durum_ = spotify.Spotify(tmp_path, "cid", "x").baglanti_adresi()
    assert "code_challenge_method=S256" in adres and "127.0.0.1%3A8766" in adres and durum_ in adres
    assert 43 <= len(dogrulayici) <= 128


@pytest.mark.parametrize("girdi", ["https://open.spotify.com/playlist/37i9dQZF1DXcBWIGoYBM5M?si=abc",
                                   "spotify:playlist:37i9dQZF1DXcBWIGoYBM5M", "37i9dQZF1DXcBWIGoYBM5M"])
def test_kimlik_ayikla(girdi):
    assert spotify.kimlik_ayikla(girdi) == "37i9dQZF1DXcBWIGoYBM5M"


def test_kimlik_ayikla_hatali():
    with pytest.raises(ValueError):
        spotify.kimlik_ayikla("https://open.spotify.com/track/kisa")


# ── Takip ───────────────────────────────────────────────────
def _yuklenmis(tmp_path, kimlik="adele-someone-like-you", ad="Someone Like You", isrc="GXM2X2626596"):
    d = durum.Durum(kimlik, "Adele", ad, asama="yuklendi")
    durum.yaz(tmp_path, d)
    (tmp_path / kimlik / "paket").mkdir()
    (tmp_path / kimlik / "paket" / "metadata.json").write_text(
        json.dumps({"yukleme": {"isrc": isrc, "yayin_tarihi": "2026-10-28"}}), encoding="utf-8")
    return d


def test_takip_henuz_yayinda_degil(tmp_path):
    _yuklenmis(tmp_path)
    (d, uyari), = takip.takip_et(SahteSpotify(), tmp_path, "Orvane", "TR")
    assert d.asama == "yuklendi" and d.yayin["son"]["canli"] is False and uyari == []
    assert durum.oku(tmp_path, d.kimlik).yayin["son"]["yayin_tarihi"] == "2026-10-28"


def test_takip_canli_arama_sirasi_ve_kayip(tmp_path):
    _yuklenmis(tmp_path)
    bizim = _parca("ours", "Someone Like You", "Orvane", isrc="GXM2X2626596")
    sp = SahteSpotify(isrc={"GXM2X2626596": [bizim]},
                      arama={"Someone Like You": [_parca("adele", "Someone Like You", "Adele"),
                                                  _parca("x", "Someone Like You", "Biri"), bizim]})
    (d, uyari), = takip.takip_et(sp, tmp_path, "Orvane", "TR")
    assert d.asama == "yayinda" and uyari == []
    assert (d.yayin["son"]["arama_sirasi"], d.yayin["son"]["sanatci_id"]) == (3, "a-Orvane")
    assert len(d.yayin["gecmis"]) == 1
    takip.takip_et(sp, tmp_path, "Orvane", "TR")  # aynı sonuç geçmişe yeni satır yazmaz
    assert len(durum.oku(tmp_path, d.kimlik).yayin["gecmis"]) == 1
    (d, uyari), = takip.takip_et(SahteSpotify(), tmp_path, "Orvane", "TR")
    assert d.yayin["son"]["kayip"] is True and "kaldırılmış olabilir" in uyari[0]
    assert d.asama == "yayinda" and len(d.yayin["gecmis"]) == 2


def test_takip_profil_bolunmesi(tmp_path):
    _yuklenmis(tmp_path)
    _yuklenmis(tmp_path, "coldplay-the-scientist", "The Scientist", "GXM2X2610493")
    p1 = _parca("1", "Someone Like You", "Orvane", isrc="GXM2X2626596")
    p2 = _parca("2", "The Scientist", "Orvane", isrc="GXM2X2610493")
    p2["artists"][0]["id"] = "baska-profil"
    takip.takip_et(SahteSpotify(isrc={"GXM2X2626596": [p1], "GXM2X2610493": [p2]}), tmp_path, "Orvane", "TR")
    assert takip.profil_kimlikleri(tmp_path) == {"a-Orvane", "baska-profil"}


def test_takip_isrc_yoksa_uyarir(tmp_path):
    d = durum.Durum("x-y", "X", "Y", asama="yuklendi")
    durum.yaz(tmp_path, d)
    (_, uyari), = takip.takip_et(SahteSpotify(), tmp_path, "Orvane", "TR")
    assert "ISRC yok" in uyari[0]


def test_duzenleme_ve_takma_ad_eklenmez(tmp_path):
    assert kesif.Aday("X", "Satisfya Slowed + Bass Boosted", "k").duzenleme
    assert kesif.Aday("X", "Shorty Party (Sped Up Tik Tok) - Remix", "k").duzenleme
    assert not kesif.Aday("X", "Serial Killer", "k").duzenleme
    a = kesif.Aday("Lizzy Rey", "Serial Killer", "k", geri_geldi=False)
    kesif.talep_olc(a, arama=lambda q: [("Lana Del Rey - Serial Killer (Unreleased)", 3_000_000)])
    assert a.youtube_izlenme == 3_000_000 and a.sanatci_uyusuyor is False and a.puan == 0
    b = kesif.Aday("Sezen Aksu", "Gülümse", "k", geri_geldi=False)
    kesif.talep_olc(b, arama=lambda q: [("Sezen Aksu - Gülümse (Official Video)", 7_000_000)])
    assert b.sanatci_uyusuyor is True and b.puan == 7_000_000
    lyol = tmp_path / "liste.toml"
    lyol.write_text("", encoding="utf-8")
    (tmp_path / "c").mkdir()
    assert [x.sanatci for x in kesif.listeye_ekle([a, b], lyol, tmp_path / "c", 5)] == ["Sezen Aksu"]


@pytest.mark.parametrize(("sanatci", "baslik", "beklenen"), [
    ("Del", "Lana Del Rey - Put Me in a Movie", False),
    ("Lana Del Rey", "Lana Del Rey - Put Me in a Movie (Unreleased)", True),
    ("Sezen Aksu", "Sezen Aksu & Tarkan - Şarkı", True),
    ("Tarkan", "Sezen Aksu & Tarkan - Şarkı", True),
    ("1nonly", "1nonly x Ciscaux - Cotton Candy Swirls", True),
    ("Adele", "Someone Like You (Official Video) Adele", True),
    ("¥$", "¥$ - FIELD TRIP", None),
    ("Del", "put me in a movie- Lana del rey", False),
    ("Del", "Brite Lites || Lana Del Rey full song", False),
    ("Day$okee", "Day$okee- MAMACITA feat REDEMBRECE (prod SPLXTSTXCS)", True),
    ("JAY-Z", "JAY-Z - Empire State Of Mind", True),
    ("HAARPER", "HAARPER - Cadavers in My Cadillac (Lyrics)", True),
    ("Del", "Lana Del Rey-Mermaid Motel(lyrics)", False),
    ("JAY-Z", "JAY-Z Empire State Of Mind", True),
])
def test_sanatci_eslesir(sanatci, baslik, beklenen):
    assert kesif.sanatci_eslesir(sanatci, baslik) is beklenen


def test_soz_kontrol_sozsuz_ve_uzun():
    from yanki import ag

    def sozsuz(url, p):
        if url.endswith("/get"):
            return {"instrumental": True, "plainLyrics": None, "duration": 1080}
        raise AssertionError

    a = kesif.soz_kontrol(kesif.Aday("GY!BE", "East Hastings", "k", youtube_izlenme=10**6, geri_geldi=False), sozsuz)
    assert a.soz_var is False and a.puan == 0

    def uzun(url, p):
        return {"plainLyrics": "la la\nla", "duration": 600}

    b = kesif.soz_kontrol(kesif.Aday("A", "B", "k", youtube_izlenme=10**6, geri_geldi=False), uzun)
    assert b.soz_var is True and b.sure_sn == 600 and b.puan == 0

    def yok(url, p):
        if url.endswith("/get"):
            raise ag.Bulunamadi(url)
        return []

    assert kesif.soz_kontrol(kesif.Aday("A", "B", "k"), yok).soz_var is False


def test_puan_kapali_pazar_orani():
    tam = kesif.Aday("A", "1", "k", youtube_izlenme=1000, geri_geldi=False, sanatci_uyusuyor=True,
                     bakilan_pazarlar=["US", "GB", "DE", "TR"], kapali_pazarlar=["US", "GB", "DE", "TR"])
    yarim = kesif.Aday("B", "2", "k", youtube_izlenme=1000, geri_geldi=False, sanatci_uyusuyor=True,
                       bakilan_pazarlar=["US", "GB", "DE", "TR"], kapali_pazarlar=["DE", "TR"])
    assert (tam.puan, yarim.puan) == (1000, 500)
    assert (kesif.hal(tam), kesif.hal(yarim)) == ("kaldırılmış", "kaldırılmış")
    yarim.neden = "kismi"
    assert kesif.hal(yarim) == "kısmen kapalı"


def test_bosluk_dogrula_csv_adayini_pazar_pazar_sorar():
    sp = SahteSpotify()
    sp.baska_yerde_acik = {"id1"}  # her pazarda açık: aynı parça geri gelmiş
    a = kesif.bosluk_dogrula(sp, kesif.Aday("S", "Ş", "k", spotify_id="id1"), ("US", "GB"))
    assert a.geri_geldi is True and a.geri_gelen[0]["neden"] == "ayni_parca"
    b = kesif.bosluk_dogrula(SahteSpotify(), kesif.Aday("S", "Ş", "k", spotify_id="id2"), ("US", "GB"))
    assert (b.geri_geldi, b.neden, b.kapali_pazarlar) == (False, "kaldirildi", ["US", "GB"])


# ── Katalog farkı (Deezer) ──────────────────────────────────
def _deezer(cevaplar):
    istekler = []

    def json_al(url, p=None):
        yol = url.replace("https://api.deezer.com", "")
        istekler.append(yol)
        return cevaplar[yol]

    json_al.istekler = istekler
    return json_al


DEEZER = {
    "/search/artist": {"data": [{"id": 1, "name": "Massive Attack"}]},
    "/artist/1/related": {"data": [{"id": 2, "name": "Portishead"}]},
    "/chart/0/artists": {"data": [{"id": 3, "name": "Tarkan"}]},
    "/artist/1/top": {"data": [
        {"id": 11, "title": "Teardrop", "rank": 800000, "artist": {"name": "Massive Attack"}},
        {"id": 12, "title": "Angel (Sped Up)", "rank": 900000, "artist": {"name": "Massive Attack"}},
        {"id": 13, "title": "Az Bilinen", "rank": 1000, "artist": {"name": "Massive Attack"}}]},
    "/artist/2/top": {"data": [{"id": 21, "title": "Glory Box", "rank": 700000, "artist": {"name": "Portishead"}}]},
    "/artist/3/top": {"data": [{"id": 31, "title": "Şımarık", "rank": 600000, "artist": {"name": "Tarkan"}}]},
    "/track/31": {"isrc": "TRA019700001"},
    "/track/11": {}, "/track/21": {}, "/track/13": {},
}


def test_katalog_tara_kapali_yok_var_ve_onbellek(tmp_path):
    from datetime import datetime

    from yanki import katalog

    sp = SahteSpotify(arama={
        'track:"Teardrop" artist:"Massive Attack"': [_parca("t1", "Teardrop", "Massive Attack", oynar=False)],
        'track:"Glory Box" artist:"Portishead"': [_parca("g1", "Glory Box", "Portishead")],
    })
    sp.istek_sayisi = 0
    sp.baska_yerde_acik = set()
    ayar = katalog.Ayar(tohumlar=("Massive Attack",), liste_turleri=(0,), benzer_adet=1, butce=100, min_rank=500000)
    ja = _deezer(DEEZER)
    adaylar = katalog.tara(sp, tmp_path, ("US", "GB"), ayar, json_al=ja, bildir=lambda *_: None,
                           simdi=datetime(2026, 10, 9))
    # sped up atlandı (düşük rank'lı "Az Bilinen" elle tohum olduğu için eşiğe takılmaz); Teardrop her pazarda
    # kapalı, Şımarık Spotify'da hiç yok (ad + ISRC)
    assert [(a.ad, a.neden, a.kapali_pazarlar) for a in sorted(adaylar, key=lambda a: a.ad)] == [
        ("Az Bilinen", "spotify_yok", ["US", "GB"]), ("Teardrop", "kaldirildi", ["US", "GB"]),
        ("Şımarık", "spotify_yok", ["US", "GB"])]
    on = katalog.onbellek_oku(tmp_path)
    assert {k: v.durum for k, v in on.items()} == {"11": "kapali", "13": "yok", "21": "var", "31": "yok"}
    assert list(on) == ["11", "13", "21", "31"]  # sorma sırası: tohum (rank sırasıyla) → benzer → liste
    assert "/track/31" in ja.istekler  # adla bulunamayan ISRC'yle de soruldu
    sp.sorgular.clear()
    katalog.tara(sp, tmp_path, ("US", "GB"), ayar, json_al=ja, bildir=lambda *_: None, simdi=datetime(2026, 10, 10))
    assert 'track:"Glory Box" artist:"Portishead"' not in sp.sorgular  # "var" önbellekte taze: yeniden sorulmaz


def test_katalog_butce_sinirlar(tmp_path):
    from yanki import katalog

    class Sayan(SahteSpotify):
        def ara(self, sorgu, market, adet=10):
            self.istek_sayisi += 1
            return super().ara(sorgu, market, adet)

        def isrc_ara(self, isrc, market):
            self.istek_sayisi += 1
            return []

    sp = Sayan()
    sp.istek_sayisi = 0
    ayar = katalog.Ayar(tohumlar=("Massive Attack",), liste_turleri=(0,), benzer_adet=1, butce=3, min_rank=500000)
    katalog.tara(sp, tmp_path, ("US",), ayar, json_al=_deezer(DEEZER), bildir=lambda *_: None)
    # her parça en fazla 2 istek: bütçe 3 iken 3 parçanın hepsi sorulamaz
    assert sp.istek_sayisi <= 3 and len(katalog.onbellek_oku(tmp_path)) < 3


def test_deezer_kota_ve_bulunamadi(monkeypatch):
    from yanki import ag, katalog

    monkeypatch.setattr(katalog.time, "sleep", lambda s: None)
    cevaplar = iter([{"error": {"code": 4}}, {"data": []}])
    assert katalog.deezer("/x", None, lambda u, p: next(cevaplar)) == {"data": []}
    with pytest.raises(ag.Bulunamadi):
        katalog.deezer("/track/0", None, lambda u, p: {"error": {"code": 800}})


def test_takip_pazar_pazar_sira(tmp_path):
    _yuklenmis(tmp_path)
    bizim = _parca("ours", "Someone Like You", "Orvane", isrc="GXM2X2626596")

    class Pazarli(SahteSpotify):
        def ara(self, sorgu, market, adet=10):
            return {"GB": [bizim], "DE": [_parca("x", "Someone Like You", "Adele"), bizim]}.get(market, [])

    (d, _), = takip.takip_et(Pazarli(isrc={"GXM2X2626596": [bizim]}), tmp_path, "Orvane", ("GB", "DE", "TR"))
    assert d.yayin["son"]["siralar"] == {"GB": 1, "DE": 2, "TR": None} and d.yayin["son"]["arama_sirasi"] == 1


def test_playlist_onbellek_snapshot_ve_haftalik(tmp_path):
    from collections import Counter
    from datetime import datetime

    sp = SahteSpotify(playlist=[_parca("1" * 22, "Var", "X"), _parca("2" * 22, "Yok", "Y", False)])
    gun = datetime(2026, 10, 9)
    s1 = Counter()
    assert len(kesif.playlist_tara_onbellekli(sp, "p", ("TR",), tmp_path, s1, gun)) == 1
    s2 = Counter()
    assert kesif.playlist_tara_onbellekli(sp, "p", ("TR",), tmp_path, s2, datetime(2026, 10, 12)) is None
    assert s1 == s2 == Counter({"X": 1, "Y": 1}) and sp.tam_tarama == 1
    sp.snapshot = "s2"  # playlist değişti → tam tarama
    assert kesif.playlist_tara_onbellekli(sp, "p", ("TR",), tmp_path, Counter(), datetime(2026, 10, 12)) is not None
    sp.snapshot = "s2"  # değişmedi ama hafta doldu → yine tam tarama (parça sonradan kaldırılmış olabilir)
    assert kesif.playlist_tara_onbellekli(sp, "p", ("TR",), tmp_path, Counter(), datetime(2026, 10, 20)) is not None
    assert sp.tam_tarama == 3
