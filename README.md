# Yanki

Listeye yazılan yabancı şarkıların cover'ını kiralık GPU'da [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5)
ile (kendi eğittiğimiz cover LoRA'sıyla) üretir, yayınlanamayacak adayları otomatik eler, dinleme odasında onaya sunar,
onaylananı paketler ve RouteNote'a tarayıcıyla yükler (son "Distribute" Scryne'ın tıklaması). Şarkı kaynağı Spotify'dan
kaldırılmış, hâlâ aranan şarkılar ve hattın iyi yaptığı türlerde popüler şarkılar (`yanki kesif`); yüklenen parçanın
Spotify'da çıkıp çıkmadığını ve adı arandığında kaçıncı sırada olduğunu `yanki takip` izler.

**Şu an (2026-10-15 akşam):** üretim açık, tarif ep20 + CFG 10, yalnız kör testlerde yayınlanabilir çıkan türlerde
(balad, pop, rock, metal, pop-punk, country, dance-pop; tür dışı şarkı üretilmez, `uretim.tur_disi`). Otomatik onay
(24 saat veto) ve RouteNote'a otomatik gönderim açık (`[routenote] gece = true`); RouteNote oturumu düşünce gönderim
durur ve "giriş yap" bildirilir. S34 (dikkat + MLP LoRA) Scryne söyleyince. Tunearo API'si 2026-10-12'de kapandı.

## Günlük akış

0. **Keşif (kendiliğinden):** gece koşusu üç kaynaktan kaldırılmış şarkı arar: Deezer katalog farkı (Deezer'da
   dinlenen ama Spotify'da kapalı/olmayan), `config/kesif.toml` → `playlistler`, ve varsa `girdi/kesif/`'teki STILLMORE
   CSV'leri. Adaylar ücretsiz elemelerden (düzenleme, YouTube talebi, sanatçı, söz) sonra Spotify'da doğrulanır
   (geri gelmiş mi, hangi pazarlarda kapalı, kaç rakip cover) ve en iyi `gece_ekle` tanesi listeye girer (sırada bekleyen şarkısı olan sanatçıdan yenisi eklenmez). Dinleme
   odasında **Keşif**: adayı dinle, listeye ekle ya da ele. Elle: `uv run yanki kesif [--ekle N]`.
1. `girdi/liste.toml`'a şarkı ekle (sanatçı + şarkı adı yeter) ya da 0. adımdaki gibi keşiften.
2. **Sürekli koşu:** bilgisayar açıkken her 30 dk `\Yanki\Surekli` (`scripts/surekli.ps1`) `yanki calistir`
   koşar (Scryne, 2026-10-10: "gece 3'ü beklemeye gerek yok"); `\Yanki\Gece` 03:00'te bilgisayarı uykudan uyandırıp
   aynısını koşar ve özet bildirimi gösterir (o an sürekli koşu sürüyorsa bildirim göstermeden çıkar). Görevler Görev
   Zamanlayıcı'da kapatılırsa pano ve `yanki durum` söyler. Her koşuda: hazırlık (kaynak ses YouTube, sözler LRCLIB, künye ve stil
   MusicBrainz), üretim, veto penceresi, paket, yükleme sırası. Üretim prizde ve GPU boşken, kullanıcı etkinken de,
   koşu başına en çok 2 şarkı evde, kiralık GPU'da `[uzak] sarki` (bekleyen onarımlar önce). Her koşunun ilk adımı açık
   kalmış kiralık GPU'yu siler (iş olmasa da). Keşif, takip ve disk temizliği günde bir. Keşif ve takip Spotify
   uygulamasını kullanır: uygulama kapalıysa ya da bilgisayar 20 dk'dır kullanılmıyorsa, bir şey çalmıyorsa; Spotify
   API'si kilitliyken keşif kilit kalkana kadar bekler. Hazırlıkta düşen şarkı (söz/kaynak yok) en erken 4 saat sonra
   yeniden denenir; `girdi/`'ye söz ya da ses bırakılırsa hemen. Adımlar birbirinden yalıtılmış: biri düşerse hatası
   günlüğe yazılır, koşu sürer ve hata bildirimi gelir. İş yapılmayan koşu günlüğe yazmaz. Günlük:
   `calisma/gunluk/<tarih>.log`; ayar: `config/operasyon.toml` → `[surekli]`. Hemen istersen elle
   `uv run yanki calistir` (`--hepsi`: zamanı gelmemiş adımlar da; aynı anda tek koşu, kilitli). Dinleme odası koşu
   sürerken de açık kalabilir: kararlar şarkı başına kilitle yazılır, koşu onları ezmez.
