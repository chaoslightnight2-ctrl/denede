# Denede — Türkçe Merak Shorts Botu

Üretim hattı: `Groq senaryosu → Türkçe ses → kelime zamanlı altyazı → Pexels dikey b-roll → ffmpeg montaj → YouTube Shorts yüklemesi`.

Çıktı 1080×1920 dikey, yaklaşık 32 saniyedir. Otomatik yayın hattı yalnızca YouTube'a yükleme yapar; başka sosyal platformlara çapraz paylaşım yapmaz.

## İçerik yaklaşımı

Denede tek bir dar alt nişe bağlı değildir. Günlük üretim; psikoloji, gündelik bilim, uzay, hayvanlar ve doğa, teknoloji ve yapay zekâ, tarih ve arkeoloji, coğrafya, diller, kültür, yemeklerin kökenleri, mitoloji, mantık ve günlük eşyaların çalışma biçimi gibi 15 geniş konu alanı arasında döner.

Her Short için senaryo paketi ayrı ayrı üretir: merak uyandıran ama videoda karşılığı bulunan başlık, ilk sahnede güçlü hook, konunun cevabını veren kısa anlatım, izleyiciye konuya özel yorum sorusu ve doğal Denede abonelik çağrısı, konuya özel açıklama/etiketler. Başlık, sahne, etiket ve açıklama biçimleri yüklemeden önce kod tarafından doğrulanır. Yanlış istatistik, kaynağı belirsiz iddia ve vaat edilen cevabı vermeyen clickbait istemi engellenir.

## Hızlı başlangıç (Windows)

```powershell
cd freefaceless
Copy-Item .env.example .env   # GROQ + PEXELS anahtarları
.\setup.ps1
# YouTube yetkisi (bir kez):
.\.venv\Scripts\python.exe -m src.authorize
# Üret, yükleme yapma:
.\.venv\Scripts\python.exe -m src.pipeline --no-upload
# Dört videonun kuru üretim provası:
.\.venv\Scripts\python.exe -m src.daily_batch --no-upload
```

Gerekenler: Python 3.11+, ffmpeg, Groq ve Pexels anahtarı, YouTube Data API OAuth bilgileri.

## GitHub Actions

`.github/workflows/freefaceless.yml` her gün 00:30 Türkiye saatinde çalışır. Dört ayrı konu alanından Shorts üretir ve 06:00 / 12:00 / 18:00 / 23:00 saatlerine zamanlar. YouTube'a önce private olarak yükleyip `publishAt` ile planlar. Actions'ı elle başlatmadık; kodu GitHub üzerinden güncelledik.

Gerekli Actions secrets: `GROQ_API_KEY`, `PEXELS_API_KEY`, `CLIENT_SECRETS_JSON`, `YOUTUBE_REFRESH_TOKEN`.

