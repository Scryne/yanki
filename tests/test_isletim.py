"""Denetim 3 (2026-10-10) bulgularının testleri: kiralık GPU'da işçi başlatma, günlüğün canlı akması, dış servislerin
geçici hataları, dinleme odasının ve Spotify köprüsünün yerel korunması, yedek, durum, keşif çeşitliliği."""

import http.client
import io
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yanki import ag, ayarlar, durum, kesif, liste, runpod, sunucu, tunearo, uzak


class _Cevap(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


# ── kiralık GPU: işçi başlatma komutu SSH kanalını hemen bırakır ──
def _git_bash() -> str | None:
    yol = shutil.which("bash")
    return yol if yol and "system32" not in yol.lower() else None  # WSL'nin bash'i değil


@pytest.mark.skipif(_git_bash() is None, reason="bash yok")
def test_baslatma_betigi_ssh_kanalini_isci_bitmeden_birakir(tmp_path):
    """Eski betikte `&` bütün `cd && export && …` zincirini arka plana atıyordu: zinciri koşan alt kabuk stdout'u
    işçi bitene kadar tutuyor, SSH komutu her koşuda 120 sn zaman aşımına düşüyordu."""
    ev = tmp_path / "ev"
    (ev / ".local" / "bin").mkdir(parents=True)
    sahte_uv = ev / ".local" / "bin" / "uv"
    sahte_uv.write_text("#!/bin/sh\nsleep 8\necho bitti\n", encoding="utf-8")
    sahte_uv.chmod(0o755)
    dizin = tmp_path / "is"
    dizin.mkdir()
    yol = lambda p: p.as_posix().replace("C:", "/c").replace("c:", "/c")  # noqa: E731 — Git Bash yolu
    betik = uzak.baslatma_betigi(yol(tmp_path), yol(dizin))
    bas = time.monotonic()
    r = subprocess.run([_git_bash(), "-c", betik], capture_output=True, timeout=6,
                       env={**os.environ, "HOME": yol(ev)})
    assert r.returncode == 0 and time.monotonic() - bas < 4
    assert (dizin / "motor.pid").read_text().strip().isdigit()


def test_isci_kos_biten_is_sayisini_yazar():
    class Pod:
        def __init__(self):
            a, b = {"id": "a", "basari": True}, {"id": "b", "basari": False}
            self.yokla = [[], [a], [a, b]]

        def komut(self, betik, zaman_asimi=120, tekrar=True):
            if "motor_sonuc.json" not in betik or "cat " not in betik:
                return ""
            s = self.yokla.pop(0)
            return json.dumps(s) + "\n#DURUM#\n" + ("BITTI" if not self.yokla else "SURUYOR") + "\n"

    satirlar = []
    sonuc = uzak.isci_kos(Pod(), "/root/ACE", 60, aralik_sn=0, toplam=2, bildir=satirlar.append)
    assert len(sonuc) == 2
    assert [s.split(" (")[0] for s in satirlar] == ["  uzak motor: 1/2 iş bitti", "  uzak motor: 2/2 iş bitti"]
    assert "1 hatalı" in satirlar[-1]


def test_runpod_sorgusu_gecici_hatada_yeniden_denenir_pod_acan_istek_denenmez(monkeypatch):
    cagri = []

    def urlopen(istek, timeout):
        cagri.append(1)
        if len(cagri) == 1:
            raise http.client.RemoteDisconnected("koptu")
        return _Cevap(json.dumps({"data": {"myself": {"clientBalance": 12.5}}}).encode())

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(runpod.time, "sleep", lambda _: None)
    assert runpod.bakiye("x") == 12.5 and len(cagri) == 2
    cagri.clear()
    with pytest.raises(runpod.RunPodHatasi, match="ulaşılamadı"):
        runpod.gql("x", "mutation { podFindAndDeployOnDemand }", deneme=1)
    assert len(cagri) == 1


# ── günlük: uzun adımın çıktısı adım sürerken akar ──
def test_calistir_adim_ciktisi_adim_bitmeden_gunlukte(tmp_path, monkeypatch):
    from yanki import cli

    a = replace(ayarlar.yukle(), kok=tmp_path)
    monkeypatch.setattr(cli.ayarlar, "yukle", lambda: a)
    monkeypatch.setattr(cli, "_kesif_ayarlari", lambda _k: {"kesif": {"gece_ekle": 0}})
    for ad in ("_hazirla", "_otomatik_onay", "_paketle", "_dagitim_durum", "_takvim_hatirlat", "_temizle",
               "_yedekle"):
        monkeypatch.setattr(cli, ad, lambda *_a: print("paketlenecek onaylı şarkı yok") or 0)
    gunluk = io.StringIO()
    monkeypatch.setattr(sys, "stdout", gunluk)
    gorulen = {}

    def uret(*_):
        print("üretim (kiralık GPU): A — B (3 sırada)")
        gorulen["sirasinda"] = gunluk.getvalue()  # adım sürerken günlükte ne var
        print("uretildi  A — B: 3/3 aday kapıdan geçti")
        return 0

    monkeypatch.setattr(cli, "_uret_surekli", uret)
    assert cli._calistir(cli.argparse.Namespace(liste=None, analizsiz=False)) == 0
    assert gorulen["sirasinda"].startswith("── üretim (") and "A — B (3 sırada)" in gorulen["sirasinda"]
    cikti = gunluk.getvalue()
    assert "3/3 aday" in cikti and "── paketleme" not in cikti  # iş yapmayan adım yine yazılmaz


def test_adim_ciktisi_yalniz_bos_satirsa_yazilmaz_hata_olunca_yazilir():
    from yanki.cli import _AdimCiktisi

    hedef = io.StringIO()
    c = _AdimCiktisi("── takvim (03:00:00)", hedef)
    c.write("takvim: kuyruk boş\n")
    assert c.bitir() is False and hedef.getvalue() == ""
    c = _AdimCiktisi("── yedek (03:00:00)", hedef)
    c.write("yedek güncel (son: …)")  # satır sonu yok
    assert c.bitir(zorla=True) and hedef.getvalue() == "── yedek (03:00:00)\nyedek güncel (son: …)\n"


# ── dış servisler: geçici hatalar ──
def test_json_al_retry_after_bekler_dorduncu_denemede_alir(monkeypatch):
    """LRCLIB yükte 503 "ServerOverloaded" veriyor (2026-10-10 keşfinde isteklerin %39'u); üç ardışık 503 şarkıyı
    söz yok'a düşürüyordu."""
    cagri, uykular = [], []

    def urlopen(istek, timeout):
        cagri.append(1)
        if len(cagri) < 4:
            basliklar = http.client.HTTPMessage()
            basliklar["Retry-After"] = "7"
            raise urllib.error.HTTPError(istek.full_url, 503, "busy", basliklar, io.BytesIO(b"{}"))
        return _Cevap(b'{"plainLyrics": "la"}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(ag.time, "sleep", uykular.append)
    assert ag.json_al("https://lrclib.net/api/get") == {"plainLyrics": "la"}
    assert uykular == [7.0, 7.0, 7.0]
    assert ag.bekleme_sn(None, 1) == 4.0


def test_tunearo_kopuk_cevap_yeniden_denenir(monkeypatch):
    cagri = []

    def urlopen(istek, timeout):
        cagri.append(1)
        if len(cagri) == 1:
            raise http.client.RemoteDisconnected("Remote end closed connection without response")
        if len(cagri) == 2:
            raise http.client.IncompleteRead(b"{")
        return _Cevap(b'{"status": "pending"}')

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr("time.sleep", lambda *_: None)
    assert tunearo.Istemci("tn").get("/releases/r/status") == {"status": "pending"} and len(cagri) == 3
    # POST hiç yinelenmez (yinelenen yayın açıp parça kotasını yakmasın)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *_a, **_k: (_ for _ in ()).throw(
        http.client.RemoteDisconnected("koptu")))
    with pytest.raises(tunearo.TunearoHatasi, match="RemoteDisconnected"):
        tunearo.Istemci("tn").post("/releases", {})