3. Dinleme odası oturum açılınca kendiliğinden başlar (`\Yanki\Oda`, `scripts/oda.ps1`): http://127.0.0.1:8765/,
   özet Windows bildirimiyle gelir, bildirime tıklayınca oda açılır. Elle: `yanki dinle` ya da Kokpit → Yanki → Çalıştır. Orijinalle karşılaştır; bozuk yer varsa dalga üzerinde sürükleyip
   **Bu aralığı onar**; iyi olanı **Bu adayı onayla**. Yanlışlıkla reddedilen şarkı **Reddi geri al** ile döner.
4. Onarım istendiyse bir sonraki `yanki calistir` (ya da `yanki uret`) iki onarım sürümü üretir; dinleme odasında iyisini
   **Bunu kabul et**.
5. Onaylanan şarkı paketlenir: `calisma/<kimlik>/paket/` (FLAC, 3000×3000 JPG, `metadata.json`, `YUKLE.md`). Kapak
   şarkının moduna göre Pinterest'ten (insansız, yazısız; her yeni kapak bildirilir); beğenmezsen `yanki kapak
   <kimlik> --yeni`, kendi görselin için şarkı klasörüne `kapak_ozel.jpg`.
6. **RouteNote'a yükleme (`yanki/routenote.py`, tarayıcıyla; API yok):** dinleme odası → **Sanatçı**: "Taslağı
   hazırla" formun dört adımını (albüm, ses + parça, kapak, mağaza/bölge) doldurur, göndermez; "Gönder…" şarkının adı
   yazılınca "Distribute"a basar (geri alınamaz). Elle: `yanki yukle <kimlik>` (taslak), `--gonder` (gönderim).
   Taslak açılmadan önce yazar ad/soyadı, açık içerik, dil ve dosya boyutu denetlenir; yarıda kalan taslak kaldığı
   adımdan sürer. Oturum birkaç saatte düşer: odada "RouteNote'a giriş yap" ya da `yanki routenote giris` (şifre
   tutulmaz). Son tıktan sonra iş düşerse hat yeniden göndermez; Sanatçı'da **Kontrol et** çıkar, panelde gördüğünü
   seç (ya da `yanki routenote gonderildi|gonderilmedi <kimlik>`). Panelden silinen taslak: `yanki routenote
   taslak-silindi <kimlik>`. Başka bir dağıtımcıya elle yüklendiyse `yanki yuklendi <kimlik> --isrc … --upc …
   --yayin-tarihi …`.
7. Gece koşusu ya da `uv run yanki takip`: parça Spotify'da çıkınca aşama `yayinda`; dinleme odasında **Yayın**
   pazar pazar arama sırasını gösterir. Bildirim gelir: yayına çıktı, en iyi arama sırası değişti, Spotify'dan kalktı,
   yayın tarihinin üstünden 3 gün geçtiği halde yok (dağıtımcı reddi şüphesi). Reddedildiyse
   `yanki dagitim-red <kimlik> --neden "…"`: şarkı `paketlendi`ye döner, düzeltip `yanki paketle --yeniden`.
8. **Takvim:** `yanki takvim` paketleri yükleme sırasıyla gösterir (keşif puanı önce; yayın tarihi yüklemeden
   `yayin_on_gun` gün sonra, RouteNote incelemesi için en az 10; `config/yayin.toml` → `[takvim]`). Dağıtımcı bir
   parçayı reddederse neden anlaşılıp düzeltilene kadar yeni yükleme yok. `[routenote] gece = false` iken sırası gelen
   paket yalnız bildirilir; odadan açmak sanatçı adını yazdırır. Dinleme odası **Yayın** ve **Sanatçı**'da da görünür.
9. **Geri çekme:** RouteNote'ta önce panelden kaldır, sonra `yanki geri-cek <kimlik> --kaldirildi`: şarkı `onaylandi`ya
   döner, RouteNote kaydı geçmişe taşınır, gece güncel ayarlarla yeniden paketlenip kuyruğa girer.

Spotify kotası dar (geliştirici API'si, 2026-10-09'da ~1.000 istekte 23 saatlik ceza): uzun 429 alınırsa kilit
`calisma/.spotify_kota.json`'a yazılır ve süresi dolana kadar hiçbir komut API'ye istek atmaz; günlük tavan 400
istek. Takip API'yi neredeyse hiç kullanmaz: canlılık ve Türkiye'deki arama sırası her gece Spotify uygulamasının
kendi aramasıyla (STILLMORE köprüsü, kotasız), diğer pazarların sırası şarkı başına haftada bir API'den
(`config/kesif.toml` → `[takip]`). Uygulama açılamazsa (o an bir şey çalıyorsa) takip API'yle sürer. Dinleme
odası Spotify'a hiç istek atmaz.

Bildirimler `calisma/olaylar.jsonl`'a da yazılır (aynı olay bir kez). Gece koşusu sonunda dış servislerin (YouTube,
LRCLIB, MusicBrainz, Deezer, Spotify) istek/hata sayısı günlüğe, günlük toplamı `calisma/gunluk/servisler.json`'a.

**Sanatçı hesabı:** tek dağıtımcı RouteNote, tek Orvane. Spotify profili ilk yayında RouteNote'ta "Create a new
profile" ile oluşur; profil adresindeki kimlik odada (Sanatçı → Dağıtım) kaydedilince sonraki yüklemeler o profili
seçer, profil önerilerde yoksa yeni profil açılmaz. Takip profilin bölündüğünü görürse bildirir.

**Kiralık GPU:** üretim RunPod'da (A40 48 GB, saniye faturalı; `config/motor.toml` → `[uzak]`, `yanki/uzak.py`):
sunucu açılır, ACE-Step yereldeki sürümle kurulur, şarkılar nicelemesiz ve tek parça üretilir (tam şarkı ~140 sn), sonuç
iner, sunucu silinir. Anahtarlar `.env` → `RUNPOD_API_KEY` (ve ikinci hesap `RUNPOD_API_KEY_2`). Evde üretim kapalı
(Scryne, 2026-10-10; `yerel_yedek = false`): bakiye `en_az_bakiye`'nin altında, aylık harcama `aylik_butce`'ye ulaşmış
ya da GPU stokta yoksa üretim sırada bekler. Her pod açan sürecin kimliğiyle kaydedilir (`calisma/.runpod/sahip/`):
sahibi ölmüş (koşu ortasında kapanan bilgisayar) ya da silinemeyip bırakılmış pod sonraki koşunun ilk adımında silinir,
sayılmamış süresi bütçeye yazılır; kilitsiz koşan deneyin ya da eğitimin pod'una dokunulmaz. Uzak işçi 30 dk hiç
ilerlemezse durdurulur. Harcama: `calisma/gunluk/runpod.json`, panoda
"Bu ay GPU". Ölçümler: `docs/arastirma/06`. `yanki bastan [--uygula]`: şarkıları baştan üretime alır (adaylar ve paket
`calisma/_arsiv/<tarih>/`'e; yüklenmişler geri çekilir, inceleme bitince üretime döner).

**Ses modeli eğitimi (`yanki egit`):** ACE-Step XL-SFT'ye cover görevinde LoRA (vokal ve eşlik birlikte;
`yanki/egitim.py`, `yanki/kapak_hazirla.py`, `config/egitim.toml`). Veri yerelde hazırlanır (`--yalniz-veri`,
ücretsiz): çok türlü, her sanatçıdan bir şarkı, cover listesindeki sanatçılar hariç; YouTube'dan tam bant Opus, LRCLIB
sözü aynı yerden kesilir. Eğitim kiralık GPU'da (A40), ardından karşılaştırmalı deneme → `calisma/dinleme/lora/<zaman>/
OKU.md`; deneme düşerse eğitim yine kaydedilir, `yanki egit --deneme-yeniden <zaman>`. Üretimdeki LoRA: dördüncü
eğitimin 20. epoch'u (`config/motor.toml` → `[motor] lora`; kör testte yayınlanabilir 9/17). Klasör yoksa yalnız üretim
durur, `yanki durum` gösterir.

**Tür çizgisi:** keşif hattın tarifi dinlenmiş türlerinde kalır (balad, pop, piyano/akustik, rock). Rap, metal,
elektronik, Latin/Brezilya vb. aday Deezer türünden tanınır, puan almaz, kendiliğinden listeye girmez (dinleme
odasında "Yine de ekle"). Aynı kalıp otomatik onayı da sınırlar (`yanki/onay.py` → `DENENMEMIS`).

Diğer komutlar: `yanki durum` (motor, model, araçlar, GPU, anahtarlar, disk, şarkıların aşaması), `yanki ozet` (tek satır),
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
powershell -File scripts/gorev_kur.ps1                     # \Yanki\Surekli (açıkken 30 dk), \Yanki\Gece (03:00), \Yanki\Oda
# Keşif ve takip için: developer.spotify.com → Create app (Premium hesap), Redirect URI http://127.0.0.1:8766/callback
copy .env.example .env                                     # SPOTIFY_*, TYPESAFE_API_KEY, RUNPOD_API_KEY
uv run yanki spotify-baglan                                # yalnız kendi playlist'lerini taramak için
uv run yanki routenote giris                               # RouteNote oturumu (bir kez; düşünce yeniden)
```

