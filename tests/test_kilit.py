import subprocess
import sys

from yanki import kilit


def test_ikinci_koşu_kilidi_alamaz_birinci_bitince_alir(tmp_path):
    yol = tmp_path / "k.kilit"
    with kilit.tek_kosu(yol) as birinci:
        assert birinci
        # ayrı süreç (gece görevi gibi) kilidi alamamalı
        kod = ("import sys; from pathlib import Path; from yanki import kilit\n"
               "with kilit.tek_kosu(Path(sys.argv[1])) as a: print(a)")
        cikti = subprocess.run([sys.executable, "-c", kod, str(yol)], capture_output=True, text=True).stdout.strip()
        assert cikti == "False"
    with kilit.tek_kosu(yol) as tekrar:
        assert tekrar


def test_olen_surecin_kilidi_kalmaz(tmp_path):
    yol = tmp_path / "k.kilit"
    kod = ("import sys, os; from pathlib import Path; from yanki import kilit\n"
           "with kilit.tek_kosu(Path(sys.argv[1])) as a: os._exit(3)")  # temizlik yapmadan öl
    assert subprocess.run([sys.executable, "-c", kod, str(yol)]).returncode == 3
    with kilit.tek_kosu(yol) as alindi:
        assert alindi


def test_yazan_komutlar_kilit_altinda(monkeypatch):
    from yanki import cli

    alinanlar = []
    import contextlib

    @contextlib.contextmanager
    def sahte(yol):
        alinanlar.append(yol.name)
        yield False  # başka koşu sürüyor

    monkeypatch.setattr(kilit, "tek_kosu", sahte)
    monkeypatch.setattr(cli, "_uret", lambda _: (_ for _ in ()).throw(AssertionError("kilitsiz çalıştı")))
    assert cli.main(["uret"]) == 3
    assert cli.main(["calistir"]) == 0
    assert alinanlar == [".yanki.kilit", ".yanki.kilit"]
