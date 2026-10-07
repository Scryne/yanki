# Dağıtımcı karşılaştırması (2026-10-07)

Faz 5'in açık kararı (dağıtımcı) için operasyonel tarama: dağıtımcı tamamen AI vokalli ve AI enstrümanlı bir cover'ı
kabul ediyor mu, formda ne istiyor, kaça mal oluyor. Hukuki değerlendirme yok. Zendesk tabanlı yardım sayfalarının
çoğu (DistroKid, TuneCore, CD Baby, LANDR, UnitedMasters) tam metin okunamadı (403). Bu sayfalardaki bulgular resmî
alan adlarının arama özetlerinden geliyor, yüklemeden önce yeniden bakılmalı.

## Özet

| | Tam AI ses | AI cover | Cover adımı | Fiyat | Ses / kapak | Not |
|---|---|---|---|---|---|---|
| **DistroKid** | kabul, formda AI Credits alanı | açık kural yok | formda cover seçilir, $12/yıl/şarkı | $24.99 / 44.99 / 89.99 yıl | WAV/FLAC, kapak 3000 | AI beyanını Spotify'a ileten tek dağıtımcı (2026-07) |
| **RouteNote** | kabul, ek inceleme | açık kural yok | ücretsiz; ABD/CA/MX/IN/PK hariç tutulur | ücretsiz (%85) ya da $10 + $9.99/yıl | **WAV yok, FLAC/MP3 44,1** (2023 kaynağı), kapak 3000 JPG | AI içerik Amazon ve Kore mağazalarına gitmez; AI aracına kredi verilmez |
| **Ditto** | kabul, bazı mağazalar hariç | açık kural yok | yalnız yayın için ek adım yok, indirme için belge | $19 / 59 / 109 yıl | WAV 16/44,1, kapak 3000 JPG | kapaktaki başlık metadata ile birebir |
| **Too Lost** | kabul, kalite kontrol | bulunamadı | $14.99 | $19.99 yıl | bulunamadı | yalnız arama özeti |
| TuneCore | "lisanslı veri setiyle eğitilmiş model" şartı, vaka bazlı | belirsiz | $17 / $70 (Royalty Solutions) | $24.99+ yıl | WAV, kapak 1600–3000 | yazılı teyitsiz kullanılmaz |
| CD Baby | **ret** (kısmi AI dahil) | ret | — | — | — | elenir |
| Amuse | sınırlı | **"AI covers will also be rejected"** | — | — | — | elenir |
| LANDR | tamamen AI'ya dayananı dağıtmayabilir | **dağıtılmıyor** | — | — | — | elenir |
| UnitedMasters | kabul | **cover dağıtılmıyor** | — | — | — | elenir |
| Soundrop | **ret** | ret | — | — | — | elenir |

Yükleme API'si: dağıtımcıların hiçbirinde bireysel kullanım için yok (LabelGrid'in API'si kurumsal planda, $139/ay+).
`paket.py`'nin "yükleme insanda kalır" varsayımı geçerli.

## Spotify tarafı (operasyonel)

- Ses taklidi yalnız taklit edilen sanatçının izniyle. Spam filtresi toplu yüklemeyi, kopyayı ve çok kısa parçaları
  öneriden çıkarıyor (Spotify newsroom, 2025-09-25). → Yüklemeler seyrek tutulmalı.
- AI Credits (DDEX) gönüllü, sıralamaya etkisi duyurulmadı. Beyan Spotify'a yalnız dağıtımcı iletirse ulaşıyor.
- "AI Persona" rozeti (2026-09): fotogerçekçi AI insan olarak sunulan sanatçı, takip edilmedikçe önerilerden çıkıyor.
  Yalnız AI araçlarıyla üretmek rozeti tetiklemiyor. → Sanatçı profilinde fotogerçekçi AI insan görseli kullanılmaz.

## Hatta etkisi

- **RouteNote seçilirse:** paket WAV yerine FLAC (44,1 kHz / 16 bit) üretmeli. WAV kabul etmediği bilgisi 2023
  tarihli; yükleme ekranında doğrulanmalı. YUKLE.md'de AI aracı kredi alanına yazılmamalı.
- **DistroKid seçilirse:** formdaki AI sorusunda "all of the audio" seçilir. Bu seçenek sanatçının insan mı AI persona
  mı olduğunu da soruyor. Cover adımı formda.
- Her iki adayda da "tamamen AI vokal + AI enstrüman, orijinal söz ve beste" için açık bir kabul cümlesi yok. Para
  ödemeden önce destek ekibine yazılı soru sorulmalı.
- Türkiye'den ödeme hiçbir dağıtımcının resmî sayfasında açıkça teyit edilmedi (DistroKid Tipalti, RouteNote/Ditto
  PayPal + banka + Payoneer).

## Kaynaklar

DistroKid: [AI politikası](https://support.distrokid.com/hc/en-us/articles/41182362733715-Can-I-Upload-Music-Made-With-AI-Tools-to-DistroKid),
[AI Credits](https://support.distrokid.com/hc/en-us/articles/50784235803411-What-Are-AI-Credits),
[Cover Songs](https://support.distrokid.com/hc/en-us/sections/360004388974-Cover-Songs),
[fiyat](https://distrokid.com/pricing/), [DMN 2026-05-14](https://www.digitalmusicnews.com/2026/05/14/distrokid-ai-credit-disclosure-what-it-looks-like/),
[Interspace 2026-07-19](https://interspacemusic.com/blog/spotify-ai-credits-live-disclosure-only-travels-through-your-distributor/) ·
RouteNote: [AI](https://support.routenote.com/kb-article/can-i-upload-ai-releases/),
[AI biçimi](https://support.routenote.com/kb-article/how-should-i-format-a-release-containing-ai-generated-music/),
[cover](https://support.routenote.com/kb-article/can-i-upload-cover-songs-with-routenote/),
[cover biçimi](https://support.routenote.com/kb-article/how-do-i-format-a-cover-with-routenote/),
[ücret](https://support.routenote.com/kb-article/how-much-does-routenote-cost/),
[WAV](https://routenote.com/blog/can-i-upload-wav-to-routenote/),
[kapak](https://support.routenote.com/kb-article/what-are-the-album-artwork-requirements/) ·
Ditto: [AI](https://support.dittomusic.com/en/articles/13973284-can-i-release-ai-generated-music-with-ditto-music),
[cover](https://support.dittomusic.com/en/articles/4424809-can-i-release-cover-songs-remixes-or-songs-using-samples),
[fiyat](https://dittomusic.com/en/pricing) ·
TuneCore: [GenAI](https://support.tunecore.com/hc/en-ca/articles/46914166185236-TuneCore-s-GenAI-Policy) ·
CD Baby: [AI](https://support.cdbaby.com/hc/en-us/articles/23638450756237-Understanding-Production-Sounds) ·
Amuse: [içerik](https://support.amuse.io/en/articles/131081-content-not-approved-on-amuse) ·
LANDR: [AI](https://www.landr.com/ai-music-tools-and-music-distribution) ·
UnitedMasters: [cover](https://support.unitedmasters.com/hc/en-us/articles/27418124255763-Can-I-release-cover-songs-through-UnitedMasters) ·
Soundrop: [içerik](https://support.soundrop.com/hc/en-us/articles/41702672171789-Downtown-Music-Content-Policy) ·
Spotify: [newsroom 2025-09-25](https://newsroom.spotify.com/2025-09-25/spotify-strengthens-ai-protections/),
[AI Persona](https://support.spotify.com/us/artists/article/ai-personas/).
