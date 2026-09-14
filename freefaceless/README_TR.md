# FreeFaceless Türkçe Uyarlama (freefaceless/)

Ücretsiz pipeline: `senaryo (Groq) → ses (edge-tts) → altyazı (faster-whisper, lokal) → b-roll (Pexels) → montaj (ffmpeg) → yükleme (YouTube Data API)`.

Çıktı: 1080x1920, 30fps, ~32-35 sn Türkçe Short.

## Hızlı başlangıç (Windows)

```powershell
cd freefaceless
Copy-Item .env.example .env   # içine GROQ + PEXELS anahtarlarını yaz
.\setup.ps1
# YouTube yetkisi (bir kez, tarayıcı açılır):
.\.venv\Scripts\python.exe -m src.authorize
# Kuru çalıştırma (yüklemez):
.\.venv\Scripts\python.exe -m src.pipeline --no-upload
# Gerçek çalıştırma:
.\run_daily.ps1
# Tek nişe zorla:
.\.venv\Scripts\python.exe -m src.pipeline --niche "Uzayın Korkunç Sırları"
```

Gerekenler: **Python 3.11+**, **ffmpeg** (`winget install Gyan.FFmpeg`),
ücretsiz **Groq** + **Pexels** anahtarı, `client_secret.json`
(Google Cloud → YouTube Data API v3 → OAuth Desktop).

## GitHub Actions

`.github/workflows/freefaceless.yml` — sadece **manuel** tetiklenir
(`workflow_dispatch`, niş seçimli). Mevcut günlük 4'lü botla kota çakışmasın
diye zamanlayıcı kapalı gelir.

Gerekli Actions secrets: `GROQ_API_KEY`, `PEXELS_API_KEY`,
`CLIENT_SECRETS_JSON`, `YOUTUBE_REFRESH_TOKEN`.

## Mevcut bottan farkı

| Konu | `main.py` + runner'lar | `freefaceless/` |
|---|---|---|
| Senaryo | g4f (kararsız, ücretsiz) | Groq API (ücretsiz katman, stabil) |
| Tekrar önleme | yok (aynı fallback metinler dönüyor) | `state.json` ile kullanılmış konular elenir |
| Altyazı zamanlama | Edge WordBoundary / enerji analizi | faster-whisper word-timestamps (lokal) |
| Görsel | sahne başına 1 Pexels videosu | sahne başına Pexels + süre eşleme (ffmpeg concat) |
| Caption | PIL tek kelime | ASS karaoke altyazı (ffmpeg burn-in) |

Not: faster-whisper ilk çalışta ~140MB model indirir; CPU'da çalışır.
