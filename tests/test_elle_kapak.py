"""Elle taslağa Pinterest kapağı (insansız, yazısız, kullanılmamış pin; "Başka kapak") ve sökülen yeniden yayın akışı:
Bulucu'dan başkasının kalkmış kaydını aynı ISRC'yle FreshTunes taslağına dolduran uçlar kapalı (2026-10-16)."""

import io
import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from yanki import ayarlar, elle, elle_kapak, kaynak, sunucu

KOK = Path(__file__).resolve().parents[1]


@pytest.fixture
def kok(tmp_path):
    (tmp_path / "config").mkdir()
    shutil.copy(KOK / "config" / "yayin.toml", tmp_path / "config" / "yayin.toml")
    return tmp_path


def _pin(no, en):
    return {"id": no, "type": "pin", "seo_alt_text": "misty forest lake at dusk", "image_signature": f"i{no}",
            "images": {"orig": {"url": f"https://p/{no}.jpg", "width": en, "height": en}}}


def _jpeg(en=1080) -> bytes:
    b = io.BytesIO()
    Image.new("RGB", (en, en), (10, 20, 30)).save(b, "JPEG")
    return b.getvalue()


def test_pinterest_kapagi_buyuk_ve_kullanilmamis_pin(tmp_path, kok):
    c = tmp_path / "calisma"
    k = elle.yeni(c, kok, "Kendi Şarkım", sablon="freshtunes")["kimlik"]
    (c / "a-b").mkdir(parents=True)  # başka bir Yanki şarkısında kullanılmış pin yeniden seçilmez
    (c / "a-b" / "kapak_kaynak.json").write_text(json.dumps({"pin_id": "1"}), encoding="utf-8")
    inen = []
    satir = elle_kapak.pinterest_kapak(c, k, arayici=lambda q: [_pin("1", 3000), _pin("2", 900), _pin("3", 1080)],
                                       indirici=lambda u: inen.append(u) or _jpeg())
    assert "Pinterest" in satir and inen == ["https://p/3.jpg"]  # 1 kullanılmış, 2 küçük (en az 1000, 3000'e büyür)
    m = elle.oku(c, k)
    assert m["kapak"]["kaynak"] == "pinterest" and any("Pinterest" in x for x in elle.kontrol(c, k)["uyari"])
    with Image.open(elle.klasor(c, k) / "kapak.jpg") as im:
        assert im.size == (3000, 3000)
    with pytest.raises(elle_kapak.Hata, match="Pinterest'te"):
        elle_kapak.pinterest_kapak(c, k, arayici=lambda q: [_pin("3", 1080)], indirici=lambda u: _jpeg())
    # "Başka kapak": önceki pinler reddedilmiş sayılır
    elle_kapak.pinterest_kapak(c, k, arayici=lambda q: [_pin("3", 1080), _pin("4", 1080)], indirici=lambda u: _jpeg())
    elle_kapak.pinterest_kapak(c, k, arayici=lambda q: [_pin("3", 1080), _pin("4", 1080), _pin("5", 1080)],
                               indirici=lambda u: _jpeg())
    kaynak_ = json.loads((elle.klasor(c, k) / "kapak_kaynak.json").read_text(encoding="utf-8"))
    assert kaynak_["pin_id"] == "5" and {"3", "4"} <= set(kaynak_["onceki"])


def test_odada_pinterest_kapagi_ve_sokulen_uclar(tmp_path, kok, monkeypatch):
    c = tmp_path / "calisma"
    k = elle.yeni(c, kok, "Kendi Şarkım", sablon="freshtunes")["kimlik"]
    cagri = []
    monkeypatch.setattr(elle_kapak, "pinterest_kapak", lambda c_, k_: cagri.append(k_) or "kapak: Pinterest (x)")
    oda = TestClient(sunucu.uygulama(replace(ayarlar.yukle(), kok=kok), c), base_url="http://127.0.0.1:8765")
    r = oda.post(f"/api/elle/{k}/pinterest", json={})
    assert r.status_code == 200 and r.json()["mesaj"].startswith("kapak: Pinterest") and cagri == [k]
    # başkasının kalkmış kaydını yeniden yayınlayan akış söküldü
    for yol in ("/api/bulucu/freshtunes", f"/api/elle/{k}/kaynak", "/api/elle-freshtunes/sanatcilar"):
        assert oda.post(yol, json={"parca": "5l6tv2lFylSdCgkWyfHC0P"}).status_code in (404, 405)
    assert oda.get("/api/kendi").status_code in (404, 405)


def test_youtube_bos_arama_sorguyu_aday_saymaz(monkeypatch):
    """2026-10-16: arama boş dönünce sorgunun kendisi 0:00 süreli aday olarak listeleniyordu (hazırlıkta da)."""
    import yt_dlp

    class Sahte:
        def __init__(self, *_a):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_a):
            return False

        def extract_info(self, hedef, download=False):
            if hedef.startswith("http"):
                return {"id": "abc", "title": "Video", "duration": 120, "channel": "K"}
            return {"id": hedef.split(":", 1)[1], "title": hedef, "entries": []}

    monkeypatch.setattr(yt_dlp, "YoutubeDL", Sahte)
    assert kaynak.youtube_adaylari("knownbyC Slow Fall official audio") == []
    assert [a.id for a in kaynak.youtube_adaylari("https://www.youtube.com/watch?v=abc")] == ["abc"]
