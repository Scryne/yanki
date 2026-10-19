"""Ses modeli eğitimi (yanki/egitim.py): veri, kiralık GPU orkestrasyonu ve LoRA'nın üretime bağlanması. Gerçek
ağ, GPU ve ffmpeg yok; pod sahte."""

import json
import re
from dataclasses import replace
from pathlib import Path

import pytest

from yanki import ayarlar, durum, egitim, kaynak, liste, motor, runpod, sozler, uzak

GERCEK_LORA_DENETLE = ayarlar.lora_denetle  # conftest testlerde etkisizleştiriyor

KOK = Path(__file__).resolve().parents[1]


# Popüler keşif (2026-10-13) eğitim sanatçısı süzgeci yokken listeye bunları ekledi; süzgeç (kesif.listeye_ekle) o
# günden beri eklemiyor. Yeni bir çakışma testi kırar.
ESKI_CAKISMA = {"arctic monkeys", "billie eilish", "calvin harris", "camila cabello", "dua lipa", "katy perry",
                "lady gaga", "linkin park", "onerepublic", "post malone", "red hot chili peppers", "shawn mendes",
                "sia", "system of a down"}


def test_gercek_egitim_ayari_okunur_ve_cover_sanatcisi_icermez():
    """Veri cover listesindeki sanatçıları içermemeli (kapak yaptığımız kayıtlar ezberlenmesin, tek bir sesin
    kopyası olmasın); her sanatçıdan en çok bir şarkı."""
    ayar, sarkilar = egitim.oku(KOK / "config" / "egitim.toml")
    cover = {s.sanatci.casefold() for s in liste.yukle(KOK / "girdi" / "liste.toml")}
    assert len(sarkilar) >= egitim_en_az() and not {s.sanatci.casefold() for s in sarkilar} & cover - ESKI_CAKISMA
    assert len({s.sanatci for s in sarkilar}) == len(sarkilar)
    assert ayar.model == "acestep-v15-xl-sft" and ayar.deneme_olcekleri
    # deneme şarkıları eğitimde yok (sınadığımız kaydı ezberlemesin); 2026-10-12'den beri karşılaştırma önceki
    # LoRA'nın hazır çıktılarıyla (kör test), LoRA'sız kol yok
    assert not {s.kimlik for s in sarkilar} & set(ayar.deneme_sarkilari)


def test_egitimdeki_sarkinin_coveri_uretilmez(tmp_path):
    from yanki import uretim

    (tmp_path / "config").mkdir()
    (tmp_path / "config" / "egitim.toml").write_text("".join(
        f'[[sarki]]\nsanatci = "{s}"\nad = "{ad}"\nstil = "rock"\n'
        for s, ad in (("Arctic Monkeys", "Do I Wanna Know?"), ("Red Hot Chili Peppers", "Californication"))),
        encoding="utf-8")
    a = replace(ayarlar.yukle(), kok=tmp_path)
    c = tmp_path / "calisma"
    for s, ad, asama in (("Arctic Monkeys", "Do I Wanna Know?", "analiz"), ("Arctic Monkeys", "R U Mine?", "analiz"),
                         ("Red Hot Chili Peppers", "Californication", "onarim")):  # üretilmiş olanın onarımı sürer
        durum.yaz(c, durum.Durum(liste.kimlik(s, ad), s, ad, asama=asama))
    assert sorted(d.kimlik for d in uretim.uretilecek(a, c)) == ["arctic-monkeys-r-u-mine",
                                                                   "red-hot-chili-peppers-californication"]
    assert uretim.egitimde(tmp_path / "yok") == set()  # eğitim ayarı yoksa süzgeç boş


def egitim_en_az():
    from yanki import cli

    return cli.EGITIM_EN_AZ_ORNEK


@pytest.mark.parametrize("metin, hata", [
    ('[egitim]\nbilinmeyen = 1\n', "bilinmeyen"),
    ('[egitim]\nbetim = false\n[[sarki]]\nsanatci = "A"\nad = "B"\n', "stil"),  # betimsiz eğitimde stil şart
    ('[[sarki]]\nsanatci = "A"\nad = "B"\nstil = "x"\n[[sarki]]\nsanatci = "a"\nad = "b"\nstil = "y"\n', "iki kez"),
    ('[egitim]\nen_uzun_sn = 10\n', "en_uzun_sn"),
])
def test_ayar_dogrulama(tmp_path, metin, hata):
    yol = tmp_path / "egitim.toml"
    yol.write_text(metin, encoding="utf-8")
    with pytest.raises(ValueError, match=hata):
        egitim.oku(yol)


