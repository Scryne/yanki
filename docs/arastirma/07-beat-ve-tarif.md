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
