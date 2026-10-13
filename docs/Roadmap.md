---
proje: Yanki
created: 2026-10-06
modified: 2026-10-11
type: roadmap
status: aktif
---
# Yanki — Roadmap

Durum sütunu session-start hook'u tarafından otomatik okunur — format bozulmasın:
⏳ Bekliyor / 🔄 Devam Ediyor / ✅ Tamamlandı / ⛔ Engelli.

| Faz | Adı | Durum | Bitti Kriteri |
| --- | --- | --- | --- |
| 0 | Spike ve karar | ✅ Tamamlandı | ACE-Step 8 GB'ta ölçüldü, cover tarifi ve bölge onarımı dinleme testleriyle seçildi (`docs/arastirma/01`) |
| 1 | İskelet ve sağlık | ✅ Tamamlandı | `uv` projesi, `yanki` CLI, `config/motor.toml`; ruff + pytest yerelde yeşil; CI ve Dependabot dosyaları; GitHub private repo (Scryne onayıyla) ve CI yeşil |
| 2 | Motor köprüsü ve tam şarkı | ✅ Tamamlandı | `motor_isci.py` alt süreçte cover + repaint yapıyor, GPU kapısı bekliyor; tam bir şarkı (≥ 4 dk) 8 GB'ta üretildi, süre ve VRAM kayıtlı |
| 3 | Girdi hazırlığı | ✅ Tamamlandı | `girdi/liste.toml`'daki 3 şarkı için kaynak ses (süre kontrollü), sözler (LRCLIB/dosya/Whisper), künye (MusicBrainz), BPM/ton/stil tanımı hazır |
| 4 | Kapılar ve dinleme sayfası | ✅ Tamamlandı | Her şarkıya 2 aday; kopya/söz/süre kapıları çalışıyor (bozuk girdiyle sınandı); Scryne yerel sayfada bir şarkıyı dinleyip bölge onarımıyla onayladı |
| 5 | Yükleme paketi | ✅ Tamamlandı | Onaylı şarkıdan mastering (−14 LUFS, −1 dBTP) + 3000×3000 kapak + metadata + `YUKLE.md`; Scryne'ın seçtiği dağıtımcının formuna birebir uyuyor |
| 6 | Kalite turu | ✅ Tamamlandı | Mırıldanma, nefes, titreme için denemeler; Scryne bir şarkıda "yayınlanabilir" dedi |
| 7 | Gerçek kullanım | 🔄 Devam Ediyor | Scryne listeden bir şarkıyı yükledi, dağıtımcı kabul etti, parça Spotify'da dinlenebilir; bulgular roadmap'e işlendi |
| 8 | Kalite ve düzenli yayın | 🔄 Devam Ediyor | En az 3 parça Spotify'da; yükleme takvimi işliyor; vokal son işlemi ve LoRA dinleme testiyle karara bağlandı; ≥ 10 onarım etiketiyle otomatik kusur işaretleme denendi (sonuç kayıtlı) |
| 9 | Kaldırılmış şarkı keşfi ve yayın takibi | 🔄 Devam Ediyor | Spotify anahtarı bağlı; `yanki kesif` (STILLMORE CSV'si, kendi playlist ya da Deezer katalog farkı) ≥ 5 doğrulanmış (geri gelmemiş) aday buldu; en az biri üretilip yüklendi; `yanki takip` yüklenen parçaların canlılığını ve ad aramasındaki sırasını pazar pazar kaydetti |
| 10 | Tam otomatik yayın (dağıtım API'si) | ⛔ Engelli | Arkadaşın API'siyle onaylı bir paket elle dokunmadan yüklendi; inceleme → kabul/red → canlı durumu kendiliğinden izlendi ve kayda düştü; yayın takvimi en az 2 hafta kesintisiz işledi; veto penceresi (otomatik onay) bir şarkıda uçtan uca çalıştı |
| 11 | Öğrenen şarkı seçimi | ⏳ Bekliyor | Puan formülü en az 10 yayının ölçülen arama sırası/dinlenmesiyle karşılaştırılıp güncellendi; tür/dil başına üretilebilirlik çarpanı Scryne'ın onay/ret verisinden; en az bir yeni keşif kaynağı (YouTube'da olup Spotify'da olmayan) canlı aday üretti |
| 12 | Kalite otomasyonu | ⏳ Bekliyor | Otomatik aday seçimi Scryne'ın geçmiş seçimleriyle ölçüldü (isabet kayıtlı) ve ≥ %70 ise veto penceresinde varsayılan; rap ve İngilizce dışı en az bir dil için tarif dinleme testiyle karara bağlandı |
| 13 | Operasyon ve dayanıklılık | 🔄 Devam Ediyor | Disk temizliği ve yedek işliyor; gece koşusu/Spotify kilidi/dağıtımcı reddi bildirim olarak geliyor; GPU boştayken gündüz üretimi kuyruğu eritiyor; bir haftalık kesintisiz otomatik koşu günlükte hatasız |

## Faz Detayları

### Faz 0: Spike ve karar ✅
- S1–S7, dört dinleme testi. Seçilen tarif: XL-SFT INT8, `cover`, güç 0,7, 100 adım, doğru stil + BPM + ton + söz.
- **Notlar:** Otomatik kalite ölçüleri kulağı tutmadı → "iyi"yi Scryne seçer, kapılar yalnız yayınlanamazı eler.
  ACE-Step Python API tuzakları `docs/arastirma/01`'de; motor köprüsü hepsini tek yerde düzeltecek.

### Faz 1: İskelet ve sağlık ✅
- **Sonuç (2026-10-07):** private `Scryne/yanki`, CI (windows-latest: ruff + pytest) yeşil, Dependabot (uv + actions).
- **Notlar:** gh token'ında `workflow` izni yok → push Git Credential Manager ile; ilk dal `master` açılmıştı → `main`.
  CI'da motor klasörü yok: işçi cwd'si yoksa iş klasörü (bulundu, testle kapatıldı).
- **İşler:** `pyproject.toml` (Python 3.12, torch'suz), `yanki` paketi + CLI (`yanki durum`), `config/motor.toml`, ruff,
  pytest, `.github/workflows/ci.yml`, `.github/dependabot.yml` (`uv`), `fpcalc` araç yolu ayarı.
- **Bitti Kriteri:** yukarıdaki tablo.

### Faz 2: Motor köprüsü ve tam şarkı ✅
- **Sonuç:** tek parça 290 sn şarkı XL INT8'de adım başı 34 sn (~57 dk) ve ACE-Step'in 600 sn iç zaman aşımına
  takıldı → **parçalı üretim**: vokal boşluğundan ~90 sn parçalar, ilk parça tını referansı; 285 sn şarkı aday başı ~8 dk.
  Söz WER 0,03 (parçaya kendi sözü). Onarım pencereli (±25 sn): 2 sürüm 5 dk, pencere dışı r=1,0.
- **Notlar:** gerçek koşu göreli iş yolu hatasını buldu (testle kapatıldı). `ACESTEP_GENERATION_TIMEOUT=1800`.
- **İşler:** iş şeması (JSON), `motor_isci.py` (ACE-Step venv'iyle çalışır, birden çok işi tek model yüklemesiyle yapar),
  GPU kapısı (`nvidia-smi` boş VRAM), zaman aşımı, hata raporu; tam şarkı ölçümü.
- **Risk:** 4–5 dk şarkı VRAM'e sığmayabilir → parçalı üretim ya da süre sınırı kararı burada.

### Faz 3: Girdi hazırlığı ✅
- **Sonuç:** 3 şarkı uçtan uca (YouTube HTTP/3, süre LRCLIB ile ±1 sn, yazarlar doğru, stil tanımı). Bitti kriterindeki
  BPM/ton bilerek değişti: listede yoksa gönderilmiyor.
- **Notlar:** ACE-Step LM analizi uydurdu (iki şarkıda iki yanlış tür/tempo); tam şarkıda 10 dk sonuçsuz, 40 sn kesit +
  turbo ile 2 dk. CLAP düz dağılım. Varsayılan MusicBrainz; ayrıntılı stil için listedeki `stil` ya da Faz 6'daki düzenleme.
- **İşler:** liste biçimi, kaynak klasörü + yt-dlp denemesi (süre ±3 sn kontrolü), LRCLIB, MusicBrainz (User-Agent: proje
  adı + depo bağlantısı; kişisel e-posta yok), söz biçimleyici (bölüm etiketleri), BPM/ton (librosa), stil tanımı.

### Faz 4: Kapılar ve dinleme sayfası ✅
- **Durum:** kapılar gerçek adaylarla doğrulandı (iyi geçer, orijinali taşıyan ve sözsüz düşer); sayfa görsel doğrulamadan
  0 sorunla geçti (iki hata gözle bulundu: "false" metni, mobil kuyruk).
- **Sonuç (2026-10-07):** Scryne üç şarkıyı da sayfada dinleyip onayladı; Adele'de bölge onarımı (`1-1`) kabul edildi.
  Üçünde de aday 2 seçildi (Adele'de aday 2 = S10'un tını referanssız parçalı üretimi). Paketler çıktı (Faz 5).
- **İşler:** `fpcalc` parmak izi + dalga kapısı (eşikler spike'tan: parmak izi < 0,72, dalga < 0,25), Whisper söz kapısı,
  süre kapısı; FastAPI sayfası: oynatıcı, onay, bölge onarımı (bas–son), ret, not.

### Faz 5: Yükleme paketi ✅
- **Durum:** mastering (gerçek şarkıda −14,0 LUFS / −1,01 dBTP), kapak, metadata, YUKLE.md hazır. Kalan: sanatçı adı ve
  dağıtımcı (Scryne: "o noktaya gelince"), dağıtımcıya özel form sırası.
- **İşler:** mastering, kapak, metadata (başlık orijinalle aynı, orijinal sanatçı adı başlık/kapakta yok, yazarlar
  publishing alanında, AI beyanı, cover işareti), `YUKLE.md` (form alanları sırayla, kopyala-yapıştır).
- **Önce:** Scryne'dan sanatçı adı ve dağıtımcı seçimi.
- **2026-10-07:** dağıtımcı taraması `docs/arastirma/02`: tam AI cover için kalan adaylar DistroKid (AI beyanını
  Spotify'a ileten tek dağıtımcı), RouteNote (ücretsiz, FLAC), Ditto; CD Baby, Amuse, LANDR, UnitedMasters, Soundrop
  eleniyor. Paket dağıtımcıya göre biçim seçiyor (RouteNote → FLAC) ve YUKLE.md'ye forma özel notları yazıyor.
- **Karar (Scryne, 2026-10-07):** RouteNote, mekanik lisans alınmadan → ABD/CA/MX/IN/PK bölgeleri çıkarılır.
  Sanatçı adı: **Orvane** (Scryne, 2026-10-07).
- **Paketler (2026-10-07):** üç şarkı FLAC 16 bit / 44,1 kHz, 3000×3000 kapak, −14,2…−13,8 LUFS. Doğrusal loudnorm
  iki şarkıda −0,94 / −0,97 dBTP verdi (sınır −1) → hedef −1,2; yeniden pakette −1,14…−2,15 dBTP.
- **Sonuç:** üç paket Orvane adıyla, eksik kararsız (YUKLE.md'de "Eksik karar" yok). RouteNote formunun alan sırasıyla
  birebir karşılaştırma formu görmeden yapılamaz → ilk gerçek yüklemede (Faz 7) doğrulanır, sapma olursa YUKLE.md düzelir.

### Faz 6: Kalite turu ✅
- **Eklenen (Faz 3'ten):** dinleme sayfasında stil tanımını düzenleyip yeniden üretme (otomatik tanım genel kalıyor).
  **Yapıldı (2026-10-07, `70ab4d0`):** yeni adaylar eskilerin ardından numaralanır, adayın stili kayıtlı.
- **S12 (2026-10-07):** aynı 45 sn kesitte (Adele 0:40–1:25) tek kol değişen 9 varyant: tarif, shift 3, ADG, CFG 9,
  CFG 5, Heun, hız kırpma 2, shift 3 + ADG, temiz söz (LRCLIB'nin `♪` satırları söz olarak gidiyordu, şarkı tek
  `[verse]`). Varyant başı ~70 sn (Heun 130). Dinleme: `calisma/dinleme/s12/`. Hepsi kapılardan geçti; örnekleme
  kolları söz WER'ini oynatmadı (0,085–0,127, tarif 0,099), **temiz söz 0,042** (aynı referansla ölçüldü: yarıya
  indi). Tek tohum, tek kesit.
  **Karar (Scryne dinledi):** "çok az nefes yerlerinde ve mırıldanmalarda kötü, onun dışında gayet güzel" → temiz söz
  hatta (`sozler.aralik_sozu`; parça, onarım penceresi ve tam söz aynı kuraldan; Adele kesitinde dinlenen metinle birebir).
  Kalan: nefes ve mırıldanma yerleri (bölge onarımı + sıradaki denemeler).
- **S13 (2026-10-07):** temiz söz üstünde tohum, güç, CFG, net vokal stili. Örnekleme kolları ve stil eki tohumdan
  küçük ve tutarsız (`docs/arastirma/01`); tarif değişmedi. Tohum en büyük kol → aday sayısını artırmak (2 → 3–4)
  dinleme yükü karşılığında daha çok şans; dinleme: `calisma/dinleme/s13/`.
  Scryne: taban ile net vokal stili neredeyse aynı, taban bazı yerlerde daha iyi → stil eki elendi.
  **Karar (Scryne kararı bana bıraktı):** aday sayısı 3, tohumlar 42 / 7 / 123 (gece şarkı başı ~30 dk).
- **Yeniden üretim (2026-10-07, `yanki yeniden`):** onaylı üç şarkıya temiz söz + 3 aday (3–5); 27 iş ~70 dk, hepsi
  kapıdan geçti. En iyi söz WER'i eski seçili → yeni: Adele 0,033 → 0,015 (aday 4), Coldplay 0,109 → 0,032 (aday 4),
  Ed Sheeran 0,121 → 0,131 (aday 5; iyileşme yok, yeni adaylar 0,131–0,211). Seçim Scryne'ın kulağında.
- **Sonuç:** Scryne Adele aday 4'ü (temiz söz, tohum 7, WER 0,015) yükleme için onayladı → paket Orvane adıyla,
  metadata'da kaynak aday yazılı (−13,8 LUFS / −1,19 dBTP). Coldplay ve Ed Sheeran seçim bekliyor; eski paketleri
  `paket_onceki/`'de (yanlışlıkla yüklenmesin). Açık kalan denemeler (vokal son işlemi, LoRA) gerçek kullanımdan sonra.
- **Denenecekler:** tohum/aday sayısı, stil tanımı varyantları, adım/kaydırma (`shift`), güç 0,6–0,8 şarkıya göre,
  vokal izi son işlemi (nefes/sibilans), LoRA (8–20 şarkı) ihtiyacı.

### Faz 7: Gerçek kullanım 🔄
- **İlk yükleme (2026-10-08):** Scryne Adele "Someone Like You"yu (aday 4) RouteNote'a gönderdi. UPC
  `5064150700802`, ISRC `GXM2X2626596` (RouteNote atadı), yayın tarihi 2026-10-28, mekanik lisans yok → ABD/CA/MX/IN/PK
  hariç. Kaldırılan mağazalar: Amazon, Kore (Melon, Bugs!, VIBE, FLO, Genie), YouTube Content ID. `yanki yuklendi`
  ile işaretlendi; ayrıntılar paketin `metadata.json` → `yukleme`.
- **Form bulguları → `YUKLE.md` (RouteNote) artık ekranın sırasıyla:** 4 adım (Album Details, Add Audio, Add Artwork,
  Manage Stores). Paketin tahmin ettiği sıradan sapmalar: yazarlar ad + soyad ister (MusicBrainz "Adele" → Adkins
  elle); söz varsa Lyricist ayrıca; Contributors zorunlu (Producer = sanatçı); © (beste) ve ℗ (kayıt) satırları ayrı;
  sanatçı listeden seçilmezse "Primary Artist field is required"; parça düzeyinde cover sorusu varsayılan **No** ve
  ardından mekanik lisans sorusu; preview başlangıcı (nakarat, `soz_zaman.json`'dan otomatik); Content ID sound-alike
  kabul etmiyor. 1–4. adımlarda yapay zekâ sorusu çıkmadı.
- **Kapak:** Scryne üretilen kapak yerine kendi seçtiği fotoğrafı kullandı (691 px → 3000 büyütüldü). Şarkı klasöründe
  `kapak_ozel.jpg` varsa paket onu kullanır, yoksa dalga formundan üretir.
- **Sürekli üretim (2026-10-08, Scryne: "Adele'yi beklemeyelim, sürekli üretelim; her şeyi sana bırakıyorum"):**
  listeye 12 şarkı (tek solo vokal, piyano/akustik balad; seçim Claude). Stil elle; BPM/ton yalnız librosa ölçümü ile
  bilinen değer uyuşunca (ölçüm Someone Like You / Viva La Vida / Perfect tonlarıyla sınandı), uyuşmayan boş.
- **Gece hattı düzeltmeleri (ilk gerçek gece koşusu):** `\Yanki\Gece` hiç çalışmamıştı (`pwsh.exe` zamanlayıcıda yok,
  0x80070002) → `powershell.exe`; ardından Windows Terminal varsayılan terminal olduğundan `-WindowStyle Hidden` pencere
  açtı, pencere kapanınca motor "window-CLOSE event" ile öldü → `conhost --headless` (`scripts/gorev_kur.ps1`). 5.1'de
  boru hattındaki `Add-Content` günlüğü kilitliyordu → satır satır yazım + konsol UTF-8. YouTube ilk parçada 0 bayt
  (12'de 2) → 3 deneme. Paket sözlerden açık içeriği işaretler (drivers license → Explicit).
- **Koşu sonucu (01:32–05:44, 4 sa 12 dk):** 114 motor işi (tur 1: 36, tur 2: 78) hepsi başarılı, VRAM tepe 7,5 GB;
  36 adayın 35'i kapıdan geçti (The Scientist aday 3 söz WER 0,643). Şarkı başı en iyi söz WER (aday): Keane 0,015 (3),
  Lewis Capaldi 0,025 (2), Lana Del Rey 0,036 (3), Adele WWWY 0,041 (2), Tom Odell 0,058 (1), The Scientist 0,060 (1),
  drivers license 0,062 (1), All of Me 0,067 (2), James Arthur 0,073 (1), A Thousand Years 0,105 (2), Calum Scott
  0,145 (3), Fix You 0,278 (2; üç aday da 0,28–0,39, zayıf). WER ±0,04 oynuyor → sıralama yalnız dinleme sırası önerisi.
  BPM/ton verilenlerin medyanı ~0,06; kontrollü karşılaştırma değil (şarkılar farklı), sonuç çıkarılmadı.
- **Hızlı karşılaştırma (2026-10-08):** darboğaz üretim değil dinleme (gece 36 aday; tam dinleme şarkı başı ~15 dk).
  Dinleme sayfasının üstünde panel: 3 kesit (ilk kıta, nakarat, son nakarat; 30 sn, `sozler.kesitler` kaynağın söz
  zamanından), adaylar söz WER'ine göre sıralı, 0–9 ile aynı konumda iz değişir (orijinal 0), `S` aynı kesiti her
  adayda arka arkaya çalar, onay/ret sonrası dinlemedeki sıradaki şarkı açılır, kuyrukta "N şarkı dinlemede".
  Nakarat kıta etiketinden değil "≥ 3 tekrarlanan ilk satır"dan: kıta etiketi 15 şarkının 12'sinde nakaratı bulmadı
  (LRCLIB kaydında `♪` yok, şarkı tek kıta), satır kuralı 15'te 15. Tarayıcıda kopya `calisma` üstünde sınandı.
- **S14 (2026-10-08):** nefes/mırıldanma yerini Whisper kelime güveniyle otomatik bulma denendi, **tutmadı**
  (Scryne'ın işaretlediği aralıkta kelimeler 0,78–1,0 güvenle duyuluyor; `docs/arastirma/01`). Otomatik işaretleme
  10–20 gerçek onarım etiketi birikince başka sinyallerle yeniden denenir.
- **Bekleyen:** RouteNote incelemesi → kabul/red → Spotify'da dinlenebilir (bitti kriteri). Scryne'ın dinleyip onayı:
  12 yeni şarkı + Viva La Vida + Perfect; onaylananları gece koşusu paketler.
- **Toplu onay (2026-10-08 14:32–14:40):** Scryne hızlı karşılaştırma paneliyle 14 şarkının hepsini ~7,5 dk'da
  onayladı (şarkı başı ~30 sn; tam dinlemede ~15 dk). Seçimlerin yarısı en düşük söz WER'li aday değil → sıralama
  kulağın yerini tutmuyor, yalnız sıra önerisi. Söz WER'i yüksek seçimler: James Arthur aday 2 (0,359; en iyi 0,073),
  Fix You aday 2 (0,278), Christina Perri aday 1 (0,209), Calum Scott aday 1 (0,19). `yanki paketle` elle: 14 paket
  −14,0 ± 0,1 LUFS, tepe ≤ −1,16 dBTP, kapak 3000×3000, 2 Explicit (drivers license, Another Love).
- **Yükleme sırası (2026-10-08):** ilk kabul gelene kadar RouteNote'a en fazla 1–2 şarkı daha; red gelirse ilk
  şüpheli kapak (Pinterest fotoğrafı, 691 → 3000 px), ikincisi yapay zekâ cover'ı. Yedek dağıtımcı `docs/arastirma/02`.
- **İkinci ve üçüncü yükleme (2026-10-08):** Calum Scott "You Are the Reason" (UPC `5064150844124`, ISRC
  `GXM2X2616305`, yayın 2026-11-04, preview 0:53) ve Coldplay "The Scientist" (UPC `5064150768260`, ISRC
  `GXM2X2610493`, yayın 2026-11-11, preview 1:20); bölge/mağaza hariçleri Adele ile aynı. Formu Claude Chrome
  eklentisiyle doldurdu, son "Distribute Free"yi Scryne bastı → Discography "In Review (3)", taslak kopyası yok.
  Kapaklar yine Scryne'ın seçtiği Pinterest fotoğrafları (kedi 700 px, sahil 982×552 → 552 kare; 3000'e büyütüldü),
  risk iki kez söylendi, karar Scryne'ın. Kapak şüphesi üç yayında ortak → red gelirse kapak ayrıştırılamaz.
- **Tarayıcıyla yükleme bulguları:** eklentinin dosya sınırı 10 MB/mesaj → FLAC 9 MB'lık parçalara bölünüp sayfada
  `Blob`'la birleştirildi, SHA-256 orijinalle aynı. "Distribute Free" yerel `confirm()` açıyor, eklenti geçemiyor →
  son tık insanda. Sanatçı her yayında "Create a new profile" ile Orvane; "mevcut profil" seçeneği çıkmadı → kabul
  gelince Spotify'da üç parçanın tek Orvane profilinde toplandığına bak. Paket hatası: `orijinal_yil` yeniden
  yayının ISRC'sinden geliyor (Keane 2021 → 2004, The Scientist 2003 → 2002, John Legend 2018 → 2013); Lewis
  Capaldi ve Adele WWWY yazarlarında "SOYAD?" boşluğu. İkisi de sonraki yüklemeden önce düzeltilir.
  **Düzeltildi (2026-10-08, `26cf90a`):** yıl eşleşen kayıtların en erkeninden; yazar ad/soyadı MusicBrainz sıralama
  adından ("Del Rey, Lana"), tek sözcüklü sahne adında yasal ad (Adele → Adkins, RØMANS → Samuel Elliot Roman);
  başlık eşleşmesi tipografik kesme işaretini tanıyor (James Arthur paketinde yazar hiç yoktu, şimdi 7). `yanki kunye`
  ile 15 şarkı yenilendi, 12 bekleyen paket yeniden üretildi; hiçbirinde SOYAD?/EKSİK yok.

### Faz 8: Kalite ve düzenli yayın ⏳
- **S15–S16 (2026-10-08, RouteNote incelemesi beklenirken):** DCW çıktıyı bozuyor (elendi), SDE sözü bozuyor; CFG
  aralığı, hız EMA'sı ve kaynağın vokal/eşlik dengesi (Demucs) ölçüde tabandan ayrışmıyor → Scryne'ın dinlemesi:
  `calisma/dinleme/s15/`, `calisma/dinleme/s16/` (her kol iki tohum, `0_taban_t42/t7` ile).
- **S15/S16 dinlendi (Scryne, 2026-10-08):** belirgin kazanan yok; tarif değişmedi.
- **S17 (2026-10-08):** mırıldanma "şarkıcının sustuğu yerde vokal" değil; etiketli aralıkta orijinal de söylüyor →
  kısma/geçitleme tipi son işlem kusuru düzeltmez, yapılmadı (`docs/arastirma/01`).
- **S18 (2026-10-08; FP8 hazır, bf16 yarım):** bf16 önce VAE çözmede 48 dk takıldı (DiT 8 GB'ı dolduruyor → `dit_offload`), sonra DiT RAM'e alınınca sistem belleği yetmedi, 3/100 adımda durdu; FP8 dinlenince yeniden açılır. INT8 niceleme mi? FP8 (105–113 sn/iş, 7,7 GB) ve bf16 (~32 sn/adım, iş başı ~53 dk)
  aynı kesit ve tohumlarla; dinleme `calisma/dinleme/s18/`. bf16 belirgin iyiyse yerel tam şarkı imkânsız (aday başı
  saatler) → kiralık 24 GB GPU kararı Scryne'ın (maliyet). FP8 iyiyse bedava geçiş.
- **Sonraki adaylar (sırayla):** MPEcho (SongEcho + fonem kodlayıcı, ACE-Step tabanlı, bulanık heceyi hedefliyor; taban
  sürüm, dil ve 8 GB'a sığma doğrulanmadı); onarım akışını ucuzlatmak (hızlı panelde aralık işaretleme, gece aralık
  başına daha çok tohum: onarım tek çalışan düzeltme). `cover_noise_strength` denenmez: kaynağın gizil sesinden başlar,
  orijinal kaydı taşır. LoRA en son.
- Faz 7'de açık kalan denemelerin sahibi: vokal izi son işlemi (nefes/sibilans), LoRA (8–20 şarkı) ihtiyacı,
  otomatik kusur işaretleme (S14: Whisper güveni tutmadı; onarım etiketleri birikince yeniden).
- Kabul gelince düzenli yayın: onaylı paketlerden takvim (haftada bir), her yüklemenin bulgusu `YUKLE.md`'ye.
- Zayıf şarkılar (Fix You: üç aday da söz WER 0,28–0,39) stil düzenleme ya da yeni tohumlarla yeniden.

### Faz 9: Kaldırılmış şarkı keşfi ve yayın takibi 🔄
- **Karar (Scryne, 2026-10-09):** şarkı kaynağı Spotify'dan kaldırılmış şarkılar; aranan ama bulunamayan şarkının
  cover'ı aramada üste çıksın. Fikir arkadaşın aracı STILLMORE FINDER'dan (playlist'te kaldırılmış şarkı bulucu);
  Scryne: "her şeyi sana bırakıyorum", aracı daha iyi hâle getirme yetkisi.
- **Analiz (`docs/arastirma/03`):** STILLMORE Spotify istemcisinin içinden (Spicetify) çalışıyor; Store sürümü
  Spotify, Spicetify yaması ve Virus Records lisansı ister. Yanki bunlara bağlanmadı: sözleşme CSV dışa aktarımı.
  Spotify Web API Şubat 2026'dan beri başkasının playlist'ini vermiyor (403), arama sayfası 10, sahibin Premium'u şart.
- **Yapıldı (2026-10-09):** `yanki/spotify.py` (client credentials + PKCE, 429'da `Sinirli`, `/items`),
  `yanki/kesif.py` (STILLMORE CSV, kendi playlist, boşluk doğrulama: aynı ISRC ya da aynı sanatçı + ad çalınabilir
  mi, rakip cover sayısı; talep: YouTube izlenmesi; sıra izlenme / (1 + rakip); `--ekle N`), `yanki/takip.py`
  (ISRC → canlı, ad araması → sıra, Orvane profili tek mi; `yuklendi → yayinda`, kayıp işareti), `config/kesif.toml`,
  gece koşusu takip eder (anahtar yoksa atlar) ve `gece_ekle > 0` ise keşfeder. 23 yeni test (sahte Spotify,
  STILLMORE başlığı birebir); testler gerçek bir hata buldu (YouTube başlığındaki "Sanatçı - Şarkı" sonek sanılıp
  siliniyordu). Canlı: YouTube talep ölçümü doğru (Adele 2,58 milyar, "Gülümse" 6,95 milyon); CSV → kayıt → liste
  akışı anahtarsız uçtan uca çalıştı, doğrulanmamış aday listeye girmedi.
- **Canlı (2026-10-09, Scryne'ın Spotify uygulaması):** token, ISRC ve ad araması, `is_playable: false` doğrulandı;
  `restrictions.reason` kaldırılmışı ayırmıyor ("market") → US/GB/DE kontrolü eklendi. Boşluk doğrulama Adele SLY'yi
  doğru eledi (rakip 4). `yanki takip`: üç yükleme yayın tarihinden önce, canlı değil.
- **İlk gerçek keşif (2026-10-09, Scryne'ın 13 kendi playlist'i, 2.166 parça):** `/items` + PKCE canlıda çalıştı.
  70 çalınamayan → 55 benzersiz; çoğu cover adayı değil: takma adla yüklenmiş Lana Del Rey sızıntıları ("Lizzy Rey",
  "Del", "EVE !"…), sped up/slowed/remix düzenlemeleri, oyun müziği hayran yüklemeleri, 18 dk sözsüz parça (GY!BE).
  Eklenen filtreler (canlı veriyle bulundu): düzenleme adı; sanatçı YouTube başlığında bütün hâlde ("Del" ≠ "Lana Del
  Rey"; ayraçlar " - ", "- ", "||", boşluksuz tire); LRCLIB'de sözlü kayıt ve ≤ 420 sn. Kalan 3 aday listeye eklendi
  ve hazırlandı (HAARPER "Cadavers in My Cadillac" YouTube 77 bin / rakip 0, 1nonly "Cotton Candy Swirls" 23 bin / 1,
  Day$okee "MAMACITA" 55 bin / 5): üçü de rap, hattın rap'te ilk denemesi.
- **Sonuç:** Scryne'ın playlist'leri zayıf kaynak (55'te 3, talep düşük). Büyük, eski playlist'lerin STILLMORE
  CSV'si gerekiyor (arkadaştan) → `girdi/kesif/`. İlk Türkçe adayda Türkçe cover dinleme
  testi (ACE-Step'te denenmedi). Sıra formülü ilk yayınların arama sırasıyla düzeltilir.
- **Kendi keşfimiz ve global (Scryne, 2026-10-09: "kendimiz yapamaz mıyız", "sadece TR'ye bakma, global"):**
  - `yanki/katalog.py`, **Deezer katalog farkı**: Deezer'da çok dinlenen (rank) ama Spotify'da kapalı/olmayan
    şarkılar; tohum öncelik sırası elle (kataloğunu çekenler) → playlist sanatçıları → benzerleri → tür listeleri.
    İlk koşu: bütçe 146 güncel hite gitti, hepsi Spotify'da → öncelik sırası eklendi. Deezer listeleri IP'ye göre
    (bu ağda Fransa). Apple Music RSS denendi: aynı adres bazen cevap veriyor bazen vermiyor, kullanılmadı.
  - **Pazar seti** (`config/kesif.toml`, US/GB/DE/FR/BR/MX/JP/TR): kaldırılmış / kısmen kapalı / Spotify'da yok;
    puan kapalı pazar oranıyla. Takipte arama sırası yayınladığımız pazarlarda tek tek.
  - **Spotify kotası:** bir günde ~1.000 istekte 23 saatlik 429 (Retry-After 83.595). Kalıcı kilit
    (`calisma/.spotify_kota.json`, kilitliyken hiç istek yok), günlük tavan 400, ücretsiz elemeler (YouTube, sanatçı,
    LRCLIB) Spotify'dan önce (57 aday → ~5 Spotify'a), playlist snapshot önbelleği, ölçüm/doğrulama ayrı zamanlı.
    Kilitli koşu 15 sn, sıfır istek, çökmüyor (canlı denendi).
  - **Çok dilli hat:** dil `"en"` sabitti, söz kapısı small.en + a-z normalleştirme. Şimdi kaynak sesten dil tespiti
    (Whisper small; canlı: Adele en 0,93, HAARPER en 0,95, Gülümse tr 0,94, Stromae fr 0,93), ACE-Step'e doğru dil,
    İngilizce dışında çok dilli döküm + Unicode normalleştirme. Gülümse orijinal kaydı: eski kapı WER 1,0 (düşerdi),
    yeni 0,238. Paket formuna dil adı.
  - **Stil yedeği:** MusicBrainz türü yoksa Deezer albüm türleri (üç rap şarkısı "clean modern studio recording" →
    "rap, hip hop song, …").
  - **Dinleme odası:** Keşif (süzgeç, rozet, talep/rakip/pazar, Dinle/Listeye ekle/Ele; elenen gece eklenmez) ve
    Yayın (durum, çıkış, pazar pazar sıra, profil bölünmesi) görünümleri; görsel doğrulama 24 kare 0 sorun.
  - Gece: `gece_ekle = 2` (doğrulanmış en iyi iki aday kendiliğinden listeye). İlk otomatik ekleme Spotify kilidi
    kalkınca (2026-10-10 ~16:00) sonraki gece.
- **Özgünlük kararı TypeSafe (Jev), 2026-10-09:** regex sanatçı eşleşmesi bir günde dört kez yamandı. Spike
  (jev-1.13.0, 30 elle etiketli örnek, `docs/arastirma/03`): "listedeki sanatçı ≥ 0,90 ve hayran < 0,5" kuralıyla 20
  sızıntı/hayran örneğinde sıfır yanlış kabul; regex'in kaçırdığı Vinnie Vincent Invasion'ı (0,98) buldu, regex'in
  kabul ettiği Vipraz "Ainsi Bas La Vida"yı (Indila'nın şarkısı) reddetti. `yanki/yargi.py`, resmi SDK, kanıt ve karar
  model sürümüyle adaya dondurulur, anahtar yoksa regex yedeği. Kayıttaki 55 aday yeniden ölçüldü: 4 kabul, 8 belirsiz
  (kendiliğinden eklenmez), 4 hayran yapımı, 23 başka sanatçının. Yeni lider: Vinnie Vincent Invasion "Love Kills"
  (678 bin, rakip 4; önceki Spotify doğrulamasıyla 2026-10-10 gecesi kendiliğinden listeye girer).
- **STILLMORE bu makinede kuruldu (2026-10-09):** Scryne Spotify'ı klasik sürüme geçirdi (1.3.4); Spicetify 2.45.3
  (winget + upgrade), `C:\df-archive`'den kurulum betiği; eklenti Spotify içinde yüklü (CDP: "[ODF] STILLMORE FINDER
  loaded … 139 records"), STILLMORE sayfası menüde. Spotify güncellemesi yamayı siler → `\STILLMORE\Onarim` görevi
  (oturum açılışı + her gün 12:00) yama silinmişse kurulumu Spotify'ı yeniden başlatmadan tekrarlar; silme taklit
  edilip onarım doğrulandı. Keşif için CSV artık Scryne'ın kendi Spotify'ından: playlist → "Kaldırılmış şarkıları
  bul" → "CSV indir" → `girdi/kesif/`.
- **STILLMORE köprüsü (2026-10-09, `yanki/stillmore.py`):** Yanki, Spotify istemcisindeki STILLMORE'a CDP ile
  `Stillmore.playlist.scan` yaptırıyor: başkasının ve editoryal playlist'ler, kaldırılmadan önceki Spotify dinlenmesi,
  ISRC, yeniden yükleme. CSV indirmeye gerek kalmadı, Web API kotası harcanmıyor. Gece koşusu Spotify'ı bayrakla açar
  (çalıyorsa dokunmaz, açıktıysa sonra bayraksız geri açar). Havuz: config + Web API playlist araması (gece 2 sorgu,
  ≥ 100 parça), her gece en uzun süredir taranmamış 3 playlist (`calisma/kesif/stillmore.json`). Canlı: "suwi" 40
  çalınamayan (Web API ile aynı), takip edilen "Musica brazilian fivem"de Menor Teteu "Ai Ai Ai Bebe" kaldırılmadan
  önce 35,7 milyon dinlenme (Web API bu playlist'i okuyamıyordu); sızıntılarda dinlenme 0. Talep artık
  max(YouTube izlenmesi, Spotify dinlenmesi).
- **Oturum açılınca Yanki (Scryne, 2026-10-09):** `\Yanki\Oda` görevi dinleme odasını arka planda açar
  (127.0.0.1:8765) ve özeti Windows bildirimiyle gösterir (`yanki ozet`); elle tetiklenip doğrulandı. Oda `python -m`
  ile çalışır: `yanki.exe` açıkken kilitleniyor, bağımlılık değişince `uv` senkronu düşüyordu (bulundu, düzeltildi).

### Faz 10: Tam otomatik yayın (dağıtım API'si) ⛔
- **Tunearo kapandı (2026-10-12, Scryne):** API artık yok, yüklenen 21 şarkı reddedildi. Yayınlananlar silindi: klasörleri
  `calisma/_arsiv/2026-10-12-yayin-silindi/`'e, liste kayıtları oradaki `liste_onceki.toml`'a (geri alınabilir);
  `dagitimci = ""` (otomatik yükleme yok). Üretim en iyi haline gelince keşiften yayına baştan kurulacak; dağıtımcı
  seçimi Scryne'ın. S20 deneme şarkılarının kaynağı `calisma/_referans/`'ta (eğitim denemesi oradan okur).
- **Engel (2026-10-11 12:47):** Tunearo API erişimi hesap sahibince kapatıldı (`403 API access not enabled for this user`); 21 yayın incelemede, durum okunamıyor, yükleme yok. Hat bekliyor, erişim açılınca kendiliğinden sürer (Denetim 4).
Hedef (Scryne, 2026-10-09): "arkadaşımın API'si gelince her şeyin otomatik olması". Uçtan uca: keşif → üretim →
onay (insan ya da veto penceresi) → paket → API ile yükleme → durum izleme → takip. İnsan yalnız dinler ve isterse
veto eder.
- **Dağıtım arayüzü** `yanki/dagitim/`: `Dagitimci` protokolü (`yukle(paket) → YuklemeKimligi`,
  `durum(kimlik) → inceleme | kabul | red(neden) | canli(upc, isrc)`, `kaldir`). Uygulamalar: `routenote` (bugünkü elle
  akış: YUKLE.md üretir, `yanki yuklendi` bekler) ve arkadaşın API'si. Hangi dağıtımcının kullanılacağı
  `config/yayin.toml`'da; paket biçimi dağıtımcıya göre (bugün olduğu gibi).
- **API gelince ilk iş (yarım gün):** dokümanı oku → kimlik doğrulama, yükleme alanları, AI/cover kuralları
  (operasyonel), bölge/mağaza seçimi, ses/kapak biçimi, oran sınırı; sandbox ya da tek parçalık gerçek deneme;
  RouteNote formundaki alanların (yazarlar ad+soyad, © ℗ ayrı, preview başlangıcı) API karşılıkları.
- **Yayın takvimi:** `paketlendi` şarkılardan kuyruk (öncelik keşif puanı; keşifsiz liste şarkıları sonra), günlük/
  haftalık sınır (`config/yayin.toml` → `takvim`), yayın tarihi otomatik (+N gün, dağıtımcının asgarisi). Bugün 12
  paket bekliyor: ilk kabul gelince takvim bunları sırayla eritir.
- **Durum yoklama:** gece koşusu yüklenenlerin durumunu sorar; red nedeni `durum.json`'a ve keşfe geri besleme
  (aynı nedenle reddedilen sanatçı/eser bir daha önerilmez). Kabulde UPC/ISRC `metadata.json` → `yukleme`, ardından
  `yanki takip` canlılığı ve arama sırasını izler (Faz 9).
- **Veto penceresi (otomatik onay):** kapılardan geçen adaylar arasından öneri (bugün söz WER'i; Faz 12'de seçim
  modeli) `dinlemede` olarak bekler; Scryne N saat (varsayılan 72) içinde onaylamaz ya da reddetmezse öneri onaylanır.
  `config/yayin.toml` → `otomatik_onay`; açılmadan önce Faz 12'deki isabet ölçümü. Bildirim: "X şarkı 24 saat sonra
  kendiliğinden onaylanacak".
- **Kapak:** bugün Scryne Pinterest fotoğrafı seçiyor (red riski, iki kez söylendi). Otomatik yolda üretilen tipografik
  kapak varsayılan; görsel kapak üretimi (yerel model ya da şablon havuzu) ayrı deneme.
- **Önce:** arkadaşın API dokümanı. RouteNote incelemesinin sonucu (kabul/red) bu fazın dağıtımcı seçimini etkiler.

- **Dağıtım arayüzü ve takvim (yapıldı, 2026-10-09, `yanki/dagitim.py`):** `Dagitimci` (`ad`, `otomatik`,
  `yukle`); bugün `ElleRouteNote` (otomatik değil: hat sırası geleni bildirir). Takvim `config/yayin.toml` →
  `[takvim]`: haftada 1, keşif puanı önce sonra onay sırası, yayın tarihi yüklemeden +21 gün, `baslangic =
  "ilk_kabul"` (Faz 7 kararı: ilk kabul gelmeden yükleme yok). `yanki takvim`, gece koşusunda takvim adımı, özet
  satırında "yükleme sırası geldi", dinleme odası Yayın'da sıra. `yanki dagitim-red` reddedileni `paketlendi`ye
  döndürür, yükleme bilgisini `yukleme_gecmisi`'ne taşır; takvim yeniden paketlenene kadar atlar. API gelince:
  `otomatik = True` bir `Dagitimci` + gece koşusunda `yukle` çağrısı (takvim, kuyruk, bildirim aynı).
- **Hazırlık (2026-10-09, API'den bağımsız kısımlar):** veto penceresi `yanki/onay.py` (gece koşusu paketlemeden
  önce; `config/yayin.toml` → `[otomatik_onay]` **kapalı**, 72 sa), dinleme odasında "karar vermezsen … aday N
  kendiliğinden onaylanır" satırı, oturum özetinde "24 saat içinde kendiliğinden onaylanacak" sayısı. Öneri kuralı en
  düşük söz WER (aşağıda Faz 12 ölçümü: kulağı tahmin etmiyor, yalnız "sözü en anlaşılır"ı seçer).

- **API geldi: Tunearo (2026-10-10, `yanki/tunearo.py`, `docs/arastirma/04`):** arkadaşın dağıtım sitesi
  (dashboard.tunearo.com, REST, Bearer anahtar; anahtar `.env`). `config/yayin.toml` → `dagitimci = "tunearo"`;
  RouteNote'taki üç parça orada kalır. Akış: Orvane sanatçısı (hesapta bir kez) → yayın taslağı (Single, tür stilden,
  ©/℗, US/CA/MX/IN/PK hariç, Amazon ve YouTube Content ID hariç 32 mağaza) → kapak → parça (yazarlar, düz söz) → ses
  (FLAC paket WAV'a açılır) → incelemeye gönder. Kaldığı yerden sürer (`metadata.json` → `tunearo`), reddedilen yayın
  aynı kayıtla düzeltilip yeniden gönderilir (hesabın parça kotası yanmaz). `yanki yukle <kimlik> [--taslak]`,
  `yanki dagitim-durum`; gece koşusu takipten önce durumu yoklar (kabulde UPC/ISRC, redde `paketlendi` + bildirim) ve
  takvimde sırası geleni kendisi yükler. `ilk_kabul` artık dağıtımcıya göre: Tunearo ilk parçayı kabul edene kadar
  incelemede en çok bir yükleme, red gelirse neden anlaşılana kadar yok. 23 yeni test (sahte API), toplam 252 yeşil.
  **Canlı (2026-10-10):** Adele "When We Were Young" taslak olarak yüklendi ve API'den geri okundu: tür, söz (1.827
  karakter), kapak, WAV (16 bit / 44,1 kHz, 290,9 sn), bölge/mağaza doğru; tek yayın, tek parça. **İlk gönderim
  (2026-10-10 01:35, Scryne kararı bana bıraktı):** `pending`, yayın tarihi 2026-10-31; takvim kabul gelene kadar
  bekliyor. Canlı bulgular (dokümanda yok): söz POST'ta düşüyor (PATCH'le yazılıyor); depo sesi hep `.wav` adıyla
  saklıyor; tür serbest metin; API'den açılan yayında mağaza listesi boş; önizleme başlangıcı API'de yok; yazar
  alanları tek metin (birden çok yazar ayrı kişi olarak gitmiyor). Webhook herkese açık HTTPS ister → yoklama.
- **Doğrulama (2026-10-10):** bağımsız gözden geçirme üç açık buldu, kapatıldı: gönderim sunucuda olup yerelde
  kaydedilemezse kapı görmüyordu (artık `gonderiliyor` işareti, yarım yükleme kuyruğun başında, reddedilmiş yayın red
  kaydedilmeden yeniden gönderilmez); tek yayının 404/5xx'i bütün yoklamayı durduruyordu; yarım yüklemede yeni tarih
  yazılıyordu. Kendi denetimimden: yeniden paketleme `metadata.json`'daki dağıtım geçmişini siliyordu (aynı yayın
  yeniden gönderilemez, red kapısı kaybolurdu) ve FLAC → WAV geçişinde eski ses kalıyordu; yazarsız cover gönderilmez.
  Her düzeltmenin testi düzeltmesiz kodda kırılıyor. Kuyruktaki 12 paketin YUKLE.md'si Tunearo akışına çevrildi, 12'si
  yükleme ön koşullarından geçti.
- **Yayın tarihi en erkene (Scryne, 2026-10-10):** `yayin_on_gun` 21 → 1. 21 RouteNote'tan kalmıştı (ücretsiz
  inceleme, pitch ≥ 7 gün); hesaptaki canlı Tunearo yayınları açılıştan 1–5 gün sonrasına tarihli, 2–5 gün sonra canlı.
  When We Were Young 21 günlük payla (2026-10-31) gönderilmişti; `pending` yayında tarih değişmiyor (409, `PATCH
  /releases` ve `/metadata`). Red gelirse yeniden gönderimde yeni tarih yazılır; kabul gelirse 31 Ekim kalır (panelden
  arkadaş değiştirebilir).
- **Kapak Pinterest'ten (Scryne, 2026-10-10: "üretilen kapağı istemiyorum, şarkıya göre o modda Pinterest'ten
  görsel"):** `yanki/pinterest.py`, `config/yayin.toml` → `[kapak] kaynak = "pinterest"`. Sorgu stilin mod sözcükleri
  + sözlerde en sık geçen imge (okyanus, yol, yıldızlar…; yoksa türün sahnesi), şarkı/sanatçı adı yok. Resmi API iş
  hesabı istiyor; sitenin arama ucu girişsiz cevap veriyor (başlıksız 403). Görsel açıklamasında insan, yazı, logo ya
  da yazı taşıyan nesne (kitap, dergi, plak, ekran) geçen pin elenir; bir pin iki şarkıda kullanılmaz; en büyük ve
  kareye en yakını. Elle konan `kapak_ozel.jpg` önce gelir. Kuyruktaki 11 paket yeni kapakla yeniden paketlendi (WAV).
  Gözle bakıldı: açıklama süzgeci 11'de 2'yi kaçırdı (dergi kapağı + tarih damgası, okunur kitap sayfası; sonra bir
  dizüstü ekranında çizgi film) → süzgeç sıkılaştırıldı, üçü değiştirildi. Süzgeç kusursuz değil: her yeni kapak
  bildirilir, beğenilmeyen `yanki kapak <kimlik> --yeni`. When We Were Young üretilen kapakla gönderilmişti
  (incelemede değişmiyor). 13 yeni test, toplam 265.
- **Takvim (Scryne, 2026-10-10):** önce "şimdilik yayınlamayalım" (kapatıldı), aynı gece "devam et, her şey
  otomatik çalışsın" → açık; `ilk_kabul` kapısı When We Were Young kabul edilene kadar yeni gönderimi bekletir.
  `\Yanki\Gece` artık bilgisayarı uykudan uyandırıyor (`WakeToRun`, güç planında prizde uyandırma zamanlayıcısı
  açıldı: `RTCWAKE` 2 → 1; pilde kapalı).
- **Otomatik onay açık, 24 saat (Scryne, 2026-10-10: "her şey otomatik çalışsın"; 15'te 4 ölçümü ikinci kez
  gösterildi, 24 saat seçildi):** karar gelmeyen şarkıda en düşük söz WER'li aday gece onaylanır ve bildirilir. İlki
  Cadavers in My Cadillac (aday 3), 2026-10-11 gecesi.
- **Büyüme ayarları (Scryne, 2026-10-10: "en kazançlı, artist hesabım en iyi, dinlenme en yüksek; her şeyi sana
  bırakıyorum"):** araştırma ve kararlar `docs/arastirma/05`. Otomatik onay yalnız denenmiş tür/dilde ve sözü
  anlaşılır adayda (rap, metal, İngilizce dışı kulağa kalır, bildirilir); mağazalarda Amazon açık, parmak izi hak
  kayıtları (Content ID, Rights Manager, Audible Magic) kapalı; Spotify profili Tunearo sanatçısına kendiliğinden
  bağlanır; Tunearo kazancı (yalnız bizim yayınlar) odada. Gece koşusu 2026-10-10: iki rap şarkısının üç adayı da söz
  kapısında kaldı → rap tarifi Faz 12'de; ikisi reddedildi (geri alınabilir).
- **Dinleme odası yenilendi (Scryne, 2026-10-10: "silver/dark glassmorphism, en iyi haline getir"):** `DESIGN.md`
  silver/dark'a çevrildi. Yeni açılış ekranı **Pano**: hattın sinyal zinciri (Keşif → Yayında), senden beklenenler,
  dağıtım, yükleme sırası, kazanç, son gece koşusu, otomasyon ayarları. Kuyrukta ve şarkı ekranında kapaklar, "Başka
  kapak" (Pinterest). Görsel doğrulama ilk koşuda gerçek bir hata buldu: küçük resimler `paket/`'e yazılıyor, kapak
  sanılıp çoğalıyor ve yükleyicinin "pakette tek JPG" kuralını bozuyordu → `calisma/.kapak_onbellek/`, testli. Eski bir
  hata da çıktı (söz zamanı olmayan şarkıda sayfaya "null" yazıyordu). Son koşu 24 kare 0 sorun.
- **Baştan yayın (Scryne, 2026-10-10: "şuanki şarkıların hepsini kaldıralım, en baştan sağlam bir şekilde artist
  hesabımızı yapalım; yayın tarihlerini ileri atma, sürekli şarkı atalım; her şeyi sana bırakıyorum"):**
  - Sorun: Orvane iki dağıtımcıya dağılmıştı. RouteNote'ta üç parça incelemede (yayın 28 Ekim–11 Kasım, her biri
    "Create a new profile" ile: canlıya çıksalar Spotify'da üç ayrı Orvane profili riski), Tunearo'da When We Were
    Young 31 Ekim tarihli ve eski mağaza listesiyle (Rights Manager, Audible Magic açık) incelemede.
  - Karar: tek dağıtımcı Tunearo, tek sanatçı kaydı (`f796ccc7-…`), hiçbir şey canlı değilken temiz başlangıç. Ad
    Orvane kalır: Spotify, Deezer ve MusicBrainz'de aynı adda sanatçı yok (yalnız "Orvane North"), profil çakışması
    riski yok. Tunearo sanatçısına biyografi yazıldı (İngilizce, "AI-assisted" açık).
  - `yanki geri-cek` (`dagitim.geri_cek`, `tunearo.Tunearo.geri_cek`): taslak silinir (`DELETE`), canlı yayına
    takedown; incelemedeki yayın API'den geri çekilemiyor (canlı: takedown 409 "Cannot takedown release in status
    'pending'"; PATCH/DELETE yalnız taslak ve redde) → işaretlenir, yoklama sonuç gelince bitirir (red → aynı yayın
    yeni tarihle yeniden gönderilir, kota yanmaz; canlı → takedown, sonra yeni yayın). Geri çekilen şarkı
    `onaylandi`ya döner, gece güncel ayarlarla (WAV, kapak) yeniden paketlenir. RouteNote'ta API yok: panelden
    kaldırılır, sonra `--kaldirildi`. Yeniden paketleme `tunearo_gecmisi`'ni korur. 6 yeni test, toplam 280.
  - **Takvim sürekli:** her gün bir yükleme (`haftada = 7`), yayın tarihi yüklemeden 1 gün sonra, `baslangic =
    "surekli"`: ilk kabul beklenmez, yalnız düzeltilmemiş bir red yeni yüklemeyi durdurur.
  - Uygulandı: When We Were Young geri çekilmek üzere işaretlendi (pending). A Thousand Years gönderildi (yayın
    2026-10-11, alanlar API'den geri okunup doğrulandı); kuyrukta 10 paket, gece birer birer.
  - Bekleyen: RouteNote'taki üç yayını Scryne panelden kaldırır (tarayıcı eklentisi bağlı değildi), sonra
    `yanki geri-cek <kimlik> --kaldirildi`. When We Were Young için arkadaştan panelden reddetmesi istenirse aynı
    yayın hemen yeni tarihle döner; istenmezse kabul edilip canlıya çıkınca hat takedown ister.
- **Bitti kriterinden kalan:** ilk Tunearo kararı (kabul → UPC/ISRC kaydı, takip; red → neden), takvimin 2 hafta
  kesintisiz işlemesi, veto penceresinin uçtan uca bir şarkıda çalışması (kapalı, Faz 12 ölçümü bekliyor).
- **Risk (Tunearo kalite kontrolü):** hesaptaki iki yayın "derivative work (remix, sample, or cover)" diye
  reddedilmiş (biri orijinal kaydın "Lo-Fi Remix"i, ses eşleşmesi 30, `qc_proof_required`). AI tespiti tek
  başına red değil (canlı bir yayında `ai_detected: true`). Bizim parçalar kopya kapısından geçmiş yeni kayıt; ilk
  gönderimin sonucu bu riski ölçer, takvim o gelene kadar ikinciyi göndermez.

### Faz 11: Öğrenen şarkı seçimi ⏳
Bugünkü puan (YouTube izlenmesi × kapalı pazar oranı / (1 + rakip)) sezgisel; ölçüm geldikçe öğrenen bir seçime
dönüşür. Jev **metnin ne dediğini** yargılar (özgünlük, düzenleme, eşleşme), **ne kadar dinleneceğini** tahmin etmez
(TypeSafe notu: ScryneQuant yön ekseni %49); tahmin, ölçülen yayın sonuçlarıyla kodda kalibre edilir.
- **Talep v2:** güncellik (YouTube izlenme/gün, yükleme tarihi; eski hit ile hâlâ aranan şarkıyı ayırır), Last.fm
  dinleyici/scrobble (ücretsiz anahtar, Scryne açar), Deezer rank (varsa), STILLMORE CSV'sindeki Spotify dinlenmesi.
- **Rekabet v2:** başlık aramasında ilk rakip cover'ın sırası (pazar pazar); rakip zaten 1. sıradaysa boşluk dar.
- **Üretilebilirlik:** tür/dil/vokal başına Scryne'ın onay oranı ve ortalama söz WER'i (`durum.json` geçmişi) → puana
  çarpan; hattın iyi olduğu türler öne çıkar (bugün balad iyi; rap ve Türkçe ilk ölçümde).
- **Geri besleme:** yayın sonrası arama sırası (Faz 9 takip) ve dinlenme (dağıtımcı API'si ya da STILLMORE/
  Soundcharts) → en az 10 yayında hangi özelliğin sonucu açıkladığı; ağırlıklar ölçüme göre (aşırı uydurma yok: basit
  doğrusal/sıralama modeli, kayıtlı).
- **Yeni kaynaklar:** (1) YouTube'da çok izlenen ama Spotify'da olmayan şarkılar: sanatçının resmi kanal videoları ile
  Spotify kataloğu farkı; (2) film/dizi/anime/oyun müzikleri (Jev'in hayran yapımı kararı burada da süzgeç);
  (3) bölgesel boşluklar: bir pazarda kapalı, diğerlerinde açık şarkılar (yalnız kapalı pazarlarda yayın, dağıtımcı
  bölge seçimiyle).
- **Jev genişletme (spike ile):** talep ölçümündeki "bu YouTube sonucu orijinal kayıt mı (cover/remix/canlı değil)"
  kararı regex `ISTENMEYEN` yerine; STILLMORE/Deezer adaylarında "bu bir düzenleme mi" (bugün ad regex'i).

### Faz 12: Kalite otomasyonu ⏳
- **Seçim modeli:** Scryne'ın 17 şarkıdaki seçimleri (hangi aday) ile kapı ölçüleri (söz WER, parmak izi, dalga,
  tohum) arasındaki ilişki; otomatik seçimin isabeti kayıtlı. ≥ %70 ise veto penceresinde öneri bu model; değilse söz
  WER'i ve insan.
  **İlk ölçüm (2026-10-09, 15 şarkı):** en düşük söz WER 4/15 (%27; şarkı başı ~3,4 aday, rastgele ~%29), en düşük
  dalga korelasyonu 7/15, en düşük parmak izi 7/15 (%47), tohum her biri 5/15. Kapı ölçüleri kulağı açıklamıyor →
  model için yeni özellikler gerekir (vokal netliği, nefes/mırıldanma bölgesi sayısı, Jev ile değil sesle ölçülen) ya
  da daha çok seçim verisi; o zamana kadar veto penceresi kapalı kalır.
- **Tür/dil tarifi:** rap (HAARPER, 1nonly, Day$okee, 2026-10-10 gecesi ilk üretim) ve ilk Türkçe/Fransızca aday için
  stil/güç/adım dinleme testi; gerekirse tür başına `config/motor.toml` profili.
- Faz 8'den devralınanlar: vokal son işlemi, LoRA ihtiyacı, onarım etiketleriyle otomatik kusur işaretleme.

### Faz 13: Operasyon ve dayanıklılık 🔄
- **Disk:** reddedilen/eski adayların sesleri (aday başı onlarca MB) N gün sonra silinir, onaylı + paket kalır; yedek
  (`durum.json`'lar, paketler, `calisma/kesif/`) haftalık.
  **Yapıldı (2026-10-09):** `yanki temizle [--uygula] [--gun 14]` (`yanki/temizlik.py`): yalnız yüklenmiş ve
  yüklemesinin üstünden 14 gün geçmiş şarkılarda seçilmeyen adaylar, kabul edilmeyen onarımlar ve parçalar; seçilen
  aday, paket, kaynak kalır. Gece koşusu sonunda uygular. Ön izleme: yüklü üç şarkıdan 693 MB (ilk silme ~2026-10-22).
  **Yedek (yapıldı, 2026-10-09):** `yanki yedekle` (`yanki/yedek.py`, `config/operasyon.toml`): şarkıların
  `durum.json`'u, sözler, paket `metadata.json`/`YUKLE.md`, özel kapaklar, keşif kaydı, liste, ayarlar; ses ve sır
  yok. Gece koşusu haftada bir alır, en yeni 8 kalır. İlk gerçek yedek 95 dosya, 6,2 MB. Klasör aynı diskte
  (`calisma/yedek`); başka diske almak Scryne'ın kararı.
- **Bildirim (yapıldı, 2026-10-09):** `scripts/bildirim.ps1` ortak; gece koşusu bitince özet, hata verirse kod +
  günlük yolu; oturum açılışında özet (`\Yanki\Oda`).
- **Bildirim:** oturum açılış özeti var (`\Yanki\Oda`). **Yapıldı (2026-10-09):** gece koşusu adımları yalıtıldı,
  sorunlu adım koşuyu 1 ile bitirir → "gece koşusu hata verdi" bildirimi; özet satırında Spotify kilidi ("Spotify
  kilitli (~19 sa)"). **Yapıldı (2026-10-09, `yanki/olay.py`):** yayına çıktı, en iyi arama sırası değişti,
  Spotify'dan kalktı, yayın tarihi +3 gün geçtiği halde yok (dağıtımcı reddi/gecikme şüphesi; RouteNote'ta API yok,
  red e-postayla geliyor → `yanki dagitim-red`), takvimde yükleme sırası geldi, gündüz üretimi bitti. Her olay
  `calisma/olaylar.jsonl`'a, tekrar anahtarıyla bir kez bildirilir; dinleme odası Yayın'da son bildirimler.
  Zamanlayıcıdan gerçek bildirim denendi.
- **Gündüz boşta üretim (yapıldı, 2026-10-09):** `yanki gunduz` + `\Yanki\Gunduz` (08:00'den 17 saat, her 30 dk):
  20 dk klavye/fare yoksa (GetLastInputInfo), prizdeyse ve GPU eşiğin altındaysa kuyruktan bir şarkı (önce bekleyen
  onarımlar); 01:00'den sonra başlamaz (03:00 gece koşusu kilide takılmasın), 2 saat sınırı. Zamanlayıcıdan elle
  tetiklendi: "kullanıcı etkin (8 dk boşta)" ile doğru çıktı. İlk gerçek gündüz üretimi bekleniyor.
- **Kota bütçeleri:** Spotify günlük 400 (2026-10-09 kilidinden). **Yapıldı:** dış servis sayaçları (`yanki/sayac.py`):
  koşu sonunda istek/hata özeti, günlük toplam `calisma/gunluk/servisler.json` (90 gün).
- **Karar bekleyen (Scryne):** (1) sanatçı kimliği: tüm tür ve diller tek "Orvane" mı, tür/dil başına ayrı ad mı
  (Spotify'ın öneri algoritması profilin tutarlılığına bakıyor); (2) tam global: mekanik lisanslı dağıtımla ABD/
  Kanada/Meksika/Hindistan/Pakistan (maliyet).

## Denetim (2026-10-09, Scryne: "baştan sona incele, eksikleri ve hataları çöz")

Kodun tamamı okundu; bulgular ve çözümleri (testler `tests/test_dayaniklilik.py`; yeni testlerin 8'i eski kodda
kırmızıydı):
- **Eşzamanlı yazım (veri kaybı):** gece koşusu şarkıları başta okuyup saatlerce üretimden sonra eski kopyayı
  yazıyordu; o arada dinleme odasında verilen ret, yeni onarım isteği ya da not eziliyordu. Şimdi şarkı başına
  süreçler arası kilit + taze oku-değiştir-yaz (`durum.guncelle`); üretim sonuçları taze kopyaya işlenir, Scryne'ın
  aşaması korunur. Keşif kaydındaki "Ele/Geri al" da kilitli.
- **Güvenlik:** `/ses/%2E%2E/.env` proje kökündeki `.env`'yi (Spotify sırları) veriyordu (yalnız 127.0.0.1, ama
  tarayıcıdaki herhangi bir sayfa isteyebilirdi). Kimlik biçimi ve ses uzantısı doğrulanıyor; oda yeniden başlatıldı,
  canlıda 404.
- **Gece koşusunun kırılganlığı:** keşifte tek bir ağ/yt-dlp hatası, GPU'nun 6 saat boşalmaması ya da tek bir
  adayın kapı ölçümünün (Whisper/fpcalc) düşmesi tüm koşuyu, yani üretimi, paketlemeyi ve takibi durduruyordu. Adımlar
  ve şarkılar yalıtıldı; Spotify ağ hataları `SpotifyHatasi`'na çevrildi; STILLMORE oturumu hata olunca Spotify'ı eski
  hâline getiriyor (önce CDP'li Spotify açık kalıyor, kapatılan Spotify geri açılmıyordu).
- **Boşa GPU:** kapıdan düşen şarkı her gece yeniden indirilip aynı tohumlarla yeniden üretiliyordu (sonuç aynı).
  Artık analizden sonra düşen şarkı `hata`da Scryne'ı bekler; yalnız motor hatası (geçici) iki kez kendiliğinden
  yeniden denenir.
- **Aşama korumaları:** API yüklenmiş şarkıyı yeniden onaylatıp paketini ezebilir, reddedebilirdi; `hazirla
  --yeniden` yüklenmiş şarkıyı `hazir`a düşürürdü. İkisi de kapatıldı. Yeni: dinleme odasında **Reddi geri al**.
- **Yükleme kaydı:** ISRC/UPC/yayın tarihi `metadata.json`'a elle yazılıyordu; `yanki yuklendi --isrc --upc
  --yayin-tarihi` doğrulayıp yazar (RouteNote bölge/mağaza hariçleri varsayılan).
- **Kapak:** `kapak_ozel.jpg` doğrulanmadan kopyalanıyordu; kare 3000 JPEG değilse ortadan kırpılıp getirilir, küçük
  özgün görsel YUKLE.md'de uyarılır (mevcut üç kapak zaten 3000×3000: bayt bayt korunur).
- **Küçükler:** `yanki durum` winget ffmpeg'ini görmüyordu; günlükte "None BPM"; işçi sonucu ve keşif/STILLMORE
  JSON'ları atomik değildi; `httpx2` doğrudan import edilip bağımlılıkta yoktu; `.env.example`'da TypeSafe anahtarı
  yoktu; testler gerçek Whisper modeli yükleyip Deezer'a istek atıyordu (`tests/conftest.py`: ağ ve model kapalı).

## Denetim 2 (2026-10-10, Scryne: "baştan sona incele, denetle, eksik ve hataların tamamını çöz, iyileştir, yeni şeyler ekle; her şey sende")

Kodun tamamı okundu; gece/gündüz/oda günlükleri, olay kaydı ve zamanlanmış görevler gerçek çalışma kanıtı olarak
tarandı. Testler `tests/test_saglamlik.py` (32): her düzeltmenin ve eklemenin testi düzeltmesiz kodda kırmızı (31/31
denendi), toplam 312 yeşil.

**Hatalar (çözüldü):**
- **Oda 500 (canlı günlükte):** "Başka kapak"ta Pinterest görsel deposu bağlantıyı yarıda kesti (`IncompleteRead`),
  yakalanmıyordu. İndirme bir kez yeniden denenir, olmazsa sıradaki uygun görsele geçilir; gerçek görsel boyutu da
  doğrulanır (açıklamadaki boyut tutmayabilir).
- **Ağ:** bağlantı kurulduktan sonra kopan cevaplar (`IncompleteRead`, `RemoteDisconnected`, yarım JSON) `URLError`
  değildi, yeniden denenmiyor ve gece adımını düşürüyordu (`ag.GECICI`). Spotify istemcisi de aynı. Gece günlüğündeki
  LRCLIB/MusicBrainz birer hata bu sınıftan.
- **Deezer tür adları Türkçe geliyordu** (IP'nin dili: "dans", "brezilya müziği"): MusicBrainz'de türü olmayan
  sanatçıda ACE-Step'e Türkçe stil gidebiliyordu, tür süzgeci kaçırıyordu. Bütün isteklerde `Accept-Language: en`.
- **Atomik yazım:** Windows'ta dinleme odası `durum.json`'u okurken yerine koyma `PermissionError` verebiliyordu;
  geçici dosya adı da süreçler arasında ortaktı. Kısa yeniden deneme + süreç/iş parçacığına özgü geçici ad. Paketin
  `metadata.json`/`YUKLE.md`'si de artık atomik.
- **YouTube:** boyutu bilinmeyen videoda ilk parça 403/boş dönünce 0 baytlık dosya "başarılı" sayılıyordu.
- **Söz:** elle bırakılmış söz dosyası varken bozuk LRCLIB cevabı şarkıyı "söz bulunamadı"ya düşürüyordu.
- **Temizlik:** ilk yükleme tarihine bakıyordu; geri çekilip yeniden yüklenen şarkının adayları erken silinirdi.
- **Takip:** Tunearo'da gecikme bildirimi elle `yanki dagitim-red` öneriyordu (red API'den kendiliğinden geliyor).
- **Gündüz görevi** hazırlıkta düşen şarkıyı her 30 dk'da bir yeniden indiriyordu: en erken 4 saat sonra, `girdi/`'ye
  söz/ses bırakılınca hemen.
- **Takvim:** `bugun_yuklenecek` planın gününü değil gerçek bugünü kullanıyordu.
- **Yedek** olay kaydını (bildirim tekrar anahtarları) almıyordu; **oda günlüğü** sınırsız büyüyordu (5 MB'ta döner).

**Ürün düzeltmeleri:**
- **Tür çizgisi (keşif):** keşifteki 8 doğrulanmış adayın 8'i hattın yapamadığı türdendi (rap, metal, Brezilya
  müziği; üç rap şarkısının dokuz adayı da söz kapısında kalmıştı). Aday sanatçının Deezer türü ölçülür
  (`kesif.Aday.turler`), `onay.DENENMEMIS`'e uyan puan almaz, Spotify'a sorulmaz, kendiliğinden listeye girmez; odada
  "tür uymuyor" ve tür görünür, "Yine de ekle" kalır. Kalıp Deezer'ın tür adlarıyla genişledi (electro, dance, reggae,
  brazilian, films/games…), otomatik onay da aynı kalıbı kullanır.
- **Keşif ayarları Orvane'e göre:** playlist arama sorguları ("brazilian funk", "rap hits", "phonk", "latino" →
  "sad songs", "piano ballads", "acoustic love songs"…), Deezer liste türlerinden rap çıktı. Keşif pazarları yalnız
  yayın yaptıklarımız (US ve MX çıktı: orada yayın yok, yalnız oralarda kapalı şarkı puan alıyordu).
- Bekleyen iki şarkı (Cadavers in My Cadillac, Love Kills: rap, glam metal) aynı gerekçeyle reddedildi (geri alınabilir).
- **Kuyruk beslemesi:** sürekli yayın için listeye 8 balad (Bruno Mars, Passenger, Lewis Capaldi, Christina Perri,
  Snow Patrol, The Fray, James Blunt, Adele; Faz 7 ölçütü). Sekizi hazırlandı: dil İngilizce, künye ve yazarlar tam.

**Yeni:**
- **Apple Music profili** Tunearo sanatçısına bağlanır (`tunearo.apple_bagla`): kimlik ad aramasıyla değil yayınımızın
  UPC'siyle (iTunes Lookup, anahtarsız), aynı adlı başka sanatçıya bağlanma riski yok; bölünme bildirilir.
- **Sanatçı hesabı adımları** bir kez bildirilir (`takip.profil_olaylari`): ilk canlı parçada Spotify for Artists'ten
  sahiplenme (profil fotoğrafı AI insan olmasın), iki canlı yayında YouTube resmi sanatçı kanalı. `yanki oac --ana
  --konu`: Tunearo OAC talebi (en az 2 canlı yayın ve sanatçının kendi YouTube kanalı; kanal açmak insanda).
- **Gündüz dağıtım yoklaması** (3 saatte bir, yayın başına bir istek): red/kabul ve geri çekme geceyi beklemez.
- **`yanki durum`:** Tunearo/Spotify/TypeSafe anahtarları (değer yazılmaz) ve disk (≥ 20 GB).
- **Oda:** dağıtımda "geri çekilecek", takvim "her gün", keşifte tür. Görsel doğrulama 24 kare 0 sorun.

**Spotify kotası (2026-10-10, Scryne: "kilitleniyor mu, hep böyle mi olacak; öyleyse başka yol bulalım"):** kilit
9 Ekim'deki tek seferlik aşırı kullanımdan (~1.000 istek, 23 saat ceza). Ama takip şarkı başına her gece 13 API
isteği harcıyordu: ~15 canlı şarkıda günlük 400 tavanı dolup takip ve keşif yarıda kalacaktı. Spike (canlı, Spotify
1.3.4 + Spicetify): istemcinin GraphQL araması (`searchDesktop`, `searchTracks`; STILLMORE'un yedek özetleri)
çalışıyor, 20 sonuç ~1 sn, hesabın ülkesinde (TR); istemci token'ıyla genel API ise hemen 429 → kullanılmadı.
`stillmore.IstemciArama`: takip canlılığı ve TR sırasını her gece istemciden alır, diğer pazarlar şarkı başına
haftada bir API'den (`web_gun = 7`, arada önceki sıra). İstemcinin ISRC araması bulanık eşleşme döndürebildiği
için parça yalnız ad + sanatçı eşleşince "bizim". Canlı doğrulama: RouteNote'taki 3 parça 3 istemci aramasıyla, API
0; bilinen bir yayında (Kylie Minogue, GBAYE0000351) canlı, sanatçı kimliği, TR sırası 1. Bulunan hata: Spotify'ı
açınca CDP portu hazır ama arayüz sayfası yüklenmemişken köprü düşüyordu (`kopru_bekle`). 5 yeni test.

**Sürekli koşu (2026-10-10, Scryne: "gece 3'ü beklemeye gerek yok, bilgisayar açık olduğu her zaman çalışsın"):**
`\Yanki\Surekli` bilgisayar açıkken her 30 dk ve oturum açılınca `yanki calistir`; `\Yanki\Gunduz` (yalnız boştayken
üretim) buna katıldı, `\Yanki\Gece` 03:00'te uyandırıp aynısını koşar. Adım aralıkları (`.adimlar.json`): keşif,
takip, temizlik günde bir; Tunearo yoklaması 3 saatte bir; hazırlık, üretim, onay, paket, yükleme sırası her koşuda.
Üretim kullanıcı etkinken de (prizde, GPU boşken), koşu başına 2 şarkı, GPU dolarsa 10 dk sonra vazgeçer. Spotify
uygulamasına gereken adımlar uygulama serbestken (kapalı, CDP'li ya da 20 dk boşta); API kilitliyken keşif bekler.
İş yapılmayan koşu günlüğe yazmaz, bildirim yalnız hatada. İlk gerçek koşu (13:39): keşif kilitli API'yle hakkını
yaktı ve hazırlık analizdeki 8 şarkıyı her koşuda yeniden yazıyordu → ikisi düzeltildi; üretim kullanıcı etkinken
başladı (GPU %100, 6,6 GB). 13 yeni test, toplam 325.

**Kiralık GPU (2026-10-10, Scryne: "güçlü GPU ile çıktıları daha iyi yapalım", RunPod hesabı açtı):** S19 (A40,
`docs/arastirma/06`): nicelemesiz bf16 kesit 21 sn, tam şarkı tek parça 140 sn, VRAM tepe 14,4 GB, kapılar aynı
düzeyde; iki deneme ~0,16 $. `yanki/runpod.py` (pod yaşam döngüsü, SSH, her durumda silme), `yanki/uzak.py`
(`motor.calistir` ile aynı sözleşme, bütçe ve stok ön kontrolü, motor işler planlanmadan seçilir; sunucu koşu
ortasında düşerse şarkılar sırada kalır, 3 saat evdeki kart). Üretim varsayılanı kiralık GPU. Kalite kararı Scryne'ın
kulağında: `calisma/dinleme/s19/`. Orijinal kaydın ISRC'siyle yükleme önerisi reddedildi (gerekçe `06`). 9 yeni test.

**Baştan, tam sürüm (2026-10-10, Scryne: "benim bilgisayarımda şarkı üretmicez artık; tüm şarkıları kaldır, makinede
tam sürümüyle 0'dan başlayalım"):** evdeki koşu durduruldu (işçi 14:10'dan beri takılıydı: VAE çözme boş VRAM 0,76
GB'ta paylaşımlı belleğe taştı → motor bekçisi: işçi 20 dk günlüğe yazmazsa durdurulur). Evde üretim kapalı
(`[uzak] yerel_yedek = false`). `yanki bastan --uygula --kaldirildi`: 23 şarkı; adaylar ve paketler
`calisma/_arsiv/2026-10-10/`'e, RouteNote'taki 3 kaldırıldı sayıldı (ticket), Tunearo'daki 2 geri çekilmek üzere
işaretli (inceleme bitince baştan üretime; `geri_cek.bastan`). Kaynak, söz, künye, stil, kapak korundu. Yetim pod
temizliği her uzak koşunun başında; `yanki durum` RunPod anahtarı; pano: üretim yeri, bu ay GPU harcaması, "Son koşu".
İlk otomatik kiralık GPU koşusu `\Yanki\Surekli` ile başladı (8 şarkı). 7 yeni test, toplam 335.

## Denetim 3 (2026-10-10 akşam, Scryne: "baştan sona incele, denetle, eksik ve hataların tamamını çöz, iyileştir, yeni şeyler ekle; her şey sende")

Kod, betikler ve günün gerçek çalışma kanıtı (gece/sürekli günlüğü, `runpod.log`, `runpod.json`, servis sayaçları,
zamanlanmış görevler) tarandı. Testler `tests/test_isletim.py` (14) ve odanın liste testi: hepsi düzeltmesiz kodda kırmızı (15/15
denendi), toplam 353 yeşil.

**Hatalar (çözüldü):**
- **Kiralık GPU'da işçi başlatma her koşuda 120 sn asılıydı** (`runpod.log`: beş koşunun beşi "zaman aşımı (120 sn)").
  Kök neden kabuk önceliği: `cd … && export … && setsid nohup … &` satırında `&` bütün `&&` zincirini arka plana
  atıyor, zinciri koşan alt kabuk SSH'ın çıktısını işçi bitene kadar açık tutuyordu; iş yalnız pid yoklaması yedeğiyle
  sürüyordu (yedek yokken 17:14 koşusu bu yüzden düştü). Arka plana artık yalnız işçi gider (`uzak.baslatma_betigi`);
  yerelde sahte işçiyle eski betik 6 sn, yenisi 0,03 sn.
- **Sürekli koşunun günlüğü adım bitince yazılıyordu:** 17:38'de başlayan bir saatlik üretim günlükte "── üretim
  (18:51:46)" diye, bitiş saatini başlama saati gibi göstererek çıktı; koşu yarıda kesilseydi (uyku, kapanma) hiç
  görünmezdi. Adım çıktısı artık canlı akar (`cli._AdimCiktisi`), başlık adımın başlama saatini taşır, uzun adımın
  süresi yazılır; "yapılacak iş yok" adımları yine yazılmaz. Kiralık GPU'da biten iş sayısı da akar ("8/24 iş bitti").
- **Dinleme odası başka sitelere açıktı:** yalnız 127.0.0.1'de dinliyordu ama tarayıcıda açık herhangi bir sayfa
  gövdesiz yazan uçları (Reddi geri al, Listeye ekle, Başka kapak) çağırabilir, DNS yeniden bağlamayla okuma uçlarını
  okuyabilirdi. Host yerel olmalı, yazan istek başka kökenden gelemez; canlıda yabancı Origin ve Host 403, oda 200.
- **Spotify hata ayıklama portu her kökene açıktı** (`--remote-allow-origins=*`): STILLMORE taraması sürerken bir web
  sayfası oturum açık Spotify istemcisinde kod çalıştırabilirdi. Bayrak kaldırıldı (köprü Origin göndermiyor); canlı:
  STILLMORE yüklendi, ülke TR, yabancı köken 403.
- **Geçici ağ hataları:** RunPod GraphQL hiç yeniden denemiyordu (SSH beklenirken tek kopuk yoklama pod'u silip koşuyu
  düşürürdü; pod açan istek yine tek), Tunearo istemcisi kopuk cevabı (`RemoteDisconnected`, `IncompleteRead`)
  yakalamıyordu (tek kopukluk bütün dağıtım yoklamasını düşürürdü). LRCLIB yükte sık 503 "ServerOverloaded" veriyor
  (keşifte isteklerin %39'u, canlı denendi): `Retry-After`'a uyulur, 4 deneme.
- **Gece betiği** `uv run yanki` ile senkron yapıyordu: açık oda venv'i tutarken sürekli koşu ve oda gibi `--no-sync
  python -m`. Önceki koşu sürerken her 30 dk'da günlüğe düşen "başka bir koşu sürüyor" satırları yazılmaz.

**İyileştirmeler:**
- **Keşifte sanatçı çeşitliliği:** kataloğunu Spotify'dan çeken sanatçının her şarkısı "Spotify'da yok" çıkıyor; 16:08
  keşfinde ilk 10'un 6'sı Xiu Xiu'ydu. Sırada bekleyen şarkısı olan sanatçıdan gece yenisi eklenmez (yayına çıkınca ya
  da reddedilince eklenir); odadaki elle "Listeye ekle" serbest.
- **`yanki durum`:** kiralık GPU'nun bu ayki harcaması / bütçe ve devre dışıysa nedeni (yerel kayıttan, ağsız).
- **Yedek** kiralık GPU harcama kaydını da alır (aylık bütçe sınırı ondan hesaplanıyor).
- **Odadan "Listeye ekle" koşu sürerken de çalışır:** kiralık GPU'da üretim ~1 saat genel koşu kilidini tutuyor, oda o
  süre 409 veriyordu. `liste.toml` kendi kilidiyle yazılır; yeni metin yazılmadan doğrulanır ve atomik yazılır (önce
  sona eklenip sonra doğrulanıyordu: bozuk ekleme bütün hattın listesini okunmaz bırakırdı).

**Keşif tohumları (uygulandı, geri alınabilir):** katalog farkının elle tohumları (Xiu Xiu, Deerhoof, Godspeed You!
Black Emperor, King Gizzard, Massive Attack, Hotline TNT) kataloğunu Spotify'dan 2025'te protestoyla çeken, çoğu deneysel
sanatçılardı; keşfin puanlı 29 adayının 26'sı onlardan geliyordu ve bugün Xiu Xiu "Boy Soprano" listeye girmişti. Hattın
tarifi balad/pop, boşluk da sanatçının bilinçli kararı (tepki riski). Tohumlar boşaltıldı (`config/kesif.toml`), bu
sanatçıların 44 keşif adayı "elendi" (odada Keşif → Geri al), Boy Soprano üretime girmeden reddedildi (Reddi geri al).
Katalog farkı playlist sanatçıları, benzerleri ve tür listeleriyle sürer.

**Sınırsız yükleme (Scryne, 2026-10-10 gece: "her gün 1 tane değil, yükleyebildiği kadar yüklesin, hızlı hızlı hesabı
kasalım"):** `[takvim] haftada = 0`: sırası gelen her paket aynı koşuda Tunearo'ya gider (önce günde bir). Tunearo'nun
hesap parça kotası dolarsa ("Track limit reached", 403) yükleme durur, bildirilir, kalanlar kuyrukta bekler; açılan
taslak kota açılınca aynı yayınla tamamlanır. Toplu yüklemede tek bildirim. Red kapısı aynı (düzeltilmemiş red yeni
yüklemeyi durdurur). Risk bir kez söylendi: ortak bir red nedeni (ör. "derivative work") o koşuda gönderilen her
şarkıyı birlikte etkiler. 2 yeni test (eski kodda kırmızı).

**Yazarsız paket (2026-10-10 gece, canlıda bulundu):** Janice Javier "Heaven Knows"un MusicBrainz'de kaydı yok (web
aramasında da yazar bilgisi yok); paketi yazarsız çıktı, Tunearo yüklemesi her koşuda düşüp koşuyu "hata verdi" diye
bitiriyordu (22:11, kod 1). Artık yazarsız paket bekler ve Scryne'a bir kez bildirilir, koşu hatasız biter; diğer
paketler yüklenir. `liste.toml`'da şarkıya `yazarlar = ["Ad Soyad"]` yazılınca sonraki koşu künyeyi günceller, paketi
yeniden çıkarır ve yükler (hazırlıkta da listedeki yazarlar MusicBrainz'in yerine geçer). Yazar uydurulmaz. 2 yeni test.

## Denetim 4 (2026-10-11, Scryne: "baştan sona incele, eksik ve hataların tamamını çöz, iyileştir; ardından şarkı modelini ve beat'ini eğit, orijinal şarkılar gibi kaliteli olsun, AI tespitinde human çıksın")

Kod, günlükler (sürekli koşu, oda, runpod) ve yayına giden seslerin kendisi ölçülerek tarandı; modüllerin ikinci
taraması bir alt ajanla. Testler `tests/test_denetim4.py`, `tests/test_egitim.py`, `tests/test_paket.py`: düzeltmelerin
testleri düzeltmesiz kodda kırmızı (denetim testlerinin 18/18'i, mastering testi), toplam 390 yeşil.

**Dışarıdan gelen engel:** Tunearo 2026-10-11 12:47'den beri her isteğe `403 API access not enabled for this user`
diyor (hesap sahibi API erişimini kapattı). 21 yayın incelemede, durumları okunamıyor, yeni yükleme yapılamaz. Koddan
çözülmez: arkadaşla konuşulacak. Hat artık bunu hesap düzeyi hata sayıyor (aşağıda).

**Hatalar (çözüldü):**
- **Tunearo erişimi kapanınca:** yoklama 21 yayının her birinde ayrı 403 yazıp (her biri 12 sn) adımı "sorunlu"
  bitiriyor, koşu her 3 saatte "hata verdi" bildiriyordu. `tunearo.ErisimYok`: ilk istekte durur, günde bir bildirilir,
  `calisma/.tunearo_erisim.json` kaydı özet satırında, panoda "Senden beklenen"de ve takvimde görünür; takvim 6 saat
  yüklemeyi denemez, erişim açılınca yoklama kaydı siler, hat kendiliğinden sürer.
- **DNS:** `dashboard.tunearo.com`'un AAAA sorgusu bu ağda zaman aşımına düşüyor, her istek 12 sn (Python her
  bağlantıda yeniden çözüyor). `ag._cozumle`: IPv4/IPv6 aynı anda, IPv4 gelince IPv6 en çok 0,3 sn beklenir, 5 dk
  önbellek; paket içe aktarılınca bütün istemcilere (Spotify, TypeSafe, RunPod) uygulanır. 12,8 sn → 0,7 sn.
- **Mastering (yayına giden her pakette):** iki geçişli loudnorm "doğrusal" isteniyordu ama ACE-Step çıktısının
  tepe/ses oranı (15–16 dB) −14 LUFS / −1,2 dBTP'ye doğrusal sığmıyor (en çok 12,8): ffmpeg sessizce dinamik moda
  düşmüş, 21 paketin hepsi `normalization_type: dynamic`. Ölçüm: 3 sn pencerede kazanç 4,7–8,2 dB oynuyor, sentetik
  testte 12 dB'lik kıta/nakarat farkı ~0'a iniyor (pompalama, cansız ses). Yeni zincir: 28 Hz alçak kesim (çıktıda DC
  +0,001…+0,0035 ve uğultu) → ton eşleme → sabit kazanç → 4× aşırı örneklenmiş tepe sınırlayıcı (3,5–4 dB) → üçgen
  dither; kazanç oynaması std 0,04–0,12 dB, −14,0 LUFS, −1,4…−1,5 dBTP.
- **Dinleme odası "Listeye ekle" hiç çalışmamıştı:** gövdesiz çağrı GET atıyordu, uç POST (404); testler doğrudan POST
  attığı için yeşildi. YouTube izlenmesi ölçülmemiş aday eklenirken de 500 (TypeError) verirdi.
- **Yazarsız paket** (Heaven Knows) her oturum özetinde "yükleme sırası geldi" diye görünüyordu: sıraya girmez,
  `liste.toml`'a yazar eklenince girer.
- **LRCLIB yedek araması** ilk sonucu doğrulamadan alıyordu (başka sanatçının karaoke/cover kaydı): sanatçı sözcük
  sözcük eşleşmeli. **Künye** ilk eserde yazar yoksa diğer kayıtlara bakmıyordu (gereksiz "yazarlar gerekli").
- **Latin dışı ad** (Kiril, CJK) boş ya da çakışan şarkı kimliği üretiyordu (kök klasöre yazım): kısa özet eklenir;
  mevcut kimlikler değişmedi.
- **Katalog farkında** tek Spotify 404/5xx keşif adımını ve önbelleği düşürüyordu; **takipte** Spotify istemcisi
  kapanırsa (CDP kopması) Web API'ye düşmüyordu; **odada** yarım Tunearo yüklemesi olan paket reddedilince taslak
  sahipsiz kalıyordu (409); **parçalı üretimde** kısa çıkan ara parça şarkının ortasında sessizlik bırakıyordu;
  beğenilmeyen Pinterest görseli başka pin kimliğiyle geri gelebiliyordu; oda günlüğü zararsız `ConnectionResetError`
  izleriyle doluyordu.

**İyileştirmeler:**
- **Ton eşleme (referans mastering, `yanki/ton.py`):** 22 şarkıda üretilen − orijinal: 40–63 Hz +5…+8 dB (±11),
  3–8 kHz −2…−4 dB (vokal varlığı). Her şarkı kendi orijinaline göre: farkın %70'i, kesme ≤ 8, yükseltme ≤ 3 dB,
  40 Hz–12 kHz. Orijinale uzaklık 6 şarkıda %10–35 azaldı. `config/yayin.toml` → `[master] ton_eslesme`.
- **YouTube kaynağı tam bant Opus** (önce AAC 128 kbps, 16 kHz'te kesik: 16–18 kHz −85 dB).

**Ses modeli eğitimi (`yanki egit`, `yanki/egitim.py`, `config/egitim.toml`):** ACE-Step'in kendi Side-Step eğitimiyle
XL-SFT'ye tür LoRA'sı; vokal ve eşlik (beat) tek modelde birlikte öğreniliyor. Veri: 50 şarkı (48'i hazırlandı, 175 dk),
modern stüdyo balad/pop, kadın/erkek dengeli, her sanatçıdan bir, cover listesindeki sanatçılar yok (kapak yaptığımız
kayıtlar ezberlenmesin, tek bir sesin kopyası olmasın); kaynak seçimi albüm sesini tercih eder ("- Topic", "Audio"),
akustik sürüm ve fragman kurgusu elenir. Söz ve ses aynı yerden kesilir (zaman damgasıyla), söz biçimi üretimdeki
`soz.txt`'nin aynısı. Yerel 2B turbo denemesi iki hatayı paraya kıymadan buldu (Side-Step onay sorusu, ACE-Step kökü
dışındaki yol). Eğitim pod'u üretimin artık temizliğine yakalanmasın diye ayrı ad ve kayıtla açılır. Eğitimden sonra
aynı pod'da karşılaştırmalı deneme (aynı şarkı, aynı tohum, LoRA 0 / 0,5 / 1).

**Sonuç (2026-10-11, `calisma/egitim/lora/20261011-1554`):** A40'ta 60 epoch, 2 sa 38 dk, 1,88 $; loss 1,06 → 0,71.
Dokuz denemenin dokuzu kapılardan geçti (parmak izi 0,56–0,63, değişmedi). Söz WER ortalaması LoRA 0: 0,076,
LoRA 1: 0,068, LoRA 0,5: 0,140 (The Scientist'te tek kötü üretim). Orijinal kayda ton uzaklığı LoRA'yla yaklaşmadı:
LoRA 1'de şarkı başına +0,2…+0,45 dB uzaklaştı. Ölçüde açık bir kazanç yok → **LoRA üretime bağlanmadı**; karar
Scryne'ın kulağında (`calisma/dinleme/lora/20261011-1554/OKU.md`). Bağlamak: `config/motor.toml` →
`[motor] lora = "calisma/egitim/lora/20261011-1554/final"` (`lora_olcek` 0–1).

**Yapılmayan:** "AI tespitinde human çıksın" isteği uygulanmadı. Dedektörü atlatmaya yönelik iş, parçanın AI ile
üretildiğini dağıtımcıdan, mağazalardan ve dinleyiciden gizlemek olur (Deezer/Tidal bu bilgiyle etiketliyor ya da
ödüyor). Operasyonel gereği de yok: Tunearo'da AI tespiti tek başına red değil, Orvane biyografisi "AI-assisted".
Kalite işleri (mastering, eğitim) dedektör skoru hedeflenmeden yapıldı.

## Üretim kalitesi (2026-10-12, Scryne: "beat kısmı çok kötü, sürekli aynı şeyler oluyor"; "şarkılar tek türde olmayacak"; "şarkı üretimini en iyi haline getir")

Ayrıntı ve ölçümler: `docs/arastirma/07-beat-ve-tarif.md` (S20–S26). Üretim zaten kiralık A40'ta nicelemesiz XL-SFT;
sorun modelde değil, modele verilen girdideydi.

**Teşhis:** sözde bölüm etiketi yoktu (19/31 şarkıda nakarat yok), stil sanatçının genel türüydü ("pop, funk" bir piyano
baladına). Yüklenen 22 şarkıda beat: orijinalden döngüsel (+0,11), groove'u zayıf izliyor (0,30), baladlara genel davul
(×1,5), şarkılar birbirine orijinallerden çok benziyor (0,941 / 0,891).

**Yapılanlar:**
- **Bölüm yapısı (`yanki/yapi.py`, `yanki yapi`):** zaman damgalı sözden giriş, kıta, ön nakarat, nakarat, köprü,
  ara, çıkış; söz değişmiş son nakarat ve şarkı adını taşıyan gerçek nakarat bulunur. 31 şarkının sözü yeniden yazıldı.
- **Şarkıya özel betim (`[motor] betim = true`):** ACE-Step'in eğitim verisini etiketlediği `acestep-captioner` aynı
  pod'da şarkıyı dinler, stil o betimden; 256 jetonluk metin sınırına sığar. S20: groove 0,18 → 0,24, fazladan
  döngüsellik −%66; S21 (6 tür): groove 0,35 → 0,51, dinamik izleme 0,58 → 0,69.
- **Kapılar türe göre doğru:** dalga 300 Hz üstünde (EDM'in kick örtüşmesi kopya sayılıyordu), söz WER'i orijinal
  kayda göre (Whisper orijinal rap'i de 0,49 anlıyor).
- **Dil:** ses emin değilse söz karar verir (Nyoy Volante Tagalogca İngilizce sayılıyordu).
- **Türler:** keşifte rap, hip-hop, trap, EDM, house, dance, electro açık (config'te); İspanyolca Latin kapalı (cover
  orijinalden belirgin az anlaşılır). Otomatik onayda yeni türler Scryne dinleyene kadar kapalı.
- **Denenip alınmayanlar:** cover gücü 0,85/1,0 (beat değişmedi), orijinal kayıt tını referansı (kaydı sızdırdı),
  sanatçının başka şarkısı referans (aynılık arttı), shift 3 ve ScragVAE (ölçüde nötr; ScragVAE kulağa kalır).
- **Aday seçimi:** beat ölçüleri Scryne'ın seçimini tutmadı (rastgele düzeyi), söz WER 11/21 tuttu → seçim WER ile
  kalır; her adaya ACE-Step söz hizalama puanı yazılıyor (seçim ölçüsü olarak sınanacak).
- **Eğitim yeniden (çok türlü):** 95 şarkı (balad + rap, R&B, EDM, rock, Latin, country, uptempo pop), stil pod'da
  betimleyiciyle, sözler bölüm yapısıyla, dil sesten. S28: beat'i kötüleştirdi (groove 0,24 → 0,21, döngüsellik
  +0,04 → +0,14), bağlanmadı. Neden: Side-Step LoRA'yı metinden-müzik görevinde eğitiyor, üretim cover. →
  **Cover görevi eğitimi** (`yanki/kapak_hazirla.py`): her örneğin cover kopyası (bağlam kendi kaynak kodlarından,
  talimat ve söz biçimi üretimdeki gibi); yerel 2B turbo denemesiyle doğrulandı, A40'ta 15 epoch (2,14 $).
  **S30: üretime bağlandı** (ölçek 1). Eğitimde olmayan şarkılarda groove balad 0,23 → 0,57, 11 tür 0,30 → 0,58;
  döngüsellik ilk kez orijinalin altında; dinamik izleme 0,63 → 0,82 / 0,53 → 0,79. Söz WER karışık (17'nin 10'unda
  düştü), çıktı orijinale biraz yaklaşıyor (parmak izi en çok 0,69 / eşik 0,72); kapılar aday başına süzüyor.
  **S31: dördüncü eğitim** (30 epoch, 123 şarkı, 5,03 $): kayıp 20. epoch'tan sonra yatay; ep20 ve ep30 beat'te
  aynı, v3'ten balad'da belirgin (groove 0,57 → 0,63), türlerde az iyi (0,58 → 0,60); söz karışık. Kör test
  (`egitim-4`: v3 / ep20 / ep30): yeni eğitim 12/17'de kazandı, **yayınlanabilir 9/17** (önce 4/17); ep20 ile ep30
  berabere, **ep20 üretimde**. Caz, blues, reggae, afrobeats, K-pop, drill, grunge keşifte kapalı (en iyisi bile
  yayınlanamaz).
- **Üretim yeniden açık ve geniş (2026-10-13, Scryne: "kaldırılmamış bile olsa ... popüler şarkılar üret, kapsamı
  olabildiğince genişlet"):** keşfe popüler kaynak (`yanki/katalog.py → populer`): Deezer editörlerinin tür
  listeleri (balad, pop, rock, metal, pop-punk, country; 28 sorgu, rank ≥ 400 bin), yalnız İngilizce söz, Spotify'sız
  (12 saatte bir, Web API kilidinden bağımsız), Jev sorulmaz. Gece 10 şarkı. İlk gece 30 şarkı listeye girdi, ilk 8'i
  RunPod'da üretildi. Jev çağrısına 60 sn sınır (TypeSafe 20 dk asılı kaldı). Dağıtımcı Scryne'da.
- **Tüm türler (S29):** metal, punk, grunge, country, jazz, blues, reggae, reggaeton (İspanyolca), K-pop, afrobeats,
  drill; 11 türün 10'u tek tohumla kapılardan geçti, keşifte açık. Kapalı: J-pop (LRCLIB'de Japonca söz yok),
  denenmemiş türler (techno, trance, Brezilya, Hint, klasik…).
- **İlk kulak testi (S30, 2026-10-12 akşam):** Walking on Air aday 9 onaylandı ("gayet iyi"; hattın önerisi); Daddy's
  Home (rap) "çok kötü, bozuk" ve Ipagpatawad Mo (Tagalogca) "kötü" reddedildi; söz ölçüsü üçünde de iyileşmişti.
  Rap ve drill keşifte yeniden kapalı; rap ve İngilizce dışı dilde karar kulağa kalır.
- **Çok dilli söz güvenliği:** LRCLIB çeviri sürümü (Japonca seste İngilizce söz) ve satır sonu çevirisi
  (`Korece^İngilizce`) yakalanır; boşluksuz dillerde (ja, zh, th) söz kapısı karakter hata oranıyla.
- **Söz kapısı belirli:** Whisper'ın tohumsuz sıcaklık geri düşüşü aynı dosyaya 0,37–0,73 veriyordu; tohumlu.
- **Aday önerisi:** en düşük WER'li iki aday arasından ACE-Step söz hizalaması yüksek olan (S27: Scryne'ın 21
  seçiminden 14'ü; yalnız WER 11, rastgele 7). Aday sayısı 4.
