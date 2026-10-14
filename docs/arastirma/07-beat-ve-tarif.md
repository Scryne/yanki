---
proje: Yanki
created: 2026-10-12
type: arastirma
---
# Beat ve üretim tarifi (2026-10-12)

Scryne: "beat kısmı çok kötü, sürekli aynı şeyler oluyor", "üretilmiş tüm şarkıların beatleri çok kötü ve aynıydı";
şarkılar tek türde olmayacak. Hedef: üretimi en iyi hale getirmek. Bütün denemeler kiralık A40'ta, XL-SFT 4B bf16
(nicelemesiz), cover, 100 adım, tohum 42; betikler `spikes/s20…s24`.

## Teşhis

**Modele giden girdi zayıftı (kod okuması, 31 şarkı):**
- Söz bölüm etiketi yoktu: 19 şarkıda hiç nakarat etiketi, 7'sinde bütün şarkı bir-iki `[verse]`. ACE-Step kılavuzu
  bölüm etiketlerini "Lyrics'teki en güçlü araç" sayıyor (motor/ACE-Step-1.5/docs/en/Tutorial.md).
- Stil sanatçının genel türüydü (MusicBrainz): "When I Was Your Man" (piyano baladı) → "pop, funk song".
  Keşifle gelen iki şarkıda yalnız "clean modern studio recording".
- Stil + talimat + üst veri metin kodlayıcıda 256 jetonda kesiliyor; üst veri (BPM, ton) stilden sonra geldiği için
  uzun stil onu sessizce düşürüyordu.

**S22 — yüklenen 22 şarkının beat'i, orijinalle (vurmalı/armonik ayrıştırma):**

| Ölçü | Değer | Anlamı |
|---|---|---|
| Vurmalı enerji / orijinal | ×1,47 | piyano baladlarına genel davul ekleniyor (Lana ×2,4, Bruno ×2,2) |
| Groove (vuruş zarfı korelasyonu) | 0,30 | orijinalin ritmini zayıf izliyor (Viva La Vida 0,09) |
| Döngüsellik farkı | +0,11 (en çok +0,52) | orijinalden daha döngü gibi: "hep aynı şey" |
| Şarkılar arası aynılık | cover 0,941 / orijinal 0,891 | üretim şarkıları tek bir sese çekiyor |

## S20 — bölüm yapısı ve şarkıya özel betim (6 şarkı: balad, orkestral rock, folk, dance-pop+rap, indie rock)

Kollar: A bugünkü · B yeni bölüm yapısı (`yanki/yapi.py`) · C B + betim (`acestep-captioner`) · D C + shift 3.
Kapılar 24/24 geçti; söz WER farkları ±0,04 ölçüm gürültüsü içinde.

| Kol | groove | döngüsellik farkı | vurmalı | bölüm değişimi (1 = orijinal) | aynılık |
|---|---|---|---|---|---|
| A | 0,182 | +0,126 | ×1,57 | 0,67 | 0,949 |
| B | 0,171 | +0,123 | ×1,54 | 0,68 | 0,950 |
| C | **0,235** | **+0,043** | ×1,34 | **0,80** | 0,956 |
| D | 0,248 | +0,035 | ×1,40 | 0,82 | 0,952 |

