---
proje: Yanki
created: 2026-10-06
modified: 2026-10-10
type: final-dokuman
status: onaylandi
---
# Yanki — Final Doküman

Kaynak: `docs/Proje-Fikri.md`, `docs/arastirma/01-spike-bulgulari.md` (S1–S7, dört dinleme testi). Scryne yetkiyi
devretti ("tamamını sana bırakıyorum", 2026-10-06); kararlar bu yetkiyle ve Scryne'ın dinleme cevaplarıyla kapandı.
Otomat'ın yapısı kopyalanmaz (Scryne, 2026-10-06): mimari aşağıdaki gereksinimlerden çıkar.

## Özet

Yanki, Scryne'ın listesine yazdığı yabancı şarkıların cover'ını yerel GPU'da (RTX 4060 Laptop, 8 GB) ACE-Step 1.5
XL-SFT ile üretir; her şarkı için üç aday çıkarır (S13: tohum en büyük kalite etkeni), otomatik kapılardan (orijinal kaydı taşımıyor, sözler var, süre
doğru) geçirir ve yerel bir dinleme sayfasına koyar. Scryne dinler: onaylar, bozuk aralığı işaretler (hat yalnız o
aralığı yeniden üretir) ya da reddeder. Onaylanan cover mastering, kapak ve dağıtımcı metadata'sıyla bir **yükleme
paketine** dönüşür; Scryne paketi dağıtımcı arayüzünden yükler (şarkı başı ~3–5 dk). Dağıtımcılarda yükleme API'si
olmadığı için yükleme adımı bilerek insanda kalır.

**Şarkı seçimi (Scryne, 2026-10-09):** hattın ana şarkı kaynağı Spotify'dan **kaldırılmış** şarkılar. Kaldırılmış
şarkıyı arayan dinleyici Spotify'da onu bulamıyor; cover'ı aramada üste çıkar. Adaylar STILLMORE FINDER'ın
(arkadaşın aracı, `docs/arastirma/03`) playlist taramasından ya da Scryne'ın playlist'lerinden gelir; Yanki boşluğun
gerçekten açık olduğunu (şarkı geri gelmemiş) doğrular, talebe göre sıralar, listeye ekler (`yanki kesif`). Başarı
ölçüsü yüklenen parçanın ad aramasındaki sırası (`yanki takip`). **Yükleme:** arkadaşın dağıtım sitesinin API'si
gelince otomatik yüklemeye geçilir (Scryne, 2026-10-09); o zamana kadar insanda.

## Değişen kararlar (2026-10-08 – 10-10)

Aşağıdaki tablo ve mimari ilk kararları tarihiyle korur; bunlar onların yerini aldı (ayrıntı ve ölçüm: `docs/Roadmap.md`).

| Konu | İlk karar | Bugün | Neden |
| --- | --- | --- | --- |
| Üretim yeri | Evdeki RTX 4060 8 GB, XL INT8, parçalı | Kiralık GPU (RunPod A40 48 GB, saniye faturalı): nicelemesiz bf16, şarkı tek parça (~140 sn); evde üretim kapalı (`[uzak] yerel_yedek = false`), aylık bütçe 15 $ | Scryne: "güçlü GPU ile daha iyi", "benim bilgisayarımda üretmicez" (2026-10-10); S19 (`docs/arastirma/06`) |
| Dağıtım | RouteNote, form insanda | Tunearo API: hat paketi kendisi yükler, durumu yoklar (kabulde UPC/ISRC, redde neden); takvim sınırsız (paketlenen her şarkı ilk koşuda; parça kotası dolarsa durur), yayın tarihi +1 gün | Arkadaşın API'si geldi (2026-10-10, `docs/arastirma/04`) |
| Onay | Her şarkıda Scryne | Veto penceresi 24 sa: denenmiş tür/dilde, sözü anlaşılır (WER ≤ 0,15) aday kendiliğinden onaylanır; diğerleri kulağa kalır | "Her şey otomatik çalışsın" (2026-10-10) |
| Kapak | Dalga formundan tipografik | Şarkının moduna göre Pinterest görseli (insansız, yazısız); `kapak_ozel.jpg` önce | Scryne: "üretilen kapağı istemiyorum" (2026-10-10) |
| Zamanlama | `\Yanki\Gece` 03:00 | `\Yanki\Surekli` bilgisayar açıkken her 30 dk (adımlar kendi aralığıyla), `\Yanki\Gece` 03:00'te uyandırır, `\Yanki\Oda` oturum açılışında | "Açıkken hep çalışsın" (2026-10-10) |
| Yayın takibi | Spotify Web API | Canlılık ve TR sırası Spotify istemcisinin kendi aramasıyla (kotasız), diğer pazarlar haftada bir Web API | Web API kotası (2026-10-09 kilidi) |
| Keşif çizgisi | Her tür | Hattın tarifi dinlenmiş türler (balad, pop, piyano/akustik, rock); rap/metal/elektronik vb. kendiliğinden girmez; sanatçı başına sırada bir şarkı | Rap adaylarının hepsi söz kapısında kaldı; Denetim 2–3 |
| Dinleme odası güvenliği | Yalnız 127.0.0.1 | + Host yerel olmalı, yazan istek başka kökenden gelemez | Denetim 3 |

