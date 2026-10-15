# 08 — Dağıtım otomasyonu (Tunearo sonrası, 2026-10-15)

Soru: Tunearo API'si kapandıktan sonra (2026-10-11, 403) paketi insansız yükleyebileceğimiz bir dağıtımcı var mı?
Faz 10'un engeli bu. Kaynaklar 2026-10-15'te okundu; hukuk analizi yok, platform kuralları yalnız "hat çalışır mı"
açısından. Önceki politika karşılaştırması `02-dagitimci-karsilastirmasi.md`.

## Sonuç

Bireysel hesaba açık, belgelenmiş ve fiyatı yayımlı tek yükleme API'si **LabelGrid**. En ucuz API planı $139/ay
(yıllık faturalı, ~1.668 $/yıl), aylık GPU bütçemizin (30 $) dört katından fazla. Bugünkü hacimde karşılanmaz.
Diğer API'ler (Revelator, FUGA, Sonosuite, Label Engine) satış ya da başvuru kapısının arkasında. DistroKid,
RouteNote, Ditto, Symphonic ve TuneCore'da bireysel kullanıma açık API bulunamadı.

**Öneri (dağıtımcı seçimi Scryne'ın):** dağıtım şimdilik RouteNote'ta elle sürsün (çalışıyor; ilk parça 2026-10-28'de
yayında), Faz 10 engelli kalsın. Model kör testlerde yayınlanabilir orana ulaşıp hacim artarsa LabelGrid yeniden
tartılır; öncesinde aşağıdaki sorular yazılı sorulur.

## Adaylar

| Aday | API | Erişim | AI cover | Bölge hariç tutma | Durum/ret okuma | Maliyet |
|---|---|---|---|---|---|---|
| LabelGrid | var, REST + sandbox + webhook | ücretli API planı, token panelden; 7 günlük deneme API'yi kapsamıyor | tam AI kabul, beyan zorunlu; cover'a özel cümle yok | yayın düzeyinde var; cover'da "Licenses" sekmesinin API'de engel olup olmadığı doğrulanamadı | var (`delivery-status`, `review-issues`, webhook) | $139/ay'dan; sayfalar arasında taahhüt (2 yıl?) çelişkili |
| Too Lost | belirsiz: `api.toolost.com/v1` OAuth yalnız gayriresmî SDK'da | resmî portal yok | AI kabul, tam AI ayrı kalite kontrol; cover bilinmiyor | doğrulanamadı | doğrulanamadı | $19,99/yıl |
| RouteNote | bulunamadı (API, CSV/DDEX, partner programı geçmiyor) | — | kabul, ek inceleme; Amazon, Kore, Content ID'ye AI gitmez | var ("Manage Stores") | yalnız web | ücretsiz (%85) |
| DistroKid | yok | — | kabul; cover'da lisans zorunlu | destek talebiyle | yok | $24,99+/yıl |
| Ditto | bulunamadı | — | AI kabul; cover'da lisans belgesi | doğrulanamadı | yok | $19+/yıl |
| Symphonic | bulunamadı | — | lisanslı model + beyan şartı (ikincil kaynak) | doğrulanamadı | yok | $29,99/yıl |
| TuneCore | eski ortak API haberi, güncel belge yok | onaylı ortak | "lisanslı veri setiyle eğitilmiş model" | — | yok | $24,99+/yıl |

## Tarayıcı otomasyonu (platform kuralı)

- DistroKid Terms (2026-09-24): "robots, spiders or scripts" ile erişim yasak. TuneCore Terms §11(9): yazılı izinsiz
  "robot, spider, scraper, or other automated means" yasak. → Bu ikisine Playwright yazılmaz.
- Symphonic §13.2 bot "dağıtmayı" yasaklıyor; kendi hesabını otomatikleştirmeyi kapsayıp kapsamadığı net değil.
- **RouteNote şart metni okunamadı** (sayfa gövdesi boş geldi). RouteNote'a Playwright yazmadan önce metin elle
  okunmalı ya da RouteNote'a yazılı sorulmalı. Doğrulanmadan otomasyon kurulmaz.
- DistroKid'de 2026-09'dan beri toplu parça kaldırma dönemi (DMN 2026-10-12); dağıtımcı değişikliği gündeme gelirse
  operasyonel risk olarak not.

## Açık kalan sorular (yazılı sorulacak; Scryne'ın hesabından)

- **LabelGrid:** tam AI vokalli cover kabul ediliyor mu; mekanik lisanssız + ABD/CA/MX/IN/PK hariç bir yayın API'den
  `distribute` edilebiliyor mu; Amazon ve YouTube Content ID kapatılabiliyor mu; sandbox ücretsiz mi.
- **Too Lost:** `api.toolost.com` resmî mi, OAuth uygulaması kaydedilebiliyor mu, AI cover kabulü.
- **RouteNote:** hesap sahibinin kendi yüklemesini tarayıcı otomasyonuyla yapması şartlara uygun mu.

## Kaynaklar

LabelGrid: [API belgesi](https://api.labelgrid.com/docs/api), [API erişimi](https://help.labelgrid.com/en/developers/api-overview/),
[fiyat](https://labelgrid.com/pricing/), [AI](https://labelgrid.com/blog/content-distribution/ai-music-on-labelgrid-what-you-need-to-know/),
[cover](https://help.labelgrid.com/en/help/cover-song-licensing/) (sayfaların çoğu 403, arama özetinden) ·
Revelator: [API](https://revelator.com/pricing/revelator-api), [belge](https://api-docs.revelator.com/v2/en/getting-started/) ·
Too Lost: [gayriresmî SDK](https://toolost.js.org/guide/getting-started) ·
RouteNote: [cover](https://support.routenote.com/kb-article/can-i-upload-cover-songs-with-routenote/),
[AI (2026-08-17)](https://support.routenote.com/kb-article/can-i-upload-ai-releases/),
[API yazısı](https://routenote.com/radar/what-is-a-music-distribution-api/) ·
Ditto: [AI](https://support.dittomusic.com/en/articles/13973284-can-i-release-ai-generated-music-with-ditto-music),
[cover](https://support.dittomusic.com/en/articles/4424809-can-i-release-cover-songs-remixes-or-songs-using-samples) ·
Şartlar: [DistroKid](https://distrokid.com/terms/), [TuneCore](https://www.tunecore.com/terms),
[Symphonic](https://symphonic.com/terms-of-use/), [RouteNote](https://routenote.com/termsandconditions) ·
[DistroKid kaldırmaları (DMN)](https://www.digitalmusicnews.com/2026/10/12/distrokid-v-umg-removals/) ·
İkincil: [LabelGrid API karşılaştırması](https://labelgrid.com/compare/best-music-distribution-apis/)
