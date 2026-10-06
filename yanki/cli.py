"""yanki komut satırı."""

import argparse
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
            print(f"  {d.asama:11} {d.sanatci} — {d.ad}" + (f"  ({d.hata})" if d.hata else ""))
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


def _calistir(args: argparse.Namespace) -> int:
    """Arka plan koşusu: yeni şarkıları hazırla, üret, onaylıları paketle."""
    kod = _hazirla(args)
    if kod:
        return kod
    _uret(args)
    args.yeniden = False
    return _paketle(args)


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
    p = alt.add_parser("paketle", help="onaylı şarkılardan yükleme paketi (mastering, kapak, YUKLE.md)")
    p.add_argument("--yeniden", action="store_true", help="paketlenmişleri de yeniden paketle")
    p.set_defaults(fn=_paketle)
    y = alt.add_parser("yuklendi", help="dağıtımcıya yüklenen şarkıyı işaretle")
    y.add_argument("kimlik")
    y.set_defaults(fn=_yuklendi)
    dn = alt.add_parser("dinle", help="dinleme sayfasını aç")
    dn.add_argument("--port", type=int, default=8765)
    dn.add_argument("--tarayicisiz", action="store_true")
    dn.set_defaults(fn=_dinle)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
