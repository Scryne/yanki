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

## S23 — beat kolları

(sürüyor: cover gücü 0,85 / 1,0, orijinal kayıt tını referansı)
