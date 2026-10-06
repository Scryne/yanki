---
proje: Yanki
created: 2026-10-06
type: proje-fikri
status: denetlendi
---
# Yanki — Proje Fikri

Scryne'ın isteği (2026-10-06): "Olan bir şarkıyı ACE-Step ile cover yapıp Spotify'a atacağız, her şeyi arkada
otomatik yapacak." Yetki devredildi ("tamamını sana bırakıyorum, en profesyonel şekilde"). Bu proje Otomat'ın
yapısını kopyalamaz; mimari kendi gereksinimlerinden çıkar (Scryne, 2026-10-06).

## Problem

Var olan yabancı şarkıların yeni kayıtlarını (cover) üretmek ve Spotify'da yayınlamak elle çok emek ister: kaynak
şarkıyı edinmek, söz çıkarmak, yeni performansı üretmek, mastering, kapak, metadata, dağıtımcı formu. Yanki bunların
hepsini arka planda yapar; Scryne'a yalnız dağıtımcı arayüzünde son yükleme kalır.

## Hedef Kullanıcı

Scryne (tek operatör). Dinleyici: Spotify'da cover arayanlar.

## Bilinen gerçekler (araştırma + spike, 2026-10-06)

- **Motor:** ACE-Step 1.5 (`ace-step/ACE-Step-1.5`, MIT, son commit 2026-08-29). v1 donmuş. 2B turbo, RTX 4060 Laptop
  8 GB'ta CPU offload ile 90 sn'lik cover ~12 sn'de; VRAM tepe 6,5 GB. Hız sorun değil.
- **Sözler şart:** söz verilmeden üretilen vokal anlamsız (WER 0,94–0,98); sözle 0,04–0,21.
- **Doğrudan cover işe yaramıyor:** `cover` modu armoniyi korumuyor (ilgisiz şarkı düzeyi); `cover-nofsq` korur ama
  orijinal kaydı taşır (dalga korelasyonu 0,41–0,90, parmak izi 0,74–0,93) → dağıtımcı parmak izi kontrolüne takılır,
  ayrıca yeni kayıt değildir.
- **Kılavuz ses yolu:** Demucs ile vokal/eşlik ayrımı → basic-pitch ile MIDI → notalardan sentez. Kılavuz besteyi
  taşır (armoni 0,88), orijinal kayıttan ses taşımaz (dalga 0,02–0,04). ACE-Step'e kaynak olarak bu verilir.
  Sonuç ölçümü: `spikes/` (S1–S4).
- **Yükleme:** tüketici dağıtımcılarında (DistroKid, TuneCore, CD Baby, Amuse, RouteNote) yükleme API'si yok;
  DistroKid ToS'u betik/bot erişimini yasaklıyor. Tam otomatik yol yalnız B2B API (LabelGrid $139/ay, 2 yıl). Amuse
  yapay zekâ cover'larını, CD Baby yapay zekâ içeriğini reddediyor; DistroKid ve RouteNote beyanla kabul ediyor.
- **Kaynak edinme:** bu ağda YouTube medya sunucusu (googlevideo) TLS'te bağlantıyı sıfırlıyor; SoundCloud bazı
  parçalarda 30 sn önizleme veriyor. Açık soru.
- **Ekonomi:** dinlenme başı ~$0,004; parça 12 ayda 1.000 dinlenmeyi geçmezse Spotify ödemez.

## Kararlar (Scryne, 2026-10-06)

- **Yükleme yarı otomatik:** hat her şeyi hazırlar; Scryne paketi dağıtımcı arayüzünden yükler (şarkı başı ~3–5 dk).
- **Şarkılar yalnız Scryne'ın listesinden;** hat kendi şarkı seçmez.
- **Şarkılar yabancı** (Türkçe değil); İngilizce sözler ana hedef.
- **Hukuki analiz yok;** platform kuralları (dağıtımcının neyi kabul ettiği) operasyonel gereksinim olarak ele alınır.

## v1: Kapsam ve "Bitti" Tanımı

- **Süre tavanı:** ~4 hafta.
- **Bitti = kullanıldı:** Scryne listesine yazdığı bir şarkının Yanki'nin ürettiği cover'ını dağıtımcıya yükledi,
  dağıtımcı kabul etti ve parça Spotify'da dinlenebilir.
- **Temel özellikler:**
  1. Liste dosyası → kaynak ses edinme (+ elle bırakılan dosya yedeği)
  2. Söz: kaynaktan çıkarma + Scryne'ın verdiği söz dosyası önceliği
  3. ACE-Step XL ile cover adayları + Scryne'ın işaretlediği aralığın bölgesel onarımı
  4. Otomatik kalite kapısı: armoni korunmuş, orijinal kayıt taşınmıyor, sözler anlaşılır; en iyi aday seçilir
  5. Mastering (loudness hedefi) + kapak + dağıtımcı metadata'sı → yükleme paketi
  6. Haftalık "hazır paketler" özeti; Scryne dinleyip onaylar/reddeder

## Kapsam Dışı

- Tam otomatik yükleme (B2B API ya da tarayıcı botu) — ekonomi ve ToS yüzünden v1'de yok.
- Hattın kendi şarkı seçmesi, Türkçe şarkılar, sanatçı ses klonu.

## Açık Sorular

- A-1: Kaynak sesi nereden alacağız (YouTube bu ağda kapalı, SoundCloud önizleme verebiliyor)?
- A-2: Dağıtımcı: RouteNote (ücretsiz, %15) mı DistroKid ($23/yıl + cover lisansı) mı? Hesap Scryne'da.
- ~~A-3: Kalite kulakla yeterli mi?~~ Kapandı (2026-10-07): dört dinleme testi; cover tanınıyor, XL güç 0,7 + 100 adım +
  bölge onarımı "az kaldı". Kılavuz ses yolu vokal üretmedi, elendi. Ayrıntı: `docs/arastirma/01`, karar: `Final-Dokuman.md`.
