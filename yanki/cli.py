"""yanki komut satırı."""

import argparse
import shutil
import sys
from pathlib import Path

from yanki import ayarlar, durum, hazirlik, liste, paket, saglik, uretim


def _durum(_: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    sonuc = saglik.kontroller(a)
    for k in sonuc:
        print(f"{'✓' if k.tamam else '✗'} {k.ad:28} {k.ayrinti}")
    sarkilar = durum.hepsi(a.kok / "calisma")
    if sarkilar:
        print()
        for d in sarkilar:
            son = (d.yayin or {}).get("son") or {}
            ek = f"  ({d.hata})" if d.hata else ""
            if son.get("canli"):
                ek += f"  [arama sırası {son['arama_sirasi'] or '>' + str(son['arama_limiti'])}, {son['zaman'][:10]}]"
            print(f"  {d.asama:11} {d.sanatci} — {d.ad}{ek}")
    return 0 if all(k.tamam for k in sonuc) else 1


# `hazirla --yeniden` yalnız onaydan önceki şarkılara: onaylı/yüklenmiş şarkı baştan hazırlanırsa aşaması `hazir`a
# düşer, yükleme kaydı ve takip kaybolurdu; bekleyen onarım da sahipsiz kalırdı
YENIDEN_HAZIRLANIR = ("yeni", "hazir", "analiz", "uretildi", "hata")


HAZIRLIK_TEKRAR_SAAT = 4  # hazırlıkta düşen şarkı en erken bu kadar sonra yeniden denenir


def _hazirlanacak_mi(d: durum.Durum | None, yeniden: bool, girdi: Path | None = None) -> bool:
    if d is None:
        return True
    if yeniden:
        return d.asama in YENIDEN_HAZIRLANIR
    # Analizden sonra düşen şarkıyı (kapı, motor) yeniden indirmek çözmez: stil değişikliği ya da `yanki yeniden`.
    if d.asama != "hata" or d.analiz:
        return d.asama == "yeni"
    # Hazırlıkta düşen şarkı (söz/kaynak yok) yeniden denenir, ama gündüz görevi her 30 dk'da bir aynı YouTube/LRCLIB
    # isteklerini atmasın: son denemeden HAZIRLIK_TEKRAR_SAAT sonra. Scryne girdi/'ye söz ya da ses bıraktıysa hemen.
    from datetime import datetime, timedelta

    son = datetime.fromisoformat(d.gecmis[-1]["zaman"]) if d.gecmis else datetime.min
    if girdi is not None:
        elle = [*girdi.glob(f"sozler/{d.kimlik}.txt"), *girdi.glob(f"kaynak/{d.kimlik}.*")]
        if any(datetime.fromtimestamp(f.stat().st_mtime) > son for f in elle):
            return True
    return datetime.now() - son >= timedelta(hours=HAZIRLIK_TEKRAR_SAAT)


def _hazirla(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    calisma, girdi = a.kok / "calisma", a.kok / "girdi"
    sarkilar = liste.yukle(Path(args.liste) if args.liste else girdi / "liste.toml")
    if not sarkilar:
        print("liste boş: girdi/liste.toml'a [[sarki]] ekle")
        return 0
    for s in sarkilar:
        mevcut = durum.oku(calisma, s.kimlik)
        if not _hazirlanacak_mi(mevcut, args.yeniden, girdi):
            if args.yeniden and mevcut:
                print(f"atlandı ({mevcut.asama}): {s.sanatci} — {s.ad}; onaylı şarkıya yeni aday: `yanki yeniden`")
            continue
        d = hazirlik.girdi_hazirla(a, s, calisma, girdi)
        print(f"{d.asama:6} {s.sanatci} — {s.ad}" + (f": {d.hata}" if d.hata else f" [{d.kaynak.get('nereden')}]"))
    if not args.analizsiz:
        # yalnız bu koşuda analiz edilenler yazılır (sürekli koşuda zaten analizde bekleyenler her 30 dk'da yazılmasın)
        hazir = {s.kimlik for s in sarkilar if (d := durum.oku(calisma, s.kimlik)) and d.asama == "hazir"}
        hazirlik.analiz_et(a, sarkilar, calisma)
        for s in sarkilar:
            d = durum.oku(calisma, s.kimlik)
            if d and s.kimlik in hazir and d.asama == "analiz" and d.analiz.get("stil"):
                tempo = " · ".join(x for x in (f"{d.analiz['bpm']} BPM" if d.analiz.get("bpm") else "",
                                               d.analiz.get("ton") or "") if x)
                print(f"analiz {s.ad}: {d.analiz['stil']} | {tempo or 'tempo/ton modele bırakıldı'}")
    return 0


def _uret(_: argparse.Namespace) -> int:
    from yanki import uzak

    a = ayarlar.yukle()
    calistir, tek_parca_sn, uzak_mi = uzak.motor_sec(a)
    if calistir is None:
        print("üretim yok: kiralık GPU kullanılamıyor, evde üretim kapalı (config/motor.toml → [uzak] yerel_yedek)")
        return 0
    print(f"üretim: {'kiralık GPU' if uzak_mi else 'evdeki GPU'}")
    islenen = uretim.uret(a, a.kok / "calisma", calistir=calistir, tek_parca_sn=tek_parca_sn,
                          betimle=uzak_mi and a.motor.betim)
    if not islenen:
        print("üretilecek bir şey yok (analiz ya da onarım bekleyen şarkı yok)")
    for d in islenen:
        gecen = sum(x.gecti for x in d.adaylar)
        ek = f" ({d.hata})" if d.hata else ""
        print(f"{d.asama:9} {d.sanatci} — {d.ad}: {gecen}/{len(d.adaylar)} aday kapıdan geçti{ek}")
    return 0


def _yeniden(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    kod = 0
    for kimlik in args.kimlik:
        try:
            with durum.guncelle(calisma, kimlik) as d:
                uretim.yeniden_uretime_al(d)
        except durum.Yok:
            print(f"'{kimlik}' bulunamadı")
            kod = 1
            continue
        except ValueError as e:
            print(f"{kimlik}: {e}")
            kod = 1
            continue
        # eski paket yeni seçim yapılana kadar yüklenmesin: kenara alınır (yeni onayda paket yeniden üretilir)
        k = durum.klasor(calisma, kimlik)
        if (k / "paket").exists():
            shutil.rmtree(k / "paket_onceki", ignore_errors=True)
            (k / "paket").rename(k / "paket_onceki")
        print(f"yeniden üretime alındı: {d.sanatci} — {d.ad} (sonraki `yanki uret` ya da gece görevi)")
    return kod


def _kunye(args: argparse.Namespace) -> int:
    """Hazır şarkıların künyesini yeniden çeker (ses ve adaylara dokunmaz); paket için ardından `paketle --yeniden`."""
    from dataclasses import asdict

    from yanki import ag, kunye

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    kod = 0
    for d in durum.hepsi(calisma):
        if args.kimlik and d.kimlik not in args.kimlik:
            continue
        try:
            yeni = asdict(kunye.bul(d.sanatci, d.ad))
        except (ag.Bulunamadi, OSError) as e:
            print(f"✗ {d.sanatci} — {d.ad}: {e}")
            kod = 1
            continue
        with durum.guncelle(calisma, d.kimlik) as d:
            d.kunye = yeni
        adlar = ", ".join(f"{x} {y}".strip() if y else f"{x} (SOYAD?)" for x, y in d.kunye["yazar_adlari"])
        print(f"✓ {d.sanatci} — {d.ad}: {d.kunye['ilk_yayin']} | {adlar}")
    return kod


def _yapi(args: argparse.Namespace) -> int:
    """LRCLIB sözlü şarkıların `soz.txt`'sini zaman damgalarından bölüm etiketleriyle yeniden yazar (`yapi.coz`) ve
    yapıyı gösterir. Scryne'ın söz dosyası (kaynak "dosya") olduğu gibi kalır. Seçilmiş adaylara dokunmaz: yeni yapı
    sonraki üretimde (`yanki yeniden`, `yanki bastan`) kullanılır."""
    import json

    from yanki import yapi

    calisma = ayarlar.yukle().kok / "calisma"
    for d in durum.hepsi(calisma):
        if args.kimlik and d.kimlik not in args.kimlik:
            continue
        k = durum.klasor(calisma, d.kimlik)
        zaman = k / "soz_zaman.json"
        if d.soz.get("kaynak") != "lrclib" or not (k / d.soz.get("dosya", "soz.txt")).exists():
            print(f"– {d.sanatci} — {d.ad}: söz Scryne'ın dosyasından ya da yok, dokunulmadı")
            continue
        satirlar = [tuple(x) for x in json.loads(zaman.read_text(encoding="utf-8"))] if zaman.exists() else []
        if satirlar:
            bolumler = yapi.coz(satirlar, d.kaynak.get("sure_sn") or d.soz.get("sure_sn"), d.ad)
        else:  # zaman damgasız LRCLIB sözü: eski [verse]/[chorus] etiketleri atılıp düz sözün tekrarlarından
            eski = (k / d.soz["dosya"]).read_text(encoding="utf-8").splitlines()
            bolumler = yapi.coz([(None, "" if x.strip().lower() in ("[verse]", "[chorus]") else x) for x in eski],
                                ad=d.ad)
        (k / d.soz["dosya"]).write_text(yapi.metin(bolumler), encoding="utf-8")
        print(f"✓ {d.sanatci} — {d.ad}: " + " · ".join(b.ad for b in bolumler))
    return 0


def _elle_yazarlari_uygula(kok: Path) -> list[str]:
    """`liste.toml`'da `yazarlar` yazılmış ama künyesi yazarsız onaylı/paketli şarkılar: künye güncellenir, paketliyse
    paket yeniden çıkar (yazarsız paket dağıtımcıya yüklenemiyor; Scryne yalnız listeye yazarları ekler). Dönen:
    güncellenen şarkıların kimlikleri."""
    calisma = kok / "calisma"
    try:
        elle = {s.kimlik: s.yazarlar for s in liste.yukle(kok / "girdi" / "liste.toml") if s.yazarlar}
    except (OSError, ValueError):
        return []
    from yanki import kunye

    guncellenen = []
    for d in durum.hepsi(calisma):
        yazarlar = elle.get(d.kimlik)
        mevcut = tuple((d.kunye or {}).get("yazarlar") or ())
        if not yazarlar or d.asama not in ("onaylandi", "paketlendi") or mevcut == tuple(map(kunye.duz, yazarlar)):
            continue
        with durum.guncelle(calisma, d.kimlik) as taze:
            taze.kunye = kunye.elle_yazarlar(taze.kunye or {}, yazarlar)
        print(f"yazarlar listeden: {d.sanatci} — {d.ad}: {', '.join(yazarlar)}")
        guncellenen.append(d.kimlik)
    paketli = [k for k in guncellenen if (durum.oku(calisma, k) or durum.Durum(k, "", "")).asama == "paketlendi"]
    if paketli:
        hatalar: list = []
        paket.paketle(calisma, kok / "config" / "yayin.toml", paketli, yeniden=True, hatalar=hatalar)
        for d, hata in hatalar:
            print(f"✗ yeniden paketlenemedi: {d.sanatci} — {d.ad}: {hata}")
    return guncellenen


def _paketle(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    _elle_yazarlari_uygula(a.kok)
    hatalar: list = []
    islenen = paket.paketle(a.kok / "calisma", a.kok / "config" / "yayin.toml", yeniden=args.yeniden,
                            hatalar=hatalar)
    if not islenen and not hatalar:
        print("paketlenecek onaylı şarkı yok")
    for d in islenen:
        print(f"paket hazır: {d.sanatci} — {d.ad} → calisma/{d.kimlik}/paket/YUKLE.md")
    for d, hata in hatalar:
        print(f"✗ paketlenemedi: {d.sanatci} — {d.ad}: {hata} (onaylı kaldı, sonraki koşu yeniden dener)")
    return 1 if hatalar else 0


def _yuklendi(args: argparse.Namespace) -> int:
    """Paketi dağıtımcıya yükledikten sonra: aşama `yuklendi`, formdaki bilgiler (ISRC, UPC, yayın tarihi) paketin
    metadata.json'una. Takip ISRC'yle çalışır; ISRC sonradan belli olursa aynı komutla eklenir."""
    from yanki import takip

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    try:
        bilgi = takip.yukleme_dogrula(args.isrc, args.upc, args.yayin_tarihi, args.onizleme)
    except ValueError as e:
        print(f"✗ {e}")
        return 1
    d = durum.oku(calisma, args.kimlik)
    if d is None or d.asama not in ("paketlendi", "yuklendi", "yayinda"):
        print(f"'{args.kimlik}' paketlenmiş bir şarkı değil" + (f" (aşama: {d.asama})" if d else ""))
        return 1
    if d.asama != "paketlendi" and not bilgi:
        print(f"zaten {d.asama}; yükleme bilgisini güncellemek için --isrc/--upc/--yayin-tarihi ver")
        return 1
    dagitimci = args.dagitimci or paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").dagitimci
    try:
        kayit = takip.yukleme_kaydet(calisma, d.kimlik, bilgi, dagitimci)
    except FileNotFoundError as e:
        print(f"✗ {e}")
        return 1
    if d.asama == "paketlendi":
        with durum.guncelle(calisma, d.kimlik) as d:
            d.gec("yuklendi")
        print(f"yüklendi olarak işaretlendi: {d.sanatci} — {d.ad}")
    else:
        print(f"yükleme bilgisi güncellendi: {d.sanatci} — {d.ad}")
    eksik = [ad for ad in ("isrc", "yayin_tarihi") if not kayit.get(ad)]
    if eksik:
        print(f"  eksik: {', '.join(eksik)} (takip ISRC'siz çalışmaz; belli olunca: yanki yuklendi {d.kimlik} "
              "--isrc … --yayin-tarihi …)")
    return 0


def _kesif_ayarlari(kok: Path) -> dict:
    import tomllib

    with open(kok / "config" / "kesif.toml", "rb") as f:
        return tomllib.load(f)


def _spotify_baglan(_: argparse.Namespace) -> int:
    """Spotify hesabını bir kez bağla (PKCE): tarayıcıda izin → 127.0.0.1'e dönüş → token calisma/.spotify.json."""
    import http.server
    import urllib.parse
    import webbrowser

    from yanki import spotify

    a = ayarlar.yukle()
    sp = spotify.Spotify(a.kok)
    try:
        adres, dogrulayici, beklenen = sp.baglanti_adresi()
    except spotify.AyarYok as e:
        print(f"✗ {e}")
        return 1
    hedef = urllib.parse.urlparse(sp.yonlendirme)
    gelen: dict = {}

    class Donus(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            gelen.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write("Yanki: Spotify bağlandı, bu sekmeyi kapatabilirsin.".encode())

        def log_message(self, *_):
            pass

    sunucu = http.server.HTTPServer((hedef.hostname, hedef.port), Donus)
    print(f"tarayıcıda Spotify izni açılıyor (dönüş adresi {sp.yonlendirme}) …")
    webbrowser.open(adres)
    while "code" not in gelen and "error" not in gelen:
        sunucu.handle_request()
    sunucu.server_close()
    if gelen.get("error") or gelen.get("state") != beklenen:
        print(f"✗ bağlanmadı: {gelen.get('error') or 'durum (state) eşleşmedi'}")
        return 1
    sp.kodu_degistir(gelen["code"], dogrulayici)
    print(f"✓ Spotify bağlandı → {sp.token_yolu}")
    return 0


def _kesif(args: argparse.Namespace) -> int:
    from collections import Counter

    from yanki import ag, katalog, kesif, spotify

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    ayar = _kesif_ayarlari(a.kok)
    k = ayar["kesif"]
    pazarlar = tuple(args.pazar or k["pazarlar"])
    sp = spotify.Spotify(a.kok)
    # `spotifysiz`: yalnız Spotify gerektirmeyen kaynaklar (popüler şarkılar); Web API kilitliyken ya da uygulama
    # meşgulken gece koşusu keşfin bu yarısını yine yapar
    spotifysiz = bool(getattr(args, "spotifysiz", False))
    dogrula = bool(sp.client_id and sp.client_secret) and not spotifysiz
    adaylar: list = []
    csvler = [Path(x) for x in args.csv] or sorted((a.kok / "girdi" / "kesif").glob("*.csv"))
    for yol in csvler:
        bulunan = kesif.stillmore_csv(yol)
        print(f"STILLMORE {yol.name}: {len(bulunan)} çalınamayan şarkı")
        adaylar += bulunan
    sayac: Counter = Counter()
    playlistler = args.playlist or (k["playlistler"] if dogrula and sp.bagli_mi() else [])
    degismeyen = 0
    for p in playlistler:
        try:
            pid = spotify.kimlik_ayikla(p)
            bulunan = kesif.playlist_tara_onbellekli(sp, pid, pazarlar, calisma, sayac)
        except spotify.Sinirli as e:
            print(f"✗ playlist taraması durdu: {e}")
            break
        except (ValueError, spotify.SpotifyHatasi) as e:
            print(f"✗ playlist {p}: {e}")
            continue
        if bulunan is None:
            degismeyen += 1
            continue
        print(f"playlist {pid}: {len(bulunan)} çalınamayan şarkı")
        adaylar += bulunan
    if degismeyen:
        print(f"{degismeyen} playlist değişmemiş (son {kesif.PLAYLIST_TAZELEME_GUN} günde tarandı), atlandı")
    _stillmore_tara(args, a.kok, calisma, ayar.get("stillmore", {}), sp, dogrula, adaylar)
    kat = ayar.get("katalog", {})
    if dogrula and kat.get("acik") and not args.katalogsuz:
        ek = [ad for ad, _ in sayac.most_common(int(kat.get("playlist_sanatcilari", 0)))]
        try:
            adaylar += katalog.tara(sp, calisma, pazarlar, katalog.Ayar.oku(kat), ek)
        except spotify.Sinirli as e:
            print(f"✗ katalog farkı: {e}")
        except (OSError, katalog.DeezerHatasi, spotify.SpotifyHatasi) as e:
            print(f"✗ katalog farkı: {e}")
    pop = ayar.get("populer", {})
    if pop.get("acik") and not getattr(args, "populersiz", False):  # Spotify gerektirmez (Deezer + ücretsiz ölçüm)
        try:
            adaylar += katalog.populer(katalog.PopulerAyar.oku(pop), pazarlar,
                                       set(kesif.oku(calisma)) | {x.kimlik for x in adaylar})
        except (OSError, katalog.DeezerHatasi) as e:
            print(f"✗ popüler şarkılar: {e}")
    if args.yeniden_olc:  # kayıttaki adaylar da (kaynak o gece taranamasa bile) yeniden ölçülür
        adaylar += [x for x in kesif.oku(calisma).values() if not any(y.kimlik == x.kimlik for y in adaylar)]
    # aynı şarkı birden çok kaynaktan gelebilir: doğrulama tek kez; düzenlemeler (sped up, remix…) hiç sorulmaz
    tekil = list({x.kimlik: x for x in adaylar}.values())
    duzenleme = [x for x in tekil if x.duzenleme]
    tekil = [x for x in tekil if not x.duzenleme]
    if duzenleme:
        print(f"{len(duzenleme)} düzenleme atlandı (sped up, slowed, remix…): "
              + ", ".join(f"{x.sanatci} — {x.ad}" for x in duzenleme[:5]) + (" …" if len(duzenleme) > 5 else ""))
    # Son 14 günde ölçülen adım yeniden yapılmaz: ücretsiz ölçüm (`olcum`) ve Spotify doğrulaması (`kontrol`) ayrı
    # zamanlı; Spotify kilitliyken bekleyen aday ertesi gece yalnız Spotify adımına girer. `--yeniden-olc`: hepsi.
    if not args.yeniden_olc:
        onceki = kesif.oku(calisma)
        for x in tekil:
            kesif.tasi(x, onceki.get(x.kimlik))
    else:
        for x in tekil:
            x.olcum = x.kontrol = None
    yayin = paket.yayin_ayarlari(a.kok / "config" / "yayin.toml")
    if tekil and not dogrula and not spotifysiz:
        print("Spotify anahtarı yok (.env): boşluk doğrulanmıyor, yalnız talep ölçülüyor; doğrulanmamış aday listeye"
              " eklenmez")
    # Önce ücretsiz elemeler (YouTube talebi + sanatçı eşleşmesi, LRCLIB sözü), Spotify en son ve yalnız bunları
    # geçenlere: Spotify kotası dar (2026-10-09: ~1.000 istekte 23 saatlik kilit), playlist adaylarının çoğu
    # sızıntı/düzenleme olarak ücretsiz adımlarda eleniyor.
    from datetime import datetime

    from yanki import yargi

    olculecek = [x for x in tekil if not kesif.taze(x.olcum)]
    try:
        yargic = yargi.ac(a.kok) if any(not x.populer for x in olculecek) else None
    except Exception as e:  # noqa: BLE001 — SDK yüklenemedi ya da istemci kurulamadı: regex yedeği
        print(f"TypeSafe istemcisi açılamadı: {e}")
        yargic = None
    if yargic is None and any(not x.populer for x in olculecek):
        print("TypeSafe yok (TYPESAFE_API_KEY): özgünlük kararı regex yedeğiyle (daha zayıf)")
    for x in olculecek:
        try:
            kesif.talep_olc(x)
        except Exception as e:  # noqa: BLE001 — YouTube araması düşerse aday kalır, talep boş
            print(f"  YouTube ölçülemedi ({x.sanatci} — {x.ad}): {e}")
            continue
        # Popüler aday Deezer editörlerinin tür listelerinden: sanatçı gerçek, sızıntı/takma ad sorusu yok (regex).
        # 2026-10-13 gecesi TypeSafe aday başına dakikalarca bekletti; 60 adaylık koşu bitmiyordu.
        if yargic and x.youtube_kanit and not x.populer:
            try:  # Jev birincil karar; düşerse regex sonucu (talep_olc'de) kalır
                x.ozgunluk = yargi.sinirli(lambda x=x, y=yargic: y.ozgunluk(x.sanatci, x.ad, x.youtube_kanit))
                x.sanatci_uyusuyor = x.ozgunluk["karar"]
            except TimeoutError as e:  # servis asılı: bu koşuda bir daha sorulmaz, kalanlar regex yedeğiyle
                print(f"  TypeSafe {e} ({x.sanatci} — {x.ad}); bu koşuda regex yedeği")
                yargic = None
            except Exception as e:  # noqa: BLE001
                print(f"  TypeSafe kararı alınamadı ({x.sanatci} — {x.ad}), regex yedeği: {e}")
        if x.sanatci_uyusuyor is True:
            try:
                kesif.soz_kontrol(x)
            except OSError as e:
                print(f"  LRCLIB'e ulaşılamadı ({x.sanatci} — {x.ad}): {e}")
                continue
        x.olcum = datetime.now().isoformat(timespec="seconds")
    if yargic:
        yargic.kapat()
    if olculecek:
        print(f"ücretsiz ölçüm: {len(olculecek)} aday (YouTube, Jev, LRCLIB)")
    # tür (Deezer, ücretsiz): hattın yapamadığı türdeki aday Spotify'a sorulmaz, kendiliğinden listeye girmez.
    # Ölçümü taze ama türüne hiç bakılmamış eski adaylar da burada tamamlanır.
    turu_yok = [x for x in tekil if x.turler is None and x.sanatci_uyusuyor is True and x.soz_var is True]
    for x in turu_yok:
        try:
            x.turler = katalog.sanatci_turleri(x.sanatci)
        except (OSError, katalog.DeezerHatasi, ag.Bulunamadi) as e:
            print(f"  Deezer türü alınamadı ({x.sanatci}): {e}")
    if uymayan := [x for x in turu_yok if x.uygun is False]:
        print(f"tür uymuyor ({len(uymayan)}): " + ", ".join(f"{x.sanatci} — {x.ad} [{'; '.join(x.turler)}]"
                                                           for x in uymayan[:5]))
    sorulacak = [x for x in tekil if kesif.spotifya_sorulur(x) and not kesif.taze(x.kontrol)]
    if dogrula and sorulacak:
        print(f"Spotify doğrulaması: {len(sorulacak)}/{len(tekil)} aday ücretsiz elemeleri geçti")
    for i, x in enumerate(sorulacak if dogrula else [], 1):
        try:
            kesif.bosluk_dogrula(sp, x, pazarlar, yayin.sanatci_adi)
        except spotify.Sinirli as e:
            print(f"✗ {e}; doğrulanan {i - 1}/{len(sorulacak)}, kalanı sonraki koşuda")
            break
        except spotify.SpotifyHatasi as e:
            print(f"✗ Spotify: {e}")
            break
    kayit = kesif.birlestir(calisma, tekil)
    sirali = kesif.sirala(kayit)
    print(f"\n{'puan':>12}  {'YouTube':>13}  rakip  pazar  durum            şarkı")
    for x in sirali[: args.goster]:
        pazar = f"{len(x.kapali_pazarlar)}/{len(x.bakilan_pazarlar)}" if x.bakilan_pazarlar else "—"
        print(f"{x.puan:12,.0f}  {(f'{x.youtube_izlenme:,}' if x.youtube_izlenme else '—'):>13}  "
              f"{x.rakip_cover if x.rakip_cover is not None else '—':>5}  {pazar:>5}  {kesif.hal(x):16} "
              f"{x.sanatci} — {x.ad}")
    if args.ekle:
        from yanki import egitim

        eklenen = kesif.listeye_ekle(sirali, a.kok / "girdi" / "liste.toml", calisma, args.ekle,
                                     {s.sanatci.casefold() for s in egitim.veri(a.kok)})
        for x in eklenen:
            print(f"listeye eklendi: {x.sanatci} — {x.ad}")
        if not eklenen:
            print("listeye eklenecek doğrulanmış yeni aday yok")
    return 0


def _stillmore_tara(args, kok: Path, calisma: Path, st: dict, sp, dogrula: bool, adaylar: list) -> None:
    """STILLMORE playlist taraması (Spotify istemcisinin içinden). Havuz: config + Web API playlist araması."""
    import subprocess
    from datetime import datetime

    from yanki import spotify, stillmore

    if not st.get("acik") or getattr(args, "stillmoresuz", False):
        return
    havuz = stillmore.havuz_oku(calisma)
    for pid in st.get("playlistler", []):
        stillmore.havuza_ekle(havuz, spotify.kimlik_ayikla(pid), "", "config")
    sorgular = st.get("arama", [])
    if dogrula and sorgular:  # her gece sıradaki birkaç sorgu (döner)
        sira = int(datetime.now().strftime("%j"))
        n = int(st.get("arama_gece", 2))
        for q in [sorgular[(sira * n + i) % len(sorgular)] for i in range(n)]:
            try:
                bulunan = sp.playlist_ara(q)
            except spotify.SpotifyHatasi as e:
                print(f"✗ playlist araması ({q}): {e}")
                break
            yeni = sum(stillmore.havuza_ekle(havuz, x["id"], x.get("name") or "", f"arama:{q}", t)
                       for x in bulunan if (t := ((x.get("items") or x.get("tracks") or {}).get("total") or 0))
                       >= int(st.get("min_parca", 100)))
            print(f"playlist araması '{q}': {len(bulunan)} sonuç, {yeni} yeni havuza")
    secilen = stillmore.sec(havuz, int(st.get("gece_playlist", 3)), int(st.get("tazeleme_gun", 7)))
    stillmore.havuz_yaz(calisma, havuz)
    if not secilen:
        return
    try:
        with stillmore.Oturum(yeniden_baslat=getattr(args, "spotify_yeniden_baslat", False)) as k:
            for pid in secilen:
                try:
                    bilgi = k.playlist_bilgi(pid) or {}
                    satirlar = k.kaldirilanlar(pid)
                except Exception as e:  # noqa: BLE001 — StillmoreYok, CDP bağlantısı koptu, zaman aşımı
                    print(f"✗ STILLMORE {pid}: {e}")
                    continue
                bulunan = stillmore.adaylara(satirlar, pid)
                havuz[pid].update({"ad": bilgi.get("name") or havuz[pid]["ad"], "toplam": bilgi.get("total"),
                                   "son_tarama": datetime.now().isoformat(timespec="seconds"),
                                   "calinamayan": len(satirlar), "aday": len(bulunan)})
                print(f"STILLMORE '{havuz[pid]['ad']}': {len(satirlar)} çalınamayan, {len(bulunan)} aday")
                adaylar += bulunan
    except (stillmore.StillmoreYok, OSError, subprocess.SubprocessError) as e:
        print(f"STILLMORE taraması atlandı: {e}")
    stillmore.havuz_yaz(calisma, havuz)


def _takip(args: argparse.Namespace) -> int:
    from yanki import spotify, takip

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    t = _kesif_ayarlari(a.kok)["takip"]
    y = paket.yayin_ayarlari(a.kok / "config" / "yayin.toml")
    sp = spotify.Spotify(a.kok)

    def calistir(istemci):
        return takip.takip_et(sp, calisma, y.sanatci_adi, tuple(t["pazarlar"]), args.kimlik or None,
                              int(t["arama_derinligi"]), bildir=_bildirici(calisma), istemci=istemci,
                              web_gun=int(t.get("web_gun", takip.WEB_GUN)))

    try:
        if t.get("istemci", True) and _takip_gerekli(calisma, args.kimlik):
            sonuc = _istemciyle(sp, calistir, getattr(args, "spotify_yeniden_baslat", False))
        else:
            sonuc = calistir(None)
    except spotify.Sinirli as e:  # kota kilidi beklenen bir durum: özet bildirimi gösterir, koşu hatası değil
        print(f"takip ertelendi: {e}")
        return 0
    except spotify.SpotifyHatasi as e:
        print(f"✗ {e}")
        return 1
    if not sonuc:
        print("takip edilecek yüklenmiş şarkı yok")
    for d, uyarilar in sonuc:
        son = (d.yayin or {}).get("son") or {}
        if not son:
            hal = "—"
        elif son["canli"]:
            siralar = ", ".join(f"{m} {s or '—'}" for m, s in (son.get("siralar") or {}).items())
            hal = f"canlı; '{d.ad}' aramasında sıra: {siralar} (ilk {son['arama_limiti']})"
        else:
            hal = f"henüz Spotify'da değil (yayın tarihi {son.get('yayin_tarihi') or '?'})"
        print(f"{'✓' if son.get('canli') else '·'} {d.sanatci} — {d.ad}: {hal}")
        for u in uyarilar:
            print(f"    ✗ {u}")
    profiller = takip.profil_kimlikleri(calisma)
    if len(profiller) > 1:
        print(f"✗ {y.sanatci_adi} profili bölünmüş: {len(profiller)} ayrı sanatçı kimliği "
              f"({', '.join(sorted(profiller))})")
    return 0


def _takip_gerekli(calisma: Path, kimlikler: list[str] | None) -> bool:
    """ISRC'si belli yüklenmiş şarkı var mı (yoksa Spotify uygulaması boşuna açılmasın)."""
    from yanki import takip

    return any(d.asama in ("yuklendi", "yayinda") and (not kimlikler or d.kimlik in kimlikler)
               and (takip.yukleme_bilgisi(calisma, d.kimlik) or {}).get("isrc") for d in durum.hepsi(calisma))


def _istemciyle(sp, fn, yeniden_baslat: bool):
    """`fn(istemci)`: Spotify uygulamasının kendi aramasıyla (kotasız). Uygulama açılamazsa (çalıyor, yama yok, kapalı
    ve elle komut) Web API'yle (`fn(None)`); açıldıktan sonraki tek tek aksaklıkta o çağrı Web API'ye düşer."""
    import subprocess

    from yanki import stillmore

    try:
        oturum = stillmore.Oturum(yeniden_baslat=yeniden_baslat)
        kopru = oturum.__enter__()
    except (stillmore.StillmoreYok, OSError, subprocess.SubprocessError) as e:
        print(f"takip Spotify uygulaması olmadan (Web API): {e}")
        return fn(None)
    try:
        istemci = stillmore.IstemciArama(kopru, sp)
        sonuc = fn(istemci)
        print(f"takip: Spotify uygulamasıyla {istemci.istek_sayisi} arama ({istemci.ulke}), Web API {sp.istek_sayisi}")
        return sonuc
    finally:
        oturum.__exit__(None, None, None)


def ozet(kok: Path) -> dict:
    """Hattın tek bakışta durumu: oturum açılış bildirimi ve günlük için. Ağa çıkmaz."""
    import time

    from yanki import kesif, spotify

    calisma = kok / "calisma"
    sarkilar = durum.hepsi(calisma)
    say = lambda *a: sum(d.asama in a for d in sarkilar)  # noqa: E731
    try:
        listede = kesif.listedekiler(kok / "girdi" / "liste.toml", calisma)
        oneri = sum(x.puan > 0 and not x.elendi and x.kimlik not in listede for x in kesif.oku(calisma).values())
    except (OSError, ValueError):
        oneri = 0
    k = spotify.Spotify(kok).kota()
    from yanki import dagitim, onay

    try:
        sira = dagitim.plan(calisma, dagitim.takvim_oku(kok / "config" / "yayin.toml"),
                            dagitimci=paket.yayin_ayarlari(kok / "config" / "yayin.toml").dagitimci).bugun_yuklenecek
    except (OSError, ValueError, KeyError):
        sira = None

    try:
        yakin = len(onay.yaklasan(calisma, onay.ayar_oku(kok / "config" / "yayin.toml")))
    except (OSError, ValueError):
        yakin = 0
    from yanki import tunearo

    erisim = tunearo.erisim_durumu(calisma)
    return {"tunearo_erisim_yok": bool(erisim), "otomatik_onay_24sa": yakin, "dinlemede": say("uretildi"),
            "onarim": say("onarim"),
            "uretimde": say("yeni", "hazir", "analiz"), "paket_bekliyor": say("paketlendi"),
            "yuklendi": say("yuklendi"), "yayinda": say("yayinda"),
            "hata": say("hata"), "kesif_onerisi": oneri, "yuklenecek": f"{sira.sanatci} — {sira.ad}" if sira else None,
            "spotify_kilit_sn": max(0, int(k.get("kilit", 0) - time.time()))}


def _ozet(args: argparse.Namespace) -> int:
    import json

    o = ozet(ayarlar.yukle().kok)
    if args.json:
        print(json.dumps(o))
        return 0
    satir = [f"{o['dinlemede']} şarkı dinlemede" if o["dinlemede"] else "dinlemede şarkı yok"]
    satir += [f"{n} {ad}" for n, ad in ((o["onarim"], "onarım bekliyor"), (o["uretimde"], "üretim sırasında"),
                                         (o["paket_bekliyor"], "paket yüklenmeyi bekliyor"),
                                         (o["yayinda"], "yayında"), (o["yuklendi"], "yayın bekliyor"),
                                         (o["kesif_onerisi"], "keşif önerisi"), (o["hata"], "hatada"),
                                         (o["otomatik_onay_24sa"], "şarkı 24 saat içinde kendiliğinden onaylanacak"))
              if n]
    if o.get("tunearo_erisim_yok"):
        satir.append("Tunearo API erişimi kapalı: yükleme ve yoklama bekliyor")
    elif o.get("yuklenecek"):
        satir.append(f"yükleme sırası geldi: {o['yuklenecek']}")
    if o["spotify_kilit_sn"]:
        satir.append(f"Spotify kilitli (~{max(1, round(o['spotify_kilit_sn'] / 3600))} sa)")
    print(" · ".join(satir))
    return 0


# Adımların en sık ne zaman koşacağı (saat). Listede olmayan adım her koşuda (sürekli koşu her 30 dk): hazırlık,
# üretim, veto penceresi, paketleme, yükleme sırası, yedek (kendi haftalık eşiği var). Keşif ve takip Spotify kotası
# ve Spotify uygulamasını yeniden başlatma yüzünden günde bir; dağıtım yoklaması dağıtımcıyı yormamak için.
ADIM_ARALIGI_SAAT = {"keşif": 24, "popüler keşif": 12, "takip": 24, "dağıtım durumu": 3, "temizlik": 24}
# Bu çıktılar "yapılacak iş yoktu" demek: sürekli koşuda yalnız bunları üreten adım günlüğe yazılmaz
BOS_CIKTI = ("üretilecek bir şey yok", "paketlenecek onaylı şarkı yok", "takvim: ", "yedek güncel",
             "liste boş", "tunearo: izlenen yükleme yok", "takip edilecek yüklenmiş şarkı yok", "toplam 0 MB")


class _AdimCiktisi:
    """Bir adımın çıktısı günlüğe canlı akar. Yalnız "yapılacak iş yok" satırlarından (`BOS_CIKTI`) ibaretse hiç
    yazılmaz; ilk gerçek satırda başlık (adımın başlama saatiyle) ve o ana kadarki satırlar yazılır, sonrası anında.

    Önce adımın bütün çıktısı bitince yazılıyordu: kiralık GPU'daki bir saatlik üretim günlükte ancak bittiğinde,
    bitiş saatini başlama saati gibi göstererek görünüyor, koşu yarıda kesilirse (uyku, kapanma) hiç görünmüyordu
    (2026-10-10 günlüğü: "── üretim (18:51:46)" altında 17:38'de başlamış üretim)."""

    def __init__(self, baslik: str, hedef):
        self.baslik, self.hedef = baslik, hedef
        self.tampon: list[str] = []
        self.yarim = ""
        self.akiyor = False

    def write(self, s: str) -> int:
        self.yarim += s
        *satirlar, self.yarim = self.yarim.split("\n")
        for satir in satirlar:
            self._satir(satir)
        return len(s)

    def flush(self) -> None:
        if self.akiyor:
            self.hedef.flush()

    def _yaz(self, satir: str) -> None:
        print(satir, file=self.hedef, flush=True)

    def _satir(self, satir: str) -> None:
        if self.akiyor:
            self._yaz(satir)
            return
        if satir.strip() or self.tampon:  # baştaki boş satırlar atılır
            self.tampon.append(satir)
        if satir.strip() and not any(x in satir for x in BOS_CIKTI):
            self.ac()

    def ac(self) -> None:
        if self.akiyor:
            return
        self.akiyor = True
        self._yaz(self.baslik)
        for satir in self.tampon:
            self._yaz(satir)
        self.tampon = []

    def bitir(self, zorla: bool = False) -> bool:
        """Yarım kalan son satırı işler; `zorla`: boş da olsa yazılır (hata, `--hepsi`). Dönen: adım yazıldı mı."""
        if self.yarim:
            self._satir(self.yarim)
            self.yarim = ""
        if zorla:
            self.ac()
        return self.akiyor


def _adim_zamanlari(calisma: Path) -> dict:
    import json

    try:
        return json.loads((calisma / ".adimlar.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _spotify_serbest(op) -> bool:
    """Spotify uygulaması (STILLMORE, takip araması) şimdi kullanılabilir mi: kapalıysa ya da zaten CDP'yle açıksa evet;
    kullanıcının açık uygulaması ancak bilgisayar `gunduz_bosta_dk` dakikadır kullanılmıyorsa yeniden başlatılır
    (çalıyorsa köprü zaten dokunmaz)."""
    import subprocess

    from yanki import sistem, stillmore

    try:
        if stillmore.cdp_acik() or not stillmore.calisiyor_mu():
            return True
        return sistem.bosta_sn() >= op.gunduz_bosta_dk * 60
    except (OSError, subprocess.SubprocessError):
        return False


def _calistir(args: argparse.Namespace) -> int:
    """Sürekli koşu (`\\Yanki\\Surekli` her 30 dk, `\\Yanki\\Gece` 03:00'te uyandırarak; Scryne 2026-10-10: "gece 3'ü
    beklemeye gerek yok, bilgisayar açıkken hep çalışsın"): kaldırılmış şarkı keşfi → liste, hazırlık, üretim (bekleyen
    onarımlar önce), veto penceresi, paketleme, dağıtım durumu, takip, yükleme sırası, temizlik, yedek. Her adım
    zamanı gelince (`ADIM_ARALIGI_SAAT`); `--hepsi` hepsini şimdi koşturur.

    Üretim kullanıcı etkinken de yapılır (ayar: `config/operasyon.toml` → `[surekli]`), prizde ve GPU boşken, koşu
    başına en çok `uretim_sarki` şarkı: saatler süren tek koşu yüklemeyi ve yoklamayı kilitlemesin. Spotify uygulamasına
    gereken adımlar (keşif, takip) uygulama serbestken (`_spotify_serbest`), değilse sonraki koşuya kalır.

    Adımlar birbirinden yalıtılmış: biri düşerse hatası günlüğe yazılır, koşu sürer ve 1 döner. Yapılacak işi olmayan
    adım yazmaz; hiçbir adım iş yapmadıysa koşu hiçbir şey yazmaz (günlük her 30 dk'da bir şişmesin)."""
    import contextlib
    import time
    import traceback
    from datetime import datetime, timedelta

    from yanki import dosya, spotify

    kok = ayarlar.yukle().kok
    calisma = kok / "calisma"
    op = ayarlar.operasyon_oku(kok)
    simdi = datetime.now()
    hepsi = bool(getattr(args, "hepsi", False))
    zamanlar = _adim_zamanlari(calisma)
    spotify_var = bool(spotify.Spotify(kok).client_id)
    gece_ekle = int(_kesif_ayarlari(kok)["kesif"].get("gece_ekle", 0))

    def zamani(ad: str) -> bool:
        if hepsi or ad not in ADIM_ARALIGI_SAAT or ad not in zamanlar:
            return True
        return datetime.fromisoformat(zamanlar[ad]) <= simdi - timedelta(hours=ADIM_ARALIGI_SAAT[ad])

    args.yeniden = False
    adimlar: list = []
    serbest = None  # Spotify uygulaması: yalnız gerekince sorulur (tasklist/pencere sorgusu)
    # Web API kilitliyken keşif doğrulayamaz: günlük hakkı yanmasın, kilit kalkınca ilk koşuda (2026-10-10: kilit
    # 16:00'da kalkacakken 13:39'da koştu, bir sonraki ancak ertesi gün olurdu)
    kilitli = spotify_var and spotify.Spotify(kok).kota().get("kilit", 0) > time.time()
    if gece_ekle and spotify_var and not kilitli and zamani("keşif") and (serbest := _spotify_serbest(op)):
        adimlar.append(("keşif", lambda: _kesif(argparse.Namespace(
            csv=[], playlist=[], pazar=None, ekle=gece_ekle, goster=10, katalogsuz=False, yeniden_olc=False,
            stillmoresuz=False, spotify_yeniden_baslat=True))))
    elif gece_ekle and zamani("popüler keşif"):  # Spotify'sız yarı: Deezer listelerinden popüler şarkılar
        adimlar.append(("popüler keşif", lambda: _kesif(argparse.Namespace(
            csv=[], playlist=[], pazar=None, ekle=gece_ekle, goster=10, katalogsuz=True, yeniden_olc=False,
            stillmoresuz=True, spotify_yeniden_baslat=False, spotifysiz=True))))
    adimlar += [("hazırlık", lambda: _hazirla(args)), ("üretim", lambda: _uret_surekli(kok, op)),
                ("veto penceresi", lambda: _otomatik_onay(kok)), ("paketleme", lambda: _paketle(args))]
    if zamani("dağıtım durumu"):  # takipten önce: kabul gelince Tunearo'nun atadığı ISRC takibe girsin
        adimlar.append(("dağıtım durumu", lambda: _dagitim_durum(argparse.Namespace())))
    if spotify_var and zamani("takip") and (serbest if serbest is not None else _spotify_serbest(op)):
        adimlar.append(("takip", lambda: _takip(argparse.Namespace(kimlik=[], spotify_yeniden_baslat=True))))
    adimlar += [("takvim", lambda: _takvim_hatirlat(kok))]
    if zamani("temizlik"):
        adimlar.append(("temizlik", lambda: _temizle(argparse.Namespace(uygula=True, gun=op.temizlik_gun))))
    adimlar.append(("yedek", lambda: _yedekle(argparse.Namespace(zorla=False))))

    sorunlu, yazilan = [], []
    for ad, fn in adimlar:
        bas = time.monotonic()
        cikti = _AdimCiktisi(f"── {ad} ({datetime.now():%H:%M:%S})", sys.stdout)
        with contextlib.redirect_stdout(cikti):
            try:
                kod = fn() or 0
            except Exception:  # noqa: BLE001 — adım yalıtımı: iz günlüğe, koşu sürer
                traceback.print_exc(file=sys.stdout)
                kod = 1
        if ad in ADIM_ARALIGI_SAAT:
            zamanlar[ad] = simdi.isoformat(timespec="seconds")
        if ad == "keşif":  # tam keşif popüler şarkıları da içerir
            zamanlar["popüler keşif"] = simdi.isoformat(timespec="seconds")
        if kod:
            sorunlu.append(ad)
        if cikti.bitir(zorla=bool(kod) or hepsi):
            yazilan.append(ad)
            gecen = time.monotonic() - bas
            if kod:
                print(f"✗ {ad} adımı sorunlu bitti ({gecen:.0f} sn)", flush=True)
            elif gecen >= 60:  # uzun adımın süresi (başlık başlama saatini taşıyor)
                print(f"  {ad} bitti ({gecen / 60:.0f} dk)", flush=True)
    dosya.json_yaz(calisma / ".adimlar.json", zamanlar)
    if yazilan:
        print(f"── koşu bitti ({datetime.now():%H:%M:%S})"
              + (f"; sorunlu adım: {', '.join(sorunlu)}" if sorunlu else ""))
        _servis_ozeti(kok)
    return 1 if sorunlu else 0


def _uret_surekli(kok: Path, op) -> int:
    """Sürekli koşunun üretimi: prizde ve GPU boşken, bekleyen onarımlar önce, en çok `surekli_uretim_sarki` şarkı;
    GPU doluysa (oyun, başka iş) beklemez, sonraki koşu dener. Biten şarkı "dinlemeye hazır" diye bildirilir."""
    import functools

    from yanki import motor, saglik, sistem, uzak

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    hedef = sorted(uretim.uretilecek(a, calisma),
                   key=lambda d: (d.asama != "onarim", d.gecmis[-1]["zaman"] if d.gecmis else ""))
    if not hedef:
        print("üretilecek bir şey yok (analiz ya da onarım bekleyen şarkı yok)")
        return 0
    if not op.surekli_uretim:
        print(f"üretim duraklatıldı (config/operasyon.toml → [surekli] uretim = false); {len(hedef)} şarkı sırada")
        return 0
    calistir, tek_parca_sn, uzak_mi = uzak.motor_sec(a)
    if calistir is None:
        print(f"üretim bekliyor: kiralık GPU kullanılamıyor, evde üretim kapalı ({len(hedef)} şarkı sırada)")
        return 0
    if uzak_mi:  # kiralık GPU: evdeki kart, priz ve kullanıcı etkinliği önemsiz
        return _uret_ve_bildir(a, hedef[: a.uzak.sarki], len(hedef), calistir, tek_parca_sn, "kiralık GPU")
    if not sistem.prizde_mi():
        print(f"üretim bekliyor: pilde ({len(hedef)} şarkı sırada)")
        return 0
    if op.surekli_bosta_bekle and sistem.bosta_sn() < op.gunduz_bosta_dk * 60:
        print(f"üretim bekliyor: bilgisayar kullanılıyor ({len(hedef)} şarkı sırada)")
        return 0
    if (kullanilan := saglik.gpu_kullanilan_mib()) is None or kullanilan >= a.gpu.bos_esik_mib:
        print(f"üretim bekliyor: GPU dolu ({kullanilan} MiB; {len(hedef)} şarkı sırada)")
        return 0
    # GPU başlamadan dolarsa (oyun açıldı) saatlerce beklemesin: 10 dk sonra vazgeçer, şarkılar sırada kalır
    return _uret_ve_bildir(a, hedef[: op.surekli_uretim_sarki], len(hedef),
                           functools.partial(motor.calistir, gpu_bekleme_sn=600), tek_parca_sn, "evdeki GPU")


def _uret_ve_bildir(a, secilen: list, sirada: int, calistir, tek_parca_sn: float, nerede: str) -> int:
    from yanki import motor

    calisma = a.kok / "calisma"
    print(f"üretim ({nerede}): " + ", ".join(f"{d.sanatci} — {d.ad}" for d in secilen) + f" ({sirada} sırada)",
          flush=True)
    bildir = _bildirici(calisma)
    try:
        uretilen = uretim.uret(a, calisma, [d.kimlik for d in secilen], calistir=calistir, tek_parca_sn=tek_parca_sn,
                               betimle=nerede == "kiralık GPU" and a.motor.betim)
    except motor.GpuMesgul as e:
        print(f"üretim bekliyor: {e}")
        return 0
    for d in uretilen:
        gecen = sum(x.gecti for x in d.adaylar)
        ek = f" ({d.hata})" if d.hata else ""
        print(f"{d.asama:9} {d.sanatci} — {d.ad}: {gecen}/{len(d.adaylar)} aday kapıdan geçti{ek}")
        if d.asama == "uretildi":
            bildir("dinleme", f"dinlemeye hazır: {d.ad}", f"{d.sanatci} — {d.ad}: {gecen} aday kapıdan geçti",
                   f"dinleme:{d.kimlik}:{d.gecmis[-1]['zaman']}")
    return 0


def _servis_ozeti(kok: Path) -> None:
    from yanki import sayac

    print(f"── dış servisler: {sayac.ozet()}")
    try:
        sayac.yaz(kok / "calisma")
    except OSError as e:
        print(f"servis sayaçları yazılamadı: {e}")


def _bildirici(calisma: Path):
    from yanki import olay

    return lambda tur, baslik, metin, anahtar=None: olay.bildir(calisma, tur, baslik, metin, anahtar)


def _erisim_yok(calisma: Path, e) -> None:
    """Tunearo hesap düzeyinde erişimi kapattı (`tunearo.ErisimYok`): kayda geçer (özet ve oda gösterir), günde bir
    bildirilir. Yüklemeler ve yoklama erişim açılınca kendiliğinden sürer; yerel kayıtlara dokunulmaz."""
    from datetime import date

    from yanki import tunearo

    tunearo.erisim_kaydet(calisma, e)
    print(f"Tunearo API erişimi kapalı ({e}); yükleme ve durum yoklaması erişim açılana kadar bekliyor")
    _bildirici(calisma)("kayip", "Tunearo API erişimi kapalı",
                        f"Tunearo her isteğe \"{e}\" diyor: yükleme ve durum yoklaması durdu. Hesap sahibinden "
                        "(arkadaşın) API erişimini yeniden açmasını iste; açılınca hat kendiliğinden sürer.",
                        f"tunearo:erisim:{date.today()}")


def _takvim_hatirlat(kok: Path) -> int:
    """Sırası gelen paketler: dağıtımcının API'si varsa (Tunearo) hepsi yüklenir, yoksa ilki bildirilir (bir kez).
    `[takvim] haftada = 0` iken sıradaki her paket bu koşuda gider. Tunearo'nun hesap parça kotası dolarsa ("Track
    limit reached") durur ve bildirir; tek bir paketin hatası diğerlerini durdurmaz."""
    from datetime import date

    from yanki import dagitim, paket, tunearo

    calisma = kok / "calisma"
    ad = paket.yayin_ayarlari(kok / "config" / "yayin.toml").dagitimci
    p = dagitim.plan(calisma, dagitim.takvim_oku(kok / "config" / "yayin.toml"), dagitimci=ad)
    bildir = _bildirici(calisma)
    for kimlik in p.yazarsiz:  # kaynakta yazar yok (MusicBrainz'de kaydı olmayan şarkı): Scryne'a bir kez
        s = durum.oku(calisma, kimlik)
        print(f"takvim: {s.sanatci} — {s.ad} yazarsız, bekliyor (girdi/liste.toml → yazarlar)")
        bildir("onay", f"yazarlar gerekli: {s.ad}",
               f"{s.sanatci} — {s.ad} için orijinal söz yazarı/besteci bulunamadı; dağıtımcı yazarsız cover "
               "almıyor. girdi/liste.toml'da şarkıya yazarlar = [\"Ad Soyad\"] ekle (sonraki koşu paketleyip "
               "yükler) ya da dinleme odasında reddet.", f"yazar_yok:{kimlik}")
    if p.beklemede:
        print(f"takvim: {p.beklemede}; kuyrukta {len(p.sira)} paket")
        return 0
    sirasi_gelen = p.bugun_yuklenecekler
    if not sirasi_gelen:
        ilk = p.sira[0] if p.sira else None
        print(f"takvim: sıradaki yükleme {ilk.yukleme:%d.%m} ({ilk.ad})" if ilk else "takvim: kuyruk boş")
        return 0
    d = dagitim.sec(ad, kok)
    if not d.otomatik:
        s = sirasi_gelen[0]
        bildir("takvim", f"yükleme sırası: {s.ad}",
               f"{s.sanatci} — {s.ad}: calisma/{s.kimlik}/paket/YUKLE.md hazır; önerilen yayın tarihi "
               f"{s.yayin_tarihi:%Y-%m-%d}. Yükleyince: yanki yuklendi {s.kimlik} --isrc …",
               f"takvim:{s.kimlik}:{s.yukleme}")
        return 0
    yuklenen, hatali = [], 0
    for s in sirasi_gelen:
        try:
            bilgi = dagitim.otomatik_yukle(calisma, d, s.kimlik, s.yayin_tarihi)
        except tunearo.ErisimYok as e:
            _erisim_yok(calisma, e)
            print(f"takvim: {len(sirasi_gelen) - len(yuklenen)} paket kuyrukta bekliyor")
            break
        except tunearo.TunearoHatasi as e:
            if e.kod == 403 and "limit" in str(e).lower():
                print(f"takvim: Tunearo parça kotası doldu ({e}); kalan {len(sirasi_gelen) - len(yuklenen)} paket "
                      "kuyrukta bekliyor")
                bildir("dagitim", "Tunearo parça kotası doldu",
                       f"{len(yuklenen)} şarkı yüklendi, {len(sirasi_gelen) - len(yuklenen)} paket bekliyor: hesabın "
                       "parça hakkı bitti (Tunearo panelinden artırılınca kendiliğinden sürer).",
                       f"kota:{date.today()}")
                break
            print(f"✗ {s.sanatci} — {s.ad}: {e}")
            hatali += 1
            continue
        except ValueError as e:
            if "orijinal yazarlar yok" not in str(e):
                print(f"✗ {s.sanatci} — {s.ad}: {e}")
                hatali += 1
                continue
            # kaynakta yazar yok (MusicBrainz'de kaydı olmayan şarkı): her 30 dk hata değil, Scryne'a bir kez
            print(f"takvim: {s.sanatci} — {s.ad} yazarsız, bekliyor (girdi/liste.toml → yazarlar)")
            bildir("onay", f"yazarlar gerekli: {s.ad}",
                   f"{s.sanatci} — {s.ad} için orijinal söz yazarı/besteci bulunamadı; dağıtımcı yazarsız cover "
                   "almıyor. girdi/liste.toml'da şarkıya yazarlar = [\"Ad Soyad\"] ekle (sonraki koşu paketleyip "
                   "yükler) ya da dinleme odasında reddet.", f"yazar_yok:{s.kimlik}")
            continue
        except (LookupError, RuntimeError, OSError) as e:  # bozuk paket, ağ: sıradaki pakete geç
            print(f"✗ {s.sanatci} — {s.ad}: {type(e).__name__}: {e}")
            hatali += 1
            continue
        yuklenen.append((s, bilgi))
        print(f"takvim: {s.sanatci} — {s.ad} {d.ad}'ya yüklendi, incelemede (yayın {s.yayin_tarihi:%Y-%m-%d}, "
              f"yayın kimliği {bilgi.get('release_id')})", flush=True)
    adi = paket.DAGITIMCI_ADI.get(d.ad, d.ad)
    if len(yuklenen) == 1:
        s, bilgi = yuklenen[0]
        bildir("dagitim", f"yüklendi: {s.ad}", f"{s.sanatci} — {s.ad} {adi} incelemesine gönderildi; yayın tarihi "
               f"{s.yayin_tarihi:%Y-%m-%d}", f"yukleme:{s.kimlik}:{bilgi.get('release_id')}")
    elif yuklenen:  # toplu yüklemede tek bildirim (her şarkıya ayrı bildirim yağmuru olmasın)
        bildir("dagitim", f"{len(yuklenen)} şarkı yüklendi",
               f"{adi} incelemesine gönderildi: " + ", ".join(s.ad for s, _ in yuklenen),
               "yukleme:" + ",".join(str(b.get("release_id")) for _, b in yuklenen))
    return 1 if hatali else 0


def _takvim(args: argparse.Namespace) -> int:
    from yanki import dagitim

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    p = dagitim.plan(calisma, dagitim.takvim_oku(a.kok / "config" / "yayin.toml"),
                     dagitimci=paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").dagitimci)
    print(f"son yükleme: {p.son_yukleme or '—'}" + (f" · {p.beklemede}" if p.beklemede else ""))
    if not p.sira:
        print("kuyruk boş: paketlenmiş şarkı yok")
    for i, x in enumerate(p.sira, 1):
        puan = f"keşif {x.puan:,.0f}" if x.puan else "liste"
        print(f"{i:2}. {x.yukleme:%Y-%m-%d} yükle → {x.yayin_tarihi:%Y-%m-%d} yayın  {x.sanatci} — {x.ad}  ({puan})")
    for kimlik in p.duzeltme:
        print(f"  ✗ {kimlik}: dağıtımcı reddetti; düzeltip `yanki paketle --yeniden` deyince kuyruğa döner")
    return 0


def _yukle(args: argparse.Namespace) -> int:
    """Paketi API'li dağıtımcıya şimdi yükler (takvimi beklemeden). --taslak: her şey yüklenir, gönderilmez."""
    from datetime import date, timedelta

    from yanki import dagitim

    a = ayarlar.yukle()
    yayin_yolu = a.kok / "config" / "yayin.toml"
    d = dagitim.sec(paket.yayin_ayarlari(yayin_yolu).dagitimci, a.kok)
    if not d.otomatik:
        print(f"✗ {d.ad or 'dağıtımcı'} için API yok: YUKLE.md ile elle yükle, sonra `yanki yuklendi`")
        return 1
    try:
        tarih = (date.fromisoformat(args.yayin_tarihi) if args.yayin_tarihi
                 else date.today() + timedelta(days=dagitim.takvim_oku(yayin_yolu).yayin_on_gun))
        bilgi = dagitim.otomatik_yukle(a.kok / "calisma", d, args.kimlik, tarih, gonder=not args.taslak)
    except (ValueError, LookupError, RuntimeError) as e:  # bozuk paket, şarkı yok, Tunearo hatası
        print(f"✗ {args.kimlik}: {e}")
        return 1
    if args.taslak:
        print(f"taslak hazır ({d.ad}): kapak, parça ve ses yüklendi, gönderilmedi. "
              f"Göndermek: yanki yukle {args.kimlik}")
    else:
        print(f"gönderildi ({d.ad}): yayın {bilgi.get('release_id')}, durum {bilgi.get('dagitim_durumu')}, "
              f"yayın tarihi {bilgi.get('yayin_tarihi')}")
    return 0


def _kapak(args: argparse.Namespace) -> int:
    """Pinterest kapağı getir (`--yeni`: beğenilmeyeni değiştir); şarkı paketliyse paket yeni kapakla yenilenir.
    Yüklenmiş şarkıya dokunmaz (dağıtımcıda kapak değişmez)."""
    import json

    from yanki import pinterest

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    kimlikler = args.kimlik or [d.kimlik for d in durum.hepsi(calisma) if d.asama == "paketlendi"]
    kod = 0
    for kimlik in kimlikler:
        d = durum.oku(calisma, kimlik)
        if d is None or d.asama not in ("onaylandi", "paketlendi"):
            print(f"✗ {kimlik}: onaylı ya da paketli değil" + (f" (aşama: {d.asama})" if d else ""))
            kod = 1
            continue
        if (durum.klasor(calisma, kimlik) / "kapak_ozel.jpg").exists():
            print(f"  {d.ad}: elle seçilmiş kapak_ozel.jpg var, o kullanılıyor (Pinterest'e bakılmadı)")
            continue
        try:
            pinterest.getir(calisma, d, yeni=args.yeni)
        except (OSError, LookupError, ValueError) as e:  # ağ, uygun görsel yok, bozuk görsel
            print(f"✗ {d.ad}: {e}")
            kod = 1
            continue
        k = json.loads((durum.klasor(calisma, kimlik) / "kapak_kaynak.json").read_text(encoding="utf-8"))
        print(f"  {d.ad}: {k['boyut'][0]}×{k['boyut'][1]} — {k['aciklama']} ({k['pin']})")
        if d.asama == "paketlendi":
            hatalar: list = []
            paket.paketle(calisma, a.kok / "config" / "yayin.toml", [kimlik], yeniden=True, hatalar=hatalar)
            for _, hata in hatalar:
                print(f"✗ {d.ad}: yeniden paketlenemedi: {hata}")
                kod = 1
    return kod


def _dagitim_durum(args: argparse.Namespace) -> int:
    """API'li dağıtımcıya yüklenenlerin durumunu yoklar (gece koşusu da yapar)."""
    from yanki import dagitim

    a = ayarlar.yukle()
    d = dagitim.sec(paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").dagitimci, a.kok)
    if not d.otomatik:
        print(f"{d.ad or 'dağıtımcı'}: API yok, durum dağıtımcı panelinde")
        return 0
    from yanki import tunearo

    try:
        sonuc = d.yokla(a.kok / "calisma", _bildirici(a.kok / "calisma"))
    except tunearo.ErisimYok as e:  # hesap düzeyi: koşu hatası değil, Scryne'ın dağıtımcıyla çözeceği durum
        _erisim_yok(a.kok / "calisma", e)
        return 0
    if d.ad == "tunearo":
        tunearo.erisim_kaydet(a.kok / "calisma", None)
        sanatci_adi = paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").sanatci_adi
        bildir = _bildirici(a.kok / "calisma")
        if profil := tunearo.profil_bagla(a.kok / "calisma", d.api, sanatci_adi, bildir):
            print(f"Spotify profili bağlandı: {profil}")
        try:  # Apple bağlama en iyi çaba: iTunes'a ulaşılamazsa sonraki gece
            if apple := tunearo.apple_bagla(a.kok / "calisma", d.api, sanatci_adi, bildir=bildir):
                print(f"Apple Music profili bağlandı: {apple}")
        except (OSError, tunearo.TunearoHatasi) as e:
            print(f"  Apple Music profili bağlanamadı: {e}")
    if not sonuc:
        print(f"{d.ad}: izlenen yükleme yok")
    for s, yeni, eski in sonuc:
        print(f"  {s.sanatci} — {s.ad}: {yeni}" + (f" (önce {eski})" if eski and eski != yeni else ""))
    return 1 if any(yeni in ("hata", "bulunamadi") for _, yeni, _ in sonuc) else 0


def _dagitim_red(args: argparse.Namespace) -> int:
    from yanki import dagitim

    a = ayarlar.yukle()
    try:
        d = dagitim.red_kaydet(a.kok / "calisma", args.kimlik, args.neden)
    except (ValueError, durum.Yok) as e:
        print(f"✗ {args.kimlik}: {e}")
        return 1
    print(f"dağıtımcı reddi kaydedildi: {d.sanatci} — {d.ad} → paketlendi (takvim yeniden paketlenene kadar atlar)")
    return 0


def _geri_cek(args: argparse.Namespace) -> int:
    """Yüklenmiş şarkıları dağıtımcıdan geri çeker; şarkı yükleme kuyruğuna döner (red sayılmaz)."""
    from yanki import dagitim

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    kimlikler = args.kimlik or [d.kimlik for d in durum.hepsi(calisma) if d.asama in ("yuklendi", "yayinda")]
    kod = 0
    for kimlik in kimlikler:
        try:
            sonuc = dagitim.geri_cek(calisma, kimlik, args.neden, a.kok, kaldirildi=args.kaldirildi)
        except (ValueError, LookupError, RuntimeError) as e:  # yüklenmemiş, panelden kaldırılmamış, Tunearo hatası
            print(f"✗ {kimlik}: {e}")
            kod = 1
            continue
        print(f"  {kimlik}: " + ("geri çekildi; gece koşusu güncel ayarlarla paketleyip kuyruğa alır"
                                 if sonuc == "tamam" else
                                 "incelemede, API geri çekemiyor: işaretlendi, sonuç gelince gece yoklaması bitirir"))
    return kod


def _bastan(args: argparse.Namespace) -> int:
    """Bütün şarkıları baştan üretime alır (Scryne, 2026-10-10: "makinede daha iyi tam sürümüyle üreticez, 0'dan
    başlayalım"): yüklenmişler dağıtımcıdan geri çekilir (Tunearo incelemede: işaret, sonuç gelince; elle dağıtımcı:
    `--kaldirildi` ile hemen), diğerlerinin adayları ve paketi arşive (`uretim.bastan`). Reddedilen ve hazırlıkta
    düşen şarkılara dokunulmaz. `--uygula` olmadan yalnız plan."""
    from yanki import dagitim, takip

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    neden = args.neden
    kod = 0
    for d in durum.hepsi(calisma):
        if args.kimlik and d.kimlik not in args.kimlik:
            continue
        if d.asama in ("yuklendi", "yayinda"):
            ad = (takip.yukleme_bilgisi(calisma, d.kimlik) or {}).get("dagitimci") or "routenote"
            elle = ad != "tunearo"
            ne = (f"{ad}: geri çekilir (panelden kaldırıldı sayılır), baştan üretime" if elle else
                  f"{ad}: geri çekilmek üzere işaretlenir, inceleme bitince baştan üretime")
            if args.uygula:
                try:
                    sonuc = dagitim.geri_cek(calisma, d.kimlik, neden, a.kok, kaldirildi=elle and args.kaldirildi,
                                             bastan=True)
                    ne += f" → {sonuc}"
                except (ValueError, LookupError, RuntimeError) as e:
                    ne, kod = f"✗ {e}", 1
        elif d.asama in uretim.BASTAN_ASAMALAR and d.analiz.get("stil"):
            ne = f"{d.asama}, {len(d.adaylar)} aday → arşiv, baştan üretime"
            if args.uygula:
                uretim.bastan(calisma, d.kimlik, neden)
        else:
            continue
        print(f"  {d.sanatci} — {d.ad}: {ne}")
    if not args.uygula:
        print("plan; uygulamak için: yanki bastan --uygula" + ("" if args.kaldirildi else " --kaldirildi"))
    return kod


def _oac(args: argparse.Namespace) -> int:
    """YouTube resmi sanatçı kanalı (OAC) talebi Tunearo'ya (en az 2 canlı yayından sonra)."""
    from yanki import tunearo

    a = ayarlar.yukle()
    try:
        cevap = tunearo.oac_iste(tunearo.Istemci.kokten(a.kok),
                                 paket.yayin_ayarlari(a.kok / "config" / "yayin.toml").sanatci_adi, args.ana, args.konu)
    except (ValueError, RuntimeError) as e:  # adres, sanatçı yok, Tunearo 422 (2 canlı yayın yok) / 409
        print(f"✗ {e}")
        return 1
    talep = cevap.get("oac_request") or cevap
    print(f"OAC talebi: {talep.get('status')} (oluşturuldu {str(talep.get('created_at'))[:10]}); Tunearo ekibi "
          "onaylayınca YouTube'daki konu kanalı resmi kanalda birleşir")
    return 0


YOKLAMA_ARALIK_SAAT = 3  # gündüz Tunearo durum yoklaması en sık bu kadar saatte bir


def _seyrek_yokla(kok: Path, simdi=None) -> None:
    """API'li dağıtımcıdaki yayınların durumunu gündüz de yoklar (yayın başına bir istek, en sık
    YOKLAMA_ARALIK_SAAT'te bir): red ya da kabul gece koşusunu beklemeden görülür ve bildirilir; geri çekilmek üzere
    işaretli yayın incelemeden çıkınca hemen kuyruğa döner. Yalnız değişiklik yazılır (gündüz günlüğü kısa kalsın)."""
    from datetime import datetime, timedelta

    from yanki import dagitim, takip

    calisma = kok / "calisma"
    simdi = simdi or datetime.now()
    isaret = calisma / ".dagitim_yoklama"
    try:
        son = datetime.fromtimestamp(isaret.stat().st_mtime)
    except OSError:
        son = datetime.min
    if simdi - son < timedelta(hours=YOKLAMA_ARALIK_SAAT):
        return
    yuklu = {(takip.yukleme_bilgisi(calisma, d.kimlik) or {}).get("dagitimci") for d in durum.hepsi(calisma)
             if d.asama in ("yuklendi", "yayinda")}
    if not yuklu:
        return
    try:
        ad = paket.yayin_ayarlari(kok / "config" / "yayin.toml").dagitimci
        d = dagitim.sec(ad, kok)
    except (OSError, ValueError, KeyError) as e:
        print(f"dağıtım yoklaması yapılamadı: {e}")
        return
    if ad not in yuklu or not d.otomatik:
        return
    isaret.parent.mkdir(parents=True, exist_ok=True)
    isaret.touch()
    from yanki import tunearo

    try:
        sonuc = d.yokla(calisma, _bildirici(calisma))
    except tunearo.ErisimYok as e:
        _erisim_yok(calisma, e)
        return
    except Exception as e:  # noqa: BLE001 — anahtar yok, ağ: gündüz üretimini etkilemez
        print(f"dağıtım yoklaması yapılamadı: {type(e).__name__}: {e}")
        return
    for x, yeni, eski in sonuc:
        if yeni != eski:
            print(f"dağıtım: {x.sanatci} — {x.ad}: {eski} → {yeni}")


def _gunduz(args: argparse.Namespace) -> int:
    """Gündüz boşta üretim (`\\Yanki\\Gunduz` görevi, her 30 dk): koşullar uygunsa kuyruktan bir şarkı üretir.
    Koşul tutmazsa tek satır nedenle çıkar (görev günde ~34 kez çalışır, günlük kısa kalsın). Üretim koşullarından
    bağımsız olarak dağıtım durumu seyrek yoklanır (`_seyrek_yokla`)."""
    from datetime import datetime

    from yanki import saglik, sistem

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    op = ayarlar.operasyon_oku(a.kok)
    simdi = datetime.now()
    _seyrek_yokla(a.kok, simdi)
    if not op.gunduz_acik:
        return print("gündüz üretimi kapalı (config/operasyon.toml)") or 0
    if not op.surekli_uretim:
        return print("üretim duraklatıldı (config/operasyon.toml → [surekli] uretim = false)") or 0
    if a.uzak.acik and not a.uzak.yerel_yedek:  # evde üretim kapalı; sürekli koşu sunucuda üretir
        return print("evde üretim kapalı (config/motor.toml → [uzak] yerel_yedek); üretim kiralık GPU'da") or 0
    if not op.gunduz_saatinde(simdi.hour) and not args.zorla:
        return print(f"saat dışında ({op.gunduz_saatler[0]:02d}:00–{op.gunduz_saatler[1]:02d}:00)") or 0
    if not args.zorla and (bosta := sistem.bosta_sn()) < op.gunduz_bosta_dk * 60:
        return print(f"kullanıcı etkin ({bosta / 60:.0f} dk boşta, eşik {op.gunduz_bosta_dk})") or 0
    if not sistem.prizde_mi():
        return print("pilde: üretim yok") or 0
    if (kullanilan := saglik.gpu_kullanilan_mib()) is None or kullanilan >= a.gpu.bos_esik_mib:
        return print(f"GPU boş değil ({kullanilan} MiB)") or 0
    args.yeniden, args.analizsiz = False, False
    _hazirla(args)
    hedef = sorted(uretim.uretilecek(a, calisma),
                   key=lambda d: (d.asama != "onarim", d.gecmis[-1]["zaman"] if d.gecmis else ""))[: op.gunduz_sarki]
    if not hedef:
        return print("üretilecek şarkı yok") or 0
    print(f"gündüz üretimi ({simdi:%H:%M}): " + ", ".join(f"{d.sanatci} — {d.ad}" for d in hedef), flush=True)
    bildir = _bildirici(calisma)
    for d in uretim.uret(a, calisma, [d.kimlik for d in hedef]):
        gecen = sum(x.gecti for x in d.adaylar)
        print(f"{d.asama:9} {d.sanatci} — {d.ad}: {gecen}/{len(d.adaylar)} aday kapıdan geçti")
        if d.asama == "uretildi":
            bildir("dinleme", f"dinlemeye hazır: {d.ad}", f"{d.sanatci} — {d.ad}: {gecen} aday kapıdan geçti",
                   f"dinleme:{d.kimlik}:{d.gecmis[-1]['zaman']}")
    _paketle(args)
    _servis_ozeti(a.kok)
    return 0


def _otomatik_onay(kok: Path) -> int:
    from yanki import onay

    ayar = onay.ayar_oku(kok / "config" / "yayin.toml")
    bildir = _bildirici(kok / "calisma")
    for d, neden in onay.kulak_bekleyen(kok / "calisma", ayar):
        print(f"otomatik onay yok, kulak gerekiyor: {d.sanatci} — {d.ad} ({neden})")
        bildir("onay", f"dinlemen gerekiyor: {d.ad}", f"{d.sanatci} — {d.ad} kendiliğinden onaylanmaz ({neden}); "
               "dinleme odasında karar verene kadar yayına girmez.", f"kulak:{d.kimlik}")
    for d, a in onay.uygula(kok / "calisma", ayar):
        print(f"otomatik onay ({ayar.sure_saat:g} sa veto penceresi doldu): {d.sanatci} — {d.ad}, aday {a.no}")
        # kulaktan geçmeden onaylandı: haberin olsun (yüklenmeden önce dinleme odasında geri alınabilir)
        bildir("onay", f"kendiliğinden onaylandı: {d.ad}",
               f"{d.sanatci} — {d.ad}: {ayar.sure_saat:g} saatte karar gelmedi, sözü en net aday {a.no} onaylandı. "
               "Yüklenmeden önce dinleyip değiştirebilirsin.", f"otomatik_onay:{d.kimlik}:{a.no}")
    return 0


def _yedekle(args: argparse.Namespace) -> int:
    """Yeniden üretilemeyen durumun zip yedeği (config/operasyon.toml → [yedek]). Gece koşusu haftada bir alır."""
    from yanki import yedek

    a = ayarlar.yukle()
    op = ayarlar.operasyon_oku(a.kok)
    if not args.zorla and not yedek.gerekli_mi(op):
        son = yedek.son_yedek_zamani(op.yedek_klasor)
        print(f"yedek güncel (son: {son:%Y-%m-%d %H:%M}, her {op.yedek_gun} günde bir)")
        return 0
    yol, n = yedek.yedekle(a.kok, op)
    print(f"yedek alındı: {yol} ({n} dosya, {yol.stat().st_size / 1e6:.1f} MB; en yeni {op.yedek_sakla} tanesi "
          "saklanır)")
    return 0


def _temizle(args: argparse.Namespace) -> int:
    from yanki import temizlik

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    toplam = 0
    for d in durum.hepsi(calisma):
        p = temizlik.plan(calisma, d, args.gun)
        if p is None:
            continue
        mb = p.bayt / 1e6
        if args.uygula:
            temizlik.uygula(calisma, d, p)
        toplam += mb
        eylem = "silindi" if args.uygula else "silinecek"
        print(f"{eylem}: {d.sanatci} — {d.ad}: {len(p.dosyalar)} dosya, {mb:,.0f} MB")
    if toplam or not args.uygula:
        print(f"toplam {toplam:,.0f} MB" + ("" if args.uygula else " (silmek için --uygula)"))
    return 0


EGITIM_EN_AZ_ORNEK = 10  # daha azıyla tür LoRA'sı ezberler (Side-Step: 10–50 şarkı)


def _egit(args: argparse.Namespace) -> int:
    """Ses modeli eğitimi (`yanki/egitim.py`): veri yerelde hazırlanır, LoRA kiralık GPU'da eğitilir, karşılaştırmalı
    deneme sesleri `calisma/dinleme/lora/`'ya iner. Saatler sürer; genel koşu kilidini tutmaz (durum dosyalarına
    yazmaz), üretim ve yükleme sürer."""
    import subprocess

    from yanki import egitim, runpod

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    ayar, sarkilar = egitim.oku(a.kok / "config" / "egitim.toml")
    if args.deneme_yeniden:
        return _deneme_yeniden(a, ayar, args.deneme_yeniden, args.ara or list(ayar.deneme_ara_kayitlar))
    print(f"veri: {len(sarkilar)} şarkı → {egitim.veri_klasoru(a.kok).relative_to(a.kok).as_posix()}", flush=True)
    ornekler, dusen = egitim.veri_hazirla(a.kok, ayar, sarkilar, bildir=lambda m: print(m, flush=True))
    print(f"veri hazır: {len(ornekler)} örnek, {sum(x['duration'] for x in ornekler) / 60:.0f} dk ses; "
          f"{len(dusen)} düştü", flush=True)
    if len(ornekler) < EGITIM_EN_AZ_ORNEK:
        print(f"✗ en az {EGITIM_EN_AZ_ORNEK} örnek gerekli")
        return 1
    if args.yalniz_veri:
        return 0
    tar = egitim.paketle(a.kok, ornekler)
    print(f"kiralık GPU'da eğitim ({ayar.gpu}, {ayar.model}, {ayar.epoch} epoch, rank {ayar.rank}); veri "
          f"{tar.stat().st_size / 1e9:.2f} GB", flush=True)
    bildir = _bildirici(calisma)
    try:
        sonuc = egitim.egit(a, ayar, tar, bildir=lambda m: print(m, flush=True))
    except (runpod.RunPodHatasi, OSError, ValueError, subprocess.SubprocessError) as e:
        print(f"✗ eğitim: {type(e).__name__}: {e}")
        bildir("kayip", "LoRA eğitimi düştü", f"{type(e).__name__}: {str(e)[:300]}")
        return 1
    finally:
        tar.unlink(missing_ok=True)
    egitim.degerlendir(a, calisma, sonuc.deneme)
    egitim.kaydet(sonuc, ayar, ornek=len(ornekler))
    from yanki import dosya

    dosya.yaz(sonuc.dinleme / "OKU.md", egitim.rapor(sonuc, len(ornekler), len(dusen)))
    print(f"LoRA: {sonuc.lora}\ndinleme: {sonuc.dinleme}\nmaliyet: {sonuc.usd:.2f} $")
    bildir("dinleme", "LoRA eğitimi bitti, karşılaştırma hazır",
           f"{len(ornekler)} şarkıyla eğitildi ({sonuc.usd:.2f} $). LoRA'sız ve LoRA'lı aynı şarkılar: "
           f"{sonuc.dinleme.relative_to(a.kok).as_posix()}/OKU.md")
    return 0


def _deneme_yeniden(a, ayar, klasor: str, epochlar: list[int]) -> int:
    """Biten eğitimin ara kayıtlarıyla denemeyi yeniden üret (eğitimsiz; kayıtlar ve OKU.md güncellenir)."""
    import json
    import subprocess

    from yanki import dosya, egitim, runpod

    yerel = a.kok / egitim.KLASOR / "lora" / klasor
    if not (yerel / "egitim.json").is_file():
        print(f"✗ eğitim kaydı yok: {yerel}")
        return 1
    try:
        sonuc = egitim.deneme_yeniden(a, ayar, yerel, epochlar, bildir=lambda m: print(m, flush=True))
    except (runpod.RunPodHatasi, OSError, ValueError, subprocess.SubprocessError) as e:
        print(f"✗ deneme: {type(e).__name__}: {e}")
        return 1
    egitim.degerlendir(a, a.kok / "calisma", sonuc.deneme)
    birlesik = egitim.deneme_birlestir(yerel, sonuc.deneme, sonuc.usd)
    ornek = json.loads((yerel / "egitim.json").read_text(encoding="utf-8")).get("ornek", 0)
    dosya.yaz(birlesik.dinleme / "OKU.md", egitim.rapor(birlesik, ornek, 0))
    print(f"deneme: {sum(x['basari'] for x in sonuc.deneme)}/{len(sonuc.deneme)} · maliyet {sonuc.usd:.2f} $")
    return 0


def _dinle(args: argparse.Namespace) -> int:
    import asyncio
    import threading
    import webbrowser

    import uvicorn

    from yanki import sunucu

    a = ayarlar.yukle()
    adres = f"http://127.0.0.1:{args.port}/"
    if not args.tarayicisiz:
        threading.Timer(1.0, lambda: webbrowser.open(adres)).start()
    print(f"dinleme odası: {adres}  (durdurmak için Ctrl+C)")
    sunucu_ = uvicorn.Server(uvicorn.Config(sunucu.uygulama(a, a.kok / "calisma"), host="127.0.0.1", port=args.port,
                                            log_level="warning"))
    asyncio.run(_sessiz_sun(sunucu_))
    return 0


async def _sessiz_sun(sunucu_) -> None:
    """Tarayıcı ses akışını yarıda kesince (iz değiştirme, sekme kapama) Windows'un Proactor döngüsü bağlantıyı
    kapatırken `ConnectionResetError` izini günlüğe döküyor: zararsız, ama oda.log'u dolduruyordu (2026-10-11).
    Yalnız o hata susturulur, diğer her şey varsayılan işleyiciye gider."""
    import asyncio

    dongu = asyncio.get_running_loop()

    def isleyici(loop, baglam):
        if isinstance(baglam.get("exception"), ConnectionResetError):
            return
        loop.default_exception_handler(baglam)

    dongu.set_exception_handler(isleyici)
    await sunucu_.serve()


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="yanki", description=__doc__)
    alt = ap.add_subparsers(dest="komut", required=True)
    alt.add_parser("durum", help="motor, model, araçlar, GPU ve şarkıların durumu").set_defaults(fn=_durum)
    h = alt.add_parser("hazirla", help="listedeki şarkılar için kaynak ses, söz, künye ve analiz")
    h.add_argument("--liste", help="varsayılan girdi/liste.toml")
    h.add_argument("--yeniden", action="store_true", help="hazır şarkıları da baştan hazırla")
    h.add_argument("--analizsiz", action="store_true", help="GPU analizini atla")
    h.set_defaults(fn=_hazirla)
    alt.add_parser("uret", help="cover adaylarını ve bekleyen onarımları üret (GPU)").set_defaults(fn=_uret)
    c = alt.add_parser("calistir", help="gece koşusu: keşif, hazırlık, üretim, paket, takip, temizlik, yedek")
    c.add_argument("--liste", help="varsayılan girdi/liste.toml")
    c.add_argument("--hepsi", action="store_true", help="zamanı gelmemiş adımlar dahil hepsini şimdi koştur")
    c.set_defaults(fn=_calistir, yeniden=False, analizsiz=False)
    yn = alt.add_parser("yeniden", help="onaylı/paketli şarkıya güncel hatla yeni adaylar (eskiler kalır)")
    yn.add_argument("kimlik", nargs="+")
    yn.set_defaults(fn=_yeniden)
    kn = alt.add_parser("kunye", help="hazır şarkıların künyesini (yazarlar, orijinal yıl) yeniden çek")
    kn.add_argument("kimlik", nargs="*", help="boşsa hepsi")
    kn.set_defaults(fn=_kunye)
    ya = alt.add_parser("yapi", help="sözleri zaman damgalarından bölüm etiketleriyle yeniden yaz (giriş, nakarat…)")
    ya.add_argument("kimlik", nargs="*")
    ya.set_defaults(fn=_yapi)
    p = alt.add_parser("paketle", help="onaylı şarkılardan yükleme paketi (mastering, kapak, YUKLE.md)")
    p.add_argument("--yeniden", action="store_true", help="paketlenmişleri de yeniden paketle")
    p.set_defaults(fn=_paketle)
    y = alt.add_parser("yuklendi", help="dağıtımcıya yüklenen şarkıyı işaretle, yükleme bilgisini kaydet")
    y.add_argument("kimlik")
    y.add_argument("--isrc", help="dağıtımcının atadığı ISRC (takip bununla çalışır)")
    y.add_argument("--upc", help="sürümün UPC'si")
    y.add_argument("--yayin-tarihi", help="yayın tarihi, YYYY-AA-GG")
    y.add_argument("--onizleme", help="önizleme başlangıcı, d:ss")
    y.add_argument("--dagitimci", help="varsayılan config/yayin.toml")
    y.set_defaults(fn=_yuklendi)
    sb = alt.add_parser("spotify-baglan", help="Spotify hesabını bir kez bağla (kendi playlist'lerini taramak için)")
    sb.set_defaults(fn=_spotify_baglan)
    ks = alt.add_parser("kesif", help="Spotify'dan kaldırılmış, hâlâ aranan şarkıları bul, doğrula, sırala")
    ks.add_argument("--csv", nargs="*", default=[], help="STILLMORE CSV'si (varsayılan girdi/kesif/*.csv)")
    ks.add_argument("--playlist", nargs="*", default=[], help="kendi playlist'in (varsayılan config/kesif.toml)")
    ks.add_argument("--pazar", nargs="*", help="pazarlar, ilki ana (varsayılan config/kesif.toml)")
    ks.add_argument("--katalogsuz", action="store_true", help="Deezer katalog farkını atla")
    ks.add_argument("--stillmoresuz", action="store_true", help="STILLMORE playlist taramasını atla")
    ks.add_argument("--populersiz", action="store_true", help="popüler şarkıları (Deezer tür listeleri) atla")
    ks.add_argument("--spotify-yeniden-baslat", action="store_true",
                    help="Spotify CDP'siz açıksa (çalmıyorsa) STILLMORE için yeniden başlat (gece koşusu bunu yapar)")
    ks.add_argument("--yeniden-olc", action="store_true", help="kayıtta ölçülmüş adayları da yeniden ölç")
    ks.add_argument("--ekle", type=int, default=0, help="en iyi N doğrulanmış adayı girdi/liste.toml'a ekle")
    ks.add_argument("--goster", type=int, default=25)
    ks.set_defaults(fn=_kesif)
    tk = alt.add_parser("takip", help="yüklenenler Spotify'da mı, adı arandığında kaçıncı sırada")
    tk.add_argument("kimlik", nargs="*", help="boşsa hepsi")
    tk.set_defaults(fn=_takip)
    tm = alt.add_parser("temizle", help="yüklenmiş şarkılarda seçilmeyen adayların ve ara seslerin dosyaları")
    tm.add_argument("--uygula", action="store_true", help="yalnız listelemek yerine sil")
    tm.add_argument("--gun", type=int, default=14, help="yüklemenin üstünden en az kaç gün geçmiş olsun")
    tm.set_defaults(fn=_temizle)
    tv = alt.add_parser("takvim", help="paketlenmiş şarkıların yükleme sırası ve önerilen yayın tarihleri")
    tv.set_defaults(fn=_takvim)
    yk = alt.add_parser("yukle", help="paketi API'li dağıtımcıya (Tunearo) şimdi yükle ve incelemeye gönder")
    yk.add_argument("kimlik")
    yk.add_argument("--taslak", action="store_true", help="her şeyi yükle ama gönderme (yayın taslakta kalır)")
    yk.add_argument("--yayin-tarihi", help="YYYY-AA-GG (varsayılan bugün + takvim.yayin_on_gun)")
    yk.set_defaults(fn=_yukle)
    kp = alt.add_parser("kapak", help="şarkının moduna göre Pinterest kapağı (paketliyse paketi yeniler)")
    kp.add_argument("kimlik", nargs="*", help="boşsa paketlenmiş hepsi")
    kp.add_argument("--yeni", action="store_true", help="mevcut kapağı bırak, başka görsel seç")
    kp.set_defaults(fn=_kapak)
    alt.add_parser("dagitim-durum", help="API'li dağıtımcıya yüklenenlerin inceleme/yayın durumu").set_defaults(
        fn=_dagitim_durum)
    dr = alt.add_parser("dagitim-red", help="dağıtımcının reddettiği şarkıyı kaydet (paketlendi'ye döner)")
    dr.add_argument("kimlik")
    dr.add_argument("--neden", required=True, help="dağıtımcının red gerekçesi (ör. kapak, AI içerik)")
    dr.set_defaults(fn=_dagitim_red)
    gc = alt.add_parser("geri-cek", help="yüklenmiş şarkıyı dağıtımcıdan geri çek (yeniden paketlenip kuyruğa döner)")
    gc.add_argument("kimlik", nargs="*", help="boşsa yüklenmiş hepsi")
    gc.add_argument("--neden", default="baştan yayın (Scryne, 2026-10-10)")
    gc.add_argument("--kaldirildi", action="store_true",
                    help="elle dağıtımcıda (RouteNote) yayın panelden kaldırıldı, kaydet")
    gc.set_defaults(fn=_geri_cek)
    bs = alt.add_parser("bastan", help="şarkıları baştan üretime al (adaylar, paket arşive; yüklenmişler geri çekilir)")
    bs.add_argument("kimlik", nargs="*", help="boşsa hepsi")
    bs.add_argument("--uygula", action="store_true", help="yalnız planı göstermek yerine uygula")
    bs.add_argument("--kaldirildi", action="store_true",
                    help="elle dağıtımcıdaki (RouteNote) yayınlar panelden kaldırıldı/kaldırma istendi")
    bs.add_argument("--neden", default="baştan üretim: kiralık GPU, tam sürüm (Scryne, 2026-10-10)")
    bs.set_defaults(fn=_bastan)
    oc = alt.add_parser("oac", help="YouTube resmi sanatçı kanalı (OAC) talebi Tunearo'ya")
    oc.add_argument("--ana", required=True, help="sanatçının YouTube kanalı adresi")
    oc.add_argument("--konu", required=True, help="YouTube'un açtığı '<Sanatçı> - Topic' kanalının adresi")
    oc.set_defaults(fn=_oac)
    gz = alt.add_parser("gunduz", help="boştayken kuyruktan bir şarkı üret (\\Yanki\\Gunduz görevi çalıştırır)")
    gz.add_argument("--zorla", action="store_true", help="saat ve boşta kalma koşulunu atla (pil ve GPU yine bakılır)")
    gz.add_argument("--liste", help="varsayılan girdi/liste.toml")
    gz.set_defaults(fn=_gunduz)
    yd = alt.add_parser("yedekle", help="seçimlerin, yükleme bilgisinin ve keşif kaydının zip yedeği")
    yd.add_argument("--zorla", action="store_true", help="son yedek yeni olsa da al")
    yd.set_defaults(fn=_yedekle)
    oz = alt.add_parser("ozet", help="hattın tek satırlık durumu (oturum açılış bildirimi)")
    oz.add_argument("--json", action="store_true")
    oz.set_defaults(fn=_ozet)
    eg = alt.add_parser("egit", help="ses modeline tür LoRA'sı eğit (kiralık GPU) ve karşılaştırmalı dinleme üret")
    eg.add_argument("--yalniz-veri", action="store_true", help="yalnız eğitim verisini hazırla (ücretsiz, yerel)")
    eg.add_argument("--deneme-yeniden", metavar="ZAMAN",
                    help="eğitimsiz: bu eğitimin (calisma/egitim/lora/<ZAMAN>) ara kayıtlarıyla denemeyi yeniden üret")
    eg.add_argument("--ara", type=int, nargs="+", help="--deneme-yeniden için epoch'lar (varsayılan config)")
    eg.set_defaults(fn=_egit)
    dn = alt.add_parser("dinle", help="dinleme sayfasını aç")
    dn.add_argument("--port", type=int, default=8765)
    dn.add_argument("--tarayicisiz", action="store_true")
    dn.set_defaults(fn=_dinle)
    args = ap.parse_args(argv)
    if args.komut in YAZAN_KOMUTLAR:
        from yanki import kilit

        # gece görevi ile elle başlatılan komut aynı durum dosyalarına yazmasın
        with kilit.tek_kosu(ayarlar.yukle().kok / "calisma" / ".yanki.kilit") as alindi:
            if not alindi:
                print("başka bir yanki koşusu sürüyor (gece görevi ya da elle başlatılan); bitince tekrar dene")
                return 0 if args.komut in ("calistir", "gunduz") else 3
            return args.fn(args)
    return args.fn(args)


YAZAN_KOMUTLAR = {"hazirla", "uret", "calistir", "yeniden", "kunye", "paketle", "yuklendi", "kesif", "takip",
                  "temizle", "yedekle", "dagitim-red", "geri-cek", "bastan", "gunduz", "yukle", "dagitim-durum",
                  "kapak", "yapi"}


if __name__ == "__main__":
    raise SystemExit(main())
