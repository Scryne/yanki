# Kendi şarkılar için ücretsiz dağıtıcı (2026-10-16)

Scryne: "AI cover'ları RouteNote'tan atıyoruz ama normal şarkıları da paylaşabileceğim bir dağıtıcı lazım; para vermeden."
Operasyonel tarama (ücret, Türkiye'ye ödeme, form ve dosya şartları, platform kuralları); hukuki değerlendirme yok.
Kaynak türü: B = resmî sayfa tam metin, İ = ikincil ya da yalnız arama özeti. Karar: **FreshTunes** (Scryne, 2026-10-16).

## Neden RouteNote'taki hesap değil

- Bir RouteNote hesabı yalnız bir Spotify sanatçı sayfası talep edebiliyor (B, support.routenote.com, 2026-10-06);
  o hak Orvane'de.
- Spotify "AI Persona" rozetli profilleri editoryal ve algoritmik önerilerden çıkarıyor (B, newsroom, 2026-08-11):
  Scryne'ın kendi adı AI cover hesabıyla aynı kayıt altında durmamalı; hesaba gelebilecek bir yaptırım da ayrılır.
- Aynı kaydı iki dağıtıcıdan aynı mağazaya göndermek mağazada iki kopya yapar (İ, RouteNote blog 2015): odada
  RouteNote ve FreshTunes birlikte seçilemez.

## 2026'da ücretsiz kalanlar

| Dağıtıcı | Ücret | Türkiye'ye ödeme | Not |
|---|---|---|---|
| **FreshTunes Free** | $0; akış gelirinin %100'ü, Content ID / söz yazarı telifi / UGC %20 (B, /pricing) | Payoneer, WebMoney, MC Pay; ücretsiz planda en az 25 $, 30 güne kadar (B, yardım merkezi 2026-10-11) | Seçildi |
| RouteNote Free (ikinci hesap) | $0, %85 | PayPal, Wise üzerinden banka, Payoneer; en az 50 $ (B) | Aynı kişinin iki hesabı ToS'a uygun mu doğrulanamadı |
| SoundOn (TikTok) | $0; 12 ay %100, sonra %90 (İ) | Belirsiz | Türkiye'de kayıt açık mı doğrulanamadı |
| Freecords | "her zaman ücretsiz" (B, kendi beyanı) | belgelenmemiş | yeni, iş modeli belirsiz |

Artık ücretsiz değil: TuneCore (ücretsiz plan 2025-06-18'de kapandı, B), Amuse (Start 2024-03-27'de kapandı, İ),
DistroKid, LANDR, Too Lost, Soundrop. Kapandı: Level (İ). Türkiye merkezli ücretsiz dağıtıcı bulunamadı.

## FreshTunes şartları (helpcenter.freshtunes.com, Zendesk API'siyle okundu)

- **Ses:** FLAC ya da WAV; 44,1 kHz / 16 bit önerilir (48/88,2/96 kHz, 24 bit de kabul); yalnız stereo; 0 dBFS'i
  aşmamalı; başta ve sonda en çok 5 sn sessizlik; şarkının tamamı (2026-05-21).
- **Kapak:** JPG ya da PNG, kare, 1400–3000 px, 10 MB altı, RGB. Üstünde yalnız sanatçı ve yayın adı (metadata ile
  birebir) ya da hiç yazı; URL, e-posta, QR, fiyat, "Exclusive", servis atfı, bulanık/kırpık görsel yok (2025-07-22).
- **Form:** sanatçı "Artists" bölümünde takma adla açılır, yayından sonra değişmez; ücretsiz planda tek sanatçı.
  Spotify/Apple profil linki yapıştırılıp doğrulanır (ad birebir aynı olmalı). Besteci ve söz yazarı gerçek ad-soyad
  (ayrı kutular). ISRC ve UPC ücretsiz atanır, önceki yayının kodları girilebilir. Yayın tarihi en erken yüklemeden
  7 gün sonra (14–28 önerilir; Spotify'a özel saat için 14). Sözler mağazalara dağıtılmıyor (Musixmatch öneriliyor).
  Alan sırası, tür ve dil listeleri, label, ©/℗, explicit alanları giriş yapmadan görülemedi: ilk yüklemede formla
  karşılaştırılıp `elle.freshtunes_metni` düzeltilecek.
- **Yapay zekâ:** "tamamen yapay zekâyla üretilmiş" müzik kabul edilmiyor (yardım merkezi 2025-11-27); ToS §1 AI ile
  üretilmiş kaydı kabul etmiyor, §2/§9(i) yükleyen AI ile üretilmediğini beyan eder.
- **Otomasyon:** ToS §9(g) otomatik yollarla erişimi, §10(i) izinsiz taramayı yasaklıyor (2026-05-26). Odadan form
  doldurulmaz; hat paketi hazırlar, Scryne gönderir.
- **Hareketsizlik:** ToS §4 3 ayda bir giriş istiyor; bildirimden 30 gün sonra askı, açmak 50 $ (bakiye 50 $ altıysa
  tamamı), askıdan 6 ay sonra silinebilir. Yardım merkezi (2025-07) 6 ay ve ücretsiz diyor; yeni olan ToS esas alındı.

## Hatta

`yanki/elle.py` → `DAGITICILAR["freshtunes"]` (elle gönderim). Odada **Yükle → Kendi şarkım (FreshTunes)**: sanatçı,
profil, label ve yazarlar son FreshTunes taslağından; yapay zekâ kapalı; yayın tarihi 14 gün sonrası. Denetim: yapay
zekâ, Orvane adı, 7 günden erken ya da boş yayın tarihi, 5 sn'den uzun baş/son sessizlik (`elle.ses_olcumu`, yüklemede
ölçülür) eksik; kırpılma ve cover uyarı. Paket: `audio.flac`, `artwork.jpg`, `FRESHTUNES.txt` (kontrol listesi + form
alanları). "FreshTunes'a gönderdim" kaydı kilitler; gece koşusu 75. günden itibaren haftada bir giriş hatırlatır
(`elle.freshtunes_hatirlatma`), odada "Bugün girdim" sayacı sıfırlar.

## Kaynaklar

- RouteNote profil sınırı: https://support.routenote.com/kb-article/how-can-i-claim-my-artist-profile-on-spotify/
- RouteNote ödeme: https://support.routenote.com/kb-article/how-can-i-receive-payment-what-are-the-payment-options/
- Spotify AI Persona: https://newsroom.spotify.com/2026-08-11/ai-persona-badges-transparency/
- TuneCore ücretsiz plan sonu: https://support.tunecore.com/hc/en-us/articles/38035072731156-Updates-to-New-Artist-Plans-and-Social-Platform-Releases
- Amuse Start kapanışı (İ): https://routenote.com/blog/amuse-has-dropped-free-distribution-for-artists/
- FreshTunes: https://freshtunes.com/pricing, https://freshtunes.com/terms,
  [ses](https://helpcenter.freshtunes.com/hc/en-us/articles/17254305207324-Audio-File-Requirements),
  [kapak](https://helpcenter.freshtunes.com/hc/en-us/articles/17254280163740-Coverart-Guidelines-and-Requirements),
  [yayın tarihi](https://helpcenter.freshtunes.com/hc/en-us/articles/17254819508636-Planning-your-release-Release-date),
  [UPC/ISRC](https://helpcenter.freshtunes.com/hc/en-us/articles/17254426214300-What-are-UPC-and-ISRC-codes),
  [sanatçı profili](https://helpcenter.freshtunes.com/hc/en-us/articles/17254531509532-How-do-I-create-an-artist-profile),
  [yazar adları](https://helpcenter.freshtunes.com/hc/en-us/articles/17254633611932-Why-should-I-provide-songwriters-real-names),
  [para çekme](https://helpcenter.freshtunes.com/hc/en-us/articles/17257367072796-How-Can-I-Withdraw-My-Royalties),
  [AI politikası](https://helpcenter.freshtunes.com/hc/en-us/articles/17257357349020-FreshTunes-Policy-on-AI-Music),
  [sözler](https://helpcenter.freshtunes.com/hc/en-us/articles/17254324775964-Lyrics)
- FreshTunes kart ödemesi: https://www.musicweek.com/labels/read/label-services-platform-freshtunes-expands-options-for-royalty-payments/093322