- Kazanç betimden geliyor (B tek başına değiştirmedi; yapı yine de doğru söz biçimi ve S12'deki WER kazancı için kalır).
- Bruno Mars: groove 0,22 → 0,42, döngüsellik +0,33 → −0,09. Betim: "sparse, focusing entirely on the piano".
- shift 3 küçük ve tutarsız; tarife alınmadı.
- Şarkılar arası aynılık değişmedi: üretimin ses imzası (çözücü/miks), stil metninden gelmiyor → S23.
- Karar: `[motor] betim = true` (2026-10-12).

## S24 — beat ölçüleri aday seçimini tutuyor mu (21 şarkı, Scryne'ın 3 aday arasından seçimi)

Rastgele isabet ≈ 7,2/21. groove 7, az döngü 8, eğri 8, vurmalı 7, bölüm 7, parmak izi 8; **söz WER 11** (seçilenin
ortalama sırası 1,52). Aynı tarifin adayları beat'te birbirine benziyor: beat tariften düzelir, aday seçiminden
değil. Seçim ölçüsü söz WER olarak kalır.

## S23 — beat kolları (C tarifi üstüne, aynı 6 şarkı)

| Kol | groove | döngüsellik farkı | vurmalı | bölüm | aynılık | kapı |
|---|---|---|---|---|---|---|
| C (güç 0,7) | 0,235 | +0,043 | ×1,34 | 0,80 | 0,956 | 6/6 |
| G85 (güç 0,85) | 0,232 | +0,040 | ×1,36 | 0,83 | 0,956 | 6/6 |
| G100 (güç 1,0) | 0,232 | +0,018 | ×1,40 | 0,76 | 0,955 | 6/6 |
| R70 (orijinal tını referansı) | 0,400 | +0,081 | ×1,28 | 0,77 | 0,952 | 5/6 |
| R85 (referans + güç 0,85) | 0,423 | +0,055 | ×1,21 | 0,77 | 0,936 | 5/6 |

- Cover gücü beat'i değiştirmiyor: "son %30 adım kaynaksız → vurmalı uyduruluyor" varsayımı tutmadı. 0,7 kalır.
- Orijinal kaydı tını referansı vermek groove'u yükseltiyor ama orijinal kaydı sızdırıyor: parmak izi 0,53 → 0,58–0,67,
  dalga 0,01–0,04 → 0,06–0,12, Anise.K'da dalga 0,35 (kapı 0,25) düştü. Yayın yolu olamaz (spike S1'deki
  `cover-nofsq` gibi). Reddedildi.