## Teknoloji Stack

| Katman | Seçim | Gerekçe |
| --- | --- | --- |
| Dil, paket | Python 3.12, `uv` (proje ortamı torch'suz) | Ağır ML bağımlılıkları motorun kendi ortamında kalır; hat hafif ve test edilebilir |
| Üretim motoru | ACE-Step 1.5 **XL-SFT 4B**, `int8_weight_only`, CPU offload; `motor/ACE-Step-1.5` (kendi venv'i, gitignore) | Dinleme testleri: XL en iyisi; INT8 8 GB'ta 90 sn → ~100–140 sn. bf16 sığmıyor (adım başı 72–150 sn) |
| Motor köprüsü | `yanki/motor_isci.py`, motorun venv'iyle **iş başına alt süreç** (JSON iş → FLAC + rapor) | REST sunucusu açılışta nicelemeyi geçirmiyor (XL INT8 imkânsız). Python API'de bilinen tuzaklar (talimat, büyük harf iz, repaint aralığı) tek yerde düzeltilir. Süreç bitince GPU boşalır |
| Cover tarifi | `cover`, güç 0,7, 100 adım, kaynağa uygun stil tanımı + BPM + ton + gerçek sözler | Dinleme testi 3: 12 numaralı aday en iyi ("az kaldı") |
| Parçalı üretim | Vokal boşluğundan (LRCLIB zaman damgaları) ~90 sn parçalar, 1 sn bindirme, ilk parçanın çıktısı sonrakilere tını referansı; eşit güçlü geçişle dikiş | Tek parça 290 sn: adım başı 34 sn (~57 dk) ve ACE-Step 600 sn iç zaman aşımı. Parçalı: aday başı ~8 dk, söz WER 0,03 |
| Bölge onarımı | `repaint` ±25 sn **pencerede** (kes → onar → geri dik), aralık başına iki tohum | Dinleme testi 4: 14 düzeldi. Tam şarkıda repaint de tüm şarkıyı işler; pencereli gerçek koşu: 2 sürüm 5 dk, pencere dışı r=1,0 |
| Sözler | LRCLIB API (zaman damgalı, anahtarsız) → yoksa Scryne'ın söz dosyası → yoksa Whisper | LRCLIB bu ağdan çalışıyor; Someone Like You için süre birebir (285 sn) |
| Künye | MusicBrainz API (kayıt → eser → söz yazarı/besteci) | Dağıtımcı cover formunda orijinal yazarlar zorunlu |
| BPM / ton / stil tanımı | Listedeki `stil`/`vokal`/`bpm`/`ton` esas; yoksa MusicBrainz sanatçı türleri (ilk iki) + solo sanatçının cinsiyeti; BPM/ton listede yoksa **gönderilmez** | ACE-Step 5Hz LM ölçüldü ve uydurdu (Viva La Vida → "İbranice Eurodance", Perfect → "saksafonlu pop-rock 130 BPM"); CLAP düz dağılım verdi. Yanlış tanım/tempo göndermek hiç göndermemekten kötü. LM yolu `analiz_yontemi = "lm"` ile seçilebilir |
| Kaynak ses | YouTube: yt-dlp adresi bulur, medya **HTTP/3** (`curl_cffi`, QUIC) ile iner; yedek `girdi/kaynak/` klasörü; **süre kontrolü** (LRCLIB süresiyle) | Bu ağda ISS içi googlevideo düğümü TCP+TLS'i kesiyor, QUIC çalışıyor (S8: 290 sn şarkı 0,4 sn). SoundCloud 30 sn önizleme verebiliyor, kullanılmaz |
| Otomatik kapılar | Chromaprint (`fpcalc`) parmak izi benzerliği, dalga korelasyonu, Whisper ile söz var mı, süre | Spike'ta kalibre edildi: orijinali taşıyan çıktı parmak izi ≥ 0,74, iyi cover ~0,59–0,66 |
| Dinleme sayfası | FastAPI + tek HTML (yerel, `127.0.0.1`) | Yarı otomatik akışın kalbi: dinle, onayla, aralık işaretle, reddet |
| Mastering | `pyloudnorm` + ffmpeg (−14 LUFS, −1 dBTP, 44,1 kHz / 16 bit; RouteNote için FLAC) | Spotify normalizasyon hedefi; RouteNote WAV almıyor |
| Kapak | Pillow ile kodla üretilen tipografik kapak, 3000×3000 JPG | Orijinal sanatçı adı/logosu yok (dağıtımcı kuralı); model gerektirmez |
| Durum | Şarkı başına `calisma/<kimlik>/durum.json` (atomik yazım) | İnsan okunur, tek dosya; dinleme sayfası ve hat aynı kaydı okur. SQLite gereksiz çıktı |
| Kalite | ruff, pytest; CI'da GPU'suz testler | Motor çağrısı arayüzün arkasında; testler sahte motorla |
| Şarkı keşfi | Üç kaynak: STILLMORE CSV'si (`girdi/kesif/`), Web API ile kendi playlist'ler, **Deezer katalog farkı** (`yanki/katalog.py`). Ücretsiz elemeler önce (düzenleme adı, YouTube talebi + sanatçı eşleşmesi, LRCLIB sözü ve süre), Spotify en son: boşluk (ISRC ve sanatçı + ad) ve pazar başına kapalılık. `calisma/kesif/adaylar.json`; `--ekle N`, `gece_ekle` ya da dinleme odası | Başkasının playlist'ini Şubat 2026'dan beri yalnız Spotify istemcisi okuyor (STILLMORE); Deezer anahtarsız, popülerlik + ISRC veriyor. Spotify kotası dar (bir günde ~1.000 istekte 23 saat kilit) → kalıcı kilit, günlük tavan 400 |
| Özgünlük kararı | TypeSafe Jev (`yanki/yargi.py`, resmi SDK): YouTube ilk 5 sonucu kanıt; "listedeki sanatçının mı / başka sanatçının (takma ad, sızıntı) mı / belirsiz" Choice + "hayran yapımı mı" Noul; kabul ≥ 0,90 ve hayran < 0,5; karar + model sürümü adaya dondurulur; anahtar yoksa regex yedeği | Anlam gerektiren karar (global kural: önce TypeSafe, spike ile). Spike: 20 sızıntı/hayran örneğinde sıfır yanlış kabul, regex'in iki hatasını düzeltti |
| Dil | Kaynak sesten Whisper `small` ile dil tespiti → ACE-Step `vocal_language`; söz kapısı İngilizcede `small.en` (eşikler onunla), diğer dillerde `small`; Unicode normalleştirme | Keşif global; sabit `en` Türkçe/Fransızca adayı söz kapısında düşürüyordu (Gülümse: WER 1,0 → 0,238) |
| Yayın takibi | Spotify Web API (client credentials): ISRC araması → canlı, ad araması → sıra (yayınladığımız her pazarda), sanatçı kimliği → profil tek mi; `durum.json` → `yayin`; dinleme odasında Yayın görünümü | Faz 7 bitti kriterini (Spotify'da dinlenebilir) ve stratejinin başarısını elle bakmadan ölçer. Anahtar `.env`'de |
| Zamanlama | Görev Zamanlayıcı `\Yanki\Gece` 03:00 → `scripts/gece.ps1` → `yanki calistir`; yazan komutlar tek işletim sistemi kilidi | "Her şey arkada" (Scryne); bilgisayar yerelde GPU'lu olduğu için bulut cron değil. Kilit süreç ölünce kalkar |

Model kimlikleri (`acestep-v15-xl-sft`, niceleme, adım, güç) kod içine gömülmez: `config/motor.toml`.

## Mimari

```
girdi/liste.toml  (Scryne: sanatçı + şarkı, isteğe bağlı stil/söz düzeltmesi)
  └─ hazırlık: kaynak ses (klasör | yt-dlp) + süre kontrolü → 48 kHz WAV
       ├─ sözler (LRCLIB → dosya → Whisper) → ACE-Step söz biçimi
       ├─ künye (MusicBrainz) → yazarlar, orijinal yayın
       └─ BPM, ton, stil tanımı (librosa + ACE-Step LM)
  └─ GPU kapısı: boş VRAM < eşik değilse bekle (Otomat vb. GPU'yu kullanıyorsa)
  └─ motor işi (alt süreç): cover × 3 tohum (parçalı) → FLAC
  └─ otomatik kapılar: parmak izi < eşik, dalga < eşik, söz var, süre ±2 sn → geçmeyen aday düşer
  └─ dinleme sayfası: Scryne → onay | bölge onar (bas–son) → motor işi: repaint → tekrar dinle | ret
  └─ paket: mastering + kapak + metadata.json + YUKLE.md (dağıtımcı formunun alan alan kopya metni)
  └─ Scryne yükler → paket "yüklendi" işaretlenir
```

Önemli tasarım kararları:
- **Orijinalden yalnız beste.** Kaynak kaydı çıktıda taşıyan yollar (`cover-nofsq` ≥ 0,5, Flow-Edit) kullanılmaz; kapı
  bunu her adayda ölçer.
- **Kalite kapısı kulak.** Otomatik kalite ölçüleri (Audiobox, perde, gürültülülük) Scryne'ın duyduğunu görmedi; otomatik
  kapılar yalnız "yayınlanamaz" durumları (kopya, sessizlik, eksik söz) eler, "iyi"yi Scryne seçer.
- **Motor alt süreçte.** Hat torch yüklemez; motor çökerse iş düşer, hat ayakta kalır. Her iş GPU kapısından geçer.
- **Tam şarkı.** Spike'lar 90 sn'likti; tam şarkının (3–5 dk) 8 GB'ta süresi ve VRAM'i Faz 2'de ölçülür.

## Kapsam (v1)

- **Süre tavanı:** ~4 hafta.
- **Bitti = kullanıldı:** Scryne listesine yazdığı bir şarkının Yanki'nin ürettiği cover'ını dinleme sayfasında onayladı,
  paketi dağıtımcıya yükledi, dağıtımcı kabul etti ve parça Spotify'da dinlenebilir.

## Riskler ve Doğrulamalar

| Risk | Durum |
| --- | --- |
| ACE-Step 8 GB'ta çalışır mı | ✅ S1: 2B turbo 12 sn; XL INT8 100–140 sn / 90 sn ses |
| Cover orijinal kaydı taşır mı | ✅ ölçüldü: `cover` taşımıyor (parmak izi 0,59, dalga 0,02); `cover-nofsq`/Flow-Edit taşıyor → kullanılmaz |
| Şarkı tanınıyor mu | ✅ Scryne: "dinleyen biri Someone Like You der" |
| Kalite yayın seviyesinde mi | 🔄 Scryne: "az kaldı" (mırıldanma, nefes, titreme). Bölgesel onarım çalışıyor. Faz 6 |
| Kaynak ses edinme | ✅ S8: HTTP/3 ile YouTube'dan tam şarkı iniyor; yedek kaynak klasörü |
| Tam şarkı 8 GB'ta | ✅ parçalı üretimle aday başı ~8 dk (S10) |
| Otomatik stil tanımı | ⚠️ LM ve CLAP güvenilmez çıktı; MusicBrainz türleri + cinsiyet genel kalıyor ("piano ballad" gibi ayrıntı yok). Faz 6: dinleme sayfasında stili düzenleyip yeniden üretme |
| Kaldırılmış şarkı stratejisi aramada üste çıkar mı | ⏳ ilk yayınlar canlı olunca `yanki takip` ölçer |
| Keşif adayları cover'lanabilir mi (rap, İngilizce dışı) | ⏳ hat balad için kalibre; ilk üç keşif şarkısı rap (2026-10-10 gecesi üretim), ilk Türkçe/Fransızca aday dinleme testiyle |
| Spotify API kısıtları (Şubat 2026) keşfi engeller mi | ⚠️ başkasının playlist'i API'de 403 → STILLMORE CSV'si; arama ve ISRC çalışıyor (dokümana göre, canlı doğrulanmadı) |
| Dağıtımcı AI cover'ı kabul eder mi | ⏳ Faz 7'de ilk gerçek yükleme. Seçilen: RouteNote (`docs/arastirma/02`); tam AI cover için açık kabul cümlesi yok |

## Kapsam Dışı

- Tarayıcı botuyla otomatik yükleme (ToS dışı). Arkadaşın dağıtım sitesinin API'si gelince yükleme otomatikleşir.
- Sanatçı ses klonu, orijinal kaydı girdi olarak taşıyan yollar, orijinal sanatçı adının başlıkta/kapakta kullanılması.
- ~~Hattın kendi şarkı seçmesi, Türkçe şarkılar~~ (2026-10-09: kaldırılmış şarkılar keşiften gelir ve Türkçe
  olabilir. Türkçe cover kalitesi denenmedi → ilk Türkçe adayda dinleme testi.)
- Promosyon, dinlenme artırma.

## Scryne'dan beklenenler (açık)

- Sanatçı adı: **Orvane** (Scryne, 2026-10-07). Uydurma, gönderme taşımayan marka adı; aramada çakışma yok, "Aurane"
  Aure/Aurora'ya yakın düştüğü için elendi.
- Dağıtımcı: **RouteNote**, mekanik lisans alınmadan (Scryne, 2026-10-07). Lisanssız cover kuralı gereği ABD, Kanada,
  Meksika, Hindistan ve Pakistan bölgeleri çıkarılır; ses FLAC 44,1 kHz / 16 bit.
