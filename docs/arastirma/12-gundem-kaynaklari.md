# 12 — Gündem kaynakları (2026-10-26)

Scryne (2026-10-26): "ai cover için şarkı keşfini gündemde hangi popüler şarkılar varsa, hangi şarkılar trendde ve çok
dinleniyorsa öyle ayarlarsak daha fazla dinlenme alabiliriz"; "yabancı şarkılar atıcaz". Soru: her gün otomatik
okunabilecek, ücretsiz, kurala uygun "şu an trend" kaynakları hangileri. Hukuk analizi yok; yalnız şartlar, anahtar,
sınır, alanlar. Kaynaklar 2026-10-26'da okundu ve canlı denendi.

## Sonuç (uygulanan: `yanki/trend.py`, `config/kesif.toml` → `[trend]`)

| Kaynak | Kullanım | Neden |
|---|---|---|
| **Deezer ülke Top-100 listeleri** | birincil | Anahtarsız, günlük güncelleniyor, satırda ISRC ve `rank`. "Deezer Charts" kullanıcısının (637006841) "Top <Ülke>" playlist'leri; kimlikler adla çözülür. `/chart/0` ülke ayırmıyor. |
| **Apple Music most-played RSS** | ikinci kaynak | `rss.marketingtools.apple.com/api/v2/{cc}/music/most-played/100/songs.json`; anahtarsız, ülke bazlı, ISRC ve sayı yok. Eski `itunes.apple.com/.../rss/topsongs` güvenilmez (1992 kaydı geldi). |
| **Spotify Top 50'ler** | isteğe bağlı | Web API editoryal listeleri yeni uygulamalara kapalı (2024-11-27 duyurusu), Şubat 2026'da playlist içeriği yalnız sahip/ortak listelerde. Spotify uygulamasının içindeki STILLMORE köprüsüyle (Bulucu'nun kullandığı yol) okunur; parça başına toplam dinlenme gelir, iki gün arası fark günlük dinlenmedir. Spotify çalıyorsa ya da köprü yoksa atlanır. |
| Spotify Viral 50 | yok | Mayıs 2026'da kaldırıldı (`37i9dQZEVXbLiRSasKsNU9` 404). |
| kworb.net | kullanılmadı | Gerçek günlük Spotify akışları var, robots serbest, ama açık izin/şart yok ve Spotify verisinin kopyası. |
| Last.fm | kullanılmadı | Ücretsiz anahtar yalnız ticari olmayan kullanım (ToS 3.1). |
| YouTube Data API | kullanılmadı | `mostPopular` Temmuz 2025'ten beri "Trending Music/Movies/Gaming"; müzik ayrımı doğrulanamadı, başlık ayrıştırması gürültülü. |
| Shazam, Billboard, TikTok | yok | Resmî ücretsiz uç yok. |

Deezer şartları "strictly limited for a non-commercial purpose" diyor ve otomatik erişim yasağı içermiyor: hat yalnız
liste metaverisini okuyor, Deezer içeriği kullanmıyor; gri alan olarak not edildi. Oran sınırı ikincil kaynağa göre 50
istek / 5 sn; hat koşu başına ~10 istek atıyor.

## Seçilen listeler ("yabancı şarkılar")

Deezer: Worldwide, USA, UK, Canada, Australia, Ireland, Germany, Netherlands. Apple: us, gb, ca, au, ie. Spotify: Top 50
Global, USA, UK, Canada, Australia (kimlikler open.spotify.com başlığıyla doğrulandı). Türkiye listeleri yok; aday ayrıca
İngilizce söz şartından geçer.

## Puan

Liste başına `ağırlık × (toplam − sıra + 1) / toplam` (Spotify 1,5; global liste ×1,5), toplanır. Son 3 günde ilk kez
görülen ×1,3; 3 gün önceki en iyi sırasından yükselen +%50'ye kadar; Spotify günlük dinlenmesi log ölçekte en çok ×2.
Listeden düşen şarkı 3 gün sonra puan almaz. İlk canlı okuma (2026-10-26): 13 liste, 1.300 satır, 21 sn, 301 aday;
başta Ella Langley "Choosin' Texas", ADÉLA "Nicole Kidman", Olivia Rodrigo "stupid song", Taylor Swift "Patient Zero".

## Kaynaklı tek zamanlama verisi

Trend döneminde cover/sound-alike dinlenmesine dair nicel, hakemli veri bulunamadı. Anekdot: Hiko'nun "Vegas" sped-up
cover'ı orijinal remix Spotify'da yokken onu geçti (Refinery29, ikincil); Chartmetric'e göre TikTok gönderisi başına
bağlı Spotify akışı 2020'de ~738'den 2025'te ~275'e düştü. Gündemdeki şarkının cover'ı orijinalle aynı aramada
yarışır; başarı ölçüsü yine `yanki takip`'in arama sırası ve dinlenmesi.

## Kaynaklar

[Deezer chart](https://api.deezer.com/chart/0/tracks) · [Deezer Charts listeleri](https://api.deezer.com/user/637006841/playlists) ·
[Deezer şartları](https://developers.deezer.com/termsofuse) · [Apple RSS](https://rss.marketingtools.apple.com/api/v2/us/music/most-played/5/songs.json) ·
[Spotify Web API değişikliği 2024-11-27](https://developer.spotify.com/blog/2024-11-27-changes-to-the-web-api) ·
[Şubat 2026 geçiş rehberi](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide) ·
[Viral 50 kaldırıldı](https://routenote.com/blog/spotify-removes-viral-charts/) · [Last.fm ToS](https://www.last.fm/api/tos) ·
[YouTube revizyonları](https://developers.google.com/youtube/v3/revision_history) · [kworb SSS](https://kworb.net/faq.html) ·
[Chartmetric](https://hmc.chartmetric.com/why-tiktok-songs-go-viral-faster/)
