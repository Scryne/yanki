"""yanki komut satırı."""

import argparse
import sys

from yanki import ayarlar, saglik


def durum(_: argparse.Namespace) -> int:
    a = ayarlar.yukle()
    sonuc = saglik.kontroller(a)
    for k in sonuc:
        print(f"{'✓' if k.tamam else '✗'} {k.ad:28} {k.ayrinti}")
    return 0 if all(k.tamam for k in sonuc) else 1


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(prog="yanki", description=__doc__)
    alt = ap.add_subparsers(dest="komut", required=True)
    alt.add_parser("durum", help="motor, model, araçlar ve GPU hazır mı").set_defaults(fn=durum)
    args = ap.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
