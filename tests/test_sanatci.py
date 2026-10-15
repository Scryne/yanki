import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from yanki import ayarlar, durum, sanatci, sunucu

KOK = Path(__file__).resolve().parents[1]
ODA = "http://127.0.0.1:8765"


@pytest.fixture
def kok(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(KOK / "config" / "yayin.toml", tmp_path / "config" / "yayin.toml")
    return tmp_path


def _paketli(c: Path, kimlik: str, ad: str, routenote: dict | None = None) -> durum.Durum:
    d = durum.Durum(kimlik, "Orijinal", ad, kaynak={"dosya": "kaynak.wav"})
    for a in ("uretildi", "onaylandi", "paketlendi"):
        d.gec(a)
    durum.yaz(c, d)
    p = durum.klasor(c, kimlik) / "paket"
    p.mkdir(parents=True)
    meta = {"baslik": ad, "hazirlanma": "2026-10-13", **({"routenote": routenote} if routenote else {})}
    (p / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
    return d


def test_ayar_yaz_yalniz_satiri_degistirir_yorumlari_korur(kok):
    once = (kok / "config" / "yayin.toml").read_text(encoding="utf-8")
    sonuc = sanatci.ayar_yaz(kok, {"gece": True, "yayin_on_gun": 30, "spotify_sanatci_id": "4Z8W4fKeB5YxbusRsdQVPb"})
    assert sonuc == {"gece": True, "spotify_sanatci_id": "4Z8W4fKeB5YxbusRsdQVPb", "yayin_on_gun": 30}
    sonra = (kok / "config" / "yayin.toml").read_text(encoding="utf-8")
    farkli = [(a, b) for a, b in zip(once.splitlines(), sonra.splitlines(), strict=True) if a != b]
    assert len(farkli) == 3 and all(a.split("=")[0] == b.split("=")[0] for a, b in farkli)
    # [tunearo] gibi başka bölümlerde aynı adlı anahtar olsa da yalnız hedef bölüm değişir
    assert sonra.count("gece = true") == 1


@pytest.mark.parametrize("degisiklik", [{"yayin_on_gun": 0}, {"spotify_sanatci_id": "x/../y"}])
def test_ayar_yaz_bozuk_degeri_yazmaz(kok, degisiklik):
    once = (kok / "config" / "yayin.toml").read_text(encoding="utf-8")
    with pytest.raises(ValueError):
        sanatci.ayar_yaz(kok, degisiklik)
    assert (kok / "config" / "yayin.toml").read_text(encoding="utf-8") == once


def test_katalog_hal(tmp_path):
    c = tmp_path / "calisma"
    _paketli(c, "a-kuyruk", "Kuyruk")
    _paketli(c, "b-yarim", "Yarım", {"upc": "5064150000001", "adim": "ses"})
    _paketli(c, "c-hazir", "Hazır", {"upc": "5064150000002", "adim": "hazir", "isrc": "ZZA192600001"})
    hal = {x["ad"]: x["hal"] for x in sanatci.katalog(c, lambda *_: None)}
    assert hal == {"Kuyruk": "kuyruk", "Yarım": "taslak_yarim", "Hazır": "taslak_hazir"}
    assert [x["ad"] for x in sanatci.katalog(c, lambda *_: None)] == ["Hazır", "Yarım", "Kuyruk"]  # hazır olan önce


@pytest.fixture
def oda(tmp_path, kok, monkeypatch):
    c = tmp_path / "calisma"
    _paketli(c, "numb", "Numb", {"upc": "5064149827466", "adim": "hazir"})
    baslayan = []
    monkeypatch.setattr(sanatci.Isci, "baslat", lambda self, ad, kimlik=None: baslayan.append((ad, kimlik)) or
                        {"ad": ad, "kimlik": kimlik})
    a = replace(ayarlar.yukle(), kok=kok)
    return TestClient(sunucu.uygulama(a, c), base_url=ODA), baslayan


def test_sanatci_ozeti(oda):
    istemci, _ = oda
    r = istemci.get("/api/sanatci").json()
    assert r["ad"] == "Orvane" and [x["hal"] for x in r["katalog"]] == ["taslak_hazir"]
    assert r["ayar"]["gece"] is False


def test_gonderim_sarki_adi_yazilmadan_baslamaz(oda):
    istemci, baslayan = oda
    assert istemci.post("/api/sanatci/numb/gonder", json={"onay": "evet"}).status_code == 422
    assert baslayan == []
    assert istemci.post("/api/sanatci/numb/gonder", json={"onay": " numb "}).status_code == 200
    assert baslayan == [("gonder", "numb")]


def test_gonderim_baska_siteden_gelemez(oda):
    istemci, baslayan = oda
    r = istemci.post("/api/sanatci/numb/gonder", json={"onay": "Numb"}, headers={"Origin": "https://kotu.example"})
    assert r.status_code == 403 and baslayan == []


def test_odadan_ayar(oda, kok):
    istemci, _ = oda
    assert istemci.post("/api/sanatci/ayar", json={"gece": True}).json()["gece"] is True
    assert "gece = true" in (kok / "config" / "yayin.toml").read_text(encoding="utf-8")
    assert istemci.post("/api/sanatci/ayar", json={"yayin_on_gun": 500}).status_code == 422


def test_isci_tek_is_ve_gunluk(tmp_path, monkeypatch):
    """Gerçek alt süreç (zararsız `yanki --help`; RouteNote'a dokunan komut değil): günlük dosyaya yazılır, ikinci iş
    sürerken reddedilir."""
    c = tmp_path / "calisma"
    c.mkdir()
    monkeypatch.setattr(sanatci, "IS_KOMUTLARI", {"deneme": (["--help"], False)})
    isci = sanatci.Isci(tmp_path, c)
    k = isci.baslat("deneme")
    assert k["ad"] == "deneme" and Path(k["gunluk"]).exists()
    with pytest.raises(RuntimeError):
        isci.baslat("deneme")
    isci._surec.kill()
    isci._surec.wait()
    d = isci.durum()
    assert d["bitis"] is not None and not d["suruyor"]