- Şarkılar arası aynılık stil metniyle ve cover gücüyle kıpırdamıyor; yalnız tını referansı biraz düşürdü → S25:
  aynı sanatçının **başka** bir şarkısı referans (prodüksiyon imzası o sanatçıya, cover'ı yapılan kayıt sızmaz) ve
  ScragVAE çözücüsü.

## S26 — yeni mastering aynılığı düşürüyor mu (22 yüklenen şarkı, seçilmiş aday, yeni zincir + ton eşleme)

Orijinale tonal uzaklık her şarkıda düştü (ör. Bruno Mars 6,98 → 4,29 dB, Lana Del Rey 2,50 → 1,37 dB); şarkılar
arası aynılık 0,941 → 0,934 (orijinaller 0,891). Ton eşleme yardımcı ama "hepsi aynı" hissi spektral dengeden değil
üretimden geliyor: çözüm üretim tarafında (S25, eğitim).

## S25 — sanatçının başka şarkısı tını referansı (X) ve ScragVAE (V), C tarifi üstüne

| Kol | groove | döngüsellik farkı | vurmalı | bölüm | aynılık | kapı |
|---|---|---|---|---|---|---|
| C (aynı 5 şarkı, Anise.K hariç) | 0,256 | +0,074 | ×1,42 | 0,83 | — | 5/5 |
| X referans = sanatçının başka şarkısı (Deezer en çok dinlenen) | 0,319 | +0,070 | ×1,49 | 0,70 | 0,971 | 5/5 |
| C (6 şarkı) | 0,235 | +0,043 | ×1,34 | 0,80 | 0,956 | 6/6 |
| V ScragVAE | 0,251 | +0,035 | ×1,53 | 0,83 | 0,958 | 6/6 |

- X: groove yükseldi (Passenger 0,37 → 0,62) ama aynılık arttı (0,971), Viva La Vida'nın bölüm değişimi çöktü
  (0,63 → 0,18) ve aynı sanatçının sesi parmak izini yükseltti (Passenger 0,66, Jar of Hearts 0,62; eşik altında).
  Alınmadı.
- V: ölçülerde nötr. Bu ölçüler ritim/yapı; çözücünün etkisi tını (metalik vokal, transient) — kulağa kalır.
- Tarif: C (bölüm yapısı + betim, güç 0,7, shift 1, resmî çözücü). Aynılık için kalan kaldıraç: çok türlü veriyle,
  betimli stil ve bölüm etiketli sözle LoRA (2026-10-12 gece, 95 şarkı).

## S21 — yeni tarif balad dışı türlerde (A bugünkü, N bölüm yapısı + betim; her türden tanınmış bir şarkı)

| Tür | Şarkı | söz WER A → N | orijinalin WER'i | dinamik izleme A → N | kapı (yeniden ayarlı) |
|---|---|---|---|---|---|
| rap | Kendrick Lamar — HUMBLE. | 0,53 → 0,52 | 0,49 | 0,33 → 0,44 | geçer |
| melodik rap / R&B | Drake — Hotline Bling | 0,19 → 0,11 | — | 0,56 → 0,82 | geçer |
| EDM | Avicii — Wake Me Up | 0,29 → 0,24 | — | 0,73 → 0,86 | geçer |
| Latin (İspanyolca) | Luis Fonsi — Despacito | 1,03 → 0,70 | 0,31 | 0,60 → 0,56 | düşer |
| synth-pop | The Weeknd — Blinding Lights | 0,20 → 0,32 | — | 0,76 → 0,80 | geçer |
| rock | Imagine Dragons — Believer | 0,22 → 0,13 | — | 0,71 → 0,86 | geçer |

Beat (S22 ölçüleri, 6 tür): groove 0,35 → **0,51** (Hotline Bling 0,09 → 0,82, Believer 0,41 → 0,60), bölüm değişimi
0,83 → 0,92, dinamik izleme 0,58 → 0,69. Şarkılar arası aynılık cover 0,93 / orijinal 0,94: farklı türden kaynakta
cover'lar da orijinaller kadar farklı. "Hepsi aynı"nın bir kaynağı da yüklenen 22 şarkının neredeyse hepsinin balad
olması ve genel stil tanımıydı.

Kapılardaki iki tür körlüğü bu denemeyle bulundu ve düzeltildi (yanki/kapilar.py):
- **Dalga** tam bantta EDM'in kick/bas örtüşmesini (cover kaynağın zamanlamasını izliyor) kopya sanıyordu: Avicii 0,26
  (eşik 0,25). 300 Hz üstünde 0,03; orijinali taşıyan örnek her bantta 0,45. Kapı artık 300 Hz üstünde, eşik 0,20.
- **Söz WER** mutlak eşikti: Whisper orijinal rap kaydını da 0,49 anlıyor. Kapı orijinale göre: aday orijinalden en
  çok 0,10 kötü (tavan 0,80).

Keşifte açılan türler (config/kesif.toml): rap, hip-hop, trap, EDM, house, dance, electro. İspanyolca Latin kapalı
(cover orijinalden belirgin anlaşılmaz). Otomatik onayda bu türler kapalı kalır: Scryne dinleyince açılır
(calisma/dinleme/s21/).

## S27 — ACE-Step söz hizalama puanı aday seçimini tutuyor mu (21 şarkı, 62 aday, Scryne'ın seçimi)

Eski adaylar işçide "puanla" göreviyle üretildikleri koşullarla (kaynak, adayın stili, o günkü söz, tohum) puanlandı.
Rastgele ≈ 7,2. Yalnız DiT hizalama 9/21 (seçilenin sırası 1,81), LM hizalama 6/21, yalnız söz WER 11/21 (1,52).
**En düşük WER'li iki aday arasından hizalaması yüksek olan: 14/21.** (İki kural denendi; sıra toplamı 11/21. Örneklem
küçük, veri biriktikçe yeniden ölçülür.) Otomatik onayın önerisi bu kurala geçti (`onay.oneri`).

## S28 — çok türlü LoRA (95 şarkı, betimli stil, bölüm etiketli söz, 40 epoch; 2026-10-12 gecesi)

S20'nin 6 şarkısı, üretim tarifi (betim + bölüm yapısı), LoRA ölçeği 0 / 0,5 / 1; 18 çıktının 18'i kapıdan geçti.

| Ölçek | groove | döngüsellik farkı | vurmalı | bölüm | dinamik izleme | söz WER | hizalama |
|---|---|---|---|---|---|---|---|
| 0 | **0,238** | **+0,040** | ×1,36 | **0,82** | 0,63 | **0,137** | **0,131** |
| 0,5 | 0,207 | +0,137 | ×1,58 | 0,60 | 0,72 | 0,150 | 0,119 |
| 1 | 0,216 | +0,115 | ×1,45 | 0,64 | 0,72 | 0,181 | 0,108 |

