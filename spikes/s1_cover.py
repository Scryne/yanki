"""S1: ACE-Step 1.5 cover görevi RTX 4060 Laptop (8 GB) üzerinde çalışıyor mu, ne kadar sürüyor?

ACE-Step venv'iyle çalışır:
  motor/ACE-Step-1.5/.venv/Scripts/python spikes/s1_cover.py <kaynak.wav> <cikti_dir> [--guc 0.7] [--soz soz.txt]
"""

import argparse
import json
import sys
import time
from pathlib import Path

MOTOR = Path(__file__).resolve().parents[1] / "motor" / "ACE-Step-1.5"
sys.path.insert(0, str(MOTOR))

import torch  # noqa: E402

from acestep.constants import TASK_INSTRUCTIONS  # noqa: E402
from acestep.handler import AceStepHandler  # noqa: E402
from acestep.inference import GenerationConfig, GenerationParams, generate_music  # noqa: E402
from acestep.llm_inference import LLMHandler  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("kaynak")
    ap.add_argument("cikti")
    ap.add_argument("--guc", type=float, default=0.7)
    ap.add_argument("--soz", default=None)
    ap.add_argument("--stil", default="acoustic soul ballad, warm male vocal, piano and strings, intimate studio recording")
    ap.add_argument("--model", default="acestep-v15-turbo")
    ap.add_argument("--adim", type=int, default=8)
    ap.add_argument("--tohum", type=int, default=42)
    ap.add_argument("--offload", action="store_true")
    ap.add_argument("--dit-offload", action="store_true", help="DiT de CPU'ya (XL, 8 GB)")
    ap.add_argument("--nicem", default=None, help="int8_weight_only | fp8_weight_only | w8a8_dynamic")
    ap.add_argument("--bpm", type=int, default=None)
    ap.add_argument("--ton", default="", help="ör. 'A major'")
    ap.add_argument("--gorev", default="cover", choices=["cover", "cover-nofsq", "lego", "text2music", "repaint"])
    ap.add_argument("--flow", default=None, help="flow-edit: 'n_min,n_max' (text2music + kaynak)")
    ap.add_argument("--kaynak-stil", default="", help="flow-edit: orijinal kaydın tanımı")
    ap.add_argument("--repaint-guc", type=float, default=0.5, help="repaint: 0 agresif, 1 muhafazakâr")
    ap.add_argument("--vae", default=None, help="official | scragvae")
    ap.add_argument("--iz", default="vocals", help="lego: üretilecek iz")
    ap.add_argument("--rehber", type=float, default=7.0, help="guidance (turbo yok sayar)")
    a = ap.parse_args()
    Path(a.cikti).mkdir(parents=True, exist_ok=True)

    t0 = time.perf_counter()
    dit = AceStepHandler()
    durum, ok = dit.initialize_service(
        project_root=str(MOTOR), config_path=a.model, device="cuda", offload_to_cpu=a.offload,
        offload_dit_to_cpu=a.dit_offload,
        quantization=a.nicem,
        vae_checkpoint=a.vae,
    )
    t_yukle = time.perf_counter() - t0
    print("init:", ok, durum[:300])
    if not ok:
        sys.exit(1)

    # lego: belge repainting_end=-1 "sona kadar" diyor ama kod end > start şartı arıyor; süreyi açıkça ver
    import soundfile as sf

    bolge = {}
    if a.gorev in ("lego", "repaint"):
        bolge = dict(repainting_start=0.0, repainting_end=float(sf.info(a.kaynak).duration), chunk_mask_mode="explicit")

    akis = {}
    if a.flow:
        n_min, n_max = (float(x) for x in a.flow.split(","))
        akis = dict(flow_edit_morph=True, flow_edit_source_caption=a.kaynak_stil, flow_edit_n_min=n_min, flow_edit_n_max=n_max)

    soz = Path(a.soz).read_text(encoding="utf-8") if a.soz else ""
    if a.flow:
        akis["flow_edit_source_lyrics"] = soz
    params = GenerationParams(
        task_type=a.gorev,
        # Python API talimatı görev türüne göre kendisi seçmiyor; varsayılan text2music talimatıdır
        instruction=TASK_INSTRUCTIONS[a.gorev].format(TRACK_NAME=a.iz.upper()),  # API de büyük harfle veriyor
        guidance_scale=a.rehber,
        # text2music kaynak sesi kullanmaz; süre kaynaktan alınır (karşılaştırma aynı uzunlukta olsun)
        src_audio=None if (a.gorev == "text2music" and not a.flow) else a.kaynak,
        duration=float(sf.info(a.kaynak).duration) if a.gorev == "text2music" else -1.0,
        repaint_strength=a.repaint_guc,
        **akis,
        thinking=False,
        caption=a.stil,
        lyrics=soz,
        vocal_language="en",
        bpm=a.bpm,
        keyscale=a.ton,
        audio_cover_strength=a.guc,
        inference_steps=a.adim,
        seed=a.tohum,
        **bolge,
    )
    config = GenerationConfig(batch_size=1, use_random_seed=False, seeds=[a.tohum], audio_format="flac")

    torch.cuda.reset_peak_memory_stats()
    t1 = time.perf_counter()
    sonuc = generate_music(dit, LLMHandler(), params, config, save_dir=a.cikti)
    t_uret = time.perf_counter() - t1

    rapor = {
        "basari": sonuc.success,
        "hata": sonuc.error,
        "model": a.model,
        "gorev": a.gorev,
        "guc": a.guc,
        "soz_var": bool(soz),
        "adim": a.adim,
        "yukleme_sn": round(t_yukle, 1),
        "uretim_sn": round(t_uret, 1),
        "vram_tepe_gb": round(torch.cuda.max_memory_allocated() / 1e9, 2),
        "dosyalar": [x.get("path") for x in (sonuc.audios or [])],
    }
    print(json.dumps(rapor, ensure_ascii=False, indent=2))
    Path(a.cikti, "rapor.json").write_text(json.dumps(rapor, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
