"""ACE-Step işçisi: motorun kendi venv'iyle çalışır, `yanki` paketinden hiçbir şey import etmez.

  motor/ACE-Step-1.5/.venv/Scripts/python.exe yanki/motor_isci.py <is.json> <sonuc.json>

is.json:
  {"motor": {"klasor": ..., "model": ..., "niceleme": "int8_weight_only" | null, "cpu_offload": true,
              "lm_model": ..., "lm_backend": "pt", "lora": yol | null, "lora_olcek": 1.0},
   "isler": [{"id", "gorev": "cover" | "repaint" | "anla" | "betimle", "kaynak", "cikti_klasor", "stil",
              "stil_betimden": betimle işinin id'si | null, "soz", "dil", "bpm", "ton",
              "guc", "adim", "tohum", "bolge": [bas, son] | null, "referans": yol | null,
              "lora_olcek": 0–1 | null (işe özel; karşılaştırmalı dinleme), "ek": {GenerationParams alanı: değer}}]}

Model bir kez yüklenir, işler sırayla yapılır; her işin sonucu (başarı, hata, süre, VRAM tepe, çıktı dosyası)
sonuc.json'a yazılır. Bir işin hatası diğerlerini durdurmaz.

ACE-Step Python API tuzakları (docs/arastirma/01) burada düzeltilir:
- `instruction` görev türüne göre seçilmiyor (varsayılan text2music talimatı gider) → TASK_INSTRUCTIONS[gorev]
- repaint'te `repainting_end=-1` kodda "sona kadar" sayılmıyor (end > start şartı) → aralık açıkça verilir
- `thinking` varsayılan True; cover/repaint LM kullanmaz, LM yüklenmez → False

"anla": kaynak ses anlamsal kodlara çevrilir, 5Hz LM stil tanımı/BPM/ton/dil çıkarır
(REST full_analysis_only ile aynı yol).
LM yalnız ilk "anla" işinde, bir kez yüklenir.

"betimle": ACE-Step'in eğitim verisini etiketlediği müzik betimleyicisi (`ACE-Step/acestep-captioner`, Qwen2.5-Omni
tabanlı 11B, bf16 ~22 GB) kaynak sesi dinleyip tür, enstrümanlar, ritim, vokal, yapı ve tını betimi yazar. Model
ilk "betimle" işinde indirilip yüklenir, betimle işleri bitince bellekten atılır. Cover/repaint işi
`"stil_betimden": <betimle işinin id'si>` taşırsa stil o betimden kurulur (`betim_stili`): aynı pod'da önce dinlenir,
sonra üretilir. DiT yalnız cover/repaint/anla işi varsa yüklenir.
"""

import json
import re
import sys
import time
import traceback
from pathlib import Path

BETIMLEYICI = "ACE-Step/acestep-captioner"
BETIM_ISTEMI = "*Task* Describe this audio in detail\n"
BETIM_ORNEKLEME = 16000
BETIM_EN_UZUN_SN = 300  # betimleyicinin ses penceresi (preprocessor_config: chunk_length 300)
# DiT metin kodlayıcısı talimat + stil + üst veriyi 256 jetonda keser (acestep/core/generation/handler/
# conditioning_text.py); üst veri (BPM, ton, süre) stilden sonra geldiği için uzun stil onu sessizce düşürür.
# Talimat ve üst veri ~70 jeton → stil en çok ~170 jeton; İngilizcede kelime başı ~1,3 jeton.
STIL_EN_COK_KELIME = 120


def betim_stili(betim: str, en_cok: int = STIL_EN_COK_KELIME) -> str:
    """Betimleyici metni → cover stili: tek paragraf, en çok `en_cok` kelime, cümle sınırında kesilir."""
    metin = " ".join(betim.split())
    if len(metin.split()) <= en_cok:
        return metin
    cumleler, secilen = re.split(r"(?<=[.!?])\s+", metin), []
    for c in cumleler:
        if len(" ".join([*secilen, c]).split()) > en_cok:
            break
        secilen.append(c)
    return " ".join(secilen) if secilen else " ".join(metin.split()[:en_cok])


def _betimleyici(klasor: Path):
    import torch
    from huggingface_hub import snapshot_download
    from transformers import Qwen2_5OmniForConditionalGeneration, Qwen2_5OmniProcessor

    yol = snapshot_download(BETIMLEYICI, local_dir=str(klasor / "checkpoints" / "acestep-captioner"))
    model = Qwen2_5OmniForConditionalGeneration.from_pretrained(yol, torch_dtype=torch.bfloat16, device_map="cuda")
    model.disable_talker()
    return model, Qwen2_5OmniProcessor.from_pretrained(yol)


def _betimle(model, islemci, kaynak: str) -> str:
    import soundfile as sf
    import torch
    import torchaudio

    ses, sr = sf.read(kaynak, dtype="float32", always_2d=True)
    dalga = torchaudio.functional.resample(torch.from_numpy(ses.mean(1)), sr, BETIM_ORNEKLEME).numpy()
    dalga = dalga[: BETIM_EN_UZUN_SN * BETIM_ORNEKLEME]
    mesaj = [{"role": "user", "content": [{"type": "text", "text": BETIM_ISTEMI}, {"type": "audio", "audio": dalga}]}]
    metin = islemci.apply_chat_template(mesaj, add_generation_prompt=True, tokenize=False)
    girdi = islemci(text=metin, audio=[dalga], sampling_rate=BETIM_ORNEKLEME, return_tensors="pt", padding=True)
    girdi = girdi.to(model.device).to(model.dtype)
    with torch.inference_mode():
        cikti = model.generate(**girdi, return_audio=False, max_new_tokens=512, do_sample=False)
    return islemci.batch_decode(cikti[:, girdi["input_ids"].shape[1]:], skip_special_tokens=True)[0].strip()


