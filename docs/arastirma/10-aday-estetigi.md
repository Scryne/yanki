---
proje: Yanki
created: 2026-10-18
type: arastirma
---
# Aday estetiği: hazır değerlendiriciler (2026-10-18)

Scryne (2026-10-18): "AI cover hattını çok daha profesyonel bir hale getirebilmek için neler yapabiliriz?" → "her şeyi
sana bırakıyorum, model eğitimi hariç". En büyük açık yayına giden adayın seçimi: öneri kuralı (söz WER'i + ACE-Step
hizalaması) Scryne'ın kulak seçimini 12 şarkıda 3 tutuyor (%25; rastgele 2,1, `yanki isabet`). Veto penceresi açık
(Scryne'ın kararı, 2026-10-10), dinlenmeyen şarkıda yayına giden aday şansa yakın. Kapı ölçüleri (söz, beat, parmak
izi) kulağı açıklamıyor (Faz 12 ölçümleri, `docs/arastirma/07`).

## Seçenekler (araştırma, kaynaklar aşağıda)

| Değerlendirici | Ne ölçer | Kurulum | İnsan tercihiyle |
|---|---|---|---|
| **SongEval** (ASLP-lab, 2025) | tam şarkı; Coherence, Musicality, Memorability, Clarity, Naturalness (1–5) | repo + MuQ-large (HF), checkpoint repoda (96 MB) | Music Arena çift tercihi %70,8; kendi verisinde Musicality LCC 0,916 (iyimser) |
| **Audiobox Aesthetics** (Meta, 2025) | 10 sn pencerelerin ortalaması; CE, CU, PC, PQ (1–10) | `pip install audiobox_aesthetics` | Music Arena %68,5 |
| MuseCritic (2026) | MOSS-Audio-8B + LoRA | 8 GB'a sığmaz | %71,4 (fark ~0,5 puan): alınmadı |
| Song Aesthetics Evaluation (ISMIR 2026) | vokal/eşlik ayrı | stem ayırma + conda: alınmadı | — |

ACE-Step 1.5 makalesi kendi çıktısını SongEval ve Audiobox'la raporluyor (SongEval Coh 4,72 / Mus 4,67). Hiçbir kaynak
"aynı şarkının 4 adayı arasında" sıralama doğruluğu ölçmemiş: adaylar aynı tarif ve şarkıdan, farkları küçük. Bu yüzden
değerlendirici körü körüne bağlanmaz, Scryne'ın seçimleriyle ölçülür.

## Kurulum ve ölçü

`araclar/degerlendirici/` (ayrı venv, torch 2.7.1 cu128; README → Kurulum), işçi `yanki/degerlendirici_isci.py`.
Tuzaklar: transformers 5.x MuQ'yu düşürüyor (`EasyDict … _attn_implementation`) → 4.46.3; dizüstü RTX 4060'ta GPU'nun
~6,4 GB'ı başka işlerle dolu, MuQ-large 4 dk şarkıda sığmıyor (CUDA bellek hatası bağlamı da bozuyor) → varsayılan CPU,
dosya başı ~77 sn (iki model birlikte).

## Sınama (2026-10-18)

Elde kalan veriyle (2026-10-18 temizliği seçilmeyen adayların ve eski deneme setlerinin seslerini sildi): kör test
`egitim-4`'te Scryne'ın ep20/ep30 arasında seçtiği 12 şarkı, yayınlanabilir (8) ve "hepsi kötü" (4) kollar, 17 deneme
şarkısının orijinali, yüklenen 13 şarkının seçili adayı ve orijinali. 77 dosya, CPU, hatasız
(`calisma/olcum/estetik/sonuc.json`).

| Soru | SongEval ort. | En iyi tek eksen | Audiobox PQ |
|---|---|---|---|
| İki model arasında Scryne'ın seçtiğini tutar mı (12) | 6/12 | Coherence, Clarity 8/12 | 7/12 |
| Yayınlanabilir ile hepsi kötüyü ayırır mı (AUC) | 0,50 | Coherence 0,59 | 0,44 (PC 0,75) |
| Orijinal kayıt cover'dan yüksek mi (17) | **16/17** (3,98 / 3,40) | Naturalness 16/17 | 4/17 (cover'ı yüksek tutar) |
| Yüklenen 13 şarkıda orijinal > seçili aday | **13/13** (4,33 / 3,64) | | 0/13 |

- **Seçim için yok:** iki model arasındaki puan farkı 1–5 ölçeğinde ~0,06; 8/12 bile tesadüften ayrılmıyor (p ≈ 0,19).
  Yayınlanabilirliği de ayırmıyor: "hepsi kötü" Smells Like Teen Spirit orijinalinin 0,25 altında, "yayınlanabilir"
  Enter Sandman 0,34 altında.
- **SongEval insan kaydı ile AI cover'ı açıkça ayırıyor** (en çok doğallık ekseninde); Audiobox tersini söylüyor
  (temiz, yüksek sesli üretimi ödüllendiriyor), seçimde tek başına kullanılmaz.
- Sınırlar: ep20 ve ep30 kulakta da berabereydi (S31), yani zor bir sınav; aynı tohumla iki model, farklı tohumlu
  adaylardan daha benzer çıkar. Asıl sınav aynı şarkının dört adayı arasında Scryne'ın seçimi: o veri ancak bundan
  sonra birikiyor (puanlar `Aday.estetik`'te).

**Karar:** seçici bağlı ama uykuda (`otomatik`): en az 10 kulak seçiminde %70 ve kuraldan iyi olmadıkça öneriyi
almaz. Bugünkü kanıtla o eşiği geçmesi beklenmiyor; geçmezse 10 seçimden sonra puanlama adımı kapatılır (koşu başı
~10 dk CPU). Ayrı kullanım: model karşılaştırmasında (S34) "orijinale göre doğallık açığı" kör testin yanında nesnel
ikinci ölçü olabilir (17 şarkı × 2 tohum ortalaması, tek adaydan çok daha az gürültülü).

## Bağlantı (hatta)

- Dinlemeye çıkan her kapıdan geçmiş aday koşuda puanlanır (`estetik` adımı, koşu başı en çok 8, düşük öncelik); puan
  `Aday.estetik`'te, dosya temizlikte silinse de kalır.
- `onay.oneri(d, "estetik")`: en yüksek puanlı aday; bir adayın puanı yoksa kural.
- `[otomatik_onay] secici = "otomatik"`: estetik seçici en az 10 kulak seçiminde %70'i tutturup kuraldan iyiyse öneri
  onundur (Faz 12 ölçütü), değilse kural. `yanki isabet` ikisini aynı şarkılarda yan yana gösterir.
- Puan odada gösterilmez: Scryne görürse seçimi puandan etkilenir ve ölçüm kendini doğrular.

## Kaynaklar

- SongEval: https://github.com/ASLP-lab/SongEval, arXiv 2505.10793
- Audiobox Aesthetics: https://github.com/facebookresearch/audiobox-aesthetics, https://huggingface.co/facebook/audiobox-aesthetics
- ACE-Step 1.5: arXiv 2602.00744; ACE-Step v1: arXiv 2506.00045
- MuseCritic (Music Arena karşılaştırması): arXiv 2608.11755
- Song Aesthetics Evaluation: arXiv 2601.12222