## Ayarlar

- `config/motor.toml` — model, niceleme, cover gücü, adım, aday/onarım tohumları, GPU eşiği. Tarifin kaynağı dinleme
  testleri (`docs/arastirma/01-spike-bulgulari.md`).
- `config/yayin.toml` — sanatçı adı, dağıtımcı (`routenote` | `distrokid` | `""`; `tunearo` kapandı), mastering hedefi
  (−14 LUFS, −1,2 dBTP, ton eşleme), otomatik onay, yayın takvimi, RouteNote (`[routenote]`: gece yüklemesi, Spotify
  sanatçı kimliği). RouteNote'ta kapatılan mağazalar ve hariç bölgeler `yanki/routenote.py`'de.
- `config/egitim.toml` — LoRA eğitiminin verisi (şarkı + stil metni) ve ayarları (rank, epoch, deneme şarkıları).
- `config/kesif.toml` — keşif pazarları, taranacak playlist'ler, gece listeye kaç aday eklensin, arama derinliği.
- `config/operasyon.toml` — yedek klasörü (varsayılan `calisma/yedek`; başka diske almak daha güvenli), sıklığı,
  kaç yedek saklanacağı; disk temizliğinin gün eşiği; gündüz üretiminin saatleri, boşta kalma eşiği.
- Liste alanları ve kaynak/söz dosyasını elle verme: `girdi/liste.toml` başındaki açıklama.

