"""ACE-Step işçisi: motorun kendi venv'iyle çalışır, `yanki` paketinden hiçbir şey import etmez.

  motor/ACE-Step-1.5/.venv/Scripts/python.exe yanki/motor_isci.py <is.json> <sonuc.json>

is.json:
  {"motor": {"klasor": ..., "model": ..., "niceleme": "int8_weight_only" | null, "cpu_offload": true,
              "lm_model": ..., "lm_backend": "pt"},
   "isler": [{"id", "gorev": "cover" | "repaint" | "anla", "kaynak", "cikti_klasor", "stil", "soz", "dil", "bpm", "ton",
              "guc", "adim", "tohum", "bolge": [bas, son] | null}]}

Model bir kez yüklenir, işler sırayla yapılır; her işin sonucu (başarı, hata, süre, VRAM tepe, çıktı dosyası)
sonuc.json'a yazılır. Bir işin hatası diğerlerini durdurmaz.

ACE-Step Python API tuzakları (docs/arastirma/01) burada düzeltilir:
- `instruction` görev türüne göre seçilmiyor (varsayılan text2music talimatı gider) → TASK_INSTRUCTIONS[gorev]
- repaint'te `repainting_end=-1` kodda "sona kadar" sayılmıyor (end > start şartı) → aralık açıkça verilir
- `thinking` varsayılan True; cover/repaint LM kullanmaz, LM yüklenmez → False

"anla": kaynak ses anlamsal kodlara çevrilir, 5Hz LM stil tanımı/BPM/ton/dil çıkarır
(REST full_analysis_only ile aynı yol).
LM yalnız ilk "anla" işinde, bir kez yüklenir.
"""

import json
import sys
import time
import traceback
from pathlib import Path


def main() -> int:
    is_yolu, sonuc_yolu = Path(sys.argv[1]), Path(sys.argv[2])
    is_ = json.loads(is_yolu.read_text(encoding="utf-8"))
    m = is_["motor"]
    klasor = Path(m["klasor"]).resolve()
    sys.path.insert(0, str(klasor))

    import soundfile as sf
    import torch
    from acestep.constants import TASK_INSTRUCTIONS
    from acestep.handler import AceStepHandler
    from acestep.inference import GenerationConfig, GenerationParams, generate_music
    from acestep.llm_inference import LLMHandler

    sonuclar = []

    def yaz():
        sonuc_yolu.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=2), encoding="utf-8")

    t0 = time.perf_counter()
    dit = AceStepHandler()
    durum, ok = dit.initialize_service(
        project_root=str(klasor),
        config_path=m["model"],
        device="cuda",
        offload_to_cpu=bool(m.get("cpu_offload", True)),
        quantization=m.get("niceleme") or None,
    )
    yukleme_sn = round(time.perf_counter() - t0, 1)
    if not ok:
        sonuclar.append({"id": None, "basari": False, "hata": f"model yüklenemedi: {durum[:500]}"})
        yaz()
        return 2

    llm = LLMHandler()  # cover/repaint LM'yi atlar; yalnız "anla" için yüklenir
    for i in is_["isler"]:
        kayit = {"id": i["id"], "basari": False, "hata": None, "yukleme_sn": yukleme_sn}
        try:
            gorev = i["gorev"]
            if gorev == "anla":
                if not llm.llm_initialized:
                    lm_durum, lm_ok = llm.initialize(
                        checkpoint_dir=str(klasor / "checkpoints"), lm_model_path=m["lm_model"],
                        backend=m.get("lm_backend", "pt"), device="cuda", offload_to_cpu=True,
                    )
                    if not lm_ok:
                        raise RuntimeError(f"LM yüklenemedi: {lm_durum[:300]}")
                t1 = time.perf_counter()
                kodlar = dit.convert_src_audio_to_codes(i["kaynak"])
                if not kodlar or kodlar.startswith("❌"):
                    raise RuntimeError(f"ses kodlara çevrilemedi: {kodlar[:200]}")
                meta, lm_durum = llm.understand_audio_from_codes(audio_codes=kodlar, temperature=0.3)
                if not meta:
                    raise RuntimeError(f"LM anlayamadı: {lm_durum[:300]}")
                kayit["sure_sn"] = round(time.perf_counter() - t1, 1)
                kayit["analiz"] = {k: meta.get(k) for k in
                                   ("caption", "bpm", "keyscale", "timesignature", "language", "genres", "duration")}
                kayit["basari"] = True
                sonuclar.append(kayit)
                yaz()
                continue
            if gorev not in ("cover", "repaint"):
                raise ValueError(f"desteklenmeyen görev: {gorev}")
            bolge = {}
            if gorev == "repaint":
                bas, son = i["bolge"]
                bolge = dict(repainting_start=float(bas), repainting_end=float(son), chunk_mask_mode="explicit")
            params = GenerationParams(
                task_type=gorev,
                instruction=TASK_INSTRUCTIONS[gorev],
                src_audio=i["kaynak"],
                caption=i["stil"],
                lyrics=i["soz"],
                vocal_language=i.get("dil", "en"),
                bpm=i.get("bpm"),
                keyscale=i.get("ton") or "",
                audio_cover_strength=float(i.get("guc", 1.0)),
                inference_steps=int(i["adim"]),
                seed=int(i["tohum"]),
                thinking=False,
                **bolge,
            )
            config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[int(i["tohum"])], audio_format="flac")
            Path(i["cikti_klasor"]).mkdir(parents=True, exist_ok=True)
            torch.cuda.reset_peak_memory_stats()
            t1 = time.perf_counter()
            sonuc = generate_music(dit, llm, params, config, save_dir=i["cikti_klasor"])
            kayit["sure_sn"] = round(time.perf_counter() - t1, 1)
            kayit["vram_tepe_gb"] = round(torch.cuda.max_memory_allocated() / 1e9, 2)
            if not sonuc.success or not sonuc.audios:
                raise RuntimeError(sonuc.error or "çıktı yok")
            cikti = sonuc.audios[0]["path"]
            kayit.update(basari=True, cikti=str(Path(cikti).resolve()), cikti_sure_sn=round(sf.info(cikti).duration, 2))
        except Exception as e:  # bir işin hatası diğerlerini durdurmaz
            kayit["hata"] = f"{type(e).__name__}: {e}"
            kayit["iz"] = traceback.format_exc()[-2000:]
        sonuclar.append(kayit)
        yaz()
    return 0 if all(k["basari"] for k in sonuclar) else 1


if __name__ == "__main__":
    raise SystemExit(main())
