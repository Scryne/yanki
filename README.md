# Yanki

Listeye yazılan yabancı şarkıların cover'ını kiralık GPU'da [ACE-Step 1.5](https://github.com/ace-step/ACE-Step-1.5)
ile (kendi eğittiğimiz cover LoRA'sıyla) üretir, yayınlanamayacak adayları otomatik eler, dinleme odasında onaya sunar,
onaylananı paketler ve dağıtımcıya hazırlar: 2026-10-26'dan beri DistributeMusic.AI (panelden Scryne yükler; API
anahtarı eklenirse hat yükler), önceki 14 şarkı RouteNote'ta (tarayıcı otomasyonu, takibi sürüyor). Şarkı kaynağı 2026-10-26'dan
beri gündem: şu an listelerde olan, yükselen yabancı şarkılar (`yanki kesif`, `yanki/trend.py`); yüklenen parçanın
Spotify'da çıkıp çıkmadığını ve adı arandığında kaçıncı sırada olduğunu `yanki takip` izler.

**Şu an (2026-10-26, Denetim 7):** 2026-10-20'deki dondurma çözüldü. Dağıtımcı DistributeMusic.AI, panel kipi
(`docs/arastirma/11`): paketler 16 bit WAV + panel alanlı `YUKLE.md`; cover kuralı destekten yazılı sorulana kadar API
gönderimi kapalı (`[distributemusic] sozlesme_kabul = false`). Kuyrukta 143 şarkı üretim bekliyor; dondurmada silinen
kaynak sesleri üretimden hemen önce kayıtlı videodan geri iner. Zamanlanmış görevler (`\Yanki\`) hâlâ kapalı.

**Önceki durum (2026-10-15 akşam, güncelleme 2026-10-16):** üretim açık, tarif ep20 + CFG 10, yalnız kör testlerde yayınlanabilir çıkan türlerde
(balad, pop, rock, metal, pop-punk, country, dance-pop; tür dışı şarkı üretilmez, `uretim.tur_disi`). Otomatik onay
(24 saat veto) ve RouteNote'a otomatik gönderim açık (`[routenote] gece = true`); RouteNote oturumu düşünce gönderim
durur ve "giriş yap" bildirilir. S34 (dikkat + MLP LoRA) Scryne söyleyince. Tunearo API'si 2026-10-12'de kapandı.
2026-10-16: 12 şarkı RouteNote incelemesinde; RunPod bakiyesi 0,80 $ (`en_az_bakiye` 1 $), kredi yüklenene kadar üretim
bekliyor (panoda görünür). Otomatik onayın öneri kuralı kulak seçimini 12'de 3 tutuyor (`yanki isabet`).
2026-10-18: dinlemeye çıkan her aday hazır değerlendiricilerle (SongEval + Audiobox) puanlanıyor (`yanki estetik`, koşuda
kendiliğinden); estetik seçici kulak seçimlerinde eşiği geçince öneriyi o veriyor (`[otomatik_onay] secici = "otomatik"`).

## Günlük akış

0. **Keşif (kendiliğinden, gündem):** gece koşusu günlük listeleri okur: Deezer ülke Top-100'leri, Apple Music en çok
   çalınanlar ve (Spotify uygulaması köprüyle açılabiliyorsa) Spotify Top 50'ler; yalnız yabancı pazarlar
   (`config/kesif.toml` → `[trend]`, kaynaklar `docs/arastirma/12`). Puan: kaç listede ve kaçıncı sırada, son 3 günde
   yeni girdi mi, yükseliyor mu, Spotify'da günde kaç dinleniyor (anlık görüntüler `calisma/kesif/trend/`). Adaylar
   ücretsiz elemelerden geçer (düzenleme, YouTube'da sanatçının kendi kaydı, LRCLIB'de İngilizce söz, hattın iyi yaptığı
   tür) ve en iyi `gece_ekle` tanesi listeye girer (sırada bekleyen şarkısı olan sanatçıdan yenisi eklenmez). Eski
   kaldırılmış şarkı kaynakları (katalog farkı, STILLMORE havuzu, popüler listeler) kapalı ama duruyor; Bulucu'dan
   keşfe gönderilenler (`girdi/kesif/*.csv`) yine okunur. Dinleme
   odasında **Keşif**: adayı dinle, listeye ekle ya da ele. Elle: `uv run yanki kesif [--ekle N]`.
1. `girdi/liste.toml`'a şarkı ekle (sanatçı + şarkı adı yeter) ya da 0. adımdaki gibi keşiften.
2. **Sürekli koşu:** bilgisayar açıkken her 30 dk `\Yanki\Surekli` (`scripts/surekli.ps1`) `yanki calistir`
   koşar (Scryne, 2026-10-10: "gece 3'ü beklemeye gerek yok"); `\Yanki\Gece` 03:00'te bilgisayarı uykudan uyandırıp
   aynısını koşar ve özet bildirimi gösterir (o an sürekli koşu sürüyorsa bitmesini en çok 3 saat bekler, sonra kendisi
   koşar). Görevler Görev
   Zamanlayıcı'da kapatılırsa pano ve `yanki durum` söyler. Her koşuda: hazırlık (kaynak ses YouTube, sözler LRCLIB, künye ve stil
   MusicBrainz), üretim, veto penceresi, paket, yükleme sırası. Üretim prizde ve GPU boşken, kullanıcı etkinken de,
   koşu başına en çok 2 şarkı evde, kiralık GPU'da `[uzak] sarki` (bekleyen onarımlar önce). Her koşunun ilk adımı açık
   kalmış kiralık GPU'yu siler (iş olmasa da). Keşif, takip ve disk temizliği günde bir. Keşif ve takip Spotify
   uygulamasını kullanır: uygulama kapalıysa ya da bilgisayar 20 dk'dır kullanılmıyorsa, bir şey çalmıyorsa; Spotify
   API'si kilitliyken keşif kilit kalkana kadar bekler. Hazırlıkta düşen şarkı (söz/kaynak yok) en erken 4 saat sonra
   yeniden denenir; `girdi/`'ye söz ya da ses bırakılırsa hemen. Adımlar birbirinden yalıtılmış: biri düşerse hatası
   günlüğe yazılır, koşu sürer ve hata bildirimi gelir (aynı hata günde bir kez). İş yapılmayan koşu günlüğe yazmaz;
   bekleme hâli (kiralık GPU açılamıyor, pil) değişince bir kez yazılır. Kiralık GPU'nun açılamama nedeni (bakiye,
   aylık sınır, stok, ağ) panoda "Senden beklenen"de, `yanki durum` ve oturum özetinde görünür; bakiye/sınır günde bir
   bildirilir. Otomatik yüklemesi düşen paket her koşuda değil, 2, 4, 8 … en çok 24 saatte bir yeniden denenir
   (`yanki takvim` ve odadaki Yükleme sırası gösterir; **Şimdi yeniden dene** beklemeyi siler). Günlük:
   `calisma/gunluk/<tarih>.log`; ayar: `config/operasyon.toml` → `[surekli]`. Hemen istersen elle
   `uv run yanki calistir` (`--hepsi`: zamanı gelmemiş adımlar da; aynı anda tek koşu, kilitli). Dinleme odası koşu
   sürerken de açık kalabilir: kararlar şarkı başına kilitle yazılır, koşu onları ezmez.
3. Dinleme odası oturum açılınca kendiliğinden başlar (`\Yanki\Oda`, `scripts/oda.ps1`): http://127.0.0.1:8765/,
   özet Windows bildirimiyle gelir, bildirime tıklayınca oda açılır. Elle: `yanki dinle` ya da Kokpit → Yanki → Çalıştır. Orijinalle karşılaştır; bozuk yer varsa dalga üzerinde sürükleyip
   **Bu aralığı onar**; iyi olanı **Bu adayı onayla**. Yanlışlıkla reddedilen şarkı **Reddi geri al** ile döner.
4. Onarım istendiyse bir sonraki `yanki calistir` (ya da `yanki uret`) iki onarım sürümü üretir; dinleme odasında iyisini
   **Bunu kabul et**.
5. Onaylanan şarkı paketlenir: `calisma/<kimlik>/paket/` (dağıtımcının biçiminde ses: DistributeMusic WAV, RouteNote
   FLAC; 3000×3000 JPG, `metadata.json`, `YUKLE.md`). Dağıtımcı değişince eski paket kendiliğinden yenilenir. Kapak
   şarkının moduna göre Pinterest'ten (insansız, yazısız; her yeni kapak bildirilir); beğenmezsen `yanki kapak
   <kimlik> --yeni`, kendi görselin için şarkı klasörüne `kapak_ozel.jpg`.
6. **DistributeMusic.AI'ye yükleme (`yanki/distributemusic.py`, 2026-10-26'dan beri etkin):** panel kipinde takvim
   sırası geleni bildirir; `YUKLE.md`'deki alanlarla distributemusic.ai panelinden yükle (Release type Single,
   Version type Cover, Composer/Lyricist orijinal yazarlar ad + soyad, **AI-generated: Yes**), sonra `yanki yuklendi
   <kimlik>` (kodlar çıkınca `--isrc … --upc …`). Plan: Pro (10–20 $/yıl; Starter yılda yalnız 1 single). `.env` →
   `DISTRIBUTEMUSIC_API_KEY` (Label + API planı) eklenirse API kipi: hat dosyaları ve yayını kendisi gönderir, durumu
   yoklar (`yanki dagitim-durum`; red/düzeltme isteği şarkıyı `paketlendi`ye döndürür), ama yalnız
   `[distributemusic] sozlesme_kabul = true` iken. Şartlar "yazılı lisanssız telifli melodi"yi anında hesap kapatma
   nedeni sayıyor ve cover için kural yazmıyor: toplu yüklemeden önce destekten yazılı sor (soru metni araştırma
   11'de). Bölge hariç tutma burada yok.
   **RouteNote (önceki dağıtımcı; `yanki/routenote.py`, tarayıcıyla; API yok):** dinleme odası → **Sanatçı**: "Yükle ve
   gönder…" formun dört adımını (albüm, ses + parça, kapak, mağaza/bölge) doldurur ve şarkının adı yazılınca aynı
   oturumda "Distribute"a basar (geri alınamaz). RouteNote'un yayın sayfası yalnız taslağı dolduran tarayıcı
   oturumunda dolu: önceki oturumda hazırlanmış taslak panelden elle gönderilir, sonra odada **Panelde gönderdim**
   (ya da `yanki routenote gonderildi <kimlik>`); bu paketler gece kuyruğuna girmez, bir kez bildirilir. Kaydı
   değiştiren düğmeler önce ne olacağını sorar. Elle: `yanki yukle <kimlik>` (taslak), `--gonder` (gönderim).
   Tarayıcı profili aynı anda tek işte açılır: oda işi ya da giriş sürerken gece yüklemesi o koşuda bekler.
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
   `yayin_on_gun` gün sonra: DistributeMusic'te 2, RouteNote incelemesi için en az 10; `config/yayin.toml` →
   `[takvim]`). Dağıtımcı bir
   parçayı reddederse neden anlaşılıp düzeltilene kadar yeni yükleme yok. `[routenote] gece = false` iken sırası gelen
   paket yalnız bildirilir; odadan açmak sanatçı adını yazdırır. Dinleme odası **Yayın** ve **Sanatçı**'da da görünür.
9. **Geri çekme:** panelden kaldır (DistributeMusic'te takedown 5 $, API'de ucu yok; RouteNote'ta ücretsiz), sonra
   `yanki geri-cek <kimlik> --kaldirildi` (hepsi için `--hepsi`): şarkı `onaylandi`ya
   döner, RouteNote kaydı geçmişe taşınır, gece güncel ayarlarla yeniden paketlenip kuyruğa girer.

Spotify kotası dar (geliştirici API'si, 2026-10-09'da ~1.000 istekte 23 saatlik ceza): uzun 429 alınırsa kilit
`calisma/.spotify_kota.json`'a yazılır ve süresi dolana kadar hiçbir komut API'ye istek atmaz; günlük tavan 400
istek. Takip API'yi neredeyse hiç kullanmaz: canlılık ve Türkiye'deki arama sırası her gece Spotify uygulamasının
kendi aramasıyla (STILLMORE köprüsü, kotasız), diğer pazarların sırası şarkı başına haftada bir API'den
(`config/kesif.toml` → `[takip]`). Uygulama açılamazsa (o an bir şey çalıyorsa) takip API'yle sürer. Dinleme
odası Spotify Web API'sine hiç istek atmaz.

**Dinleme odasının iki yüzü** (kenar çubuğunun üstündeki düğme; her yüz son açtığın görünümü hatırlar):
- **Orvane · AI cover hattı:** Pano, Karşılaştırma, Keşif, Yayın, Sanatçı ve kenarda şarkılar (aşağıdaki akışın tamamı).
- **Kendi müziğim · FreshTunes:** *Taslaklar* (açılış; kendi şarkıların: ses ve kapağı sen verirsin, kapağı istersen
  Pinterest'ten bulur; boş taslaklar tek tıkla silinir) ve *Bulucu*. Kenarda şarkılar yerine taslakların.

**Bulucu (dinleme odası → Kendi müziğim → Bulucu, `yanki/bulucu.py`):** STILLMORE FINDER'ın motoru odada. Spotify linki, ISRC ya da
UPC yapıştırılır; okuma Spotify uygulamasının içinden yapılır (STILLMORE köprüsü, kotasız):
- **Playlist:** kalkmış şarkılar, kalkmadan önceki dinlenmeleri, distribütör, 90 günlük sayaç penceresi, aynı
  ISRC'nin çalınan kopyası ve şarkının hattaki yeri (listede, keşifte, düzenleme). Boşluğu olanlar tek tıkla keşfe
  gönderilir (`girdi/kesif/bulucu.csv`; gece keşfi aynı elemelerden geçirir). "Gece taransın" listeyi STILLMORE
  havuzuna alır (`calisma/kesif/bulucu_izlenen.json`).
- **Parça:** distribütör (licensor UUID, güven), ISRC/UPC, label, dinlenme, süre, tempo/ton, yazarlar, pazarlar ve
  aynı ISRC'li yüklemeler.
- **Sanatçı:** dinleyici, şehirler ve yer aldığı listeler (her biri taranabilir); **Katalog**: her yayının
  distribütörü ve dinlenmesi, birden çok kez yüklenenler.
- **Albüm**, **ISRC**, **UPC** araması.
- **Liste keşfi** (sağdaki panel): konuya göre popüler playlist'ler — şimdilik "Hint şarkıları (Bollywood)". On iki
  sorgu Spotify istemcisinin kendi aramasıyla (kotasız), konu dışı listeler addan/açıklamadan süzülür (istemci hesabın
  ülkesinde aradığı için Türkiye listeleri de geliyordu), en çok 80 liste takipçi sayısıyla en popülerden sıralanır;
  her biri **Tara** ile taranır, taranmışlarda kalkmış sayısı ve **Aç**. Konu eklemek: `yanki/bulucu.py` → `KONULAR`.

Köprü kapalıysa odadaki "Spotify'a bağlan" Spotify'ı hata ayıklama portuyla (yalnız 127.0.0.1) yeniden açar; bir şey
çalıyorsa önce sorar. Sonuçlar `calisma/bulucu/`'da kalır, "Son aramalar"dan yeniden açılır.

**Elle yayın (dinleme odası → Kendi müziğim → Taslaklar, `yanki/elle.py`):** kendi şarkın ya da hazırladığın herhangi bir kayıt için
taslak. Form yazdıkça kaydedilir (`calisma/elle/<kimlik>/`):
- **Dosyalar:** sesi (WAV/FLAC/AIFF/MP3) ve kapağı (JPG/PNG, en az 1400²) bilgisayarından sürükle; hat FLAC 44,1 kHz
  16 bit'e ve 3000×3000 RGB JPG'ye (ortadan kare) çevirir.
- **Bilgiler:** ad, sürüm, sanatçı, Spotify profili, dil ve tür (RouteNote'un listeleri), açık içerik, sözlü/enstrümantal,
  cover mı (cover: orijinal sanatçı, mekanik lisans yoksa ABD/Kanada/Meksika/Hindistan/Pakistan hariç), besteciler ve söz
  yazarları (ad + soyad), yapımcı, ©/℗, label, ISRC (boşsa dağıtıcı atar), UPC, yayın tarihi (boş: onaylanınca), ilk
  yayın tarihi, önizleme başlangıcı, yapay zekâ (Amazon ve Kore mağazaları kapanır), YouTube Content ID.
- **Dağıtıcı:** *RouteNote* (AI cover'lar, Orvane; otomatik: form tarayıcıyla doldurulur ve aynı oturumda gönderilir;
  onay için şarkının adı yazılır; `yanki elle-yukle <kimlik> --gonder`), *FreshTunes* (Scryne'ın kendi şarkıları, kendi
  adıyla; aşağıda) ya da *başka dağıtıcı (elle)*: DistroKid, TuneCore vb. otomasyonu yasakladığı için ses + kapak +
  `BILGILER.txt` tek ZIP'te iner. Aynı kayıt RouteNote ve FreshTunes'a birlikte gönderilemez (mağazada iki kopya).
  Sağ panel eksikleri listeler; tamamlanmadan gönder düğmesi açılmaz. Gönderilen taslak kilitlenir.
- **Kendi şarkıların: FreshTunes** (ücretsiz, akış gelirinin %100'ü; `docs/arastirma/09`). Yükle → **Kendi şarkım
  (FreshTunes)**: sanatçı, profil, label ve yazarlar son FreshTunes taslağından gelir, yapay zekâ kapalı, yayın tarihi
  14 gün sonrası. FreshTunes yapay zekâ kaydını ve botu yasaklıyor: hat denetler (yapay zekâ, Orvane adı, yayın tarihi
  en erken 7 gün, başta/sonda en çok 5 sn sessizlik, kırpılma) ve **FreshTunes paketini** (`audio.flac`, `artwork.jpg`,
  kontrol listesi ve form alanlarıyla `FRESHTUNES.txt`) indirir. Kapak yoksa "Pinterest'ten kapak bul" (cover'lardaki
  gibi insansız, yazısız; `yanki/elle_kapak.py`); formu sen doldurursun, sonra **FreshTunes'a
  gönderdim**. FreshTunes 3 ayda bir giriş istiyor (yoksa askı, açmak 50 $): 75. günden itibaren haftada bir bildirim
  gelir, Yükle'de **Bugün girdim** sayacı sıfırlar. Para Payoneer'la çekilir (en az 25 $).

**Yayından sonra (dinleme odası → Yayın → Performans, `yanki performans`):** RouteNote paneli botla okunmaz (site
şartları madde 2: "collecting data … using bots … or other automated data gathering methods"). Onun yerine:
- **Dinlenme:** takip her gece canlı parçalarımızın Spotify sayacını Spotify uygulamasından okur, günlük seri tutar.
- **Kazanç:** ayda bir RouteNote → Performance → Reports'tan *Monthly Sales Report*'u indir, `girdi/kazanc/`'a koy
  (rapor ay sonundan ~45 gün sonra gelir, USD). Sütunlar adlarından tanınır, satır şarkıya ISRC/UPC ile bağlanır.
- **Keşfe geri besleme:** türün ortanca günlük dinlenmesi / bütün şarkıların ortancası → keşif puanında tür çarpanı
  (karekök, 0,6–1,6; en az 4 şarkı, türde 2, her biri 14 gün yayında). Sayacı hâlâ duran (son 90 günde kalkmış)
  şarkı ×1,3. Gece keşfi kulaktan geçmiş şarkılarımızın sanatçılarının yer aldığı karışık playlist'leri STILLMORE
  havuzuna ekler (`config/kesif.toml` → `[stillmore] sanatci_*`).
- **RouteNote kararları e-postadan (`yanki eposta`, gece 6 saatte bir):** `.env`'ye `EPOSTA_KULLANICI` (RouteNote
  hesabının Gmail adresi) ve `EPOSTA_SIFRE` (Google hesabı → Güvenlik → 2 adımlı doğrulama → Uygulama şifreleri).
  Yalnız gönderende "routenote" geçen iletiler, salt okunur. Onay → yükleme kaydında `approved` (tarihsiz yayında
  "Spotify'da hâlâ yok" alarmı onay + 7 + 3 güne kayar); düzeltme isteği → bildirim; red → şarkı `paketlendi`ye döner, RouteNote kaydı geçmişe, takvim düzeltilene kadar yeni yükleme açmaz.
  Elle gönderilen taslağın onay e-postası gelirse gönderim kendiliğinden kaydedilir. İletilerin metni
  `calisma/eposta/ornek/`'e düşer (kurallar ilk örneklerle sıkılaştırılır).

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

**Tür çizgisi:** keşif hattın kör testlerde yayınlanabilir çıktığı türlerde kalır (balad, pop, piyano/akustik, rock,
metal, pop-punk, country, dance-pop). Rap/hip-hop, folk, grunge, reggaeton/Latin, EDM (techno, dubstep, trance), K-pop
vb. aday Deezer türünden tanınır, puan almaz, kendiliğinden listeye girmez (dinleme odasında "Yine de ekle"); liste
`config/kesif.toml` → `haric_turler`. Otomatik onayı ayrı bir liste sınırlar (`config/yayin.toml` →
`[otomatik_onay] denenmemis_turler`). Tür dışı şarkı üretilmez (`uretim.tur_disi`).

Diğer komutlar: `yanki durum` (motor, model, araçlar, GPU, anahtarlar, disk, şarkıların aşaması), `yanki ozet` (tek satır),
`yanki temizle [--uygula]` (yüklenmiş şarkılarda seçilmeyen adaylar, reddedilen şarkıların sesleri, 7 günden eski
`_arsiv`'in sesleri — yayın kayıtları kalır; gece koşusu kendisi siler),
`yanki yedekle [--zorla]` (seçimler, yükleme bilgisi — `bastan` arşivi ve eski paketin taslak UPC'si dahil —, elle
taslakların bilgisi ve kapağı, RouteNote e-posta kaydı, kazanç raporları, keşif kaydı ve CSV'leri, kulak oyları, liste,
ayarlar; ses ve
sır yok; gece haftada bir; üretimdeki LoRA yedek klasörüne bir kez kopyalanır),
`yanki isabet [--ayrinti]` (otomatik onayın öneri kuralı Scryne'ın kulak seçimlerini ne sıklıkla tutuyor; Faz 12 eşiği
%70; ölçüm `calisma/dinleme/isabet.json`'a, oran panoda "Otomatik onay" satırında; estetik seçici yan yana),
`yanki estetik [--en-cok N]` (dinlemedeki adaylara SongEval + Audiobox puanı, CPU'da ~80 sn/aday; koşu her seferinde
en çok 8 aday puanlar; puan `durum.json`'da adayın `estetik` alanında, odada gösterilmez: seçimin kör kalması için),
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
# Aday estetiği (SongEval + Audiobox, yanki/estetik.py; yoksa adım atlanır). Ayrı venv: motorun torch'una dokunmaz
git clone --depth 1 https://github.com/ASLP-lab/SongEval araclar/degerlendirici/SongEval
uv venv araclar/degerlendirici/.venv --python 3.12
$py = "araclar/degerlendirici/.venv/Scripts/python.exe"
uv pip install --python $py torch==2.7.1 torchaudio==2.7.1 --index-url https://download.pytorch.org/whl/cu128
uv pip install --python $py muq==0.1.0 librosa==0.11.0 hydra-core==1.3.2 audiobox_aesthetics soundfile einops `
  transformers==4.46.3                                     # 5.x MuQ'yu düşürüyor (_attn_implementation)
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
- **Kapılar:** orijinal kaydı taşıyan (parmak izi ≥ 0,72 ya da dalga korelasyonu ≥ 0,20), sözsüz (WER ≥ 0,5) ya da yanlış
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
