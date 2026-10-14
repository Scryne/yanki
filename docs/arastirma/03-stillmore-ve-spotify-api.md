# STILLMORE FINDER ve Spotify Web API (2026-10-09)

Scryne'ın isteği (2026-10-09): arkadaşının aracı STILLMORE FINDER Spotify'dan kaldırılmış şarkıları buluyor; Yanki bu
şarkıların cover'ını yayınlasın, şarkıyı arayan dinleyici bizim parçayı bulsun. Bu not aracın ne yaptığını, Yanki'ye
neyin nasıl alındığını ve Spotify Web API'nin bugünkü sınırlarını kaydeder. Hukuki değerlendirme yok.

## STILLMORE FINDER ne yapıyor

Depo: `github.com/Caferlyy/distro-finder-bulmaca` (son commit `8ce0f09`, 2026-10-06, v12.1). Virus Records markalı,
lisans anahtarıyla açılan bir araç ailesi:

**Güncelleme (2026-10-14, v12.5, `8ed2471`):** `C:\df-archive` çekildi, eklenti `install-spicetify.mjs --no-restart` ile
yeniden uygulandı. Yanki'nin dayandığı `Stillmore.playlist.info/scan` ve satır alanları (`removed.reasonCode`, `plays`,
`isrc`, `reuploads`, `artistListeners`) değişmedi. Yenilikler: 90 gün sayacı (kaldırılan parçanın dinlenmesi 90 gün
korunur), `KUR.bat` tek tık kurulum, token'lı GitHub güncellemesi ve `uploader/` (STILLMORE Yükleyici: dağıtımcı
formunu bir kez öğrenip yayınları **taslak** olarak giren Playwright paneli, `127.0.0.1:4747`; göndermez).

| Parça | Ne | Nerede çalışır |
|---|---|---|
| `spicetify/stillmore-finder.js` + `custom-app/stillmore` | Spotify masaüstü istemcisine eklenen sağ tık paneli ve tam sayfa uygulama (v12) | Spotify'ın içinde (Spicetify) |
| Next.js paneli (`app/`, `src/`) | Distribütör, ISRC/UPC, Soundcharts dinlenme, sanatçı kataloğu | `127.0.0.1:3000`, Electron kabuğuyla |
| `desktop/` | Electron kabuğu; Spotify'ı `--remote-debugging-port=9222` ile açıp istemcinin kendi metadata isteğini yaptırır (CDP) | Windows |
| `license-panel/` | Virus Records anahtar paneli; her analiz ucu lisans yoksa 402 döner | sunucu (Dokploy) |