def test_kesit_sozu_uretimdeki_bicimde_ve_kesitle_ayni_yerden():
    zamanli = tuple((t, m) for t, m in zip((5, 10, 50, 55, 100, 105, 150, 155), "a1 a2 n1 n2 b1 b2 n1 n2".split(),
                                           strict=True))
    soz = sozler.Soz(sozler.yapi.metin(sozler.yapi.coz(zamanli, 160.0)), "lrclib", 160.0, zamanli)
    assert egitim.kesit_sozu(soz, 160, 160) == soz.metin  # kesilmeyen şarkı: üretimdeki soz.txt'nin aynısı
    # 104 sn'de kesildi: 101'den sonra başlayan satır yok; yapı bütün şarkıdan (nakarat iki kez geçiyor)
    assert egitim.kesit_sozu(soz, 104, 160) == ("[Intro]\n\n[Verse 1]\na1\na2\n\n[Instrumental]\n\n[Chorus]\nn1\nn2"
                                               "\n\n[Instrumental]\n\n[Verse 2]\nb1")
    assert egitim.kesit_sozu(soz, 60, 160) == "[Intro]\n\n[Verse 1]\na1\na2\n\n[Instrumental]\n\n[Chorus]\nn1\nn2"
    # zaman damgası yoksa düz sözden kesitin oranı kadar satır
    duz = sozler.Soz("[Verse 1]\na\nb\n\n[Chorus]\nc\nd", "dosya", 100.0)
    assert egitim.kesit_sozu(duz, 60, 100) == "[Verse 1]\na\nb"


def test_kaynak_secimi_album_sesini_tercih_eder_akustik_ve_kurguyu_eler():
    a = [kaynak.Aday("klip", "X - Song (Official Music Video)", 200.0),
         kaynak.Aday("akustik", "X - Song (Acoustic)", 201.0, "X - Topic"),
         kaynak.Aday("kurgu", "X - Song // Film Trailer", 200.0, "X - Topic"),
         kaynak.Aday("soz", "X - Song (Lyrics)", 201.0),
         kaynak.Aday("ses", "X - Song (Audio)", 202.5)]
    assert egitim.sec(a, 200.0).id == "ses"
    assert egitim.sec([*a, kaynak.Aday("topic", "Song", 203.0, "X - Topic")], 200.0).id == "topic"
    assert egitim.sec(a[:1], 200.0).id == "klip"
    with pytest.raises(kaynak.KaynakYok):
        egitim.sec(a[1:3], 200.0)


def test_ornek_hazirlama_kesit_ve_onbellek(tmp_path, monkeypatch):
    calistirilan = []

    def ffmpeg(arg, check):
        calistirilan.append(arg)
        Path(arg[-1]).write_bytes(b"fLaC")

    monkeypatch.setattr(egitim.subprocess, "run", ffmpeg)
    monkeypatch.setattr(egitim.ses, "sure", lambda _y: 300.0)
    monkeypatch.setattr(egitim.ses, "arac", lambda ad: ad)
    zamanli = ((10.0, "bir"), (100.0, "iki"), (239.0, "üç"))
    soz = sozler.Soz("[verse]\nbir\niki\nüç", "lrclib", 300.0, zamanli)
    indirilen = []

    def indir(vid, hedef):
        indirilen.append(vid)
        hedef.write_bytes(b"x")
        return hedef

    s = egitim.VeriSarki("A", "B", "piano ballad")
    bag = dict(lrclib=lambda *_: soz, adaylar=lambda _q: [kaynak.Aday("v1", "A - B (Audio)", 299.0)], indir=indir)
    m = egitim.ornek_hazirla(s, egitim.Ayar(en_uzun_sn=240), tmp_path, **bag)
    assert m["lyrics"] == "[Intro]\n\n[Verse 1]\nbir\n\n[Instrumental]\n\n[Verse 2]\niki\n\n[Instrumental]"
    assert m["duration"] == 240 and m["caption"] == "piano ballad"
    assert "-t" in calistirilan[0] and any("afade" in x for x in calistirilan[0])  # kesilen şarkı yumuşak biter
    assert not (tmp_path / "a-b.indirilen").exists()
    # ikinci kez inmez; stil düzeltilince yalnız metin güncellenir
    s2 = egitim.VeriSarki("A", "B", "acoustic ballad")
    assert egitim.ornek_hazirla(s2, egitim.Ayar(), tmp_path, **bag)["caption"] == "acoustic ballad"
    assert indirilen == ["v1"]
    with pytest.raises(LookupError, match="zaman damgalı"):
        egitim.ornek_hazirla(egitim.VeriSarki("C", "D", "x"), egitim.Ayar(), tmp_path,
                             lrclib=lambda *_: sozler.Soz("[verse]\nx", "lrclib", 200.0), adaylar=lambda _q: [],
                             indir=None, surumler=lambda *_: [])
    # `/get` başka sürümü verdi (Uptown Funk 51 sn): zaman damgalı sürümlerden videonun süresine uyan alınır
    zamanli_uzun = ((10.0, "uzun bir"), (100.0, "uzun iki"))
    s3 = egitim.VeriSarki("E", "F", "funk")
    m3 = egitim.ornek_hazirla(s3, egitim.Ayar(en_uzun_sn=240), tmp_path, indir=indir,
                              lrclib=lambda *_: sozler.Soz("[Verse 1]\nkısa", "lrclib", 51.0, ((1.0, "kısa"),)),
                              adaylar=lambda _q: [kaynak.Aday("v2", "E - F (Audio)", 270.0)],
                              surumler=lambda *_: [sozler.Soz("x", "lrclib", 51.0, ((1.0, "kısa"),)),
                                                   sozler.Soz("y", "lrclib", 269.0, zamanli_uzun)])
    assert "uzun bir" in m3["lyrics"] and indirilen[-1] == "v2"


