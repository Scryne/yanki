"""Müzik estetiği işçisi: değerlendiricinin kendi venv'iyle çalışır, `yanki` paketinden hiçbir şey import etmez.

  araclar/degerlendirici/.venv/Scripts/python.exe yanki/degerlendirici_isci.py <girdi.json> <sonuc.json>

girdi.json: {"songeval": "<SongEval klonu>", "dosyalar": ["a.flac", ...], "cpu": false}
sonuc.json: {"<dosya>": {"songeval": {Coherence, Musicality, Memorability, Clarity, Naturalness},
                         "audiobox": {CE, CU, PC, PQ}, "sure_sn", "aygit"} | {"hata": "..."}}

İki hazır, eğitimsiz değerlendirici (araştırma 2026-10-18, `docs/arastirma/10`):
- SongEval (ASLP-lab, 2025): tam şarkı; MuQ-large gizil özellikleri üstünde beş eksen (1–5). Şarkı bütün olarak
  girer (24 kHz). Music Arena çift tercihinde %70,8.
- Audiobox Aesthetics (Meta, 2025): 10 sn pencerelerin ağırlıklı ortalaması; CE/CU/PC/PQ (1–10). Aynı testte %68,5.
Modeller bir kez yüklenir. GPU belleği yetmezse o dosya CPU'da yeniden denenir; bir dosyanın hatası diğerlerini
durdurmaz. Sonuç her dosyadan sonra yazılır (yarıda kalan koşu baştan başlamaz).
"""

import json
import os
import sys
import time
from pathlib import Path


def _songeval(klon: Path, aygit):
    import torch
    from hydra.utils import instantiate
    from muq import MuQ
    from omegaconf import OmegaConf
    from safetensors.torch import load_file

    sys.path.insert(0, str(klon))  # config.yaml generator'ı `model.Generator` diye kurar
    ayar = OmegaConf.load(klon / "config.yaml")
    model = instantiate(ayar.generator).eval()
    model.load_state_dict(load_file(str(klon / "ckpt" / "model.safetensors"), device="cpu"), strict=False)
    muq = MuQ.from_pretrained("OpenMuQ/MuQ-large-msd-iter").eval()
    eksenler = ("Coherence", "Musicality", "Memorability", "Clarity", "Naturalness")

    @torch.no_grad()
    def puanla(yol: str, cihaz) -> dict:
        import librosa

        model.to(cihaz)
        muq.to(cihaz)
        ses, _ = librosa.load(yol, sr=24000)
        gizli = muq(torch.tensor(ses).unsqueeze(0).to(cihaz), output_hidden_states=True)["hidden_states"][6]
        p = model(gizli).squeeze(0)
        return {e: round(float(p[i]), 4) for i, e in enumerate(eksenler)}

    return puanla


def _audiobox():
    from audiobox_aesthetics.infer import initialize_predictor

    tahminci = initialize_predictor()

    def puanla(yol: str, cihaz) -> dict:
        tahminci.device = cihaz
        tahminci.model.to(cihaz)
        return {k: round(float(v), 4) for k, v in tahminci.forward([{"path": yol}])[0].items()}

    return puanla


def main(girdi: Path, cikti: Path) -> int:
    import torch

    g = json.loads(girdi.read_text(encoding="utf-8"))
    cpu = torch.device("cpu")
    asil = cpu if g.get("cpu") or not torch.cuda.is_available() else torch.device("cuda")
    sonuc = json.loads(cikti.read_text(encoding="utf-8")) if cikti.exists() else {}
    se, ab = _songeval(Path(g["songeval"]), asil), _audiobox()
    for yol in g["dosyalar"]:
        if yol in sonuc and "hata" not in sonuc[yol]:
            continue
        t = time.time()
        for cihaz in dict.fromkeys([asil, cpu]):
            try:
                sonuc[yol] = {"songeval": se(yol, cihaz), "audiobox": ab(yol, cihaz), "aygit": cihaz.type}
                break
            except RuntimeError as e:
                if "out of memory" not in str(e):
                    sonuc[yol] = {"hata": f"{type(e).__name__}: {str(e)[:300]}"}
                    break
                # GPU başka işle dolu (oyun, üretim): bu ve kalan dosyalar CPU'da; bellek hatası CUDA bağlamını
                # bozabildiği için GPU'ya geri dönülmez
                torch.cuda.empty_cache()
                asil = cpu
                sonuc[yol] = {"hata": "GPU belleği yetmedi"}
            except Exception as e:  # noqa: BLE001 — tek dosya diğerlerini durdurmaz
                sonuc[yol] = {"hata": f"{type(e).__name__}: {str(e)[:300]}"}
                break
        sonuc[yol]["sure_sn"] = round(time.time() - t, 1)
        gecici = cikti.with_suffix(".tmp")
        gecici.write_text(json.dumps(sonuc, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(gecici, cikti)
        print(f"{Path(yol).name}: {sonuc[yol]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1]), Path(sys.argv[2])))