Çekirdek kural: distribütör **yalnız** parçanın lisans veren (licensor) UUID'sinin `json/uuid's.json`'daki 137 kayıtla
birebir eşleşmesinden çıkar (RouteNote `e5627993…`, DistroKid `18fbcef4…`, TuneCore). Licensor UUID'yi yalnız
Spotify istemcisinin iç metadata yanıtı (protobuf, alan 21) taşır; herkese açık Web API vermez.

**Kaldırılmış şarkı bulucu** (v12, playlist sayfası): istemcinin `PlaylistAPI`'si listedeki gri (çalınamayan) parçaları
verir; her biri için neden ("Kaldırılmış" = hiçbir ülkede açık değil, "Ülkende kapalı"), ISRC, distribütör, label,
Spotify dinlenme sayısı (iç GraphQL `playcount`), sanatçının aylık dinleyicisi, aynı ISRC'nin çalınabilir yeniden
yüklemesi. "CSV indir" ile dışa aktarılır (BOM'lu UTF-8, virgül; sütunlar `csv.playlist`).

## Yanki'ye ne alındı, neden böyle

STILLMORE'un çalışması üç şeye bağlı: Microsoft Store dışı Spotify (bu makinede Store sürümü kurulu, 1.304), Spicetify
yaması (Spotify'ın uygulama dosyalarını değiştiriyor; deposundaki notta bir müşterinin Spotify'ı bozulmuş) ve Virus
Records lisans anahtarı. Yanki'yi bunlara bağlamak gece hattını kırılgan yapardı. Bu yüzden:

- **Bulma iki yoldan:** STILLMORE'un CSV'si (`girdi/kesif/*.csv`, başkasının playlist'i dahil her playlist) ya da Web
  API ile Scryne'ın kendi/ortak playlist'leri. CSV sözleşmesi testte birebir (`tests/test_kesif.py`).
- **STILLMORE'da olmayan iki adım:** (1) boşluk doğrulama: aynı ISRC ya da aynı sanatçı + aynı ad çalınabilir
  durumda geri gelmişse aday düşer; aynı adlı başka çalınabilir parçalar rakip cover sayılır. (2) Talep: YouTube'daki
  orijinal yüklemenin izlenmesi (anahtarsız; canlı denendi: Adele SLY 2,58 milyar, Sezen Aksu "Gülümse" 6,95 milyon).
- **Yayın takibi:** yüklenen parçanın ISRC'si Spotify'da çıktı mı, şarkının adı arandığında kaçıncı sırada, Orvane
  profili tek mi. Stratejinin başarı ölçüsü arama sırası.
- STILLMORE'un HTTP paneli (`POST /api/lookup`, `/api/song/{uuid}/streams`) entegre edilmedi: lisans (402), yönetici
  oturumu ve masaüstü köprüsü ister; Yanki'nin ihtiyacı CSV + Web API ile karşılanıyor. Distribütörü ve Soundcharts
  dinlenmesini görmek istenirse istemci eklenebilir.

## Spotify Web API, 2026 sonbaharı

Kaynaklar developer.spotify.com (erişim 2026-10-09):
[Şubat 2026 duyurusu](https://developer.spotify.com/blog/2026-02-06-update-on-developer-access-and-platform-security),
[geçiş rehberi](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide),
[Şubat](https://developer.spotify.com/documentation/web-api/references/changes/february-2026) /
[Mart](https://developer.spotify.com/documentation/web-api/references/changes/march-2026) /
[Temmuz](https://developer.spotify.com/documentation/web-api/references/changes/july-2026) changelog'ları,
[playlist öğeleri](https://developer.spotify.com/documentation/web-api/reference/get-playlists-items),
[arama](https://developer.spotify.com/documentation/web-api/reference/search),
[redirect URI](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).

| Konu | Durum | Yanki'deki karşılığı |
|---|---|---|
| Development Mode | Sahibin aktif Premium'u şart (yeni uygulamalar 2026-02-11, mevcutlar 2026-03-09); en fazla 5 kullanıcı | Scryne'ın Premium hesabıyla bir uygulama |
| Arama | `limit` en fazla 10 (önce 50), `offset` ≤ 1000; `isrc:` filtresi parça aramasında geçerli | `Spotify.ara` sayfa başı 10, derinlik `offset` ile |
| ISRC (`external_ids`) | Şubat'ta kalktı, Mart 2026'da geri geldi | ISRC araması ve takip buna dayanıyor |
| Playlist parçaları | `/tracks` kalktı → `/items`; yalnız sahibi/ortağı olunan playlist, diğerleri 403. Spotify'ın editoryal/algoritmik listeleri 2024-11'den beri kapalı | Başkasının playlist'i için STILLMORE CSV'si; 403'te açıklayıcı hata |
| `is_playable` | `market` verilince geliyor; `restrictions.reason` = market / product / explicit | Kaldırılmış = `is_playable: false` |
| Redirect URI | `http://127.0.0.1:PORT/...` kabul, `localhost` yasak | `http://127.0.0.1:8766/callback` |
| Hız sınırı | 30 sn kayan pencere, 429 + `Retry-After`; kota aşımında `QUOTA_EXCEEDED` (Temmuz 2026). STILLMORE tek uygulamada 13 saatlik 429 ölçtü (2026-08) | İstekler sıralı; kısa bekleme bir kez, uzunsa `Sinirli` ve koşu kalanı sonraya bırakır |

**Canlı doğrulama (2026-10-09, Scryne'ın uygulamasıyla, client credentials):**
- Token, ISRC araması (`external_ids.isrc` ve `is_playable` dönüyor) ve ad araması (sayfa 10) çalışıyor.
- `is_playable: false` geliyor: Spotify'ın olmadığı CN'de tek parça ve arama sonuçları `false`, `restrictions.reason`
  = `market`. **Bulgu:** "bu ülkede kapalı" da "market" döndüğü için gerekçe kaldırılmışı ayırmıyor → `playlist_tara`
  parçayı US/GB/DE'de de sorar; hiçbirinde açık değilse `kaldirildi`.
- ISRC araması aynı ISRC'yi başka sanatçı adıyla taşıyan kopyaları da döndürüyor (Rolling in the Deep: 4 sonuç,
  biri başka sanatçı) → bu durumda kayıt Spotify'da çalınabiliyor, boşluk kapalı sayılır.
- Boşluk doğrulama canlıda: Adele "Someone Like You" geri gelmiş (aynı sanatçı + ad) → elendi, rakip 4.
- `yanki takip`: üç yükleme henüz canlı değil (yayın 2026-10-28 / 11-04 / 11-11), beklenen sonuç.

**Kota (2026-10-09, kendi ölçümümüz):** testler + üç keşif koşusu, bir günde ~1.000 istek → 429,
`Retry-After: 83595` (23,2 saat). Development Mode kotası belgelenmiyor; günlük tavan 400 bu ölçüme göre konuldu
(yarısının altı). STILLMORE aynı tür kilidi 13 saat ölçmüştü.

**Deezer (2026-10-09):** anahtarsız; `/chart/{tür}/artists` IP'ye göre ülke listesi veriyor (bu ağda Fransa: Tiakola,
Jul, GIMS…), `/artist/{id}/top` → `rank` (0–1M), `/track/{id}` → ISRC; hata 200 içinde (`code 4` kota, 800 yok).
Kaldırılmış underground şarkılar Deezer'da da yok, sanatçıları var → stil yedeği sanatçı albüm türlerinden.
Apple Music RSS (`rss.marketingtools.apple.com`) bu ağdan güvenilmez (aynı adres bir 200, sonra zaman aşımı).

**TypeSafe özgünlük spike'ı (2026-10-09, jev-1.13.0):** 30 gerçek keşif adayı elle etiketlendi (10 gerçek sanatçı,
17 takma adlı sızıntı, 3 oyun müziği hayran yapımı). State: listedeki sanatçı + ad + YouTube ilk 5 sonucu (başlık,
kanal, izlenme). Sorular: `kimin` Choice (listed_artist / other_artist / unclear) ve `hayran` Noul. Sonuç:
"listed_artist ≥ 0,90 ve hayran < 0,5" kabul kuralıyla sızıntı/hayranda yanlış kabul 0/20 (en yüksek sızıntı L. Del
Rei 0,77–0,85); gerçeklerde HAARPER/1nonly/Day$okee/GY!BE/Adele/Sezen Aksu ≥ 0,98, Vinnie Vincent Invasion 0,98
(regex kaçırıyordu). Vipraz "Ainsi Bas La Vida" other_artist 0,94: şarkı Indila'nın, elle konan "gerçek" etiketi
yanlıştı (regex de kabul etmişti). Belirsiz kanıt: 505bubble unclear, ¥$ other_artist 0,80 (yanlış ret; tutucu yön,
zararsız). İstek ~600 token, ~0,3 sn (IPv4 taşımayla; IPv6 DNS ilk bağlantıyı 12 sn bekletiyor). Ham sonuç:
oturum notu, karar kayıtları `calisma/kesif/adaylar.json` → `ozgunluk`.

**Hâlâ doğrulanmadı:** `/items` yanıtındaki parça alanının adı (`item` / `track`; kod ikisini okuyor) ve kullanıcı
token'ı akışı (`yanki spotify-baglan`, Scryne'ın tarayıcıda izni gerekiyor; yalnız kendi playlist'lerini taramak için).
