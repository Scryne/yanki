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


def _hazirlanacak_mi(d: durum.Durum | None, yeniden: bool) -> bool:
    if d is None:
        return True
    if yeniden:
        return d.asama in YENIDEN_HAZIRLANIR
    # hazırlıkta düşen şarkı (söz/kaynak yok) her koşuda yeniden denenir: Scryne dosyayı girdi/'ye bırakmış olabilir.
    # Analizden sonra düşen şarkıyı (kapı, motor) yeniden indirmek çözmez: stil değişikliği ya da `yanki yeniden`.
    return d.asama == "yeni" or (d.asama == "hata" and not d.analiz)


def _hazirla(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    calisma, girdi = a.kok / "calisma", a.kok / "girdi"
    sarkilar = liste.yukle(Path(args.liste) if args.liste else girdi / "liste.toml")
    if not sarkilar:
        print("liste boş: girdi/liste.toml'a [[sarki]] ekle")
        return 0
    for s in sarkilar:
        mevcut = durum.oku(calisma, s.kimlik)
        if not _hazirlanacak_mi(mevcut, args.yeniden):
            if args.yeniden and mevcut:
                print(f"atlandı ({mevcut.asama}): {s.sanatci} — {s.ad}; onaylı şarkıya yeni aday: `yanki yeniden`")
            continue
        d = hazirlik.girdi_hazirla(a, s, calisma, girdi)
        print(f"{d.asama:6} {s.sanatci} — {s.ad}" + (f": {d.hata}" if d.hata else f" [{d.kaynak.get('nereden')}]"))
    if not args.analizsiz:
        hazirlik.analiz_et(a, sarkilar, calisma)
        for s in sarkilar:
            d = durum.oku(calisma, s.kimlik)
            if d and d.asama == "analiz" and d.analiz.get("stil"):
                tempo = " · ".join(x for x in (f"{d.analiz['bpm']} BPM" if d.analiz.get("bpm") else "",
                                               d.analiz.get("ton") or "") if x)
                print(f"analiz {s.ad}: {d.analiz['stil']} | {tempo or 'tempo/ton modele bırakıldı'}")
    return 0


def _uret(_: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    islenen = uretim.uret(a, a.kok / "calisma")
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


def _paketle(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
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

    from yanki import katalog, kesif, spotify

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    ayar = _kesif_ayarlari(a.kok)
    k = ayar["kesif"]
    pazarlar = tuple(args.pazar or k["pazarlar"])
    sp = spotify.Spotify(a.kok)
    dogrula = bool(sp.client_id and sp.client_secret)
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
        except (OSError, katalog.DeezerHatasi) as e:
            print(f"✗ katalog farkı: {e}")
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
    if tekil and not dogrula:
        print("Spotify anahtarı yok (.env): boşluk doğrulanmıyor, yalnız talep ölçülüyor; doğrulanmamış aday listeye"
              " eklenmez")
    # Önce ücretsiz elemeler (YouTube talebi + sanatçı eşleşmesi, LRCLIB sözü), Spotify en son ve yalnız bunları
    # geçenlere: Spotify kotası dar (2026-10-09: ~1.000 istekte 23 saatlik kilit), playlist adaylarının çoğu
    # sızıntı/düzenleme olarak ücretsiz adımlarda eleniyor.
    from datetime import datetime

    from yanki import yargi

    olculecek = [x for x in tekil if not kesif.taze(x.olcum)]
    try:
        yargic = yargi.ac(a.kok) if olculecek else None
    except Exception as e:  # noqa: BLE001 — SDK yüklenemedi ya da istemci kurulamadı: regex yedeği
        print(f"TypeSafe istemcisi açılamadı: {e}")
        yargic = None
    if olculecek and yargic is None:
        print("TypeSafe yok (TYPESAFE_API_KEY): özgünlük kararı regex yedeğiyle (daha zayıf)")
    for x in olculecek:
        try:
            kesif.talep_olc(x)
        except Exception as e:  # noqa: BLE001 — YouTube araması düşerse aday kalır, talep boş
            print(f"  YouTube ölçülemedi ({x.sanatci} — {x.ad}): {e}")
            continue
        if yargic and x.youtube_kanit:
            try:  # Jev birincil karar; düşerse regex sonucu (talep_olc'de) kalır
                x.ozgunluk = yargic.ozgunluk(x.sanatci, x.ad, x.youtube_kanit)
                x.sanatci_uyusuyor = x.ozgunluk["karar"]
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
        eklenen = kesif.listeye_ekle(sirali, a.kok / "girdi" / "liste.toml", calisma, args.ekle)
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
    try:
        sonuc = takip.takip_et(sp, calisma, y.sanatci_adi, tuple(t["pazarlar"]), args.kimlik or None,
                               int(t["arama_derinligi"]), bildir=_bildirici(calisma))
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
    return {"otomatik_onay_24sa": yakin, "dinlemede": say("uretildi"), "onarim": say("onarim"),
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
    if o.get("yuklenecek"):
        satir.append(f"yükleme sırası geldi: {o['yuklenecek']}")
    if o["spotify_kilit_sn"]:
        satir.append(f"Spotify kilitli (~{max(1, round(o['spotify_kilit_sn'] / 3600))} sa)")
    print(" · ".join(satir))
    return 0


def _calistir(args: argparse.Namespace) -> int:
    """Arka plan koşusu: (açıksa) kaldırılmış şarkı keşfi → listeye ekle, yeni şarkıları hazırla, üret (bekleyen
    onarımlar dahil), veto penceresi, onaylıları paketle, yüklenenleri takip et, disk temizliği, haftalık yedek.
    Liste boş olsa da onarım ve paketleme yapılır; Spotify anahtarı yoksa keşif ve takip atlanır.

    Adımlar birbirinden yalıtılmış: biri düşerse (YouTube, Deezer, GPU, ağ) hatası günlüğe yazılır, koşu sonraki
    adımla sürer ve sonunda 1 döner (gece.ps1 hatayı bildirim olarak gösterir). Önce keşifteki tek bir ağ hatası
    üretimi, paketlemeyi ve takibi de durduruyordu."""
    import time
    import traceback
    from datetime import datetime

    from yanki import spotify

    kok = ayarlar.yukle().kok
    op = ayarlar.operasyon_oku(kok)
    spotify_var = bool(spotify.Spotify(kok).client_id)
    gece_ekle = int(_kesif_ayarlari(kok)["kesif"].get("gece_ekle", 0))
    args.yeniden = False
    adimlar: list = []
    if gece_ekle and spotify_var:
        adimlar.append(("keşif", lambda: _kesif(argparse.Namespace(
            csv=[], playlist=[], pazar=None, ekle=gece_ekle, goster=10, katalogsuz=False, yeniden_olc=False,
            stillmoresuz=False, spotify_yeniden_baslat=True))))
    adimlar += [("hazırlık", lambda: _hazirla(args)), ("üretim", lambda: _uret(args)),
                ("veto penceresi", lambda: _otomatik_onay(kok)), ("paketleme", lambda: _paketle(args)),
                # takipten önce: kabul gelince Tunearo'nun atadığı ISRC takibe girsin
                ("dağıtım durumu", lambda: _dagitim_durum(argparse.Namespace()))]
    if spotify_var:
        adimlar.append(("takip", lambda: _takip(argparse.Namespace(kimlik=[]))))
    else:
        print("takip atlandı: Spotify anahtarı yok (.env → SPOTIFY_CLIENT_ID/SECRET)")
    adimlar += [("takvim", lambda: _takvim_hatirlat(kok)),
                ("temizlik", lambda: _temizle(argparse.Namespace(uygula=True, gun=op.temizlik_gun))),
                ("yedek", lambda: _yedekle(argparse.Namespace(zorla=False)))]
    sorunlu = []
    for ad, fn in adimlar:
        bas = time.monotonic()
        print(f"── {ad} ({datetime.now():%H:%M:%S})", flush=True)
        try:
            kod = fn() or 0
        except Exception:  # noqa: BLE001 — adım yalıtımı: iz günlüğe, koşu sürer
            traceback.print_exc(file=sys.stdout)
            kod = 1
        if kod:
            sorunlu.append(ad)
            print(f"✗ {ad} adımı sorunlu bitti ({time.monotonic() - bas:.0f} sn)", flush=True)
    print(f"── koşu bitti ({datetime.now():%H:%M:%S})" + (f"; sorunlu adım: {', '.join(sorunlu)}" if sorunlu else ""))
    _servis_ozeti(kok)
    return 1 if sorunlu else 0


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


def _takvim_hatirlat(kok: Path) -> int:
    """Sırası gelen paket: dağıtımcının API'si varsa (Faz 10) yüklenir, yoksa bildirilir (bir kez)."""
    from yanki import dagitim, paket

    calisma = kok / "calisma"
    ad = paket.yayin_ayarlari(kok / "config" / "yayin.toml").dagitimci
    p = dagitim.plan(calisma, dagitim.takvim_oku(kok / "config" / "yayin.toml"), dagitimci=ad)
    if p.beklemede:
        print(f"takvim: {p.beklemede}; kuyrukta {len(p.sira)} paket")
        return 0
    s = p.bugun_yuklenecek
    if s is None:
        ilk = p.sira[0] if p.sira else None
        print(f"takvim: sıradaki yükleme {ilk.yukleme:%d.%m} ({ilk.ad})" if ilk else "takvim: kuyruk boş")
        return 0
    d = dagitim.sec(ad, kok)
    if d.otomatik:
        bilgi = dagitim.otomatik_yukle(calisma, d, s.kimlik, s.yayin_tarihi)
        print(f"takvim: {s.sanatci} — {s.ad} {d.ad}'ya yüklendi, incelemede (yayın {s.yayin_tarihi:%Y-%m-%d}, "
              f"yayın kimliği {bilgi.get('release_id')})")
        _bildirici(calisma)("dagitim", f"yüklendi: {s.ad}",
                            f"{s.sanatci} — {s.ad} {paket.DAGITIMCI_ADI.get(d.ad, d.ad)} incelemesine gönderildi; "
                            f"yayın tarihi {s.yayin_tarihi:%Y-%m-%d}", f"yukleme:{s.kimlik}:{bilgi.get('release_id')}")
        return 0
    _bildirici(calisma)("takvim", f"yükleme sırası: {s.ad}",
                        f"{s.sanatci} — {s.ad}: calisma/{s.kimlik}/paket/YUKLE.md hazır; önerilen yayın tarihi "
                        f"{s.yayin_tarihi:%Y-%m-%d}. Yükleyince: yanki yuklendi {s.kimlik} --isrc …",
                        f"takvim:{s.kimlik}:{s.yukleme}")
    return 0


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
    sonuc = d.yokla(a.kok / "calisma", _bildirici(a.kok / "calisma"))
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


def _gunduz(args: argparse.Namespace) -> int:
    """Gündüz boşta üretim (`\\Yanki\\Gunduz` görevi, her 30 dk): koşullar uygunsa kuyruktan bir şarkı üretir.
    Koşul tutmazsa tek satır nedenle çıkar (görev günde ~34 kez çalışır, günlük kısa kalsın)."""
    from datetime import datetime

    from yanki import saglik, sistem

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    op = ayarlar.operasyon_oku(a.kok)
    simdi = datetime.now()
    if not op.gunduz_acik:
        return print("gündüz üretimi kapalı (config/operasyon.toml)") or 0
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
    hedef = sorted((d for d in durum.hepsi(calisma) if d.asama in ("onarim", "analiz")),
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


def _dinle(args: argparse.Namespace) -> int:
    import threading
    import webbrowser

    import uvicorn

    from yanki import sunucu

    a = ayarlar.yukle()
    adres = f"http://127.0.0.1:{args.port}/"
    if not args.tarayicisiz:
        threading.Timer(1.0, lambda: webbrowser.open(adres)).start()
    print(f"dinleme odası: {adres}  (durdurmak için Ctrl+C)")
    uvicorn.run(sunucu.uygulama(a, a.kok / "calisma"), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


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
    c.set_defaults(fn=_calistir, yeniden=False, analizsiz=False)
    yn = alt.add_parser("yeniden", help="onaylı/paketli şarkıya güncel hatla yeni adaylar (eskiler kalır)")
    yn.add_argument("kimlik", nargs="+")
    yn.set_defaults(fn=_yeniden)
    kn = alt.add_parser("kunye", help="hazır şarkıların künyesini (yazarlar, orijinal yıl) yeniden çek")
    kn.add_argument("kimlik", nargs="*", help="boşsa hepsi")
    kn.set_defaults(fn=_kunye)
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
                  "temizle", "yedekle", "dagitim-red", "gunduz", "yukle", "dagitim-durum", "kapak"}


if __name__ == "__main__":
    raise SystemExit(main())
