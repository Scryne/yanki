---
proje: Yanki
created: 2026-10-06
modified: 2026-10-07
type: roadmap
status: aktif
---
# Yanki — Roadmap

Durum sütunu session-start hook'u tarafından otomatik okunur — format bozulmasın:
⏳ Bekliyor / 🔄 Devam Ediyor / ✅ Tamamlandı / ⛔ Engelli.

| Faz | Adı | Durum | Bitti Kriteri |
| --- | --- | --- | --- |
| 0 | Spike ve karar | ✅ Tamamlandı | ACE-Step 8 GB'ta ölçüldü, cover tarifi ve bölge onarımı dinleme testleriyle seçildi (`docs/arastirma/01`) |
| 1 | İskelet ve sağlık | 🔄 Devam Ediyor | `uv` projesi, `yanki` CLI, `config/motor.toml`; ruff + pytest yerelde yeşil; CI ve Dependabot dosyaları; GitHub private repo (Scryne onayıyla) ve CI yeşil |
| 2 | Motor köprüsü ve tam şarkı | ⏳ Bekliyor | `motor_isci.py` alt süreçte cover + repaint yapıyor, GPU kapısı bekliyor; tam bir şarkı (≥ 4 dk) 8 GB'ta üretildi, süre ve VRAM kayıtlı |
| 3 | Girdi hazırlığı | ⏳ Bekliyor | `girdi/liste.toml`'daki 3 şarkı için kaynak ses (süre kontrollü), sözler (LRCLIB/dosya/Whisper), künye (MusicBrainz), BPM/ton/stil tanımı hazır |
| 4 | Kapılar ve dinleme sayfası | ⏳ Bekliyor | Her şarkıya 2 aday; kopya/söz/süre kapıları çalışıyor (bozuk girdiyle sınandı); Scryne yerel sayfada bir şarkıyı dinleyip bölge onarımıyla onayladı |
| 5 | Yükleme paketi | ⏳ Bekliyor | Onaylı şarkıdan mastering (−14 LUFS, −1 dBTP) + 3000×3000 kapak + metadata + `YUKLE.md`; Scryne'ın seçtiği dağıtımcının formuna birebir uyuyor |
| 6 | Kalite turu | ⏳ Bekliyor | Mırıldanma, nefes, titreme için denemeler; Scryne bir şarkıda "yayınlanabilir" dedi |
| 7 | Gerçek kullanım | ⏳ Bekliyor | Scryne listeden bir şarkıyı yükledi, dağıtımcı kabul etti, parça Spotify'da dinlenebilir; bulgular roadmap'e işlendi |

## Faz Detayları

### Faz 0: Spike ve karar ✅
- S1–S7, dört dinleme testi. Seçilen tarif: XL-SFT INT8, `cover`, güç 0,7, 100 adım, doğru stil + BPM + ton + söz.
- **Notlar:** Otomatik kalite ölçüleri kulağı tutmadı → "iyi"yi Scryne seçer, kapılar yalnız yayınlanamazı eler.
  ACE-Step Python API tuzakları `docs/arastirma/01`'de; motor köprüsü hepsini tek yerde düzeltecek.

### Faz 1: İskelet ve sağlık
- **İşler:** `pyproject.toml` (Python 3.12, torch'suz), `yanki` paketi + CLI (`yanki durum`), `config/motor.toml`, ruff,
  pytest, `.github/workflows/ci.yml`, `.github/dependabot.yml` (`uv`), `fpcalc` araç yolu ayarı.
- **Bitti Kriteri:** yukarıdaki tablo.

### Faz 2: Motor köprüsü ve tam şarkı
- **İşler:** iş şeması (JSON), `motor_isci.py` (ACE-Step venv'iyle çalışır, birden çok işi tek model yüklemesiyle yapar),
  GPU kapısı (`nvidia-smi` boş VRAM), zaman aşımı, hata raporu; tam şarkı ölçümü.
- **Risk:** 4–5 dk şarkı VRAM'e sığmayabilir → parçalı üretim ya da süre sınırı kararı burada.

### Faz 3: Girdi hazırlığı
- **İşler:** liste biçimi, kaynak klasörü + yt-dlp denemesi (süre ±3 sn kontrolü), LRCLIB, MusicBrainz (User-Agent: proje
  adı + depo bağlantısı; kişisel e-posta yok), söz biçimleyici (bölüm etiketleri), BPM/ton (librosa), stil tanımı.

### Faz 4: Kapılar ve dinleme sayfası
- **İşler:** `fpcalc` parmak izi + dalga kapısı (eşikler spike'tan: parmak izi < 0,72, dalga < 0,25), Whisper söz kapısı,
  süre kapısı; FastAPI sayfası: oynatıcı, onay, bölge onarımı (bas–son), ret, not.

### Faz 5: Yükleme paketi
- **İşler:** mastering, kapak, metadata (başlık orijinalle aynı, orijinal sanatçı adı başlık/kapakta yok, yazarlar
  publishing alanında, AI beyanı, cover işareti), `YUKLE.md` (form alanları sırayla, kopyala-yapıştır).
- **Önce:** Scryne'dan sanatçı adı ve dağıtımcı seçimi.

### Faz 6: Kalite turu
- **Denenecekler:** tohum/aday sayısı, stil tanımı varyantları, adım/kaydırma (`shift`), güç 0,6–0,8 şarkıya göre,
  vokal izi son işlemi (nefes/sibilans), LoRA (8–20 şarkı) ihtiyacı.
