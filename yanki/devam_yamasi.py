"""Side-Step devam yaması (pod'da, ACE-Step kökü argümanla): `yanki/egitim.py` → `Ayar.devam`.

Side-Step bağdaştırıcıyı `decoder.load_state_dict(state_dict, strict=False)` ile yüklüyor. PEFT'in kaydettiği
anahtarlarda bağdaştırıcı adı yok (`lora_A.weight`), modeldekilerde var (`lora_A.default.weight`): hiçbir ağırlık
yüklenmeden eğitim sessizce sıfırdan başlardı (2026-10-13, ep20 dosyasının 512 anahtarının hepsi böyle). Yükleme
PEFT'in kendi yükleyicisiyle değiştirilir; eşleşmeyen anahtar varsa eğitim düşer. Yalnız standart kütüphane: pod'da
`uv run python` ile, ACE-Step ortamından bağımsız çalışır.
"""

import sys
from pathlib import Path

ESKI = "            decoder.load_state_dict(state_dict, strict=False)\n"
YENI = (
    "            from peft import set_peft_model_state_dict\n"
    "            _sonuc = set_peft_model_state_dict(decoder, state_dict)\n"
    "            _fazla = list(getattr(_sonuc, 'unexpected_keys', []) or [])\n"
    "            if _fazla:\n"
    "                raise RuntimeError(f'devam: {len(_fazla)} anahtar eslesmedi: {_fazla[:3]}')\n"
    "            print(f'[YANKI] devam: {len(state_dict)} anahtar yuklendi', flush=True)\n"
)
DOSYA = "acestep/training_v2/trainer_helpers.py"


def yamala(kok: Path) -> str:
    yol = kok / DOSYA
    s = yol.read_text(encoding="utf-8")
    if YENI in s:
        return "zaten yamalı"
    if s.count(ESKI) != 1:
        raise SystemExit(f"yama yeri bulunamadı ({s.count(ESKI)} eşleşme): {yol}")
    yol.write_text(s.replace(ESKI, YENI), encoding="utf-8")
    return "yama tamam"


if __name__ == "__main__":
    print(yamala(Path(sys.argv[1])))