def test_kaldirilmis_video_tek_sarkiyi_dusurur_bot_engeli_hazirligi_durdurur(tmp_path):
    zamanli = ((10.0, "bir"), (100.0, "iki"))
    hata = {"A": "ERROR: [youtube] x: Video unavailable",
            "B": "ERROR: [youtube] y: Sign in to confirm you’re not a bot. Use --cookies"}

    def indir(vid, _hedef):
        raise RuntimeError(hata[vid])  # yt-dlp DownloadError gibi: OSError değil

    bag = dict(lrclib=lambda *_: sozler.Soz("[verse]\nbir", "lrclib", 200.0, zamanli), indir=indir,
               adaylar=lambda q: [kaynak.Aday(q.split()[0], f"{q} (Audio)", 200.0)])
    ornekler, dusen = egitim.veri_hazirla(tmp_path, egitim.Ayar(), [egitim.VeriSarki("A", "a", "x")],
                                          bildir=lambda *_: None, **bag)
    assert ornekler == [] and "unavailable" in dusen[0][1]
    with pytest.raises(egitim.YoutubeEngeli, match="bot"):
        egitim.veri_hazirla(tmp_path, egitim.Ayar(), [egitim.VeriSarki("A", "a", "x"), egitim.VeriSarki("B", "b", "x")],
                            bildir=lambda *_: None, **bag)


def test_cover_sanatcisi_veriye_girmez(tmp_path):
    (tmp_path / "girdi").mkdir()
    (tmp_path / "girdi" / "liste.toml").write_text('[[sarki]]\nsanatci = "Adele"\nad = "Hello"\n', encoding="utf-8")
    ornekler, dusen = egitim.veri_hazirla(tmp_path, egitim.Ayar(), [egitim.VeriSarki("ADELE", "Skyfall", "x")],
                                          bildir=lambda *_: None)
    assert ornekler == [] and "cover listesindeki" in dusen[0][1]
    assert json.loads((egitim.veri_klasoru(tmp_path) / "dataset.json").read_text(encoding="utf-8"))["samples"] == []


def test_uzak_komutlar_onay_sormaz_ve_ace_step_kokunde_kalir():
    """Side-Step onay sorusu stdin yokken "Aborted" ile bitiyordu; ACE-Step kökü dışındaki yol "Path escapes safe
    root" (ikisi de yerel denemede bulundu)."""
    ayar = egitim.Ayar()
    for k in (egitim.on_isleme_komutu(ayar), egitim.egitim_komutu(ayar)):
        assert "train.py --yes --plain fixed" in k and "--dataset-dir" in k and "--output-dir" in k
    assert egitim.UZAK.startswith(runpod.ACESTEP_DIZIN + "/")
    b = egitim.arka_plan_betigi("/root/ACE-Step-1.5", "uv run x", "egitim")
    assert b.index("nohup") < b.index("&") and b.rstrip().endswith("egitim.pid") and "egitim.kod" in b


class _EgitimPodu:
    acilan: list = []

    def __init__(self, kok, gpu="NVIDIA A40", ad="", kayit_adi="", **_k):
        self.id, self.ad, self.kayit_adi = "pod-e", ad, kayit_adi
        self.komutlar, self.gonderilen, self.alinan, self.is_json = [], {}, [], None
        _EgitimPodu.acilan.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.kapandi = True

    def komut(self, betik, zaman_asimi=120, tekrar=True):
        self.komutlar.append(betik)
        if ".kod 2>/dev/null || echo SURUYOR" in betik:
            return "0\n#\n[OK] Training complete!\n"
        if "find . -name 'adapter_config.json'" in betik:
            return ("./checkpoints/epoch_20_loss_1.1/adapter_config.json\n"
                    "./checkpoints/epoch_20_loss_1.1/adapter_model.safetensors\n"
                    "./final/adapter_config.json\n./final/adapter_model.safetensors\n")
        if "betim_sonuc.json" in betik and betik.startswith("cat "):  # biri düşer: listedeki stil kalır
            return json.dumps([{"id": "a.flac", "basari": True, "analiz": {"betim": "A punchy trap beat with 808s."}},
                               {"id": "b.flac", "basari": False, "hata": "x"}])
        if "motor_sonuc.json" in betik and betik.startswith("cat "):
            return json.dumps([{"id": i["id"], "basari": True, "cikti": f"{i['cikti_klasor']}/x.flac", "sure_sn": 140}
                               for i in json.loads(self.is_json)["isler"]])
        return ""

    def gonder(self, yerel, uzak_, zaman_asimi=900):
        self.gonderilen[str(yerel)] = uzak_
        if uzak_.endswith("motor_is.json"):
            self.is_json = Path(yerel).read_text(encoding="utf-8")

    def al(self, uzak_, yerel, zaman_asimi=900):
        self.alinan.append(uzak_)
        Path(yerel).parent.mkdir(parents=True, exist_ok=True)
        Path(yerel).write_text("{}" if str(yerel).endswith(".json") else "x", encoding="utf-8")
        return Path(yerel)

    def maliyet(self):
        return 1.25