LoRA beat'i kötüleştiriyor (daha döngüsel, bölümler arası daha düz), sözü bulanıklaştırıyor; yalnız dinamik izleme
iyileşiyor. İlk LoRA (balad) da ölçüde kazanç vermemişti. Olası neden: Side-Step LoRA'yı metinden-müzik görevinde
eğitiyor, üretim cover görevi (kaynak kodlarıyla koşullu); öğrenilen stil cover'a iyi taşınmıyor. Üretime bağlanmadı.
Not: söz WER'i bu ölçümde hâlâ tohumsuz Whisper'la (aşağıdaki düzeltmeden önce).

## Söz WER'inin belirliliği (2026-10-12)

Aynı dosya iki süreçte 0,37 ve 0,73 (blink-182 orijinal). Neden çok iş parçacıklı hesap değil (önceki not yanlış),
Whisper'ın sıcaklık geri düşüşü: eşik tutmayınca tohumsuz örnekleme. Sıcaklık 0 belirli ama zor kayıtta tutunamıyor
(Gasolina 1,0); sabit tohumlu geri düşüş belirli ve kurtarıcı (0,51). `kapilar.dokum` artık tohumlu.

## S29 — kalan türler (N = üretim tarifi, tek tohum; söz kapısı tohumlu Whisper, orijinale göre)

| Tür | Şarkı | söz WER (eşik) | orijinalin WER'i | kapı |
|---|---|---|---|---|
| metal | Metallica — Enter Sandman | 0,62 (0,72) | 0,62 | geçti |
| pop-punk | blink-182 — All the Small Things | 0,48 (0,80) | 0,70 | geçti |
| grunge | Nirvana — Smells Like Teen Spirit | 0,17 (0,80) | 1,26 | geçti |
| country | Shania Twain — You're Still the One | 0,20 (0,50) | 0,27 | geçti |
| jazz | Frank Sinatra — Fly Me to the Moon | 0,22 (0,50) | 0,36 | geçti |
| blues | B.B. King — The Thrill Is Gone | 0,58 (0,50) | 0,36 | düştü (tek aday; üretimde 4) |
| reggae | Bob Marley — Three Little Birds | 0,29 (0,56) | 0,46 | geçti |
| reggaeton (es) | Daddy Yankee — Gasolina | 0,35 (0,61) | 0,51 | geçti |
| K-pop (ko/en) | BLACKPINK — How You Like That | 0,48 (0,61) | 0,51 | geçti |
| afrobeats | Burna Boy — Last Last | 0,72 (0,80) | 0,75 | geçti |
| UK drill | Central Cee — Doja | 0,23 (0,59) | 0,49 | geçti |
| J-pop (ja) | YOASOBI — Idol | — | — | hazırlıkta durdu: LRCLIB yalnız İngilizce sürümün sözünü veriyor |

Parmak izi 0,50–0,61, dalga ≤ 0,08: hiçbiri orijinali taşımıyor. Keşifte açıldı: metal, punk, grunge, country, jazz,
blues, reggae, reggaeton/Latin, K-pop, afrobeats, drill. Hazırlıkta bulunan iki çok dilli söz açığı kapandı: LRCLIB
çeviri sürümü (Japonca seste İngilizce söz) ve satır sonu çevirisi (`Korece^İngilizce`).

## S30 — cover görevinde eğitilmiş LoRA (2026-10-12; üretime bağlandı)

S28'in teşhisi: Side-Step metinden-müzik görevinde eğitiyor (bağlam sessizlik, başka talimat, dil başlıksız söz),
üretim cover. `yanki/kapak_hazirla.py` her örneğin yanına bir cover kopyası yazar: hedef aynı kayıt, bağlam kaydın
kendi anlamsal kodlarından (üretimdeki tokenize → detokenize), talimat ve söz biçimi üretimdeki gibi. 95 şarkı × 2
tensör, 15 epoch, A40'ta 155 dk, 2,14 $. Değerlendirme eğitimde olmayan şarkılarla (deneme şarkılarının sanatçıları da
eğitimde yok), aynı tohum, üretim tarifi (betim + bölüm yapısı), LoRA ölçeği dışında her şey aynı.

Balad/pop (S20'nin 6 şarkısı; 18 çıktının 18'i kapıdan geçti):

