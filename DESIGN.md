---
version: alpha
name: Yanki
description: Cover adaylarını dinleyip onaylamak, bozuk aralığı dalga formunda işaretlemek için yerel dinleme odası.
colors:
  zemin: "#0B0A1A"
  zemin-2: "#1A0F2E"
  parilti: "#123B4A"
  yuzey: "#14122A"
  yuzey-cam: "rgba(20, 18, 42, 0.62)"
  cizgi: "rgba(255, 255, 255, 0.10)"
  metin: "#ECEAF6"
  metin-2: "#A9A5C4"
  primary: "#F2A93B"
  primary-zayif: "rgba(242, 169, 59, 0.22)"
  oynatma: "#6FD3E8"
  dalga: "#5E5A86"
  dalga-calinan: "#B9B4E6"
  gecti: "#8FD19E"
  dustu: "#E5735C"
typography:
  baslik:
    fontFamily: "Space Grotesk"
    fontWeight: 600
    fontSize: 22px
    lineHeight: 1.2
  govde:
    fontFamily: "Inter"
    fontWeight: 400
    fontSize: 14px
    lineHeight: 1.5
  zaman:
    fontFamily: "JetBrains Mono"
    fontWeight: 500
    fontSize: 12px
    lineHeight: 1.4
rounded:
  kucuk: 6px
  panel: 14px
spacing:
  1: 4px
  2: 8px
  3: 12px
  4: 16px
  6: 24px
  8: 32px
---

# Yanki

## Overview

Taban disiplin global Dark Glassmorphism kurallarıdır; bu dosya Yanki'yi ayıran katmanı kaydeder.

- **Mood:** gece stüdyosunun kontrol odası. Sakin, koyu, kulak odaklı; göz dalga formunda dinlenir. Pano değil,
  dinleme masası.
- **Farklılaştırıcı detay:** dalga formu sayfanın kahramanıdır. Bozuk aralık saniye yazılarak değil, dalganın üzerinde
  sürüklenerek amber bir bantla işaretlenir; bant analog kayıt makinesindeki punch-in işaretini andırır.

## Colors

Zemin derin çivit → erik gradyanı, sol üstte soluk bir petrol yeşili parıltı (cam bunun önünde okunur). Tek sıcak
renk **amber**: seçili aralık, birincil eylem (onayla, onar). Çalma imleci soğuk **camgöbeği** — amberle karışmaz,
ikisi aynı anda dalga üstünde görünür. Kapı rozetleri **ada çayı yeşili / mercan**; doygun kırmızı-yeşil yok, uzun
dinleme seansında göz yormasın.

## Typography

Başlıklar Space Grotesk (şarkı adı, aşama), gövde Inter. Bütün zaman kodları ve kapı değerleri JetBrains Mono:
"0:58–1:02" sütun sütun hizalanır, rakamlar kaymaz.

## Components

- **Yerleşim:** solda dar şarkı kuyruğu (cam), sağda seçili şarkı. Adaylar alt alta, her biri tam genişlikte bir dalga
  şeridi; yan yana kart dizisi yok.
- **Aday şeridi:** opak `yuzey` (cam değil — dalga net okunmalı). Üstte aday no + tohum + kapı rozetleri, ortada dalga
  (yükseklik 96px), altta zaman kodu ve eylemler.
- **Seçim bandı:** sürüklemeyle oluşur, `primary-zayif` dolgu + 1px `primary` kenar; Esc temizler. Klavye: Shift+←/→
  seçimi 0,5 sn genişletir.
- **Onarım sürümleri:** onarılan adayın altında girintili küçük şeritler; yalnız işaretli aralık civarı (±5 sn)
  gösterilir, "Bunu kabul et" tek eylem.
- **Eylem çubuğu:** sayfanın altında sabit cam çubuk: Onayla (amber dolu), Onar (amber kenarlı), Reddet (metin, mercan).

## Do's and Don'ts

- Cam yalnız şarkı kuyruğunda ve alt eylem çubuğunda; dalga şeritleri opak.
- Dalga ve oynatma animasyonu `backdrop-filter`'lı katmanın altında yeniden çizilmez (canvas üstte, cam ayrı katman).
- Rozetlerde yalnız renk değil metin de olur ("parmak izi 0,58 ✓").