# ── dinleme odası: yalnız yerel ──
@pytest.fixture
def oda(tmp_path):
    c = tmp_path / "calisma"
    d = durum.Durum("a-b", "A", "B")
    d.gec("reddedildi")
    (c / "a-b").mkdir(parents=True)
    durum.yaz(c, d)
    return sunucu.uygulama(ayarlar.yukle(), c, tmp_path / "liste.toml"), c


def test_oda_baska_siteden_yazma_istegini_ve_yabanci_hostu_reddeder(oda):
    app, c = oda
    yerel = TestClient(app, base_url="http://127.0.0.1:8765")
    r = yerel.post("/api/sarki/a-b/geri-al", headers={"Origin": "https://kotu.example"})
    assert r.status_code == 403 and durum.oku(c, "a-b").asama == "reddedildi"
    r = yerel.post("/api/sarki/a-b/geri-al", headers={"Origin": "null"})
    assert r.status_code == 403
    r = yerel.post("/api/sarki/a-b/geri-al", headers={"Sec-Fetch-Site": "cross-site"})
    assert r.status_code == 403
    # DNS yeniden bağlama: alan adı 127.0.0.1'e çevrilse de Host yabancı
    assert TestClient(app, base_url="http://kotu.example").get("/api/sarkilar").status_code == 403
    # odanın kendi sayfası (aynı köken) ve Origin'siz araç geçer
    assert yerel.get("/api/sarkilar").status_code == 200
    r = yerel.post("/api/sarki/a-b/geri-al", headers={"Origin": "http://127.0.0.1:8765"})
    assert r.status_code == 200 and durum.oku(c, "a-b").asama == "yeni"
    assert TestClient(app, base_url="http://localhost:8765").get("/api/sarkilar").status_code == 200


