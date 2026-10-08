---
proje: Yanki
created: 2026-10-06
modified: 2026-10-08
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
| 8 | Kalite ve düzenli yayın | ⏳ Bekliyor | En az 3 parça Spotify'da; yükleme takvimi işliyor; vokal son işlemi ve LoRA dinleme testiyle karara bağlandı; ≥ 10 onarım etiketiyle otomatik kusur işaretleme denendi (sonuç kayıtlı) |

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
- **Sıra:** (1) S15/S16 dinlemesi → kazanan kol tarife (`config/motor.toml` ya da kaynak ön işlemi) ve zayıf şarkılar
  (Fix You) gece `yanki yeniden`; (2) kazanan yoksa S17: çıktının vokal izi son işlemi (Demucs ile ayır → nefes/sibilans
  → yeniden miks); (3) LoRA ihtiyacı en son, 8 GB'ta eğitim ölçülmeden karar yok.
- Faz 7'de açık kalan denemelerin sahibi: vokal izi son işlemi (nefes/sibilans), LoRA (8–20 şarkı) ihtiyacı,
  otomatik kusur işaretleme (S14: Whisper güveni tutmadı; onarım etiketleri birikince yeniden).
- Kabul gelince düzenli yayın: onaylı paketlerden takvim (haftada bir), her yüklemenin bulgusu `YUKLE.md`'ye.
- Zayıf şarkılar (Fix You: üç aday da söz WER 0,28–0,39) stil düzenleme ya da yeni tohumlarla yeniden.
