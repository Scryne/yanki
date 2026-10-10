# Spotify büyüme ve platform kuralları (2026-10-10)

Scryne 2026-10-10'da "en kazançlı, artist hesabım en iyi, dinlenme en yüksek olacak şekilde her şeyi ayarla" dedi.
Bu not o kararların dayanağı. Hukuki değerlendirme yok; yalnız platform kuralları ve operasyon. Araştırma bir alt
ajanla yapıldı; aşağıdaki iddialar kaynaklı, "öneri" olanlar ayrıca işaretli.

## Bulgular (kaynaklı)

- **AI Persona etiketi (Spotify, 2026-08-11):** kamusal kimliği fotogerçekçi AI insanı olan sanatçılar etiketleniyor
  ve editoryal/algoritmik önerilerden varsayılan olarak çıkarılıyor. Profil, başlık ve **albüm görselleri** de
  inceleniyor. Yalnız AI araçlarıyla müzik yapmak etiketi tetiklemiyor. Etiket Discovery Mode'dan dışlıyor.
  support.spotify.com/us/artists/article/ai-personas/, newsroom.spotify.com/2026-08-11/ai-persona-badges-transparency/
- **Spam filtresi (2025-09-25):** toplu yükleme, kopya, SEO hileleri, yapay kısa parça. Haftalık yükleme eşiği resmî
  olarak açıklanmamış. newsroom.spotify.com/2025-09-25/spotify-strengthens-ai-protections/
- **Cover başlığı:** orijinalle aynı başlık yasak değil; başlıkta ve sanatçı alanında orijinal sanatçıya atıf
  ("Originally Performed By") yapılmaz (ikincil kaynak).
- **Release Radar:** dinleyici başına sanatçı başına haftada 1 şarkı, parça ~4 hafta görünür; takipçisi olmayana
  yalnız "benzer sanatçı" kanalından ulaşır.
- **Gelir eşiği:** parça başına son 12 ayda ≥ 1.000 dinlenme (ISRC başına), altı royalty almaz.
- **Content ID ve cover:** dağıtımcıların standardı cover'ı Content ID dışında tutmak (sound-alike kayıt "münhasır
  hak" değil, yanlış hak talebi riski). Facebook Rights Manager ve Audible Magic için ayrıca kaynak bulunamadı; aynı
  parmak izi mantığıyla dışarıda tutuldu.
- **Diğer mağazalar:** Amazon AI parçaları barındırıyor (sessiz kaldırma raporları var); Deezer tam AI parçaları
  etiketleyip önerilerden çıkarıyor ve 6 ay dinlenmeyen AI parçayı silebiliyor; Tidal tam AI parçada royalty ödemiyor;
  Apple etiketliyor, yasaklamıyor.
- **Profil:** dağıtımcı Spotify sanatçı kimliğiyle teslim ederse profil bölünmez; bölünmüşse Spotify for Artists'ten
  "content mismatch" formu. Profil sahiplenme Spotify for Artists formuyla, elle inceleme.

## Kararlar (2026-10-10)

| Karar | Gerekçe | Yer |
|---|---|---|
| Otomatik onay yalnız denenmiş tür (balad/pop/piyano rock) ve İngilizcede, en iyi aday söz WER ≤ 0,15 | Kulaktan geçmemiş kötü cover atlanır, atlama profili algoritmada aşağı çeker; Orvane'in tür kimliği tutarlı kalır | `yanki/onay.py`, `config/yayin.toml` |
| Kapakta insan, yazı yok (Pinterest süzgeci) | AI Persona etiketi albüm görselinde fotogerçekçi insanı da sayıyor | `yanki/pinterest.py` |
| Mağazalar: Amazon açık; Content ID, Rights Manager, Audible Magic kapalı | Erişim ve gelir; cover'ın parmak izi kaydı yanlış hak talebi üretir | `config/yayin.toml` → `[tunearo]` |
| Haftada 1 yayın, yayın tarihi en erken | Release Radar zaten haftada bir parça gösteriyor; asıl trafik arama (kaldırılmış şarkı) | `[takvim]` |
| Spotify profili Tunearo sanatçısına kendiliğinden bağlanır | Yeni yayınlar aynı profile düşer, bölünme bildirilir | `tunearo.profil_bagla` |
| Kapıdan geçemeyen iki rap şarkısı reddedildi (geri alınabilir) | Rap tarifi denenmedi; üç aday da söz kapısında kaldı | dinleme odası |

## Scryne'a kalan (bir kez)

- İlk parça Spotify'da görünce **Spotify for Artists**'ten Orvane profilini sahiplen (giriş gerektirir). Profil
  fotoğrafı fotogerçekçi AI insan olmasın (AI Persona); soyut görsel ya da logo.

## Öneri, uygulanmadı

- US/CA/MX/IN/PK hâlâ hariç (mekanik lisans yok, Scryne 2026-10-07). En büyük gelir kaldıracı ABD; açmak lisans
  meselesi, karar Scryne'ın.
- AI kredisini DDEX ile bildirmek (cezası yok, Apple/Tidal etiketleri için gerekebilir): Tunearo API'sinde alan yok,
  arkadaşa sorulacak.
