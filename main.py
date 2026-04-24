#!/usr/bin/env python3
"""
Viral YouTube Shorts Generator – Tam Otomatik & Gelişmiş Sürüm
Her çalıştırmada bir video üretir, YouTube'a yükler.
GitHub Actions ile zamanlanmış çalışma için optimize edilmiştir.
"""

import asyncio, os, sys, re, random, pickle, logging, json, time, traceback
from pathlib import Path
from typing import List, Tuple, Optional

from dotenv import load_dotenv
load_dotenv()

# ---------- API Anahtarları ve Kritik Kontroller ----------
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
if not PEXELS_API_KEY:
    sys.exit("❌ PEXELS_API_KEY tanımlı değil. Lütfen .env dosyasını kontrol edin.")

if not Path("client_secrets.json").exists():
    sys.exit("❌ client_secrets.json bulunamadı. Google OAuth dosyasını yerleştirin.")

CLIENT_SECRETS_FILE = "client_secrets.json"
TOKEN_PICKLE = "token.pickle"
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_CATEGORY_ID = "22"

# ---------- Loglama (hem konsola hem dosyaya) ----------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("bot.log", encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ---------- Kütüphaneler ----------
import g4f
import edge_tts
from moviepy.editor import (VideoFileClip, AudioFileClip, CompositeVideoClip,
                            CompositeAudioClip, TextClip)
from moviepy.video.fx import crop
from moviepy.audio.fx.all import audio_loop, volumex
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------- Sabit Ayarlar ----------
OUTPUT_VIDEO = "final_shorts.mp4"
VOICEOVER_FILE = "voiceover.mp3"
BACKGROUND_FILE = "background_video.mp4"
VIDEO_SIZE = (1080, 1920)
DEFAULT_VOICE = "tr-TR-EmelNeural"          # Doğal Türkçe kadın sesi
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf"
FONT_DIR = Path("fonts")
FONT_PATH = FONT_DIR / "Montserrat-Bold.ttf"
MAX_CAPTION_CHUNK_WORDS = 3                 # Altyazı chunk başına en fazla kelime
MAX_CAPTION_DURATION = 1.2                  # Bir chunk'ın max gösterim süresi (s)

# ---------- Niş Havuzu (daha viral konular eklendi) ----------
NICHE_POOL = [
    "Şok Edici Psikolojik Gerçekler",
    "Bilinmeyen İnsan Davranışları",
    "Çözülememiş Tarihi Gizemler",
    "Uzayın Korkunç Sırları",
    "Günlük Hayatta Stoacı Felsefe",
    "Başarı Psikolojisi ve Motivasyon",
    "Teknolojinin Karanlık Yüzü",
    "Mitoloji ve Efsanelerin Kökenleri",
    "İnanılmaz Bilimsel Keşifler",
    "Tuhaf ve Enteresan Yasalar"
]

# ---------- 1. Viral Senaryo Üretimi ----------
def generate_script(niche: str) -> str:
    """
    Gelişmiş prompt ile 30‑45 saniyelik viral script üretir.
    Hata durumunda alternatif modeller dener.
    """
    logger.info(f"✍️ Senaryo üretiliyor: '{niche}'")
    prompt = f"""
Sen bir viral YouTube Shorts içerik üreticisisin.
Aşağıdaki konuda TÜRKÇE, 30‑45 saniye boyunca okunacak bir metin yaz.
Metin şu kurallara uymalı:
- İlk 3 saniye mutlaka şok edici, merak uyandıran bir soru veya çarpıcı bir cümle ile başlamalı.
- Orta kısımda şaşırtıcı bilgiler, gerçekler veya hikayelerle izleyiciyi ekrana kilitlemeli.
- Sonunda güçlü bir kapanış yapıp izleyiciyi yoruma veya beğeniye teşvik etmeli (call-to-action).
- Kesinlikle sahne yönlendirmeleri, emoji veya ses efektleri olmamalı, sadece konuşma metni.
- Metin tamamen Türkçe olmalı.

Konu: {niche}

Yalnızca metni yaz, başka hiçbir şey ekleme.
"""
    models_to_try = [g4f.models.default, g4f.models.gpt_4, g4f.models.gpt_35_turbo]
    for model in models_to_try:
        try:
            response = g4f.ChatCompletion.create(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                timeout=60
            )
            script = response.strip().strip('"').strip("'")
            if len(script) < 20:
                continue
            logger.info("✅ Senaryo hazır.")
            return script
        except Exception as e:
            logger.warning(f"Model {model} başarısız: {e}")
            time.sleep(2)

    raise RuntimeError("Hiçbir model ile senaryo üretilemedi.")