| Ölçek | groove | döngüsellik farkı | vurmalı | bölüm | dinamik izleme | aynılık (orijinal 0,834) | söz WER | parmak izi | dalga |
|---|---|---|---|---|---|---|---|---|---|
| 0 | 0,234 | +0,041 | ×1,35 | 0,82 | 0,63 | 0,955 | 0,104 | 0,545 | 0,038 |
| 0,5 | 0,340 | −0,072 | ×1,34 | 0,86 | 0,74 | 0,934 | **0,094** | 0,584 | 0,073 |
| 1 | **0,569** | **−0,164** | ×1,13 | **0,98** | **0,82** | **0,918** | 0,120 | 0,620 | 0,102 |

11 tür (S29'un şarkıları; N = LoRA'sız, L = ölçek 1):

| Kol | groove | döngüsellik farkı | vurmalı | bölüm | dinamik izleme | aynılık (orijinal 0,902) | söz WER | kapı |
|---|---|---|---|---|---|---|---|---|
| N | 0,300 | +0,073 | ×1,85 | 1,12 | 0,53 | 0,911 | 0,388 | 11/11 |
| L | **0,583** | **−0,046** | **×1,38** | 1,31 | **0,79** | 0,927 | **0,374** | 10/11 (blues WER 0,70 > 0,50) |

Groove 11 türün 10'unda arttı (metal 0,11 → 0,50, afrobeats 0,06 → 0,79, K-pop 0,05 → 0,67, country 0,13 → 0,69);
dinamik izleme 11'inde. Beat orijinal kaydın ritmini ve bölüm dinamiğini izlemeye başladı: döngüsellik ilk kez
orijinalin altında. Söz karışık: 17 şarkının 10'unda düştü, 6'sında arttı (Walking on Air 0,16 → 0,41, Doja 0,23 →
0,45, B.B. King eşiği aştı); üretimde 4 aday ve kapı bunu süzer. Bedel: çıktı orijinale yaklaşıyor (parmak izi
ortalama +0,06–0,08, en çok 0,687 / eşik 0,72; dalga en çok 0,158 / eşik 0,20); kapılar aday başına aynı.

Karar: ölçek 1 üretime bağlandı (`[motor] lora`). Dinleme: `calisma/dinleme/lora/20261012-0808/` (lora_0 / 0,5 / 1),
`calisma/dinleme/s29/` (N / L).


### S30 kulak testi (2026-10-12 akşam, Scryne, üretim hattı: LoRA + betim + 4 aday)

| Şarkı | Tür / dil | En iyi söz WER (eski → yeni) | Kulak |
|---|---|---|---|
| Anise.K — Walking on Air | dance-pop + rap, İngilizce | 0,233 → 0,181 | aday 9 "gayet iyi", onaylandı (hattın önerisiyle aynı) |
| Big Daddy Kane — Daddy's Home | hip-hop, İngilizce | 0,677 → 0,566 | "çok kötü, bozuk", reddedildi |
| Nyoy Volante — Ipagpatawad Mo | OPM balad, Tagalogca | 0,561 → 0,424 | "kötü", reddedildi |

Kapılar ve söz ölçüsü üç şarkıda da iyileşti, kulak yalnız İngilizce pop'u geçirdi. Sonuç: rap keşifte yeniden kapalı
(`config/kesif.toml`); İngilizce dışı diller otomatik onayda zaten kapalı (`diller = ["en"]`). Rap ve İngilizce dışı dil
için ölçü kulağı tutmuyor: söz WER'i düşük olsa da ses bozuk olabiliyor, bu türlerde karar dinlemeden verilmez.

### S30 kör kulak testi (2026-10-12 gece, Scryne, dinleme odası → Karşılaştırma)

Kollar şarkıdan şarkıya karışık A/B/C, oy verilene kadar adsız (yanki/kulak.py; oylar `calisma/dinleme/kulak.json`).

| Set | Yeni model (LoRA, ölçek 1) en iyi | Eski model en iyi | Yarım ölçek en iyi | Hepsi kötü | Yayınlanabilir |
|---|---|---|---|---|---|
| 11 tür (eski / LoRA) | 8 | 0 | — | 3: afrobeats, UK drill, caz | 2: metal, country |
| 6 balad/pop (0 / 0,5 / 1) | 5 | 0 | 0 | 1: Let Her Go | 2: When I Was Your Man, How to Save a Life |

