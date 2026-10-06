"""yanki komut satırı."""

import argparse
import sys
from pathlib import Path

from yanki import ayarlar, durum, hazirlik, liste, saglik


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
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