# ---------- 2. Seslendirme (Türkçe TTS) ----------
async def create_voiceover(script: str) -> Tuple[str, List[Tuple[float, float, str]]]:
    """edge‑tts ile Türkçe seslendirme yapar, kelime zaman damgalarını döner."""
    logger.info("🔊 Seslendirme oluşturuluyor...")
    communicate = edge_tts.Communicate(script, DEFAULT_VOICE)
    word_timestamps = []

    with open(VOICEOVER_FILE, "wb") as f:
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                f.write(chunk["data"])
            elif chunk["type"] == "WordBoundary":
                start = chunk["offset"] / 10_000_000
                dur = chunk["duration"] / 10_000_000
                word = chunk["text"]
                word_timestamps.append((start, dur, word))

    if not word_timestamps:
        logger.warning("⚠️ Kelime zamanlaması alınamadı. Altyazı boş olacak.")
    else:
        logger.info(f"✅ {len(word_timestamps)} kelime zamanlaması alındı.")
    return VOICEOVER_FILE, word_timestamps

# ---------- 3. Arka Plan Videosu (Gelişmiş Arama) ----------
def extract_keywords(script: str, count: int = 5) -> List[str]:
    """Script'ten anlamlı anahtar kelimeler çıkarır (stop words filtresi)."""
    stop_words = {"için","gibi","kadar","ama","fakat","ancak","değil","evet","hayır",
                  "çok","daha","bir","iki","üç","dört","beş","the","and","for","with",
                  "that","this","from","are","was","were","been","being","have","has","had"}
    words = re.findall(r'\b\w{4,}\b', script.lower())
    filtered = [w for w in words if w not in stop_words]
    # Sırala: en uzun kelimeleri önce al
    filtered.sort(key=len, reverse=True)
    return filtered[:count]

def search_pexels(keywords: List[str]) -> Optional[str]:
    """
    Pexels API'de birden fazla anahtar kelime kombinasyonu dener.
    İlk bulduğu uygun dikey videonun indirme linkini döner.
    """
    headers = {"Authorization": PEXELS_API_KEY}
    for i in range(min(3, len(keywords)), 0, -1):
        query = " ".join(keywords[:i])
        logger.info(f"🔍 Pexels sorgusu: '{query}'")
        try:
            resp = requests.get(
                "https://api.pexels.com/videos/search",
                headers=headers,
                params={"query": query, "per_page": 3, "orientation": "portrait", "size": "large"},
                timeout=15
            )
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if videos:
                # En az 1080x1920 olanı seç
                for vid in videos:
                    for vf in vid["video_files"]:
                        if vf["width"] >= 1080 and vf["height"] >= 1920:
                            logger.info(f"✅ Uygun video bulundu: {vf['width']}x{vf['height']}")
                            return vf["link"]
                # Uygun boyut yoksa en büyüğünü al (sonra kırpılacak)
                best = max(videos[0]["video_files"], key=lambda x: x["width"]*x["height"])
                logger.info(f"⚠️ Tam 1080x1920 yok, en iyisi: {best['width']}x{best['height']}")
                return best["link"]
        except Exception as e:
            logger.warning(f"Pexels hatası ({query}): {e}")
            time.sleep(1)
    return None