Cover görevinde eğitilen LoRA her şarkıda eskisini yeniyor ve tam ölçek yarımını yeniyor: uyarlama arttıkça iyi.
Ama 17 şarkıdan 4'ü yayınlanabilir. Sonuç: dördüncü eğitim daha uzun (15 → 30 epoch, 20. epoch ara kayıt) ve kötü
çıkan türlerden veriyle (95 → 123 şarkı: caz, blues, afrobeats, İngiliz rap/drill, reggae, metal, folk); aynı 17
şarkıda kör testle karşılaştırılır (set `egitim-4`). Üretim bu sırada duraklatıldı (Scryne: "boş yere üretmesin").

### S31: dördüncü eğitim (2026-10-12/13, 30 epoch, 123 şarkı, A40 6,7 saat, 4,54 $ + yeniden deneme 0,49 $)

Kayıp ilk epoch'ta 1,07 → 0,86, 20. epoch'ta 0,738, 30. epoch'ta 0,731: 20'den sonra yatay. Ara kayıt denemesi ilk
koşuda düştü: Side-Step'in klasör adı (`epoch_20_loss_0.7381`) PEFT'e bağdaştırıcı adı olarak gitti, nokta reddedildi.
Düzeltme `motor_isci.lora_adi`; kayıt yerelde olduğu için `yanki egit --deneme-yeniden` ile eğitimsiz yeniden üretildi.

Aynı 17 şarkı, aynı tohum ve tarif (v3 = üretimdeki üçüncü eğitim, 15 epoch, 95 şarkı):

| Kol | groove balad (6) | groove tür (11) | söz WER balad | söz WER tür | döngüsellik balad / tür |
|---|---|---|---|---|---|
| v3 (15 ep) | 0,569 | 0,583 | 0,120 | 0,374 | −0,164 / −0,046 |
| ep20 | 0,627 | 0,598 | 0,109 | **0,372** | −0,141 / −0,052 |
| ep30 | **0,635** | 0,597 | **0,080** | 0,405 | −0,127 / −0,051 |

Beat'te ep20 ile ep30 neredeyse aynı (şarkı şarkı fark çoğunlukla < 0,02); ikisi de v3'ten balad ve pop'ta belirgin,
türlerde az iyi. Söz şarkıdan şarkıya oynuyor (tek tohum): ep30 Walking on Air 0,41 → 0,17, B.B. King 0,70 → 0,29,
ama Last Last 0,64 → 0,94, Gasolina 0,22 → 0,48. Parmak izi aynı bantta (en çok 0,689, eşik 0,72). Ölçü kararı
vermiyor; seçim kör testte (set `egitim-4`, kollar v3 / ep20 / ep30). Dinleme:
`calisma/dinleme/lora/20261012-1702/` (`lora_1` = ep30, `lora_ep20`).

### S31 kör kulak testi (2026-10-13, Scryne, set `egitim-4`)

| Kol | En iyi | Yayınlanabilir |
|---|---|---|
| v3 (15 epoch, 95 şarkı) | 3: Jar of Hearts, Three Little Birds, Last Last | 1 |
| ep20 (123 şarkı) | 6: When I Was Your Man, Viva La Vida, Enter Sandman, The Thrill Is Gone, Gasolina, Doja | 4 |
| ep30 (123 şarkı) | 6: Walking on Air, How to Save a Life, All the Small Things, You're Still the One, Fly Me to the Moon, How You Like That | 4 |
| hepsi kötü | 2: Let Her Go ("vokal"), Smells Like Teen Spirit | — |

Yayınlanabilir 9/17 (S30'da 4/17): balad/pop 4, metal, pop-punk, country, reggaeton. Yeni veri ve uzun eğitim
12/17'de eskisini yendi. ep20 ile ep30 berabere; **ep20 üretime bağlandı** (türlerde söz WER'i daha iyi, beat aynı,
daha az eğitim). En iyisi bile yayınlanamaz bulunan türler iki testte de aynı: caz, blues, reggae, afrobeats, K-pop,
drill, grunge → keşifte kapalı (`config/kesif.toml`); keşif sorguları kulağı geçen türlere daraltıldı.


### S31b: beşinci eğitim, ep20'den devam (2026-10-13, 12 epoch, 160 şarkı, A40 3,4 saat, 3,31 $)

