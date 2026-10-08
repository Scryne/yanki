# Yanki

Listeye yazılan yabancı şarkıların cover'ını yerel GPU'da [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5)
ile üretir, yayınlanamayacak adayları otomatik eler, dinleme sayfasında onaya sunar ve onaylananı Spotify dağıtımcısına
yüklenmeye hazır bir pakete çevirir. Yükleme adımı insanda kalır: dağıtımcıların yükleme API'si yok.

## Günlük akış

1. `girdi/liste.toml`'a şarkı ekle (sanatçı + şarkı adı yeter).
2. Her gece 03:00'te zamanlanmış görev (`\Yanki\Gece`, `scripts/gece.ps1`; pilde başlamaz, kaçırırsa açılınca yetişir)
   `yanki calistir` koşar: kaynak ses (YouTube), sözler (LRCLIB), künye ve stil (MusicBrainz), üç cover adayı, kapılar,
   bekleyen onarımlar, onaylılar için paket. GPU başka bir işle doluysa boşalmasını bekler; şarkı başı ~30 dk.
   Günlük: `calisma/gunluk/<tarih>.log`. Hemen istersen elle `uv run yanki calistir` (aynı anda tek koşu, kilitli).
3. `yanki dinle` (ya da Kokpit → Yanki → Çalıştır) → tarayıcıda dinleme odası. Orijinalle karşılaştır; bozuk yer varsa dalga üzerinde sürükleyip
   **Bu aralığı onar**; iyi olanı **Bu adayı onayla**.
4. Onarım istendiyse bir sonraki `yanki calistir` (ya da `yanki uret`) iki onarım sürümü üretir; dinleme odasında iyisini
   **Bunu kabul et**.
5. Onaylanan şarkı paketlenir: `calisma/<kimlik>/paket/` → `YUKLE.md`'yi açıp formu doldur, ses dosyasını (RouteNote: FLAC) ve JPG'yi yükle.
6. `yanki yuklendi <kimlik>`.

Diğer komutlar: `yanki durum` (motor, model, araçlar, GPU, şarkıların aşaması), `yanki hazirla`, `yanki uret`,
`yanki yeniden <kimlik>` (onaylı şarkıya güncel hatla yeni adaylar), `yanki kunye [kimlik]` (yazarlar ve orijinal
yılı yeniden çek), `yanki paketle [--yeniden]`.

## Kurulum (bir kez)

```powershell
uv sync                                                    # hat (torch'suz)
git clone https://github.com/ace-step/ACE-Step-1.5 motor/ACE-Step-1.5
cd motor/ACE-Step-1.5; uv sync                             # motor (torch, CUDA 12.8)
uv run acestep-download --model acestep-v15-xl-sft         # ~19 GB; VAE, metin kodlayıcı ve LM ana paketle gelir
uv run acestep-download
winget install Gyan.FFmpeg.Shared                          # ffmpeg/ffprobe
# fpcalc (Chromaprint 1.5.1, Windows x64) → araclar/fpcalc.exe
uv run yanki durum                                         # hepsi ✓ olmalı
```

## Ayarlar

- `config/motor.toml` — model, niceleme, cover gücü, adım, aday/onarım tohumları, GPU eşiği. Tarifin kaynağı dinleme
  testleri (`docs/arastirma/01-spike-bulgulari.md`).
- `config/yayin.toml` — sanatçı adı, dağıtımcı, mastering hedefi (−14 LUFS, −1 dBTP).
- Liste alanları ve kaynak/söz dosyasını elle verme: `girdi/liste.toml` başındaki açıklama.

## Nasıl çalışır

- **Cover:** ACE-Step `cover` görevi, XL-SFT 4B INT8 (8 GB'a yalnız böyle sığıyor), güç 0,7, 100 adım, kaynağa uygun stil +
  BPM + ton + gerçek sözler.
- **Parçalı üretim:** uzun şarkı vokal boşluklarından ~90 sn'lik parçalara bölünür (tek parça 290 sn şarkıda ~57 dk;
  parçalı ~8 dk). İlk parçanın çıktısı sonraki parçalara tını referansı olur.
- **Pencereli onarım:** işaretli aralığın ±25 sn'lik penceresi yeniden üretilip geri dikilir; aralık dışı birebir korunur.
- **Kapılar:** orijinal kaydı taşıyan (parmak izi ≥ 0,72 ya da dalga korelasyonu ≥ 0,25), sözsüz (WER ≥ 0,5) ya da yanlış
  süreli aday dinlemeye çıkmaz. "İyi"yi kulak seçer: otomatik kalite ölçüleri dinlemeyle uyuşmadı.
- **Motor ayrı süreç:** hat torch yüklemez; ACE-Step işçisi (`yanki/motor_isci.py`) motorun kendi ortamında çalışır.

Kararlar ve gerekçeler: `docs/Final-Dokuman.md`, yol haritası: `docs/Roadmap.md`.