def fetch_background_video(script: str) -> str:
    """Anahtar kelimelerle video indirir, bulamazsa soyut bir arama yapar."""
    keywords = extract_keywords(script)
    if not keywords:
        keywords = ["abstract", "background", "colors"]
    download_url = search_pexels(keywords)
    if not download_url and keywords != ["abstract", "background", "colors"]:
        logger.warning("İlk deneme başarısız, soyut arama deneniyor...")
        download_url = search_pexels(["abstract", "background", "colors"])

    if not download_url:
        raise RuntimeError("Pexels'te hiç video bulunamadı.")

    logger.info(f"⏬ Video indiriliyor...")
    try:
        with requests.get(download_url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(BACKGROUND_FILE, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        logger.info("✅ Arka plan videosu indirildi.")
        return BACKGROUND_FILE
    except Exception as e:
        logger.error(f"❌ İndirme hatası: {e}")
        raise

# ---------- 4. Font İşlemleri ----------
def ensure_font() -> str:
    """Fontu indirir, yoksa sistem fontu döner."""
    if FONT_PATH.exists():
        return str(FONT_PATH.resolve())
    logger.info("🔤 Montserrat Bold indiriliyor...")
    try:
        FONT_DIR.mkdir(exist_ok=True)
        with requests.get(FONT_URL, timeout=15) as r:
            r.raise_for_status()
            with open(FONT_PATH, "wb") as f:
                f.write(r.content)
        logger.info("✅ Font hazır.")
        return str(FONT_PATH.resolve())
    except Exception as e:
        logger.warning(f"⚠️ Font indirilemedi, fallback 'Arial-Bold': {e}")
        return "Arial-Bold"

# ---------- 5. Altyazı Chunking (2‑3 kelimelik gruplar) ----------
def chunk_timestamps(word_ts: List[Tuple[float, float, str]]) -> List[Tuple[float, float, str]]:
    """
    Kelimeleri 2‑3 kelimelik ve maksimum 1.2 saniyelik gruplara böler.
    Her grup (başlangıç_sn, süre, grup_metin) şeklinde döner.
    """
    if not word_ts:
        return []
    chunks = []
    current_words = []
    current_start = word_ts[0][0]
    chunk_start = current_start
    accumulated_dur = 0.0

    for start, dur, word in word_ts:
        # Yeni bir gruba başlama koşulları:
        if (len(current_words) >= MAX_CAPTION_CHUNK_WORDS or
            (current_words and accumulated_dur + dur > MAX_CAPTION_DURATION)):
            # Mevcut grubu kapat
            text = " ".join(current_words)
            # Grubun bitiş zamanını hesapla (son kelimenin başlangıcı + süresi)
            chunk_end = current_start + accumulated_dur
            chunks.append((chunk_start, chunk_end - chunk_start, text))
            # Yeni grubu başlat
            current_words = [word]
            chunk_start = start
            accumulated_dur = dur
            current_start = start
        else:
            current_words.append(word)
            accumulated_dur += dur
            # current_start aynı kalır (ilk kelimenin başlangıcı)

    # Son grubu ekle
    if current_words:
        text = " ".join(current_words)
        chunk_end = current_start + accumulated_dur
        chunks.append((chunk_start, chunk_end - chunk_start, text))

    logger.info(f"📝 {len(chunks)} altyazı grubu oluşturuldu.")
    return chunks

def generate_captions(chunked_ts: List[Tuple[float, float, str]]) -> List[TextClip]:
    """Gruplanmış zaman damgalarından MoviePy TextClip nesneleri üretir."""
    if not chunked_ts:
        return []
    font = ensure_font()
    clips = []
    for start, dur, text in chunked_ts:
        # Süreyi biraz uzatarak kaybolmayı yumuşat
        display_dur = dur + 0.1
        txt_clip = (TextClip(
                        text,
                        fontsize=80,
                        color="white",
                        font=font,
                        stroke_color="black",
                        stroke_width=6,
                        method="caption" if len(text)>15 else "label",
                        size=(VIDEO_SIZE[0]-100, None)
                    )
                    .set_start(start)
                    .set_duration(display_dur)
                    .set_position(("center", "center")))
        clips.append(txt_clip)
    logger.info(f"✅ {len(clips)} altyazı klibi oluşturuldu.")
    return clips

# ---------- 6. Video Montajı ----------
def mix_background_music(audio_clip: AudioFileClip, music_path: str = "bg_music.mp3") -> Optional[AudioFileClip]:
    """Varsa arka plan müziğini %8 ses seviyesinde ekler."""
    if not os.path.exists(music_path):
        return None
    try:
        bg_music = AudioFileClip(music_path).fx(volumex, 0.08)
        bg_music = audio_loop(bg_music, duration=audio_clip.duration)
        return CompositeAudioClip([audio_clip, bg_music])
    except Exception as e:
        logger.warning(f"⚠️ Müzik eklenemedi: {e}")
        return None

def assemble_video(bg_path: str, audio_path: str,
                   chunked_ts: List[Tuple[float, float, str]],
                   music_path: Optional[str] = None) -> str:
    """9:16 crop, ses, altyazı ve müzik ile final videosunu oluşturur."""
    logger.info("🎞️ Video montajı başlıyor...")
    bg_clip = VideoFileClip(bg_path)
    audio_clip = AudioFileClip(audio_path)
    target_dur = audio_clip.duration

    # 9:16 kırpma (merkezden)
    w, h = bg_clip.size
    if w / h < VIDEO_SIZE[0] / VIDEO_SIZE[1]:
        bg_clip = bg_clip.resize(width=VIDEO_SIZE[0])
        y_center = bg_clip.h / 2
        bg_clip = crop(bg_clip, y1=y_center - VIDEO_SIZE[1]/2, y2=y_center + VIDEO_SIZE[1]/2)
    else:
        bg_clip = bg_clip.resize(height=VIDEO_SIZE[1])
        x_center = bg_clip.w / 2
        bg_clip = crop(bg_clip, x1=x_center - VIDEO_SIZE[0]/2, x2=x_center + VIDEO_SIZE[0]/2)
    bg_clip = bg_clip.resize(VIDEO_SIZE)

    # Süre ayarı
    if bg_clip.duration < target_dur:
        bg_clip = bg_clip.loop(duration=target_dur)
    else:
        bg_clip = bg_clip.subclip(0, target_dur)

    # Ses
    final_audio = audio_clip
    if music_path:
        mixed = mix_background_music(audio_clip, music_path)
        if mixed:
            final_audio = mixed
    bg_clip = bg_clip.set_audio(final_audio)

    # Altyazılar
    caption_clips = generate_captions(chunked_ts)

    final = CompositeVideoClip([bg_clip] + caption_clips, size=VIDEO_SIZE)
    final.write_videofile(OUTPUT_VIDEO, codec="libx264", audio_codec="aac",
                         fps=30, preset="medium", threads=4,
                         verbose=False, logger=None)
    logger.info("✅ Montaj tamamlandı.")
    return OUTPUT_VIDEO

# ---------- 7. YouTube Yükleme ----------
def get_youtube_service():
    """OAuth 2.0 ile yetkilendirme yap ve YouTube servisini döndür."""
    credentials = None
    if os.path.exists(TOKEN_PICKLE):
        with open(TOKEN_PICKLE, "rb") as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            try:
                credentials.refresh(Request())
                logger.info("🔄 Token yenilendi.")
            except Exception:
                logger.warning("Token yenilenemedi, sıfırdan yetkilendirme başlatılıyor.")
                credentials = None
        if not credentials:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, YOUTUBE_SCOPES)
            credentials = flow.run_local_server(port=0, open_browser=False)  # headless ortam için
        with open(TOKEN_PICKLE, "wb") as token:
            pickle.dump(credentials, token)
    return build("youtube", "v3", credentials=credentials)

def upload_to_youtube(video_path: str, title: str,
                      description: str = "",
                      tags: Optional[List[str]] = None,
                      privacy: str = "public") -> str:
    """Video'yu YouTube'a yükler, URL döner."""
    if not os.path.exists(video_path):
        raise FileNotFoundError(f"Video bulunamadı: {video_path}")

    # Başlığa #shorts ekle
    if "#shorts" not in title.lower() and "#short" not in title.lower():
        title = f"{title} #shorts"

    youtube = get_youtube_service()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags or ["shorts", "youtubeshorts", "viral"],
            "categoryId": YOUTUBE_CATEGORY_ID
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False
        }
    }
    logger.info(f"📤 YouTube'a yükleniyor: {title}")
    media = MediaFileUpload(video_path, mimetype="video/mp4",
                            resumable=True, chunksize=5*1024*1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            logger.info(f"   Yükleme: %{int(status.progress()*100)}")
    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"
    logger.info(f"✅ Yayında: {url}")
    return url

# ---------- 8. Ana İş Akışı (Tek seferlik) ----------
async def run_pipeline(niche: str):
    """Bir niş için tüm adımları sırayla çalıştırır."""
    try:
        logger.info(f"🎲 Seçilen niş: {niche}")
        # 1. Senaryo
        script = generate_script(niche)
        logger.info("📜 Senaryo:\n" + script)

        # 2. Seslendirme
        audio_path, word_ts = await create_voiceover(script)
        if not word_ts:
            raise RuntimeError("Kelime zamanlaması olmadan devam edilemez.")

        # 3. Altyazı chunk'ları
        chunked_ts = chunk_timestamps(word_ts)

        # 4. Arka plan videosu
        bg_path = fetch_background_video(script)

        # 5. Montaj (müzik varsa kullan)
        music = "bg_music.mp3" if os.path.exists("bg_music.mp3") else None
        final_path = assemble_video(bg_path, audio_path, chunked_ts, music)

        # 6. YouTube Yükleme
        # Başlık olarak nişin kendisini ve script'ten ilk cümleyi birleştir
        first_sentence = re.split(r'[.!?]', script)[0].strip()[:50]
        video_title = f"{niche}: {first_sentence}"

        upload_to_youtube(
            video_path=final_path,
            title=video_title,
            description=f"🔥 {niche} hakkında çarpıcı gerçekler!\n"
                        f"Her gün yeni shorts videoları için abone olmayı unutma! 🛎️",
            tags=[niche.lower(), "shorts", "viral", "bilgi"]
        )
        logger.info("🎉 Tüm işlem başarıyla tamamlandı.")
    except Exception as e:
        logger.error(f"❌ Kritik hata: {e}\n{traceback.format_exc()}")
        sys.exit(1)

# ---------- 9. Giriş Noktası ----------
if __name__ == "__main__":
    niche = random.choice(NICHE_POOL)
    asyncio.run(run_pipeline(niche))