---
version: alpha
name: Yanki
description: Cover hattının yerel kontrol odası — adayları dinleyip onaylamak, bozuk aralığı dalga formunda işaretlemek, hattı, yayınları ve kazancı tek yerden izlemek.
colors:
  zemin: "#08090C"
  zemin-2: "#12151B"
  parilti: "#1B2B40"
  parilti-2: "#2A2F3A"
  yuzey: "#0F1217"
  yuzey-2: "#151920"
  yuzey-cam: "rgba(20, 23, 30, 0.58)"
  cizgi: "rgba(255, 255, 255, 0.08)"
  cizgi-gumus: "rgba(214, 222, 235, 0.32)"
  metin: "#E9ECF1"
  metin-2: "#9AA3B2"
  gumus: "#C9D1DC"
  gumus-acik: "#F4F6F9"
  gumus-koyu: "#8E98A8"
  primary: "#F2A93B"
  primary-zayif: "rgba(242, 169, 59, 0.20)"
  oynatma: "#7FD6F0"
  dalga: "#3E4552"
  dalga-calinan: "#C9D1DC"
  gecti: "#8FD19E"
  dustu: "#E5735C"
typography:
  baslik:
    fontFamily: "Space Grotesk"
    fontWeight: 600
    fontSize: 24px
    lineHeight: 1.15
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
  sayac:
    fontFamily: "JetBrains Mono"
    fontWeight: 500
    fontSize: 30px
    lineHeight: 1
rounded:
  kucuk: 8px
  panel: 16px
  kapak: 10px
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

Taban disiplin global Dark Glassmorphism kurallarıdır; Yanki'nin çeşidi **silver/dark glassmorphism** (Scryne,
2026-10-10). Bu dosya Yanki'yi ayıran katmanı kaydeder.

- **Mood:** gece stüdyosunun gümüş kontrol masası. Grafit zemin, fırçalanmış alüminyum kenarlar, kulak odaklı sakinlik.
  Pano değil, kontrol odası: dinleme masası + hattın sinyal zinciri.
- **Farklılaştırıcı detay 1:** dalga formu şarkı ekranının kahramanıdır. Bozuk aralık dalganın üzerinde sürüklenerek
  amber bir bantla işaretlenir; bant analog kayıt makinesindeki punch-in işaretini andırır.
- **Farklılaştırıcı detay 2:** Pano'da hat, bir mikser kanal şeridi gibi soldan sağa akan tek bir sinyal zinciridir
  (Keşif → Üretim → Dinleme → Paket → İnceleme → Yayında); her durak büyük mono rakamla sayar, duraklar ince gümüş bir
  hatla bağlanır. Eşit kart üçlüsü yok.

## Colors

Zemin grafit (`zemin` → `zemin-2`); arkada iki soğuk ışık: sol üstte çelik-mavi `parilti`, sağ altta gri `parilti-2`.
Cam bunların önünde okunur. Renk dili gümüş: aktif durumlar, birincil eylem (metalik `gumus-acik` → `gumus-koyu`
gradyanı, koyu metin), marka sözcüğü ve büyük sayılar gümüş gradyan metin. Tek sıcak renk **amber** ve yalnız
punch-in'de: seçili aralık ve "onar". Çalma imleci buz **camgöbeği** (`oynatma`) — amberle karışmaz. Kapı ve durum
rozetleri **ada çayı yeşili / mercan**; doygun kırmızı-yeşil yok, uzun dinleme seansında göz yormasın.

## Typography

Başlıklar Space Grotesk, gövde Inter. Bütün zaman kodları, kapı değerleri ve sayaçlar JetBrains Mono (`sayac` pano
duraklarında): rakamlar sütun sütun hizalanır, kaymaz.

## Layout

- Solda dar cam kenar çubuğu: marka, görünümler (Pano, Keşif, Yayın), şarkı kuyruğu (32 px kapak + ad + aşama).
  Mobilde üste geçer.
- **Pano** (açılış): üstte cam sinyal zinciri şeridi; altında asimetrik iki sütun — geniş sol "Senden beklenen" ve
  "Sıradaki yüklemeler", dar sağ "Kazanç", "Son gece koşusu", "Otomasyon". En altta bildirim zaman çizelgesi.
- **Şarkı ekranı:** başlıkta 132 px kapak (kare, `rounded.kapak`), yanında ad, sanatçı, aşama, künye; adaylar alt
  alta tam genişlik dalga şeritleri.

## Components

- **Cam panel:** `yuzey-cam` + `backdrop-filter: blur(14px)` + 1 px gümüş ışık yakalayan kenar (üstte `cizgi-gumus`,
  altta `cizgi`'ye solan gradyan). Yalnız kenar çubuğu, pano şeridi, pano yan panelleri, alt eylem çubuğu, bildirim.
  Desteklemeyen tarayıcıda opak `yuzey-2`.
- **Aday şeridi:** opak `yuzey` (cam değil — dalga net okunmalı). Üstte aday no + tohum + kapı rozetleri, ortada dalga
  (96 px), altta zaman kodu ve eylemler.
- **Seçim bandı:** sürüklemeyle oluşur, `primary-zayif` dolgu + 1 px `primary` kenar; Esc temizler. Shift+←/→ seçimi
  0,5 sn genişletir.
- **Düğmeler:** birincil metalik gümüş (onayla), ikincil gümüş kenarlı, punch-in amber kenarlı (onar), tehlike metin
  mercan.
- **Kapak:** kare, `rounded.kapak`, ince `cizgi` kenar ve hafif iç gölge; "Başka kapak" ikincil düğme.

## Do's and Don'ts

- Cam yalnız kilit yüzeylerde; dalga şeritleri ve liste satırları opak.
- `backdrop-filter`'lı katman canlandırılmaz; dalga canvas'ı cam katmanın altında yeniden çizilmez.
- Rozetlerde yalnız renk değil metin de olur ("parmak izi 0,58 ✓").
- Gümüş gradyan metin yalnız marka ve pano sayaçlarında; gövde metni düz `metin`.
- Kontrast: gövde ≥ 4.5:1 (`metin`/`metin-2` grafit zemin ve camda ölçüldü), hareket azaltmada geçişler kapalı.
