# 11 — DistributeMusic.AI (2026-10-26)

Scryne (2026-10-26): "dağıtıcı buldum, https://distributemusic.ai/ buradan atıcaz." Soru: hat bu dağıtımcıya nasıl
bağlanır, AI cover'ı hangi kurallarla kabul eder. Kaynaklar 2026-10-26'da okundu (site sayfaları, şartlar, API belgesi;
panel giriş arkasında, görülmedi). Hukuk analizi yok; platform kuralları yalnız "hat çalışır mı" açısından.

## Sonuç

- **AI kabul, beyan zorunlu.** Şartlar §4: AI aracıyla yapılan parçada yüklemede AI beyanı açılmalı; beyansız AI §8'de
  anında hesap kapatma nedeni. API'de `is_ai_generated: true` + `ai_music_link`. Araç listesinde ACE-Step yok (Suno,
  Udio, MusicGen, ElevenLabs…, llms.txt'te "any WAV output"). ACE-Step'in şarkı başına paylaşım sayfası olmadığı için
  hat aracın sayfasını verir (`config/yayin.toml` → `[distributemusic] ai_baglanti`).
- **Cover için kural yok, mekanik lisans hiç geçmiyor.** Şartlar §5 "telifli melodiler" dağıtılmaz; §8 "yazılı lisansı
  olmayan telifli materyal (samples, melodies, vocals, instrumentals, cover art)" anında kapatma, iade yok, bekleyen gelir
  kaybı, bütün yayınlar kaldırılır, kalıcı yasak. Bu cümleler cover'ı ne açıkça kapsıyor ne dışarıda bırakıyor. Blog
  "Cover"ı bir sürüm türü (`version_type`) olarak sayıyor.
  → **Toplu yüklemeden önce destekten yazılı sorulmalı** (aşağıda metin). Hat API kipinde `sozlesme_kabul = false`
  iken hiç gönderim yapmaz; panel kipinde YUKLE.md uyarır.
- **Bölge seçimi görünmüyor.** API'de bölge alanı yok; RouteNote'taki ABD/CA/MX/IN/PK hariç tutması burada uygulanamaz.
- **Spam kuralı:** §8 "hundreds of near-duplicate uploads" ve çok hesap kapatma nedeni; sayısal üst sınır yok.
- **Çok yeni:** alan adı 2026-06-09'da kaydedilmiş, tüzel kişi/adres yazmıyor, bağımsız kullanıcı yorumu bulunamadı
  (Trustpilot 0). Ödemenin çalıştığına dair kanıt da, şikâyet de yok.

## Fiyat ve yükleme yolu

| Plan | Ücret | Not |
|---|---|---|
| Starter | 0 $ | yılda **1 single**, gelir %85 |
| Pro | 10 $/yıl (indirimli, normali 20 $) | sınırsız yayın, %100; tek sanatçı adı (Orvane yeter) |
| Label | 50 $/yıl | sınırsız sanatçı; API planının ön koşulu |
| Distribution API | 99 $/ay ya da 999 $/yıl | Label + API: yıllık ~1.049 $ |

Çıkım en az 5 $ (PayPal, banka). Takedown 5 $.

- **Panel (önerilen, bugün):** Pro yeterli. Hat paketi hazırlar (16 bit / 44,1 kHz WAV, 3000×3000 JPG, panelin
  alanlarıyla `YUKLE.md`), takvim sırası geleni bildirir; Scryne yükler, `yanki yuklendi <kimlik>`.
- **API (hacim artarsa):** `https://distributemusic.ai/api/v1`, `Authorization: Bearer dm_live_…`, 60 istek/dk,
  webhook yok. `POST /files` (`kind=audio|cover`, dönüştürme gerekirse `GET /files/jobs/{id}`), `POST /releases`
  (açmak = incelemeye göndermek, taslak yok), `GET /releases/{id}` (`pending → approved/delivered → live`,
  `rejected`/`changes_requested` + `feedback`), `GET /releases/{id}/links` (UPC, ISRC, smart link; listelenince).
  `genre`, `song_language`, `version_type` için izinli değer listesi yayımlanmamış. `composer`/`lyricist` gerçek ad +
  soyad. Hat bunu `yanki/distributemusic.py`'de uyguladı (sahte istemciyle sınandı, **canlı denenmedi**); anahtar
  `.env` → `DISTRIBUTEMUSIC_API_KEY` eklenince kendiliğinden API kipine geçer.
- **Tarayıcı otomasyonu:** şartlarda bot/scraping yasağı bulunamadı (§8'deki "bot" yalnız dinlenme manipülasyonu), ama
  panel görülmediği için kurulmadı. RouteNote'taki gibi Playwright doldurucu ancak panel ekranları görülünce yazılır.

## Teknik

- Ses: SSS "sıkıştırılmamış WAV, 16/24 bit, ≥ 44,1 kHz; dışı QC'de reddedilir"; diğer sayfalar MP3/FLAC'ı otomatik
  dönüştürdüğünü söylüyor (çelişki). Hat WAV verir (`paket.SES_BICIMI`).
- Kapak: kare, en az 3000×3000 JPG/PNG.
- ISRC/UPC: dağıtımcı kendi önekinden ücretsiz atar, mağazaya çıkınca görünür.
- Yayın tarihi: zorunlu; asgari gün yok. QC ~24 sa (Pro ~6 sa), Spotify/Apple 2–4 gün → `yayin_on_gun = 2`.
- Sanatçı: mevcut Spotify profili seçilir ya da yenisi açılır. Orvane'in RouteNote'tan gelen bir profili olacaksa ona
  bağlanmalı (yoksa diskografi bölünür; takip bunu bildirir).

## Destek için soru (Scryne'ın hesabından, support@distributemusic.ai)

> Hello, I release AI-generated cover versions of well-known songs under the artist name "Orvane". The vocals and
> instrumentals are newly generated with ACE-Step 1.5 (an open-source music model); no part of the original recording
> is used and no real artist's voice is cloned. I credit the original songwriters as composer/lyricist and disclose the
> release as AI-generated.
> 1. Do you accept AI-generated cover versions of existing songs? Do you obtain mechanical licenses for covers (e.g. US),
>    or do I need my own license, and are any territories excluded?
> 2. What should I enter as "AI music link" for a track generated with ACE-Step (it has no per-track share page)?
> 3. What are the allowed values for `version_type` (is "Cover" valid) and `genre`?
> 4. Is there a monthly upload volume you consider normal for one artist (we would release a few singles per week)?
> Thank you.

Cevap olumluysa `config/yayin.toml` → `[distributemusic] sozlesme_kabul = true` (API kipinde gönderim açılır) ve bu
belge cevapla güncellenir.

## Kaynaklar (2026-10-26)

[Ana sayfa + SSS](https://distributemusic.ai/) · [Fiyat](https://distributemusic.ai/pricing) ·
[Şartlar (2026-07-31)](https://distributemusic.ai/terms) · [API](https://distributemusic.ai/docs/api) ·
[API planı](https://distributemusic.ai/music-distribution-api) · [AI dağıtımı](https://distributemusic.ai/ai-music-distribution) ·
[Suno → Spotify](https://distributemusic.ai/suno-to-spotify) · [Telif](https://distributemusic.ai/legal/copyright) ·
[Dönüştürücü](https://distributemusic.ai/convert) · [llms.txt](https://distributemusic.ai/llms.txt) ·
[ISRC/UPC yazısı](https://distributemusic.ai/blog/isrc-upc-explained-music-distribution) ·
[whois](https://www.whois.com/whois/distributemusic.ai) · [Trustpilot](https://www.trustpilot.com/review/distributemusic.ai)
