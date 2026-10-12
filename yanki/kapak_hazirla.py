"""Cover görevi için LoRA eğitim tensörleri (pod'da, ACE-Step venv'iyle; `yanki` paketinden bir şey import etmez).

  python kapak_hazirla.py <acestep klasörü> <model> <tensör klasörü> <dataset.json>

Neden: Side-Step LoRA'yı metinden-müzik görevinde eğitiyor (bağlam sessizlik, talimat "Fill the audio semantic mask",
söz dil başlığı olmadan, 512 jeton). Üretim cover görevi: adımların %70'inde bağlam kaynağın anlamsal kodlarından
(tokenize → detokenize "LM ipucu"), talimat "Generate audio semantic tokens", söz "# Languages / # Lyric" başlıklı,
2048 jeton. İki LoRA (balad 2026-10-11, çok türlü 2026-10-12) bu uyumsuzlukla eğitildi ve cover'da kazanç vermedi
(S28: beat daha döngüsel, söz daha bulanık).

Her Side-Step örneği (`<ad>.pt`) için yanına `<ad>__kapak.pt` yazılır: hedef aynı (orijinal kaydın latentleri),
bağlam örneğin kendi latentlerinden cover ipucu, metin ve söz üretimdeki biçimde (`conditioning_text.py` ile aynı
şablon). Model, kaynağın kodlarından orijinal stüdyo kaydını kurmayı öğrenir; özgün `.pt` (metinden-müzik) kalır:
cover çıkarımının son %30'u kaynaksız (sessizlik bağlamı) adımlar.
"""

import json
import sys
from pathlib import Path

EK = "__kapak"


def metas(m: dict) -> str:
    """`metadata_utils._dict_to_meta_string` ile aynı biçim."""
    sure = m.get("duration") or 30
    return (f"- bpm: {m.get('bpm') or 'N/A'}\n- timesignature: {m.get('timesignature') or 'N/A'}\n"
            f"- keyscale: {m.get('keyscale') or 'N/A'}\n- duration: {int(float(sure))} seconds\n")


def main() -> int:
    klasor, model_adi, tensor_klasoru, dataset_yolu = sys.argv[1:5]
    sys.path.insert(0, klasor)
    import torch
    from acestep.constants import SFT_GEN_PROMPT, TASK_INSTRUCTIONS
    from acestep.training.dataset_builder_modules.preprocess_encoder import run_encoder
    from acestep.training_v2.model_loader import load_decoder_for_training, load_silence_latent, load_text_encoder

    cihaz, dtype = "cuda", torch.bfloat16
    ckpt = str(Path(klasor) / "checkpoints")
    diller = {o["audio_path"]: o.get("language") or "en"
              for o in json.loads(Path(dataset_yolu).read_text(encoding="utf-8"))["samples"]}
    tokenizer, metin_kod = load_text_encoder(ckpt, cihaz, "bf16")
    sessizlik = load_silence_latent(ckpt, cihaz, "bf16", variant=model_adi)
    model = load_decoder_for_training(ckpt, model_adi, cihaz, "bf16")

    yazilan, atlanan = 0, 0
    for yol in sorted(Path(tensor_klasoru).glob("*.pt")):
        if yol.stem.endswith(EK) or (hedef := yol.with_name(yol.stem + EK + ".pt")).exists():
            continue
        veri = torch.load(str(yol), weights_only=False)
        m = veri["metadata"]
        lat = veri["target_latents"].to(cihaz, dtype).unsqueeze(0)  # [1, T, 64]
        maske = veri["attention_mask"].to(cihaz, dtype).unsqueeze(0)  # [1, T]
        t = lat.shape[1]
        with torch.no_grad():
            # cover ipucu: üretimdeki `prepare_condition` ile aynı yol (tokenize → detokenize, T'ye kırpılır)
            ipucu_5hz, _, _ = model.tokenize(lat, sessizlik, maske)
            ipucu = model.detokenize(ipucu_5hz)[:, :t, :]
            baglam = torch.cat([ipucu, torch.ones(1, t, ipucu.shape[-1], device=cihaz, dtype=dtype)], dim=-1)
            # metin ve söz üretimdeki biçimde (conditioning_text.py, prompt_utils._format_lyrics)
            istem = SFT_GEN_PROMPT.format(TASK_INSTRUCTIONS["cover"], m.get("caption", ""), metas(m))
            mt = tokenizer(istem, padding="longest", truncation=True, max_length=256, return_tensors="pt")
            metin_hs = metin_kod(mt.input_ids.to(cihaz)).last_hidden_state.to(dtype)
            soz = f"# Languages\n{diller.get(m.get('filename') or Path(m['audio_path']).name, 'en')}\n\n# Lyric\n" \
                  f"{m.get('lyrics', '')}<|endoftext|>"
            st = tokenizer(soz, padding="longest", truncation=True, max_length=2048, return_tensors="pt")
            soz_hs = metin_kod.embed_tokens(st.input_ids.to(cihaz)).to(dtype)
            enc_hs, enc_maske = run_encoder(model, text_hidden_states=metin_hs,
                                            text_attention_mask=mt.attention_mask.to(cihaz).to(dtype),
                                            lyric_hidden_states=soz_hs,
                                            lyric_attention_mask=st.attention_mask.to(cihaz).to(dtype),
                                            device=cihaz, dtype=dtype)
        if baglam.shape[-1] != veri["context_latents"].shape[-1]:
            print(f"atlandı (bağlam boyutu {baglam.shape[-1]} ≠ {veri['context_latents'].shape[-1]}): {yol.name}")
            atlanan += 1
            continue
        torch.save({"target_latents": veri["target_latents"], "attention_mask": veri["attention_mask"],
                    "encoder_hidden_states": enc_hs.squeeze(0).cpu(),
                    "encoder_attention_mask": enc_maske.squeeze(0).cpu(),
                    "context_latents": baglam.squeeze(0).cpu(), "metadata": {**m, "gorev": "cover"}}, str(hedef))
        yazilan += 1
        print(f"kapak: {yol.name} (T={t})", flush=True)
    print(f"kapak tensörleri: {yazilan} yazıldı, {atlanan} atlandı", flush=True)
    return 0 if yazilan else 1


if __name__ == "__main__":
    raise SystemExit(main())