# ── Spotify köprüsü: hata ayıklama portu her kökene açılmaz ──
def test_spotify_cdp_portu_her_kokene_acilmaz(tmp_path, monkeypatch):
    from yanki import stillmore

    exe = tmp_path / "Spotify.exe"
    exe.write_bytes(b"")
    acilan = []
    monkeypatch.setattr(stillmore, "SPOTIFY", exe)
    monkeypatch.setattr(stillmore.subprocess, "Popen", lambda arg, **_k: acilan.append(arg))
    monkeypatch.setattr(stillmore, "cdp_acik", lambda port=9222: True)
    stillmore.ac(cdp=True)
    assert "--remote-debugging-port=9222" in acilan[0]
    assert not any(x.startswith("--remote-allow-origins") for x in acilan[0])


# ── yedek ve durum ──
def test_yedek_kiralik_gpu_harcamasini_alir(tmp_path):
    from yanki import yedek

    uzak.harcama_yaz(tmp_path, {"zaman": datetime.now().isoformat(), "usd": 0.5})
    assert tmp_path / "calisma" / "gunluk" / "runpod.json" in yedek.dosyalar(tmp_path)


def test_durum_kiralik_gpu_harcamasini_ve_durmayi_gosterir(tmp_path):
    from yanki import saglik

    a = replace(ayarlar.yukle(), kok=tmp_path, uzak=ayarlar.Uzak(acik=True, aylik_butce=1.0))
    uzak.harcama_yaz(tmp_path, {"zaman": datetime.now().isoformat(), "usd": 0.4})
    k = saglik.uzak_kontrolu(a)
    assert k.tamam and "0.40 $ / 1.00 $" in k.ayrinti
    uzak.harcama_yaz(tmp_path, {"zaman": datetime.now().isoformat(), "usd": 0.7})
    assert not saglik.uzak_kontrolu(a).tamam
    uzak.durma_yolu(tmp_path).write_text("2026-10-10 RunPodHatasi: SSH", encoding="utf-8")
    assert "devre dışı" in saglik.uzak_kontrolu(a).ayrinti
    assert any(x.ad == "kiralık GPU" for x in saglik.kontroller(a))


# ── keşif: aynı sanatçıdan sırada bekleyen varken yenisi eklenmez ──
def test_kesif_ayni_sanatcidan_bekleyen_varken_eklemez(tmp_path):
    lyol = tmp_path / "liste.toml"
    lyol.write_text('[[sarki]]\nsanatci = "Xiu Xiu"\nad = "Boy Soprano"\n', encoding="utf-8")
    calisma = tmp_path / "calisma"
    calisma.mkdir()

    def aday(sanatci, ad, izlenme):
        return kesif.Aday(sanatci, ad, "k", youtube_izlenme=izlenme, geri_geldi=False, sanatci_uyusuyor=True)

    adaylar = [aday("Xiu Xiu", "Clowne Towne", 10**6), aday("Deerhoof", "A", 9 * 10**5),
               aday("Deerhoof", "B", 8 * 10**5), aday("Janice Javier", "Heaven Knows", 10**5)]
    eklenen = kesif.listeye_ekle(adaylar, lyol, calisma, adet=2)
    assert [(x.sanatci, x.ad) for x in eklenen] == [("Deerhoof", "A"), ("Janice Javier", "Heaven Knows")]
    # Xiu Xiu'nun şarkısı yayına çıkınca sıradaki Xiu Xiu eklenebilir
    d = durum.Durum(liste.kimlik("Xiu Xiu", "Boy Soprano"), "Xiu Xiu", "Boy Soprano")
    d.gec("yayinda")
    (calisma / d.kimlik).mkdir()
    durum.yaz(calisma, d)
    assert "xiu xiu" not in kesif.bekleyen_sanatcilar(lyol, calisma)
    assert [x.ad for x in kesif.listeye_ekle(adaylar, lyol, calisma, adet=1)] == ["Clowne Towne"]


def test_surekli_betik_kilit_mesajini_gunluge_yazmaz():
    metin = (Path(__file__).resolve().parents[1] / "scripts" / "surekli.ps1").read_text(encoding="utf-8-sig")
    assert '-like "başka bir yanki koşusu sürüyor*"' in metin
    gece = (Path(__file__).resolve().parents[1] / "scripts" / "gece.ps1").read_text(encoding="utf-8-sig")
    assert "run --no-sync python -m yanki calistir" in gece


def test_listeye_yaz_bozuk_eklemede_dosyaya_dokunmaz_ve_atomik_yazar(tmp_path):
    lyol = tmp_path / "liste.toml"
    lyol.write_text('# açıklama\n[[sarki]]\nsanatci = "A"\nad = "B"', encoding="utf-8")  # sonda satır sonu yok
    once = lyol.read_bytes()
    with pytest.raises(ValueError, match="iki kez"):
        kesif.listeye_yaz([kesif.Aday("A", "B", "k", youtube_izlenme=1)], lyol)
    assert lyol.read_bytes() == once  # önce sona eklenip sonra doğrulanıyordu: bozuk liste kalıyordu
    kesif.listeye_yaz([kesif.Aday("C", "D", "k", youtube_izlenme=1)], lyol)
    assert [s.sanatci for s in liste.yukle(lyol)] == ["A", "C"]
    assert not list(tmp_path.glob("*.tmp"))
