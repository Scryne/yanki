# Yanki

Bu proje Scryne'ın Proje Çalışma Akışı'nı takip eder (bkz. global `~/.claude/CLAUDE.md`, ve
detaylı gerekçeler için ScryneOS vault'unda `🧠 500-Knowledge/Proje-Calisma-Akisi.md`).

## Durum

Şu anki aşama `.claude/state.json` içinde tutulur, `session-start` hook'u her oturum başında
bunu okuyup bağlama enjekte eder — nerede kaldığımızı sormana gerek kalmaz. Bir aşama
bittiğinde `asama` alanını sırayla güncelle: `fikir` → `denetim` → `finalizasyon` → `roadmap`
→ `uygulama` → `tamamlandi`. Aynı anda ScryneOS vault'undaki
`🏰 300-Projects/Yanki.md` index notunu da güncelle (frontmatter `asama`/`modified` +
`**Aşama:**` satırı — vault oturumu bunu okuyarak projeyi bilir).

Hook'lar (`.claude/hooks/`) `proje-baslat` şablonunun birebir kopyasıdır; burada elle
değiştirilmez. Kanonik roadmap `docs/Roadmap.md` dışında bir dosyaysa `state.json`'a
`"roadmap": "docs/<dosya>.md"` yazılır, iki hook da onu okur.

## Dosyalar

- `docs/Proje-Fikri.md` — ilk fikir
- `docs/Final-Dokuman.md` — nihai kararlar (teknoloji stack, mimari, riskler)
- `docs/Roadmap.md` — fazlı yol haritası; her faz "Durum" sütunuyla takip edilir, hook bunu
  otomatik okur
- `DESIGN.md` (proje kökünde) — bu projeye özel frontend kimliği. Kesin değerler
  frontmatter'da, gerekçe Markdown'da.

## Frontend

Taban disiplin ve araç sırası global `frontend-sistemi` skill'inde (burada tekrarlanmaz; UI işinden önce yükle). Projeye
özel karakteri kökteki `DESIGN.md` belirler ve çelişkide global varsayılanı ezer.
