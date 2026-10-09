# Yanki

Listeye yazılan yabancı şarkıların cover'ını yerel GPU'da [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5)
ile üretir, yayınlanamayacak adayları otomatik eler, dinleme sayfasında onaya sunar ve onaylananı Spotify dağıtımcısına
yüklenmeye hazır bir pakete çevirir. Şarkı kaynağı Spotify'dan kaldırılmış, hâlâ aranan şarkılar (`yanki kesif`);
yüklenen parçanın Spotify'da çıkıp çıkmadığını ve adı arandığında kaçıncı sırada olduğunu `yanki takip` izler. Yükleme
şimdilik insanda; arkadaşın dağıtım API'si gelince otomatikleşecek.

## Günlük akış

0. **Keşif (kendiliğinden):** gece koşusu üç kaynaktan kaldırılmış şarkı arar: Deezer katalog farkı (Deezer'da
   dinlenen ama Spotify'da kapalı/olmayan), `config/kesif.toml` → `playlistler`, ve varsa `girdi/kesif/`'teki STILLMORE
   CSV'leri. Adaylar ücretsiz elemelerden (düzenleme, YouTube talebi, sanatçı, söz) sonra Spotify'da doğrulanır
   (geri gelmiş mi, hangi pazarlarda kapalı, kaç rakip cover) ve en iyi `gece_ekle` tanesi listeye girer. Dinleme
   odasında **Keşif**: adayı dinle, listeye ekle ya da ele. Elle: `uv run yanki kesif [--ekle N]`.
1. `girdi/liste.toml`'a şarkı ekle (sanatçı + şarkı adı yeter) ya da 0. adımdaki gibi keşiften.
2. Her gece 03:00'te zamanlanmış görev (`\Yanki\Gece`, `scripts/gece.ps1`; pilde başlamaz, kaçırırsa açılınca yetişir)
   `yanki calistir` koşar: kaynak ses (YouTube), sözler (LRCLIB), künye ve stil (MusicBrainz), üç cover adayı, kapılar,
   bekleyen onarımlar, onaylılar için paket, takip, disk temizliği, haftalık yedek. GPU başka bir işle doluysa
   boşalmasını bekler; şarkı başı ~30 dk. Adımlar birbirinden yalıtılmış: biri düşerse hatası günlüğe yazılır, koşu
   sürer ve sonunda hata bildirimi gelir. Günlük: `calisma/gunluk/<tarih>.log`. Hemen istersen elle
   `uv run yanki calistir` (aynı anda tek koşu, kilitli). Dinleme odası koşu sürerken de açık kalabilir: kararlar
   şarkı başına kilitle yazılır, gece koşusu onları ezmez.
   **Gündüz:** `\Yanki\Gunduz` her 30 dk bakar (08:00–01:00); 20 dk klavye/fareye dokunulmadıysa, prizdeyse ve GPU
   boşsa kuyruktan bir şarkı üretir (önce bekleyen onarımlar), bitince "dinlemeye hazır" bildirimi. Ayar:
   `config/operasyon.toml` → `[gunduz]`, günlük: `calisma/gunluk/gunduz.log`.
3. Dinleme odası oturum açılınca kendiliğinden başlar (`\Yanki\Oda`, `scripts/oda.ps1`): http://127.0.0.1:8765/,
   özet Windows bildirimiyle gelir, bildirime tıklayınca oda açılır. Elle: `yanki dinle` ya da Kokpit → Yanki → Çalıştır. Orijinalle karşılaştır; bozuk yer varsa dalga üzerinde sürükleyip
   **Bu aralığı onar**; iyi olanı **Bu adayı onayla**. Yanlışlıkla reddedilen şarkı **Reddi geri al** ile döner.
4. Onarım istendiyse bir sonraki `yanki calistir` (ya da `yanki uret`) iki onarım sürümü üretir; dinleme odasında iyisini
   **Bunu kabul et**.
5. Onaylanan şarkı paketlenir: `calisma/<kimlik>/paket/` → `YUKLE.md`'yi açıp formu doldur, ses dosyasını (RouteNote: FLAC) ve JPG'yi yükle.
6. `yanki yuklendi <kimlik> --isrc <ISRC> --upc <UPC> --yayin-tarihi YYYY-AA-GG`: aşama `yuklendi`, formdaki
   bilgiler paketin `metadata.json` → `yukleme`'sine (takip ISRC'yle çalışır). ISRC sonradan belli olursa aynı
   komut yalnız `--isrc` ile.
7. Gece koşusu ya da `uv run yanki takip`: parça Spotify'da çıkınca aşama `yayinda`; dinleme odasında **Yayın**
   pazar pazar arama sırasını gösterir. Bildirim gelir: yayına çıktı, en iyi arama sırası değişti, Spotify'dan kalktı,
   yayın tarihinin üstünden 3 gün geçtiği halde yok (dağıtımcı reddi şüphesi). Reddedildiyse
   `yanki dagitim-red <kimlik> --neden "…"`: şarkı `paketlendi`ye döner, düzeltip `yanki paketle --yeniden`.
