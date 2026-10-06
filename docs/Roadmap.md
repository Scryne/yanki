---
proje: Yanki
created: 2026-10-06
type: roadmap
status: aktif
---
# Yanki — Roadmap

Durum sütunu session-start hook'u tarafından otomatik okunur — format bozulmasın:
⏳ Bekliyor / 🔄 Devam Ediyor / ✅ Tamamlandı / ⛔ Engelli.

| Faz | Adı | Durum | Bitti Kriteri |
| --- | --- | --- | --- |
| 1 | İskelet ve sağlık | ⏳ Bekliyor | Repo GitHub'da; CI (lint + test + build) varsayılan dalda yeşil; `.github/dependabot.yml`; LLM kullanılıyorsa model kimlikleri config dosyasında (sağlık nöbeti izler) |
| 2 | | ⏳ Bekliyor | |
| 3 | Gerçek kullanım | ⏳ Bekliyor | Proje-Fikri'deki "bitti = kullanıldı" cümlesi gerçekleşti; bulgular roadmap'e işlendi |

## Faz Detayları

Faz 1 ve son faz şablonla gelir: biri projenin sessizce çürümesini engeller (2026-09 denetiminde
7 vitrin projesinin 6'sında CI aylarca kırmızıydı, iki projenin LLM modeli emekliye ayrılmıştı), öbürü
"bitti"yi kullanıma bağlar. Aradaki fazlar projeye özeldir.

### Faz 1: İskelet ve sağlık
- **İşler:**
- **Bitti Kriteri:**
- **Notlar:** (bu faz bittiğinde öğrenilen, sonraki fazlara işlenmesi gereken şey)
