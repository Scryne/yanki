"""S19: nicelemesiz (bf16) XL-SFT kiralık GPU'da, INT8/FP8 ile aynı kesit ve tohumlarla; tam şarkı tek parça.

Soru (Faz 8, S18 yarım kaldı): kalan nefes/mırıldanma kusurunun şüphelisi INT8 niceleme. 8 GB'ta bf16 adım başı 72–150
sn ve VAE çözmede takıldı; RunPod A40 (48 GB, `yanki/runpod.py`) ile ölçülür. Kollar:
- `bf16_t42`, `bf16_t7`: S18 kesiti (Adele 0:40–1:25, temiz söz, tarif, 100 adım, güç 0,7); dinleme odasında
  `0_int8_t42`/`0_int8_t7`/`fp8_*` ile yan yana.
- `tam_bf16_t7`: Someone Like You'nun tamamı tek parça (8 GB'ta parçalı üretim zorunluydu); yüklenen sürüm aday 4
  (INT8, parçalı, tohum 7) ile karşılaştırılır.
Çıktılar `calisma/dinleme/s19/`, ölçümler `calisma/_spike/s19/ozet.json`. Pod her durumda silinir.

  uv run python spikes/s19_uzak_bf16.py
"""

import json
import shutil
import subprocess
import time
from pathlib import Path

from yanki import ayarlar, durum, kapilar, runpod, sozler

KIMLIK = "adele-someone-like-you"
BAS, SON = 40.0, 85.0
COMMIT = "ca1e85f"  # yereldeki motor/ACE-Step-1.5 ile aynı


def mp3(girdi: Path, hedef: Path) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(girdi), "-b:a", "192k", str(hedef)], check=True)