8. **Takvim:** `yanki takvim` paketleri yükleme sırasıyla gösterir (keşif puanı önce, haftada bir, önerilen yayın
   tarihi +21 gün; `config/yayin.toml` → `[takvim]`). İlk parça Spotify'a çıkana kadar bekler; sonra sırası gelen
   paket gece bildirilir (dağıtım API'si gelince kendisi yüklenecek). Dinleme odası **Yayın**'da da görünür.

Spotify kotası dar: uzun 429 alınırsa kilit `calisma/.spotify_kota.json`'a yazılır ve süresi dolana kadar hiçbir
komut Spotify'a istek atmaz; günlük tavan 400 istek. Dinleme odası Spotify'a hiç istek atmaz.

Bildirimler `calisma/olaylar.jsonl`'a da yazılır (aynı olay bir kez). Gece koşusu sonunda dış servislerin (YouTube,
LRCLIB, MusicBrainz, Deezer, Spotify) istek/hata sayısı günlüğe, günlük toplamı `calisma/gunluk/servisler.json`'a.

Diğer komutlar: `yanki durum` (motor, model, araçlar, GPU, şarkıların aşaması), `yanki ozet` (tek satır),
`yanki temizle [--uygula]` (yüklenmiş şarkıların ara sesleri; gece koşusu 14 günden eskileri kendisi siler),
`yanki yedekle [--zorla]` (seçimler, yükleme bilgisi, keşif kaydı, liste, ayarlar; ses ve sır yok; gece haftada bir),
`yanki hazirla [--yeniden]` (onaylı/yüklenmiş şarkılara dokunmaz), `yanki uret`,
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
powershell -File scripts/gorev_kur.ps1                     # \Yanki\Gece (03:00), \Yanki\Oda (oturum açılışı), \Yanki\Gunduz
# Keşif ve takip için: developer.spotify.com → Create app (Premium hesap), Redirect URI http://127.0.0.1:8766/callback
copy .env.example .env                                     # SPOTIFY_CLIENT_ID / SECRET, TYPESAFE_API_KEY
uv run yanki spotify-baglan                                # yalnız kendi playlist'lerini taramak için
```

## Ayarlar

- `config/motor.toml` — model, niceleme, cover gücü, adım, aday/onarım tohumları, GPU eşiği. Tarifin kaynağı dinleme
  testleri (`docs/arastirma/01-spike-bulgulari.md`).
- `config/yayin.toml` — sanatçı adı, dağıtımcı, mastering hedefi (−14 LUFS, −1 dBTP).
- `config/kesif.toml` — keşif pazarları, taranacak playlist'ler, gece listeye kaç aday eklensin, arama derinliği.
- `config/operasyon.toml` — yedek klasörü (varsayılan `calisma/yedek`; başka diske almak daha güvenli), sıklığı,
  kaç yedek saklanacağı; disk temizliğinin gün eşiği; gündüz üretiminin saatleri, boşta kalma eşiği.
- Liste alanları ve kaynak/söz dosyasını elle verme: `girdi/liste.toml` başındaki açıklama.

## Nasıl çalışır

- **Cover:** ACE-Step `cover` görevi, XL-SFT 4B INT8 (8 GB'a yalnız böyle sığıyor), güç 0,7, 100 adım, kaynağa uygun stil +
  BPM + ton + gerçek sözler.
- **Parçalı üretim:** uzun şarkı vokal boşluklarından ~90 sn'lik parçalara bölünür (tek parça 290 sn şarkıda ~57 dk;
  parçalı ~8 dk). İlk parçanın çıktısı sonraki parçalara tını referansı olur.
- **Pencereli onarım:** işaretli aralığın ±25 sn'lik penceresi yeniden üretilip geri dikilir; aralık dışı birebir korunur.
- **Kapılar:** orijinal kaydı taşıyan (parmak izi ≥ 0,72 ya da dalga korelasyonu ≥ 0,25), sözsüz (WER ≥ 0,5) ya da yanlış
  süreli aday dinlemeye çıkmaz. "İyi"yi kulak seçer: otomatik kalite ölçüleri dinlemeyle uyuşmadı.
- **Keşif:** kaldırılmış = Spotify'da çalınamayan (`is_playable: false`). Aynı ISRC ya da aynı sanatçı + ad çalınabilir
  durumda geri geldiyse aday düşer; sıra YouTube izlenmesi × kapalı pazar oranı / (1 + rakip cover). Takma adla
  yüklenmiş sızıntılar YouTube başlığındaki sanatçıyla, düzenlemeler (sped up, remix) adla elenir. Ayrıntı:
  `docs/arastirma/03`.
- **Dil:** kaynak sesten tespit edilir (Whisper); ACE-Step'e ve söz kapısına o dil gider.
- **Motor ayrı süreç:** hat torch yüklemez; ACE-Step işçisi (`yanki/motor_isci.py`) motorun kendi ortamında çalışır.

Kararlar ve gerekçeler: `docs/Final-Dokuman.md`, yol haritası: `docs/Roadmap.md`.