## Nasıl çalışır

- **Cover:** ACE-Step `cover` görevi, XL-SFT 4B nicelemesiz (kiralık A40) + cover LoRA'sı, güç 0,7, 100 adım, CFG 10,
  4 aday; stil şarkıya özel betimden (`acestep-captioner` şarkıyı dinler), söz bölüm etiketli (`yanki/yapi.py`).
- **Parçalı üretim:** 8 dk'dan uzun şarkı (evde 110 sn'den uzun) vokal boşluklarından parçalara bölünür; ilk parçanın
  çıktısı sonraki parçalara tını referansı olur.
- **Pencereli onarım:** işaretli aralığın ±25 sn'lik penceresi yeniden üretilip geri dikilir; aralık dışı birebir korunur.
- **Kapılar:** orijinal kaydı taşıyan (parmak izi ≥ 0,72 ya da dalga korelasyonu ≥ 0,25), sözsüz (WER ≥ 0,5) ya da yanlış
  süreli aday dinlemeye çıkmaz. "İyi"yi kulak seçer: otomatik kalite ölçüleri dinlemeyle uyuşmadı.
- **Keşif:** kaldırılmış = Spotify'da çalınamayan (`is_playable: false`). Aynı ISRC ya da aynı sanatçı + ad çalınabilir
  durumda geri geldiyse aday düşer; sıra YouTube izlenmesi × kapalı pazar oranı / (1 + rakip cover). Takma adla
  yüklenmiş sızıntılar YouTube başlığındaki sanatçıyla, düzenlemeler (sped up, remix) adla elenir. Ayrıntı:
  `docs/arastirma/03`.
- **Dil:** kaynak sesten tespit edilir (Whisper); ACE-Step'e ve söz kapısına o dil gider.
- **Mastering:** 28 Hz alçak kesim (ACE-Step çıktısındaki DC ve uğultu), orijinal kayda ton eşleme (40–63 Hz fazlası
  kesilir, 3–8 kHz vokal varlığı en çok 3 dB; `yanki/ton.py`), sabit kazanç, 4× aşırı örneklenmiş tepe sınırlayıcı:
  −14 LUFS, ≤ −1,2 dBTP, şarkının dinamiği (kıta/nakarat farkı) korunur.
- **Motor ayrı süreç:** hat torch yüklemez; ACE-Step işçisi (`yanki/motor_isci.py`) motorun kendi ortamında çalışır.

Kararlar ve gerekçeler: `docs/Final-Dokuman.md`, yol haritası: `docs/Roadmap.md`.
