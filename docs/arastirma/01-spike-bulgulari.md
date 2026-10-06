---
proje: Yanki
created: 2026-10-06
type: arastirma
---
# Spike bulguları — ACE-Step 1.5 ile cover (2026-10-06)

Makine: RTX 4060 Laptop 8 GB, 24 GB RAM. Kaynaklar: Adele "Someone Like You" ilk 90 sn (A), Coldplay "Viva La Vida"
30 sn önizleme (B; SoundCloud tam parça vermedi). Ölçüm betikleri `spikes/s1…s5`. Her ölçü pozitif ve negatif kontrolle
kalibre edildi; tablo değerleri A şarkısı (B aynı yönde).

## Ölçüler
- **armoni:** hizasız kare kare kroma kosinüsü, en iyi transpozisyon. POZ (kaynak+gürültü) 0,98 · NEG (ilgisiz şarkı) 0,66.
- **parmak izi:** Chromaprint ham parmak izi eşleşen bit oranı. POZ 0,95 · NEG 0,54 · besteden sentezlenmiş kılavuz 0,67.
- **dalga:** ham dalga korelasyonu; orijinal kaydın sesi çıktıda var mı. POZ 0,92 · NEG 0,01.
- **wer:** Whisper small.en dökümü ile kaynak sözleri arası kelime hata oranı (düşük = anlaşılır).
- **melodi (S5):** Demucs vokal izlerinin pyin perde eğrileri, DTW, ±1 yarım ton. POZ 1,00 · NEG (kaydırılmış) 0,75 —
  zayıf ayırıcı.

## Sonuçlar

| Yol | armoni | parmak izi | dalga | wer | Yorum |
|---|---|---|---|---|---|
| `cover` turbo, güç 1,0 | 0,63 | 0,59 | 0,02 | 0,33 | yeni kayıt, armoni kayıp |
| `cover` base 50 adım, güç 1,0 | 0,68 | 0,59 | 0,04 | **0,11** | yeni kayıt, sözler en iyi, armoni zayıf |
| `cover-nofsq` turbo, güç 0,5 | 0,90 | 0,74 | 0,41 | 0,15 | orijinal kaydı taşıyor |
| `cover-nofsq` turbo, güç 1,0 | 0,99 | 0,93 | 0,90 | 0,35 | orijinalin neredeyse kendisi |
| kılavuz (MIDI sentezi) → `cover-nofsq` 1,0 | 0,89 | 0,66 | 0,02 | 1,00 | beste var, vokal yok |
| kılavuz → `cover-nofsq` 0,4 | 0,77 | 0,60 | 0,01 | 0,49 | ikisi de yarım |
| kılavuz → enstrümantal → `lego` VOCALS | 0,89 | 0,66 | 0,02 | 1,00 | lego bağlamı geri veriyor (r=0,99) |

## Kesin olanlar
1. Hız sorun değil: 90 sn cover turbo ~12 sn, base 50 adım ~40 sn (CPU offload, VRAM tepe 6,5 GB).
2. Söz şart: sözsüz vokal anlamsız (wer 0,94–0,98).
3. `cover-nofsq` güç ≥ 0,5 orijinal kaydı taşıyor → parmak izi kontrolüne takılır; yayın yolu olamaz.
4. GPU paylaşılıyorsa (ör. Otomat aynı anda koşarsa) ACE-Step sistem belleğine taşar: 12 sn → 600 sn. Hat GPU boş
   değilse beklemeli.

## Açık
- `cover` modunun çıktısı kulakla "aynı şarkı" mı? Ölçülerim (armoni, melodi) bunu ayıramıyor → Scryne dinleme testi
  (`calisma/dinleme/`).

## Motor tuzakları (Python API)
- `GenerationParams.instruction` görev türüne göre seçilmiyor; varsayılan text2music talimatı gidiyor. REST sunucusu
  doğru seçiyor (`job_generation_setup.py`). Üretimde REST kullan ya da `TASK_INSTRUCTIONS[gorev]` ver.
- İz adı büyük harfle: `Generate the VOCALS track…`.
- Lego/repaint: belge `repainting_end=-1` "sona kadar" diyor; Python yolunda kod `end > start` arıyor, süre açıkça verilmeli.
- Kaynağı WAV/FLAC ver: soundfile hızlı yol; torchcodec FFmpeg 9 DLL'leriyle denenmedi.
- faster-whisper 1.2.1 + PyAV 19: dosya yolu verince `metadata_errors` hatası → diziyle ver.

## Kaynak edinme
- YouTube: `youtube.com` açılıyor, medya sunucusu (googlevideo, IPv4/IPv6, farklı istemciler) TLS'te sıfırlanıyor.
- SoundCloud: bazı parçalar 30 sn önizleme (süre kontrolü şart).

## Dinleme testi 1 ve kalite turu (2026-10-06 gece)
- Scryne: cover'lar **tanınıyor** ("bu Someone Like You" denir) ama kalite çok kötü: vokal metalik/robotik, sözler
  yutuluyor, müzik bulanık, detone/ritim kayıyor. → Armoni/melodi ölçülerim gereğinden kötümserdi; kulak esas.
- Kalite vekilleri kulağı tutmadı: Audiobox Aesthetics cover'lara orijinalden yüksek PQ verdi (8,0–8,3 / 7,6); S7
  (WER, perde sapması, vuruş CV, tiz oranı) cover'ları orijinal düzeyinde gösterdi. Bu ölçüler kalite kapısı olamaz.
- Kalite kolları: model (sft 2B, XL-SFT 4B), kaynağa uygun stil tanımı (önceki denemede kadın vokal "male" yazılmıştı),
  BPM + ton, 50 adım.
- XL-SFT 8 GB'ta: bf16 + DiT offload adım başı 72–150 sn (kullanılamaz); **INT8 (`int8_weight_only`) 90 sn → 100 sn,
  VRAM 7,55 GB** (kullanılabilir). SFT 2B 50 adım: 31 sn.
- Dinleme testi 2: `6_YENI_sft_dogru_stil`, `7_YENI_xl_buyuk_model`.

## Tur 3–4 (2026-10-06 gece)
- Scryne: **11 (text2music, cover değil) temiz**; cover'larda 9 (güç 0,7) ve 10 (100 adım) en iyi, arkada mırıldanma
  azalmış, ama bazı yerlerde hâlâ çok kötü. → Model temiz üretebiliyor; kirlilik cover yolundan (kaynak koşullaması) geliyor.
- ScragVAE yüklendi ve denendi (8); öne çıkmadı.
- Flow-Edit (text2music + `flow_edit_morph`, n_max 0,6/0,8): parmak izi 0,87–0,91, dalga 0,84–0,91 → orijinal kaydın
  kendisi; elendi, dinletilmedi.
- Tam aralık repaint 9'u arıtmıyor, sıfırdan üretiyor (`repaint_strength` 0,3 ve 0,5 birebir aynı çıktı; sözler wer 0,01).
  Arıtma için doğru araç **bölgesel** repaint: yalnız bozuk saniyeler, çevresi bağlam.
- Not: aynı tohum (42) bağımsız üretimler arasında ~0,18 dalga korelasyonu bırakıyor; dalga ölçüsünde taban bu.
- Dinleme testi 3: 12 (güç 0,7 + 100 adım), 13 (güç 0,6 + 100 adım), ~140 sn / 90 sn ses.