def _sarki(c: Path, kimlik: str):
    d = durum.Durum(kimlik, "A", kimlik, asama="yuklendi", kaynak={"dosya": "kaynak.wav"},
                    soz={"dosya": "soz.txt"}, analiz={"stil": "piano ballad", "dil": "en"})
    durum.yaz(c, d)
    (c / kimlik / "kaynak.wav").write_bytes(b"RIFF")
    (c / kimlik / "soz.txt").write_text("[verse]\nsöz", encoding="utf-8")


def test_egitim_orkestrasyonu(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    monkeypatch.setattr(egitim.time, "sleep", lambda _: None)
    a = replace(ayarlar.yukle(), kok=tmp_path)
    c = tmp_path / "calisma"
    for k in ("s1", "s2"):
        _sarki(c, k)
    ayar = egitim.Ayar(deneme_sarkilari=("s1", "s2", "yok"), deneme_olcekleri=(0.0, 1.0))
    tar = tmp_path / "veri.tar"
    tar.write_bytes(b"tar")
    veri = egitim.veri_klasoru(tmp_path)
    veri.mkdir(parents=True)
    (veri / "dataset.json").write_text(json.dumps({"samples": [{"audio_path": "a.flac", "caption": "eski a"},
                                                               {"audio_path": "b.flac", "caption": "eski b"}]}),
                                       encoding="utf-8")
    kapatilan = []
    s = egitim.egit(a, ayar, tar, bildir=lambda *_: None, pod_sinifi=_EgitimPodu,
                    kur=lambda p, cm, m: runpod.ACESTEP_DIZIN, bakiye=lambda _k: 10.0,
                    kapat=lambda *x, **_k: kapatilan.append(x[2:]) or [], commit="ca1e85f")
    p = _EgitimPodu.acilan[-1]
    # eğitim pod'u üretimin artık temizliğine yakalanmaz: ayrı ad, ayrı kayıt, kendi önekiyle temizlenir
    assert p.ad == egitim.POD_AD and not p.ad.startswith("yanki-") and p.kayit_adi == egitim.POD_KAYIT
    assert kapatilan == [(egitim.POD_KAYIT, "egitim-")] and p.kapandi
    baslat = [k for k in p.komutlar if "nohup" in k]
    # önce eğitim verisi betimlenir (üretimle aynı stil dili), sonra ön işleme, eğitim, deneme
    assert "betim_is.json" in baslat[0] and ["--preprocess" in k for k in baslat[1:3]] == [True, False]
    # ön işlemeden sonra cover görevi tensörleri (üretim cover; Side-Step yalnız metinden-müzik öğretiyordu)
    assert "kapak_hazirla.py" in baslat[2] and "--epochs" in baslat[3] and "motor_isci.py" in baslat[4]
    assert p.gonderilen[str(egitim.KAPAK_BETIGI)] == f"{egitim.UZAK}/kapak_hazirla.py"
    ornekler = json.loads((veri / "dataset.json").read_text(encoding="utf-8"))["samples"]
    assert [o["caption"] for o in ornekler] == ["A punchy trap beat with 808s.", "eski b"]
    assert p.gonderilen[str(veri / "dataset.json")] == f"{egitim.UZAK}/veri/dataset.json"
    # yalnız bağdaştırıcılar iner (iyileyici durumu değil); son sürüm LoRA olur
    assert not any("training_state" in x for x in p.alinan) and s.lora == s.klasor / "final"
    assert (s.klasor / "checkpoints" / "epoch_20_loss_1.1" / "adapter_model.safetensors").exists()
    is_ = json.loads(p.is_json)
    assert is_["motor"]["lora"] == f"{egitim.UZAK}/cikti/final" and is_["motor"]["niceleme"] is None
    kapak = [i for i in is_["isler"] if i["gorev"] == "cover"]
    assert sorted((i["id"], i["lora_olcek"]) for i in kapak) == [("s1|0", 0.0), ("s1|1", 1.0), ("s2|0", 0.0),
                                                                 ("s2|1", 1.0)]
    # deneme üretim tarifiyle: stil şarkının betiminden
    assert sorted(i["id"] for i in is_["isler"] if i["gorev"] == "betimle") == ["s1|betim", "s2|betim"]
    assert all(i["stil_betimden"] == i["id"].split("|")[0] + "|betim" for i in kapak)
    assert {i["tohum"] for i in kapak} == {a.cover.tohumlar[0]} and all(i["guc"] == a.cover.guc for i in kapak)
    assert [x["dosya"].endswith(f"lora_{x['olcek']:g}.flac") for x in s.deneme] == [True] * 4
    kayit = json.loads(uzak.harcama_yolu(tmp_path).read_text(encoding="utf-8"))[-1]
    assert kayit["not"] == "egitim" and kayit["usd"] == 1.25 and uzak.bu_ay_harcama(tmp_path) == 1.25
    assert json.loads((s.klasor / "egitim.json").read_text(encoding="utf-8"))["commit"] == "ca1e85f"
    assert "lora_0" in egitim.rapor(s, 48, 2) or "lora_0.flac" in egitim.rapor(s, 48, 2)


def test_egitim_onceki_bagdastiricidan_devam_eder(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    monkeypatch.setattr(egitim.time, "sleep", lambda _: None)
    a = replace(ayarlar.yukle(), kok=tmp_path)
    tar = tmp_path / "veri.tar"
    tar.write_bytes(b"tar")
    ayar = egitim.Ayar(betim=False, kapak=False, devam="lora/ep20")
    with pytest.raises(ValueError, match="devam"):  # bağdaştırıcı yoksa pod açılmaz
        egitim.egit(a, ayar, tar, bildir=lambda *_: None, pod_sinifi=pytest.fail)
    for f in egitim.DEVAM_DOSYALARI:
        (tmp_path / "lora" / "ep20").mkdir(parents=True, exist_ok=True)
        (tmp_path / "lora" / "ep20" / f).write_text("x", encoding="utf-8")
    egitim.egit(a, ayar, tar, bildir=lambda *_: None, pod_sinifi=_EgitimPodu,
                kur=lambda p, cm, m: runpod.ACESTEP_DIZIN, bakiye=lambda _k: 10.0, kapat=lambda *x, **_k: [],
                commit="ca1e85f")
    p = _EgitimPodu.acilan[-1]
    assert p.gonderilen[str(tmp_path / "lora" / "ep20" / "adapter_model.safetensors")] == \
        f"{egitim.UZAK}/devam/adapter_model.safetensors"
    yama = next(i for i, k in enumerate(p.komutlar) if "devam_yamasi.py" in k)
    egit = next(i for i, k in enumerate(p.komutlar) if "--epochs" in k)
    assert yama < egit and f"--resume-from {egitim.UZAK}/devam " in p.komutlar[egit]
    assert "--resume-from" not in egitim.egitim_komutu(egitim.Ayar())


def test_devam_yamasi_side_step_yuklemesini_degistirir(tmp_path):
    from yanki import devam_yamasi

    yol = tmp_path / devam_yamasi.DOSYA
    yol.parent.mkdir(parents=True)
    yol.write_text("def f():\n        if x:\n" + devam_yamasi.ESKI + "            y = 1\n", encoding="utf-8")
    assert devam_yamasi.yamala(tmp_path) == "yama tamam" and devam_yamasi.yamala(tmp_path) == "zaten yamalı"
    metin = yol.read_text(encoding="utf-8")
    assert "set_peft_model_state_dict" in metin and "strict=False" not in metin
    compile(metin, str(yol), "exec")
    yol.write_text("degisti\n", encoding="utf-8")  # Side-Step değişirse sessiz geçmez
    with pytest.raises(SystemExit, match="bulunamadı"):
        devam_yamasi.yamala(tmp_path)


def test_egitim_duserse_gunluk_iner_maliyet_yazilir(tmp_path, monkeypatch):
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    monkeypatch.setattr(egitim.time, "sleep", lambda _: None)

    class Dusen(_EgitimPodu):
        def komut(self, betik, zaman_asimi=120, tekrar=True):
            if "egitim.kod 2>/dev/null" in betik:
                return "1\n#\nCUDA out of memory\n"
            return super().komut(betik, zaman_asimi, tekrar)

    a = replace(ayarlar.yukle(), kok=tmp_path)
    tar = tmp_path / "veri.tar"
    tar.write_bytes(b"tar")
    with pytest.raises(runpod.RunPodHatasi, match="egitim 1 koduyla"):
        egitim.egit(a, egitim.Ayar(betim=False), tar, bildir=lambda *_: None, pod_sinifi=Dusen,
                    kur=lambda p, cm, m: runpod.ACESTEP_DIZIN, bakiye=lambda _k: 10.0, kapat=lambda *x, **_k: [],
                    commit="x")
    p = _EgitimPodu.acilan[-1]
    assert p.kapandi and any(x.endswith("egitim.log") for x in p.alinan)
    assert "egitim 1" in json.loads(uzak.harcama_yolu(tmp_path).read_text(encoding="utf-8"))[-1]["hata"]


def test_uretim_kosusu_egitim_podunu_artik_saymaz(tmp_path, monkeypatch):
    silinen = []

    def gql(_k, sorgu, degisken=None, deneme=3):
        if "pods" in sorgu:
            return {"myself": {"pods": [{"id": "e1", "name": egitim.POD_AD}, {"id": "m1", "name": "yanki-motor",
                                                                       "runtime": {"uptimeInSeconds": 1200}}]}}
        silinen.append(degisken["id"])
        return {}

    monkeypatch.setattr(runpod, "gql", gql)
    (tmp_path / egitim.POD_KAYIT).write_text("e1", encoding="utf-8")
    assert runpod.kapat_artiklari("k", tmp_path) == ["m1"] and silinen == ["m1"]
    assert runpod.kapat_artiklari("k", tmp_path, egitim.POD_KAYIT, "egitim-") == ["e1"]


def test_lora_uretime_baglanir_yalniz_nicelemesiz_motorda(tmp_path):
    lora = tmp_path / "lora"
    lora.mkdir()
    (lora / "adapter_config.json").write_text("{}", encoding="utf-8")
    a = ayarlar.yukle()
    acik = replace(a, motor=replace(a.motor, lora=lora, lora_olcek=0.7, niceleme=None))
    assert motor.lora_ayari(acik) == {"lora": str(lora), "lora_olcek": 0.7}
    assert motor.lora_ayari(acik, model="acestep-v15-turbo") == {}  # analiz modeline uygulanmaz
    assert motor.lora_ayari(replace(acik, motor=replace(acik.motor, niceleme="int8_weight_only"))) == {}
    toml = re.sub(r"(?m)^lora = .*\n", "", (KOK / "config" / "motor.toml").read_text(encoding="utf-8")).replace(
        "[motor]\n", f'[motor]\nlora = "{tmp_path.as_posix()}/yok"\n', 1)
    (tmp_path / "motor.toml").write_text(toml, encoding="utf-8")
    eksik = ayarlar.yukle(tmp_path / "motor.toml")  # eksik klasör hattın geri kalanını durdurmaz
    with pytest.raises(ValueError, match="LoRA klasörü değil"):
        GERCEK_LORA_DENETLE(eksik)


def test_onbellekteki_eski_bicimli_soz_yenilenir(tmp_path):
    # ilk eğitim tek blok [verse] sözlerle yapılmıştı; ses yeniden inmez, söz bölüm yapısıyla kurulur
    zamanli = tuple((float(t), m) for t, m in zip((5, 10, 50, 55, 100, 105), "a1 a2 n1 n2 b1 b2".split(), strict=True))
    s = egitim.VeriSarki("A", "B", "piano ballad")
    (tmp_path / f"{s.kimlik}.flac").write_bytes(b"fLaC")
    (tmp_path / f"{s.kimlik}.json").write_text(json.dumps({"audio_path": "x", "caption": "piano ballad",
                                                           "lyrics": "[verse]\na1", "duration": 120.0}),
                                               encoding="utf-8")
    yapili = sozler.yapi.metin(sozler.yapi.coz(zamanli, 120.0, "B"))  # LRCLIB sözü zaman damgasından yapılı gelir
    m = egitim.ornek_hazirla(s, egitim.Ayar(), tmp_path, adaylar=None, indir=None,
                             lrclib=lambda *_: sozler.Soz(yapili, "lrclib", 120.0, zamanli))
    assert m["soz_bicimi"] == egitim.SOZ_BICIMI and m["lyrics"].startswith("[Intro]\n\n[Verse 1]\na1")
    again = egitim.ornek_hazirla(s, egitim.Ayar(), tmp_path, lrclib=None, adaylar=None, indir=None)
    assert again["lyrics"] == m["lyrics"]  # yenilenmiş söz bir daha sorulmaz


def test_ornek_dili_sesten_belirsizse_sozden(tmp_path):
    # önce hep "en" yazılıyordu: çok türlü veride İspanyolca şarkı yanlış etiketlenirdi
    ses = tmp_path / "x.flac"
    assert egitim.ornek_dili(ses, "x", lambda _: ("es", 0.97)) == "es"
    assert egitim.ornek_dili(ses, "Des-pa-cito quiero respirar tu cuello despacito", lambda _: ("es", 0.3)) == "es"
    ingilizce = "I heard that you're settled down and you are married now"
    assert egitim.ornek_dili(ses, ingilizce, lambda _: ("es", 0.3)) == "en"

    def bozuk(_):
        raise RuntimeError("ses okunamadı")

    assert egitim.ornek_dili(ses, "x", bozuk) == "en"


def test_betimi_olan_ornek_yeniden_betimlenmez(tmp_path):
    # her eğitimde 95 şarkıyı yeniden dinlemek boşa para: betim örnek kaydında saklanır
    from yanki.motor_isci import betim_stili

    veri = egitim.veri_klasoru(tmp_path)
    veri.mkdir(parents=True)
    (veri / "dataset.json").write_text(json.dumps({"samples": [{"audio_path": "a.flac", "caption": "eski"}]}),
                                       encoding="utf-8")
    betim = "A punchy trap beat with deep 808s."
    (veri / "a.json").write_text(json.dumps({"audio_path": "a.flac", "betim": betim}), encoding="utf-8")

    class Pod:
        def komut(self, *a, **k):
            raise AssertionError("betimleyici çalıştırılmamalı")

        def gonder(self, yerel, uzak_, zaman_asimi=900):
            pass

    yerel = tmp_path / "lora"
    yerel.mkdir()
    egitim.veri_betimle(None, egitim.Ayar(), Pod(), "/root/x", tmp_path, yerel, 60, bildir=lambda *_: None)
    caption = json.loads((veri / "dataset.json").read_text(encoding="utf-8"))["samples"][0]["caption"]
    assert caption == betim_stili(betim)


def test_ara_kayit_denemesi_bagdastiricilari_gruplar():
    # dördüncü eğitim: son bağdaştırıcı ve 20. epoch aynı işçide; işçi her bağdaştırıcıyı bir kez taksın
    dosyalar = ["./final/adapter_config.json", "./checkpoints/epoch_10_loss_0.74/adapter_config.json",
                "./checkpoints/epoch_20_loss_0.71/adapter_config.json"]
    ara = egitim.ara_kayitlar(dosyalar, (20,))
    assert ara == {20: f"{egitim.UZAK}/cikti/checkpoints/epoch_20_loss_0.71"}


def test_deneme_isleri_ara_kayitla(tmp_path):
    from dataclasses import replace

    a = ayarlar.yukle()
    c = tmp_path / "calisma"
    for kimlik in ("a-b", "c-d"):
        d = durum.Durum(kimlik, "A", "B", kaynak={"dosya": "kaynak.wav"}, soz={"dosya": "soz.txt"},
                        analiz={"stil": "pop", "dil": "en"})
        durum.yaz(c, d)
        (c / kimlik / "soz.txt").write_text("la", encoding="utf-8")
    ayar = replace(egitim.Ayar(), deneme_sarkilari=("a-b", "c-d"), deneme_olcekleri=(1.0,))
    isler = egitim.deneme_isleri(a, c, ayar, str, {20: "/ep20"}, "/final")
    assert [x[2] for x in isler] == [None, None, 1.0, 1.0, "ep20", "ep20"]  # betimler, son, ara kayıt
    assert [x[0].lora for x in isler[2:]] == ["/final", "/final", "/ep20", "/ep20"]
    # ara kayıt yokken işe özel LoRA verilmez (motor ayarındaki son bağdaştırıcı)
    assert all(x[0].lora is None for x in egitim.deneme_isleri(a, c, ayar, str)[2:])


def test_deneme_uretim_tarifiyle_iki_tohum_ve_uretim_kolu(tmp_path):
    """S34 öncesi (2026-10-18): deneme CFG'yi (cover.ek) geçmiyordu; üretimdeki model aynı pod'da aynı tarifle, kollar
    iki tohumla."""
    from dataclasses import replace

    a = ayarlar.yukle()
    c = tmp_path / "calisma"
    d = durum.Durum("a-b", "A", "B", kaynak={"dosya": "kaynak.wav"}, soz={"dosya": "soz.txt"},
                    analiz={"stil": "pop", "dil": "en"})
    durum.yaz(c, d)
    (c / "a-b" / "soz.txt").write_text("la", encoding="utf-8")
    ayar = replace(egitim.Ayar(), deneme_sarkilari=("a-b",), deneme_olcekleri=(1.0,), deneme_tohum_sayisi=2,
                   betim=False)
    isler = egitim.deneme_isleri(a, c, ayar, str, None, "/final", "/uretim/ep20")
    assert {(x[2], x[0].tohum) for x in isler} == {(kol, t) for kol in (1.0, "uretim") for t in a.cover.tohumlar[:2]}
    assert all(x[0].ek == dict(a.cover.ek) and x[0].ek for x in isler)  # CFG 10 üretimdeki gibi
    assert {x[0].lora for x in isler} == {"/final", "/uretim/ep20"}  # işçi bağdaştırıcı değiştirir: ikisi de açık
    assert len({x[0].id for x in isler}) == 4 and [x[0].lora for x in isler][:2] == ["/final", "/final"]


def test_kulak_seti_tohum_basina_set_ve_oda_bulur(tmp_path):
    from yanki import kulak

    c = tmp_path / "calisma"
    dinleme = c / "dinleme" / "lora" / "20261020-0100"
    deneme = []
    for kimlik in ("a-b", "c-d"):
        for kol in ("1", "uretim"):
            for t in (42, 7):
                yol = dinleme / kimlik / f"lora_{kol}_t{t}.flac"
                yol.parent.mkdir(parents=True, exist_ok=True)
                yol.write_bytes(b"x")
                deneme.append({"kimlik": kimlik, "kol": kol, "tohum": t, "basari": True, "dosya": str(yol)})
    deneme.append({"kimlik": "e-f", "kol": "1", "tohum": 42, "basari": False})  # tek kollu şarkı sete girmez
    sonuc = egitim.Sonuc(c / "egitim" / "lora" / "20261020-0100", dinleme, deneme=deneme)
    setler = egitim.kulak_seti(sonuc, egitim.Ayar(deneme_tohum_sayisi=2))
    assert [s["kimlik"] for s in setler] == ["egitim-20261020-0100-1", "egitim-20261020-0100-2"]
    assert setler[0]["sarkilar"] == ["a-b", "c-d"] and list(setler[0]["kollar"]) == ["uretim", "1"]
    bulunan = kulak.setler(c)
    s = bulunan["egitim-20261020-0100-2"]
    assert kulak.dosya_yolu(c, s, "a-b", "uretim") == dinleme / "a-b" / "lora_uretim_t42.flac"
    assert "egitim-20261020-0100-1" in {x["kimlik"] for x in kulak.gorunum(c)}


def test_ara_kayit_bagdastirici_adi_noktasiz():
    # dördüncü eğitim: Side-Step'in klasör adı (epoch_20_loss_0.7381) PEFT'e modül adı olarak gitti, nokta reddedildi
    from yanki.motor_isci import lora_adi

    assert lora_adi("/root/x/cikti/checkpoints/epoch_20_loss_0.7381") == "epoch_20_loss_0_7381"
    assert lora_adi("/root/x/cikti/final/") == "final"
    assert "." not in lora_adi("C:/a/epoch_10_loss_0.74")


def test_deneme_yeniden_yerel_kayitlari_bulur_ve_birlestirir(tmp_path):
    yerel = tmp_path / "calisma" / "egitim" / "lora" / "20261012-1702"
    for ad in ("epoch_10_loss_0.74", "epoch_20_loss_0.73", "epoch_30_loss_0.73"):
        (yerel / "checkpoints" / ad).mkdir(parents=True)
        (yerel / "checkpoints" / ad / "adapter_config.json").write_text("{}", encoding="utf-8")
    (yerel / "checkpoints" / "epoch_40_loss_0.7").mkdir()  # yarım inmiş: adapter_config yok
    assert egitim.yerel_ara_kayitlar(yerel, (20, 40)) == {20: yerel / "checkpoints" / "epoch_20_loss_0.73"}

    eski = [{"kimlik": "a", "kol": "1", "basari": True}, {"kimlik": "a", "kol": "ep20", "basari": False}]
    (yerel / "egitim.json").write_text(json.dumps({"usd": 4.5, "deneme": eski, "ornek": 123}), encoding="utf-8")
    s = egitim.deneme_birlestir(yerel, [{"kimlik": "a", "kol": "ep20", "basari": True}], 0.8)
    assert [(x["kol"], x["basari"]) for x in s.deneme] == [("1", True), ("ep20", True)]  # düşen kol yenisiyle
    assert s.usd == 5.3 and s.dinleme == tmp_path / "calisma" / "dinleme" / "lora" / "20261012-1702"
    assert json.loads((yerel / "egitim.json").read_text(encoding="utf-8"))["ornek"] == 123


def test_hedef_moduller_bossa_side_step_varsayilani_doluysa_komuta_gider():
    assert "--target-modules" not in egitim.egitim_komutu(egitim.Ayar())
    k = egitim.egitim_komutu(egitim.Ayar(hedef_moduller=("q_proj", "gate_proj", "down_proj")))
    assert k.endswith("--gradient-checkpointing --target-modules q_proj gate_proj down_proj")


def test_artik_pod_sahibi_yasiyorsa_dokunulmaz_terk_edilmisse_silinir_ucreti_yazilir(tmp_path, monkeypatch):
    """Kilitsiz koşan deneyin/eğitimin pod'u üretim koşusunun temizliğine yakalanmaz; silinemeyip bırakılan pod (terk)
    sahibi yaşasa da silinir ve sayılmamış süresi bütçeye yazılır. Kaydı hiç olmayan yeni pod 15 dk beklenir."""
    import os

    pods = [{"id": "canli", "name": "yanki-s33", "costPerHr": 0.4, "runtime": {"uptimeInSeconds": 5000}},
            {"id": "terk", "name": "yanki-motor", "costPerHr": 0.36, "runtime": {"uptimeInSeconds": 3600}},
            {"id": "yeni", "name": "yanki-motor", "costPerHr": 0.4, "runtime": None}]
    silinen, harcanan = [], []

    def gql(_k, sorgu, degisken=None, deneme=3):
        if "pods" in sorgu:
            return {"myself": {"pods": [p for p in pods if p["id"] not in silinen]}}
        silinen.append(degisken["id"])
        return {}

    monkeypatch.setattr(runpod, "gql", gql)
    runpod.sahip_yaz(tmp_path, "canli")  # bu süreç: yaşıyor
    runpod.sahip_yaz(tmp_path, "terk", terk=True, sayilan_sn=1800)
    assert runpod.kapat_artiklari("k", tmp_path, harcama=harcanan.append, simdi=1000.0) == ["terk"]
    assert harcanan[0]["pod"] == "terk" and harcanan[0]["usd"] == 0.18  # sayılmamış yarım saat × 0,36
    assert not (tmp_path / "sahip" / "terk").exists() and (tmp_path / "sahip" / "canli").exists()
    assert runpod.kapat_artiklari("k", tmp_path, simdi=1000.0 + runpod.ARTIK_SN) == ["yeni"]
    runpod.sahip_yaz(tmp_path, "canli")
    json_ = __import__("json")
    (tmp_path / "sahip" / "canli").write_text(json_.dumps({"pid": 2**31 - 7}), encoding="utf-8")  # ölü süreç
    assert os.getpid() != 2**31 - 7
    assert runpod.kapat_artiklari("k", tmp_path, simdi=5000.0) == ["canli"]


def test_silinemeyen_pod_terk_edilir_bildirilir_maliyeti_bırakista_durur(tmp_path, monkeypatch):
    from yanki import olay

    monkeypatch.setattr(runpod, "KAPATMA_DENEME", 2)
    monkeypatch.setattr(runpod, "KAPATMA_BEKLEME_SN", 0)
    monkeypatch.setattr(runpod, "gql", lambda *_a, **_k: (_ for _ in ()).throw(runpod.RunPodHatasi("ağ yok")))
    monkeypatch.setenv("RUNPOD_API_KEY", "x")
    p = runpod.Pod(tmp_path)
    p.id, p.saatlik, p.acilis = "p1", 0.36, runpod.time.time() - 3600
    p.__exit__(None, None, None)
    sahip = runpod.sahip_oku(p.klasor, "p1")
    assert sahip["terk"] and 3590 <= sahip["sayilan_sn"] <= 3610
    assert p.maliyet() == 0.36 and p.kapanis is not None
    assert any(o["baslik"] == "kiralık GPU silinemedi" for o in olay.oku(tmp_path / "calisma"))