def main() -> None:
    a = ayarlar.yukle()
    calisma = a.kok / "calisma"
    d = durum.oku(calisma, KIMLIK)
    k = durum.klasor(calisma, KIMLIK)
    cikti, dinleme = calisma / "_spike" / "s19", calisma / "dinleme" / "s19"
    cikti.mkdir(parents=True, exist_ok=True)
    dinleme.mkdir(parents=True, exist_ok=True)
    kesit = calisma / "_spike" / "s18" / "kaynak_kesit.wav"
    soz_kesit = sozler.aralik_sozu(json.loads((k / "soz_zaman.json").read_text(encoding="utf-8")), BAS, SON)
    soz_tam = (k / "soz.txt").read_text(encoding="utf-8")
    # karşılaştırma tabanları dinleme klasörüne
    for kaynak, ad in ((calisma / "dinleme" / "s18" / "0_int8_t42.mp3", "1_int8_t42.mp3"),
                       (calisma / "dinleme" / "s18" / "0_int8_t7.mp3", "1_int8_t7.mp3"),
                       (calisma / "dinleme" / "s18" / "fp8_t42.mp3", "2_fp8_t42.mp3"),
                       (calisma / "dinleme" / "s18" / "fp8_t7.mp3", "2_fp8_t7.mp3"),
                       (calisma / "dinleme" / "s18" / "orijinal_kesit.mp3", "0_orijinal_kesit.mp3")):
        shutil.copy(kaynak, dinleme / ad)
    secilen = next(x for x in d.adaylar if x.no == d.secilen)
    mp3(k / secilen.dosya, dinleme / f"tam_1_int8_parcali_aday{secilen.no}_t{secilen.tohum}.mp3")

    ortak = {"gorev": "cover", "stil": d.analiz["stil"], "dil": d.analiz.get("dil", "en"), "bpm": d.analiz.get("bpm"),
             "ton": d.analiz.get("ton") or "", "guc": a.cover.guc, "adim": a.cover.adim, "bolge": None,
             "referans": None, "ek": {}}
    isler = [{**ortak, "id": "bf16_t42", "kaynak": "/root/is/kesit.wav", "cikti_klasor": "/root/is/bf16_t42",
              "soz": soz_kesit, "tohum": 42},
             {**ortak, "id": "bf16_t7", "kaynak": "/root/is/kesit.wav", "cikti_klasor": "/root/is/bf16_t7",
              "soz": soz_kesit, "tohum": 7},
             {**ortak, "id": "tam_bf16_t7", "kaynak": "/root/is/tam.wav", "cikti_klasor": "/root/is/tam_bf16_t7",
              "soz": soz_tam, "tohum": 7}]
    is_json = cikti / "motor_is.json"
    ozet: dict = {"baslangic": time.strftime("%Y-%m-%dT%H:%M:%S")}

    api = runpod.anahtar(a.kok)
    if artik := runpod.kapat_artiklari(api, a.kok / "calisma" / ".runpod"):
        print("önceki koşudan kalan pod silindi:", artik)
    print(f"bakiye: {runpod.bakiye(api):.2f} $", flush=True)
    with runpod.Pod(a.kok, ad="yanki-s19") as p:
        print(f"pod {p.id} açık ({p.saatlik} $/sa), SSH {p.ip}:{p.port}", flush=True)
        t = time.time()
        hedef = runpod.acestep_kur(p, COMMIT)
        ozet["kurulum_sn"] = round(time.time() - t)
        ozet["checkpoints"] = p.komut(f"du -sh {hedef}/checkpoints/* 2>/dev/null; nvidia-smi --query-gpu=name,"
                                      "memory.total,driver_version --format=csv,noheader")
        print(f"kurulum {ozet['kurulum_sn']} sn\n{ozet['checkpoints']}", flush=True)
        is_json.write_text(json.dumps({"motor": {
            "klasor": hedef, "model": a.motor.model, "niceleme": None, "cpu_offload": False, "dit_offload": False,
            "lm_model": a.motor.lm_model, "lm_backend": a.motor.lm_backend}, "isler": isler},
            ensure_ascii=False, indent=1), encoding="utf-8")
        p.komut("mkdir -p /root/is")
        for yerel, uzak in ((kesit, "/root/is/kesit.wav"), (k / d.kaynak["dosya"], "/root/is/tam.wav"),
                            (a.kok / "yanki" / "motor_isci.py", "/root/is/motor_isci.py"),
                            (is_json, "/root/is/motor_is.json")):
            p.gonder(yerel, uzak)
        p.komut(f"cd {hedef} && export PATH=$HOME/.local/bin:$PATH ACESTEP_GENERATION_TIMEOUT=3600 PYTHONUTF8=1 && "
                "nohup uv run python /root/is/motor_isci.py /root/is/motor_is.json /root/is/motor_sonuc.json "
                "> /root/is/motor.log 2>&1 & echo $! > /root/is/motor.pid")
        t = time.time()
        while time.time() - t < 3 * 3600:  # işçi bitince sonuç dosyasında 3 iş olur ya da süreç ölür
            time.sleep(30)
            # sonuç dosyası satır sonuyla bitmiyor: durum ayrı bir ayraçtan sonra (önce "]SURUYOR" yapışıyordu). Süreç
            # pid dosyasından: `pgrep -f motor_isci.py` kendi `bash -lc` komut satırını eşleştirip hep "sürüyor" dedi
            durum_ = p.komut("cat /root/is/motor_sonuc.json 2>/dev/null || echo '[]'; echo; echo '#DURUM#'; "
                             "kill -0 $(cat /root/is/motor.pid) 2>/dev/null && echo SURUYOR || echo BITTI")
            govde, hal = durum_.split("#DURUM#")
            try:
                sonuc = json.loads(govde.strip() or "[]")
            except ValueError:  # işçi o an yazıyor
                continue
            hal = hal.strip()
            hatali = [r["id"] for r in sonuc if not r.get("basari")]
            print(f"  {round(time.time() - t)} sn: {len(sonuc)}/3 iş, {hal}"
                  + (f", hatalı {hatali}" if hatali else ""), flush=True)
            if hal == "BITTI":
                break
        ozet["uretim_sn"] = round(time.time() - t)
        p.al("/root/is/motor.log", cikti / "motor.log")
        for r in sonuc:
            ozet[r["id"]] = {x: r.get(x) for x in ("basari", "hata", "sure_sn", "vram_tepe_gb", "yukleme_sn")}
            if r.get("basari"):
                yerel = p.al(r["cikti"], cikti / f"{r['id']}.flac")
                ozet[r["id"]]["yerel"] = str(yerel)
        ozet["maliyet_usd"] = p.maliyet()
    print(f"pod silindi; maliyet ~{ozet['maliyet_usd']} $, kalan bakiye {runpod.bakiye(api):.2f} $", flush=True)

    for r_id, kaynak_ses, soz in (("bf16_t42", kesit, soz_kesit), ("bf16_t7", kesit, soz_kesit),
                                  ("tam_bf16_t7", k / d.kaynak["dosya"], soz_tam)):
        o = ozet.get(r_id) or {}
        if not o.get("yerel"):
            continue
        kp = kapilar.degerlendir(Path(o["yerel"]), kaynak_ses, soz, a.fpcalc)
        o["kapilar"] = {n: v["deger"] for n, v in kp.items()}
        o["gecti"] = kapilar.hepsi_gecti(kp)
        on = "tam_2_bf16_tekparca_t7" if r_id.startswith("tam") else f"3_{r_id}"
        mp3(Path(o["yerel"]), dinleme / f"{on}.mp3")
        print(r_id, json.dumps(o, ensure_ascii=False), flush=True)
    (cikti / "ozet.json").write_text(json.dumps(ozet, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
