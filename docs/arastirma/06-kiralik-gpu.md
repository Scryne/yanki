# Kiralık GPU (2026-10-10)

Scryne: "güçlü bir sunucu alsam şarkıların çıktılarını daha iyi yapabilir miyiz?" Evdeki RTX 4060 Laptop 8 GB, XL-SFT'yi
yalnız INT8 nicelemeyle çalıştırabiliyor; kalan nefes/mırıldanma kusurunun şüphelisi bu niceleme (S17, S18 yarım).
Araştırma bir alt ajanla yapıldı; aşağıdakiler kaynaklı, ölçümler bizim.

## Bulgular (kaynaklı)

- **VRAM katmanları** (ACE-Step README, `docs/en/GPU_COMPATIBILITY.md`): ≥20 GB XL offload'suz; ≥24 GB "tam kalite"
  (XL + 4B LM); 8–12 GB'ta XL desteklenmiyor. Kaynak: https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/GPU_COMPATIBILITY.md
- **LoRA eğitimi** (resmi rehber): 16 GB asgari, 20 GB+ önerilen, tipik ~17 GB.
  https://github.com/ace-step/ACE-Step-1.5/blob/main/docs/en/LoRA_Training_Tutorial.md
- **Resmi hız ölçümü yok** (`BENCHMARK.md` yalnız ölçüm aracının rehberi).
- **Fiyat** (2026-10-10): RunPod saniye faturalı; A40 48 GB güvenli bulut panelde 0,59 $/sa (API'de en düşük 0,35
  görünüyordu, açılan pod 0,59), RTX 4090 0,89, L40S 1,09, A100 80GB 1,79. Hetzner aylık: GEX45 (24 GB) 214 €/ay +
  209 € kurulum. https://www.runpod.io/pricing, https://docs.runpod.io/pods/pricing,
  https://www.hetzner.com/dedicated-rootserver/gex45/
- **YouTube** veri merkezi IP'lerinden indirmeyi sık engelliyor (yt-dlp "Sign in to confirm you're not a bot") →
  hat evde kalır, sunucuya yalnız motor gider.

## S19: nicelemesiz bf16, A40 (ölçüm)

Kurulum: `runpod/pytorch:1.3.3-cu1281-torch271-ubuntu2204`, ACE-Step yereldeki commit (`ca1e85f`), `uv sync` +
`acestep-download` ~40 sn (XL-SFT 19 GB veri merkezinden); sürücü 570.195.03. Spike: `spikes/s19_uzak_bf16.py`.

| İş | Süre | VRAM tepe | Söz WER | Not |
|---|---|---|---|---|
| Kesit 45 sn, tohum 42 | 21 sn | 13,7 GB | 0,042 | evde INT8 ~100 sn; INT8 0,042, FP8 0,070 |
| Kesit 45 sn, tohum 7 | 21 sn | 14,0 GB | 0,056 | FP8 0,099 |
| Tam şarkı 285 sn, tek parça, tohum 7 | 140 sn | 14,4 GB | 0,045 | evde INT8 parçalı aday başı ~8 dk; yüklenen aday 4: 0,015 |

Hepsi kapılardan geçti. Model yükleme 11,7 sn. İki deneme toplam ~0,16 $. 24 GB'lık bir kart da yeterli (tepe
14,4 GB). Kalite kararı kulakta: `calisma/dinleme/s19/` (orijinal kesit, INT8, FP8, bf16; tam şarkı INT8 parçalı ↔ bf16
tek parça).

Bulunan hatalar (düzeltildi): sonuç dosyası satır sonuyla bitmediği için durum kelimesi JSON'a yapışıyordu; `pgrep -f
motor_isci.py` kendi `bash -lc` satırını eşleştirip hep "sürüyor" dedi (pod 3 saat açık kalacaktı; elle kapatıldı)
→ pid dosyası.

## Karar

`config/motor.toml` → `[uzak]` açık: üretim kiralık GPU'da (`yanki/uzak.py`), nicelemesiz ve 480 sn'ye kadar tek
parça; sunucu açılamazsa, stok azsa ya da bütçe dolduysa evdeki kart (INT8, parçalı). Bir koşu bir pod; koşu başına en
çok 8 şarkı. Bütçe: bakiye ≥ 3 $ ve aylık ≤ 15 $ (`calisma/gunluk/runpod.json`). Aylık sabit sunucu (GEX45) şimdilik
yok: kazanç £0 ve günde 5–10 şarkıda saniye faturalı pod çok daha ucuz.

## Reddedilen öneri: orijinal kaydın ISRC'si

Scryne 2026-10-10'da kaldırılmış şarkıların ISRC'leriyle yükleme önerdi (orijinalin dinlenmesi profile geçsin). ISRC
belirli bir kaydın kimliği; cover'a orijinalin ISRC'si verilince Spotify onu eski çalma listelerindeki orijinalin yerine
bağlıyor, dinleyici orijinali dinlediğini sanıyor. Hat bunu yapmaz; her yayına dağıtımcının atadığı yeni ISRC. Sahibi
olunan bir kaydın kendisini yeniden yayınlamak ayrı ve meşru bir iş (istenirse ayrıca kurulur).