class ModelYok(RuntimeError):
    pass


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

    def yaz():  # atomik: zaman aşımında süreç öldürülürse hat yarım JSON okumasın
        gecici = sonuc_yolu.with_name(sonuc_yolu.name + ".tmp")
        gecici.write_text(json.dumps(sonuclar, ensure_ascii=False, indent=2), encoding="utf-8")
        gecici.replace(sonuc_yolu)

    # betimle işleri önce (cover işi betime dayanabilir); diğerlerinin sırası korunur
    isler = sorted(is_["isler"], key=lambda i: i["gorev"] != "betimle")
    betimler: dict[str, str] = {}
    betimleyici = None
    if any(i["gorev"] == "betimle" for i in isler):
        t0 = time.perf_counter()
        try:
            betimleyici = _betimleyici(klasor)
        except Exception as e:  # betimleyici yüklenemezse betimle işleri (ve ona dayanan işler) düşer, diğerleri sürer
            sonuclar.append({"id": None, "basari": False, "hata": f"betimleyici yüklenemedi: {type(e).__name__}: {e}",
                             "iz": traceback.format_exc()[-2000:]})
            yaz()
        betim_yukleme_sn = round(time.perf_counter() - t0, 1)

    dit = None
    yukleme_sn = None
    lora_olcek = None

    def dit_hazirla():
        nonlocal dit, yukleme_sn, lora_olcek, betimleyici
        if dit is not None:
            return dit
        if betimleyici is not None:  # VRAM: betimleyici (~22 GB) DiT'ten önce bırakılır
            import gc

            betimleyici = None
            gc.collect()
            torch.cuda.empty_cache()
        t0 = time.perf_counter()
        h = AceStepHandler()
        durum, ok = h.initialize_service(
            project_root=str(klasor),
            config_path=m["model"],
            device="cuda",
            offload_to_cpu=bool(m.get("cpu_offload", True)),
            offload_dit_to_cpu=bool(m.get("dit_offload", False)),
            quantization=m.get("niceleme") or None,
        )
        yukleme_sn = round(time.perf_counter() - t0, 1)
        if not ok:
            raise ModelYok(f"model yüklenemedi: {durum[:500]}")
        # eğitilmiş tür LoRA'sı (yanki/egitim.py): bir kez yüklenir, ölçeği işe göre değişebilir
        if m.get("lora"):
            mesaj = h.load_lora(str(m["lora"]))
            if not str(mesaj).startswith("✅"):
                raise ModelYok(f"LoRA yüklenemedi: {str(mesaj)[:500]}")
            lora_olcek = float(m.get("lora_olcek", 1.0))
            h.set_lora_scale(lora_olcek)
        dit = h
        return dit

    llm = LLMHandler()  # cover/repaint LM'yi atlar; yalnız "anla" için yüklenir
    for i in isler:
        kayit = {"id": i["id"], "basari": False, "hata": None}
        try:
            gorev = i["gorev"]
            if gorev == "betimle":
                if betimleyici is None:
                    raise RuntimeError("betimleyici yüklü değil")
                kayit["yukleme_sn"] = betim_yukleme_sn
                t1 = time.perf_counter()
                betim = _betimle(*betimleyici, i["kaynak"])
                if not betim:
                    raise RuntimeError("betimleyici boş döndü")
                betimler[i["id"]] = betim
                kayit.update(basari=True, sure_sn=round(time.perf_counter() - t1, 1), analiz={"betim": betim})
                sonuclar.append(kayit)
                yaz()
                continue
            try:
                dit_hazirla()
            except ModelYok as e:  # model yoksa kalan işlerin hiçbiri yapılamaz
                sonuclar.append({"id": None, "basari": False, "hata": str(e)})
                yaz()
                return 2
            kayit["yukleme_sn"] = yukleme_sn
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
            if i.get("lora_olcek") is not None:
                if lora_olcek is None:
                    raise ValueError("işe LoRA ölçeği verildi ama LoRA yüklü değil")
                dit.set_lora_scale(float(i["lora_olcek"]))
                kayit["lora_olcek"] = float(i["lora_olcek"])
            elif lora_olcek is not None:
                dit.set_lora_scale(lora_olcek)
            bolge = {}
            if gorev == "repaint":
                bas, son = i["bolge"]
                bolge = dict(repainting_start=float(bas), repainting_end=float(son), chunk_mask_mode="explicit")
            stil = i["stil"]
            if i.get("stil_betimden"):
                if i["stil_betimden"] not in betimler:
                    raise RuntimeError(f"dayandığı betim yok: {i['stil_betimden']}")
                stil = betim_stili(betimler[i["stil_betimden"]])
                kayit["stil"] = stil
            params = GenerationParams(
                task_type=gorev,
                instruction=TASK_INSTRUCTIONS[gorev],
                src_audio=i["kaynak"],
                reference_audio=i.get("referans") or None,
                caption=stil,
                lyrics=i["soz"],
                vocal_language=i.get("dil", "en"),
                bpm=i.get("bpm"),
                keyscale=i.get("ton") or "",
                audio_cover_strength=float(i.get("guc", 1.0)),
                inference_steps=int(i["adim"]),
                seed=int(i["tohum"]),
                thinking=False,
                **bolge,
                **i.get("ek", {}),
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
