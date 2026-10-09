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


def _hazirla(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    calisma, girdi = a.kok / "calisma", a.kok / "girdi"
    sarkilar = liste.yukle(Path(args.liste) if args.liste else girdi / "liste.toml")
    if not sarkilar:
        print("liste boş: girdi/liste.toml'a [[sarki]] ekle")
        return 1
    for s in sarkilar:
        mevcut = durum.oku(calisma, s.kimlik)
        if mevcut and mevcut.asama not in ("yeni", "hata") and not args.yeniden:
            continue
        d = hazirlik.girdi_hazirla(a, s, calisma, girdi)
        print(f"{d.asama:6} {s.sanatci} — {s.ad}" + (f": {d.hata}" if d.hata else f" [{d.kaynak.get('nereden')}]"))
    if not args.analizsiz:
        hazirlik.analiz_et(a, sarkilar, calisma)
        for s in sarkilar:
            d = durum.oku(calisma, s.kimlik)
            if d and d.asama == "analiz":
                print(f"analiz {s.ad}: {d.analiz['stil']} | {d.analiz['bpm']} BPM | {d.analiz['ton']}")
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
        d = durum.oku(calisma, kimlik)
        if d is None:
            print(f"'{kimlik}' bulunamadı")
            kod = 1
            continue
        try:
            uretim.yeniden_uretime_al(d)
        except ValueError as e:
            print(f"{kimlik}: {e}")
            kod = 1
            continue
        durum.yaz(calisma, d)
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
            d.kunye = asdict(kunye.bul(d.sanatci, d.ad))
        except (ag.Bulunamadi, OSError) as e:
            print(f"✗ {d.sanatci} — {d.ad}: {e}")
            kod = 1
            continue
        durum.yaz(calisma, d)
        adlar = ", ".join(f"{x} {y}".strip() if y else f"{x} (SOYAD?)" for x, y in d.kunye["yazar_adlari"])
        print(f"✓ {d.sanatci} — {d.ad}: {d.kunye['ilk_yayin']} | {adlar}")
    return kod


def _paketle(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    islenen = paket.paketle(a.kok / "calisma", a.kok / "config" / "yayin.toml", yeniden=args.yeniden)
    if not islenen:
        print("paketlenecek onaylı şarkı yok")
    for d in islenen:
        print(f"paket hazır: {d.sanatci} — {d.ad} → calisma/{d.kimlik}/paket/YUKLE.md")
    return 0


def _yuklendi(args: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    d = durum.oku(a.kok / "calisma", args.kimlik)
    if d is None or d.asama != "paketlendi":
        print(f"'{args.kimlik}' paketlenmiş bir şarkı değil" + (f" (aşama: {d.asama})" if d else ""))
        return 1
    d.gec("yuklendi")
    durum.yaz(a.kok / "calisma", d)
    print(f"yüklendi olarak işaretlendi: {d.sanatci} — {d.ad}")
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
    kat = ayar.get("katalog", {})
    if dogrula and kat.get("acik") and not args.katalogsuz:
        ek = [ad for ad, _ in sayac.most_common(int(kat.get("playlist_sanatcilari", 0)))]
        try:
            adaylar += katalog.tara(sp, calisma, pazarlar, katalog.Ayar.oku(kat), ek)
        except spotify.Sinirli as e:
            print(f"✗ katalog farkı: {e}")
        except (OSError, katalog.DeezerHatasi) as e:
            print(f"✗ katalog farkı: {e}")
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

    olculecek = [x for x in tekil if not kesif.taze(x.olcum)]
    for x in olculecek:
        try:
            kesif.talep_olc(x)
        except Exception as e:  # noqa: BLE001 — YouTube araması düşerse aday kalır, talep boş
            print(f"  YouTube ölçülemedi ({x.sanatci} — {x.ad}): {e}")
            continue
        if x.sanatci_uyusuyor is True:
            try:
                kesif.soz_kontrol(x)
            except OSError as e:
                print(f"  LRCLIB'e ulaşılamadı ({x.sanatci} — {x.ad}): {e}")
                continue
        x.olcum = datetime.now().isoformat(timespec="seconds")
    if olculecek:
        print(f"ücretsiz ölçüm: {len(olculecek)} aday (YouTube, LRCLIB)")
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


def _takip(args: argparse.Namespace) -> int:
    from yanki import spotify, takip

    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    t = _kesif_ayarlari(a.kok)["takip"]
    y = paket.yayin_ayarlari(a.kok / "config" / "yayin.toml")
    sp = spotify.Spotify(a.kok)
    try:
        sonuc = takip.takip_et(sp, calisma, y.sanatci_adi, tuple(t["pazarlar"]), args.kimlik or None,
                               int(t["arama_derinligi"]))
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


def _calistir(args: argparse.Namespace) -> int:
    """Arka plan koşusu: (açıksa) kaldırılmış şarkı keşfi → listeye ekle, yeni şarkıları hazırla, üret (bekleyen
    onarımlar dahil), onaylıları paketle, yüklenenleri takip et. Liste boş olsa da onarım ve paketleme yapılır.
    Spotify anahtarı yoksa keşif ve takip atlanır, koşu düşmez."""
    from yanki import spotify

    kok = ayarlar.yukle().kok
    spotify_var = bool(spotify.Spotify(kok).client_id)
    gece_ekle = int(_kesif_ayarlari(kok)["kesif"].get("gece_ekle", 0))
    if gece_ekle and spotify_var:
        _kesif(argparse.Namespace(csv=[], playlist=[], pazar=None, ekle=gece_ekle, goster=10, katalogsuz=False,
                                  yeniden_olc=False))
    _hazirla(args)
    _uret(args)
    args.yeniden = False
    kod = _paketle(args)
    if spotify_var:
        _takip(argparse.Namespace(kimlik=[]))
    else:
        print("takip atlandı: Spotify anahtarı yok (.env → SPOTIFY_CLIENT_ID/SECRET)")
    return kod


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
    c = alt.add_parser("calistir", help="hazırla + analiz + üret: arka plan koşusu")
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
    y = alt.add_parser("yuklendi", help="dağıtımcıya yüklenen şarkıyı işaretle")
    y.add_argument("kimlik")
    y.set_defaults(fn=_yuklendi)
    sb = alt.add_parser("spotify-baglan", help="Spotify hesabını bir kez bağla (kendi playlist'lerini taramak için)")
    sb.set_defaults(fn=_spotify_baglan)
    ks = alt.add_parser("kesif", help="Spotify'dan kaldırılmış, hâlâ aranan şarkıları bul, doğrula, sırala")
    ks.add_argument("--csv", nargs="*", default=[], help="STILLMORE CSV'si (varsayılan girdi/kesif/*.csv)")
    ks.add_argument("--playlist", nargs="*", default=[], help="kendi playlist'in (varsayılan config/kesif.toml)")
    ks.add_argument("--pazar", nargs="*", help="pazarlar, ilki ana (varsayılan config/kesif.toml)")
    ks.add_argument("--katalogsuz", action="store_true", help="Deezer katalog farkını atla")
    ks.add_argument("--yeniden-olc", action="store_true", help="kayıtta ölçülmüş adayları da yeniden ölç")
    ks.add_argument("--ekle", type=int, default=0, help="en iyi N doğrulanmış adayı girdi/liste.toml'a ekle")
    ks.add_argument("--goster", type=int, default=25)
    ks.set_defaults(fn=_kesif)
    tk = alt.add_parser("takip", help="yüklenenler Spotify'da mı, adı arandığında kaçıncı sırada")
    tk.add_argument("kimlik", nargs="*", help="boşsa hepsi")
    tk.set_defaults(fn=_takip)
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
                return 0 if args.komut == "calistir" else 3
            return args.fn(args)
    return args.fn(args)


YAZAN_KOMUTLAR = {"hazirla", "uret", "calistir", "yeniden", "kunye", "paketle", "yuklendi", "kesif", "takip"}


if __name__ == "__main__":
    raise SystemExit(main())
