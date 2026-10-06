"""S11: CLAP sıfır-atış etiketleme stil tanımı için güvenilir mi? (ACE-Step LM tanımları uydurdu: Viva La Vida →
"İbranice Eurodance", Perfect → "saksafonlu pop-rock".)

Motorun venv'iyle (transformers + torch orada):
  motor/ACE-Step-1.5/.venv/Scripts/python spikes/s11_clap.py <kaynak1.wav> [...]
"""

import sys

import numpy as np
import soundfile as sf
import torch
from transformers import ClapModel, ClapProcessor

KUMELER = {
    "vokal": ["a song with male vocals", "a song with female vocals"],
    "his": ["a slow emotional ballad", "a mid-tempo song", "an upbeat energetic song"],
    "enstruman": ["piano", "acoustic guitar", "electric guitar", "string orchestra", "synthesizer", "drums",
                  "bass guitar", "brass section"],
    "tur": ["pop", "rock", "soul", "r&b", "folk", "electronic dance music", "hip hop", "country", "jazz", "classical"],
}


def kesitler(yol: str, sr_hedef: int = 48000, sure: float = 10.0, adet: int = 6) -> list[np.ndarray]:
    ses, sr = sf.read(yol, dtype="float32", always_2d=True)
    ses = ses.mean(axis=1)
    if sr != sr_hedef:
        import librosa  # noqa: F401  (motor venv'inde yoksa torchaudio)
    n = int(sure * sr)
    baslar = np.linspace(0.1 * len(ses), 0.9 * len(ses) - n, adet).astype(int)
    return [ses[b: b + n] for b in baslar]


def main() -> None:
    model = ClapModel.from_pretrained("laion/larger_clap_music").eval()
    islemci = ClapProcessor.from_pretrained("laion/larger_clap_music")
    for yol in sys.argv[1:]:
        parcalar = kesitler(yol)
        print("==", yol)
        for ad, etiketler in KUMELER.items():
            with torch.no_grad():
                # yeni transformers: `audio=` (eski `audios=` sessizce yok sayılıyordu → tüm şarkılar aynı çıktı)
                g = islemci(text=etiketler, audio=parcalar, sampling_rate=48000, return_tensors="pt", padding=True)
                cikti = model(**g)
            olas = cikti.logits_per_audio.softmax(-1).mean(0)
            sira = sorted(zip(etiketler, olas.tolist(), strict=True), key=lambda x: -x[1])[:4]
            print(f"  {ad:10}", " | ".join(f"{e} {p:.2f}" for e, p in sira))


if __name__ == "__main__":
    main()