Dördüncü eğitimin 20. epoch'undan devam (Side-Step'in devam yüklemesi PEFT anahtar adı yüzünden hiçbir ağırlık
yüklemiyordu; yama `yanki/devam_yamasi.py`, podda "512 anahtar yüklendi", ilk kayıp 0,756 ↔ sıfırdan ~1,07). 52 şarkı
eklendi (80'ler/90'lar/2000'ler rock, metal, country, caz, blues, reggae, afrobeats, K-pop, rap). Kayıp 12 epoch
boyunca 0,743–0,758: yatay; model veri dağılımını ep20'de zaten öğrenmiş.

Kör test (set `egitim-5`, aynı 17 şarkı ve tohum; ep20 / ek 6 epoch / ek 12 epoch): **ep20 13**, ek12 2 (How to Save
a Life, Doja), ek6 1 (Last Last), hepsi kötü 1 (Let Her Go). Yayınlanabilir 10/17 (9'u ep20). Ek eğitim kazanmadı,
**ep20 üretimde kalır**. Scryne: "vokal şu anlık okey, beat tarafı hâlâ eksik ve kötü": ince/güçsüz, bas zayıf,
enstrüman eksik, ritim yanlış, hepsi aynı. Aynı tek-geçişli cover üstüne daha fazla eğitim beat'i düzeltmiyor → S32.

## S32 — beat'i ayrı ele almak (2026-10-14; `spikes/s32_*`)

**Ölçüm (Demucs htdemucs, 17 şarkı, ep20 − orijinal, parça seviyesi vokale göre):** bas medyan −4,1 dB (13/17
düşük), diğer enstrümanlar −2,6 dB (13/17), davul −0,7 dB. Baladlarda tersine orijinalde olmayan davul ve bas
ekleniyor (When I Was Your Man +18/+24 dB, Jar of Hearts +38/+41 dB) ve bu davulun vuruşu boğuk (crest −6,9 dB).
Kulağın "ince, bas zayıf" teşhisi ölçüde de var.

**Kollar (hepsi ep20 vokaliyle, yayın mastering'inden geçmiş, −14 LUFS):** A şu anki çıktı · B parça parça ton
eşleme (Demucs parçaları orijinalin parçalarına göre EQ + seviye; arkadaşın yapımcı isteminin otomatik hali) · E
orijinalin vokalsiz eşliğinin enstrümantal cover'ı (xl-sft + ep20, 0,47 $) + ep20 vokali · C ep20 vokali üstüne
xl-base `complete` (0,30 $; işçiye `complete` görevi eklendi). Araştırma: SFT-stems checkpoint'i yayımlanmamış,
`lego`/`complete` yalnız base/xl-base'de.

| Kol | Kapılar | Söz WER medyan | Parmak izi en çok (eşik 0,72) |
|---|---|---|---|
| A | 15/17 | 0,195 | 0,684 |
| B | 14/17 | 0,294 | 0,683 |
| E | 10/17 | 0,375 | 0,692 |
| C | 15/17 | 0,238 | **0,640** |

Sızıntı yok (orijinal eşlikten üretilen E bile eşiğin altında). Eşlik yükseldikçe Whisper vokali daha az anlıyor
(B, E): söz WER'i burada "vokal gömüldü mü" uyarısı, kalite ölçüsü değil. C orijinalden en uzak (parmak izi en
düşük): beat vokalden yeniden kuruluyor. Karar kör testte (set `beat-1`).

**Kör test (Scryne, 2026-10-14):** A 13, B 3 (Viva La Vida, Gasolina, Last Last), E 1 (How You Like That), C 0;
yayınlanamaz işaretli 3 (When I Was Your Man A, Viva La Vida B, Let Her Go A). Beat'i sonradan işlemek kazanmadı: sorun
üretimin kendisinde. Tür deseni yok: baladlarda When I Was Your Man ve Jar of Hearts iki testte de yayınlanabilir, Let
Her Go her testte kötü. Aynı ep20 dosyası `egitim-4`'te yayınlanabilir, `egitim-5`'te değil (Viva La Vida, Gasolina):
tek tohumun tek dinlemesi gürültülü; kararlar çok şarkıda ve tercih sayısıyla verilir.

## Araştırma (2026-10-14)

- ACE-Step: 2026-08-29'dan sonra yeni checkpoint/sürüm yok (son tag v0.1.8, 18 May; HF kartı xl-sft MIT). SFT-stems,
  fix-inst, 1.6/2 için kaynak yok.
- Çıkarım: INFERENCE.md "en iyi kalite" için ADG, CFG 7–9, shift 3; issue #1019 (topluluk) SFT'de CFG 7 "agresif beat",
  2 daha iyi; discussion #1268 shift 1 ↔ 3 tohum farkından küçük. DCW 28 Ağu'dan beri non-turbo'da varsayılan kapalı.
- Eğitim: Side-Step rehberi 50+ şarkıda 50–100 epoch, rank 128 "azami kalite". **Bizim eğitimlerin hepsi Side-Step
  varsayılanı `--target-modules q_proj k_proj v_proj o_proj` ile: LoRA yalnız dikkat katmanlarında**
  (`adapter_config.json`), DiT'in MLP'sine (gate/up/down_proj) hiç dokunulmadı. Ek eğitimin kazanmaması ve kaybın
  yataylaşması bununla tutarlı; tını/enstrüman dokusu MLP'de.
- Başka modeller: YuE2 (Eyl 2026, 3,58B, 24 GB) yazarlarının WildSongBench tablosunda ACE-Step 1.5'i geçiyor
  (SongBench 6,73 / 6,01); cover'ı nota + ASR üzerinden sıfırdan kuruyor; ağırlıklar CC BY-NC 4.0 + bireysel yaratıcıya
  gelir izni. MuLaCover (HeartMuLa, cover; ticari kullanım yazılı izin), LeVo 2 (lisans bulunamadı). Bağımsız insan
  tercihi bulunamadı.

## S33 — örnekleme ayarları (eğitimsiz; 2026-10-14, `spikes/s33_ornekleme.py`)

ep20, üretim tarifi, tohum 42, aynı 17 şarkı; tek ayar değişir. A taban (aynı koşunun betiğiyle), D DCW, H heun, S sde,
G CFG 10; ikinci tur J ADG, L CFG 3, K güç 0,5. Ölçüm `spikes/s33_olcum.py` (kapılar, S22 beat, S32 parça seviyeleri);
umut veren kollar kör teste. İlk koşu evdeki ağ ~10 dk kopunca yerelde düştü, pod çalışmaya devam etti; çıktılar
yeniden bağlanarak alındı (`uzak.isci_kos` artık kopuk yoklamada düşmüyor).

**İlk tur durumu (14:37, kısmi):** hesap 1'in bakiyesi koşuya yetmedi ve Scryne bilgisayarı kapattı; biten 77/85 iş
indirildi (`calisma/dinleme/s33/<şarkı>/<kol>.flac`, `sonuc.json`), pod kapatıldı. 15 şarkıda beş kolun hepsi var,
16. şarkıda yalnız A ve D, 17. şarkı yok. Hesaplar: 0,12 $ / 1,78 $. Sıradaki adımlar:
1. Ölçüm: `uv run --no-sync python spikes/s33_olcum.py kapilar`, sonra
   `motor/ACE-Step-1.5/.venv/Scripts/python.exe spikes/s33_olcum.py beat`, sonra `... s33_olcum.py ozet`.
2. İkinci tur hesap 2'yle: `uv run --no-sync python spikes/s33_ornekleme.py J L` (17 × 2 kol ≈ 1,1 $; üç kol 1,78 $'a sığmayabilir, K bakiye
   gelince). Not: koşu bir kolun bütün şarkılarını üretir; ilk turun eksik 8 işi (16. şarkı H S G, 17. şarkı hepsi)
   şimdilik eksik kalır.
3. Umut veren kollar `yanki/kulak.py` SETLER'e yeni set (`ornekleme-1`), Scryne dinleme odasında kör oylar.

## S34 — dikkat + MLP LoRA (hazır, bakiye bekliyor)

Sıfırdan (katman kümesi değişti), aynı 175 şarkı, rank 64, lr 1e-4, 20 epoch, ara kayıt 10; `config/egitim.toml`
`hedef_moduller`. Kör testte ep20'ye karşı. Gereken: tek hesapta ≥ 8,25 $; Scryne'a ~15 $ yükleyip `aylik_butce`'yi
30'dan 45'e çekmek önerildi (cevap bekleniyor). Başlatma: `yanki egit`. S33 ve S34 kazanmazsa YuE2 10 şarkıda denenir.
