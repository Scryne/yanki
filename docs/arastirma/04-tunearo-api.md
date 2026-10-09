# Tunearo API (2026-10-10)

Arkadaşın dağıtım sitesinin API'si (Roadmap Faz 10). Doküman: https://api.tunearo.com/ (v1, Temmuz 2026). Taban adres
`https://dashboard.tunearo.com/api/public/v1`, `Authorization: Bearer tn_live_…`. Anahtar `.env`'de, depoya girmez.
Kod: `yanki/tunearo.py`. Bu not dokümanı tekrar etmez; canlı denemede dokümandan farklı çıkanları ve kararları yazar.

## Hesap

- Anahtar arkadaşın hesabının tamamı: 29 sanatçı ve 8 yayın başkalarına ait. Hat yalnız kendi kaydettiği
  `release_id`'lere dokunur (`metadata.json` → `tunearo`); liste uçlarından başkasının kaydını değiştirmez.
- Orvane sanatçısı 2026-10-10'da açıldı (`f796ccc7-…`). Kod sanatçıyı adıyla bulur, yoksa bir kez açar.
- Parça kotası hesap başına (sayısı bilinmiyor, dolunca `403 Track limit reached`). Taslakta `credits_charged_tracks: 0`.

## Akış ve canlı bulgular

| Adım | Uç | Canlı bulgu |
|---|---|---|
| Sanatçı | `GET/POST /artists` | Liste `{"data": [...]}` döner (doküman `artists` diyor). `artist_ids` verilmeden yayın açılırsa adına yeni sanatçı açılıyor. |
| Yayın | `POST /releases`, `PATCH /releases/{id}` | `primary_genre` serbest metin, doğrulama yok. API'den açılan yayında `services` boş (panelden açılanlarda 34 mağaza) → açıkça gönderilir. `services`, `licensed_territories_exclude`, `producer_copyright_*`, `previously_released` PATCH'le tutuyor. |
| Kapak | `POST …/artwork-upload-url` → PUT → `PATCH cover_artwork_url` | Dokümandaki gibi. |
| Parça | `POST /releases/{id}/tracks`, `PATCH …/tracks/{tid}` | `lyrics` POST'ta düşüyor, PATCH'te tutuyor. Yazar alanları tek metin: `contributors` dizisi yok sayılıyor, `\|` ayırmıyor → virgüllü tek ad. `preview_start_time` parçada var ama API'de düzenlenemiyor ("No editable fields provided"). Bilinmeyen alan sessizce yutuluyor. |
| Ses | `POST …/audio-upload-url` → PUT → `PATCH audio_file_url` | Depo dosyayı uzantı ve tür ne verilirse verilsin `…-audio.wav` adıyla saklıyor → FLAC paket yüklemede kayıpsız WAV'a açılır. Yükleme adresi almak parçanın ses yolunu değiştirmiyor; yol PATCH ile bağlanır. |
| Gönder | `POST /releases/{id}/submit` | Parçasız yayında `400 Release must have at least one track`. |
| Durum | `GET /releases/{id}/status` | `draft`, `pending`, `approved`, `live`, `rejected`, ayrıca dokümanda olmayan `takedown`. ISRC ve UPC'yi Tunearo atıyor (canlı yayında `GBGXK…` ISRC, `506372…` UPC). |

Hata gövdesi `{"error": …, "issues": [{field, message}]}`; istemci bunu mesaja çevirir. POST yeniden denenmez
(yinelenen yayın/parça kotayı yakar), GET/PATCH 5xx ve ağ hatasında üç kez.

## Kararlar

- **Bölge:** US, CA, MX, IN, PK hariç (mekanik lisans yok; RouteNote'taki kararla aynı, Scryne 2026-10-07).
- **Mağaza:** 34 mağazadan Amazon (AI içerik almıyor) ve YouTube Content ID (cover orijinalle eşleşir) hariç; RouteNote
  kararıyla aynı. Kore mağazaları Tunearo listesinde yok. `config/yayin.toml` → `[tunearo]`.
- **©/℗:** © orijinal yıl + orijinal yazarlar, ℗ bu yıl + Orvane (RouteNote formundaki 11–12. satırla aynı).
- **Tür:** stil metninden (rap → Hip Hop/Rap, alternative → Alternative, rock → Rock, pop/ballad → Pop …), yoksa
  MusicBrainz sanatçı türlerinden sırayla, yoksa Pop. İlk denemede birleşik metin Adele'yi R&B/Soul yaptı; düzeltildi.
- **Cover beyanı:** API'de cover ya da mekanik lisans alanı yok. Orijinal yazarlar composer/songwriter/lyricist
  alanlarında; başlıkta "(Cover)" ya da orijinal sanatçı yok.
- **Webhook:** herkese açık HTTPS adres ister; hat yerelde (127.0.0.1) çalışıyor → durum yoklamayla, gece bir kez
  (öneri: yayın başına dakikada en çok bir). `TUNEARO_WEBHOOK_SECRET` `.env`'de yer tutucu.

## Kalite kontrolü riski

Tunearo'nun incelemesi ses eşleşmesi (`acr_match_count`) ve AI tespiti (`ai_detected`) yapıyor. Hesaptaki iki yayın
"potential derivative work (remix, sample, or cover) of an existing commercial recording" diye reddedilmiş, sahiplik
ya da lisans kanıtı istenmiş (`qc_proof_required: true`); biri açıkça orijinal kaydın "Lo-Fi Remix"i (eşleşme 30).
AI tespiti tek başına red değil: canlı bir yayında `ai_detected: true`, eşleşme 1. Bizim parçalar orijinal kaydın
kopyası değil (kopya kapısı, parmak izi), ama cover eşleşmesinin nasıl sayıldığı bilinmiyor. İlk gönderimin sonucu bunu
ölçer; takvimin `ilk_kabul` kapısı o gelene kadar ikinci yüklemeyi yapmaz.

## Arkadaşa iletilebilecek notlar

- Yazar alanlarına birden çok kişi (dizi ya da ayraç) ve `preview_start_time` için API desteği.
- POST /tracks'te `lyrics` alanının düşmesi.
- API'den açılan yayında `services` boş geliyor; varsayılan panel listesi olabilir.
- Doküman liste uçlarında `artists`/`tracks` diyor, `/artists` ve `/releases` `data` dönüyor.
