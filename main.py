#!/usr/bin/env python3
"""
🔥 VIRAL YOUTUBE SHORTS GENERATOR – ULTIMATE VERSION
Her çalıştırmada yüksek tutundurma odaklı bir video üretir ve YouTube'a yükler.
GitHub Actions ile tam otomatik çalışır.
"""

import asyncio, os, sys, re, random, json, logging, time, traceback
from pathlib import Path
from typing import List, Tuple, Optional

from dotenv import load_dotenv
load_dotenv()

# ---------- API Anahtarları ve Kritik Kontroller ----------
PEXELS_API_KEY = os.getenv("PEXELS_API_KEY")
YOUTUBE_REFRESH_TOKEN = os.getenv("YOUTUBE_REFRESH_TOKEN")

if not PEXELS_API_KEY:
    sys.exit("❌ PEXELS_API_KEY tanımlı değil.")
if not YOUTUBE_REFRESH_TOKEN:
    sys.exit("❌ YOUTUBE_REFRESH_TOKEN tanımlı değil.")
if not Path("client_secrets.json").exists():
    sys.exit("❌ client_secrets.json bulunamadı.")

CLIENT_SECRETS_FILE = "client_secrets.json"
YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
YOUTUBE_CATEGORY_ID = "22"  # People & Blogs

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler("bot.log", encoding="utf-8"), logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

import g4f
import edge_tts
from moviepy.editor import (VideoFileClip, AudioFileClip, CompositeVideoClip,
                            CompositeAudioClip, TextClip)
from moviepy.video.fx import crop
from moviepy.audio.fx.all import audio_loop, volumex
import requests
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# ---------- Viral İçerik Optimize Sabitler ----------
OUTPUT_VIDEO = "final_shorts.mp4"
VOICEOVER_FILE = "voiceover.mp3"
BACKGROUND_FILE = "background_video.mp4"
VIDEO_SIZE = (1080, 1920)
DEFAULT_VOICE = "tr-TR-EmelNeural"
RATE = "+15%"   # %15 daha hızlı konuşma (dinamik)
PITCH = "-5Hz"  # Hafif pes, daha ciddi
FONT_URL = "https://github.com/google/fonts/raw/main/ofl/montserrat/static/Montserrat-Bold.ttf"
FONT_DIR = Path("fonts")
FONT_PATH = FONT_DIR / "Montserrat-Bold.ttf"
MAX_CAPTION_WORDS = 2           # Bir seferde en fazla 2 kelime (tempolu)
MAX_CAPTION_DURATION = 0.75     # Maksimum 0.75 sn
FONT_SIZE = 90
STROKE_WIDTH = 8

# ---------- Niş Havuzu (Viral potansiyeli yüksek) ----------
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

# ---------- 1. Viral Senaryo Üretimi (Gelişmiş) ----------
def generate_script(niche: str) -> str:
    logger.info(f"✍️ Viral senaryo üretiliyor: '{niche}'")
    
    prompt = f"""
Sen viral YouTube Shorts metinleri yazan bir uzmansın.
Konu: {niche}

Aşağıdaki kurallara uygun, 30-40 saniyelik bir TÜRKÇE metin yaz:
1. İlk cümle şok edici bir soru veya çarpıcı bir gerçekle başlamalı (pattern interrupt).
2. Hemen ardından merak uyandıran bir boşluk bırak (curiosity gap).
3. Orta kısımda kısa, vurucu cümlelerle ilginç bilgiler ver.
4. Son cümle güçlü bir call-to-action içersin: "yorum yap", "beğen", "abone ol" gibi.
5. Emoji, sahne yönü, efekt YOK. Sadece konuşulacak metin.
6. Cümleler kısa ve net olsun. Her cümle bir satır.
Yalnızca metni döndür.
"""
    
    # Yeni g4f istemcisi
    from g4f.client import Client
    client = Client()

    for attempt in range(3):  # 3 deneme yap
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                timeout=60
            )
            script = response.choices[0].message.content.strip().strip('"').strip("'")
            if len(script) < 30:
                logger.warning("Çok kısa yanıt, tekrar deneniyor...")
                time.sleep(2)
                continue
            logger.info("✅ Senaryo hazır.")
            return script
        except Exception as e:
            logger.warning(f"Deneme {attempt+1} başarısız: {e}")
            time.sleep(3)
    
    raise RuntimeError("Senaryo üretilemedi.")

# ---------- 2. Hızlı Seslendirme (Türkçe, tempolu) ----------
async def create_voiceover(script: str) -> Tuple[str, List[Tuple[float, float, str]]]:
    logger.info("🔊 Seslendirme oluşturuluyor...")
    try:
        # Önce edge-tts dene
        communicate = edge_tts.Communicate(script, DEFAULT_VOICE, rate=RATE, pitch=PITCH)
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
        if word_timestamps:
            return VOICEOVER_FILE, word_timestamps
        else:
            logger.warning("⚠️ edge-tts kelime zamanlaması vermedi, gTTS deneniyor...")
    except Exception as e:
        logger.warning(f"edge-tts başarısız: {e}. gTTS deneniyor...")

    # Yedek: gTTS (Google Text-to-Speech) – ücretsiz
    try:
        from gtts import gTTS
        tts = gTTS(script, lang='tr', slow=False)
        tts.save(VOICEOVER_FILE)
        logger.info("✅ Seslendirme gTTS ile oluşturuldu.")

        # Kelime zamanlaması yok → her kelimeye eşit süre ver
        words = script.split()
        if not words:
            return VOICEOVER_FILE, []
        # Seslendirme süresini tahmin et (karakter başına ~0.07 sn)
        estimated_duration = len(script) * 0.07
        dur_per_word = estimated_duration / len(words) if words else 0.3
        word_ts = []
        current_time = 0.2
        for word in words:
            word_ts.append((current_time, dur_per_word, word))
            current_time += dur_per_word
        return VOICEOVER_FILE, word_ts
    except ImportError:
        logger.error("gTTS yüklü değil. pip install gtts")
        raise
    except Exception as e:
        logger.error(f"gTTS başarısız: {e}")
        raise
# ---------- 3. Arka Plan Videosu (Dramatik, koyu tonlu) ----------
def extract_keywords(script: str, count=5) -> List[str]:
    stop_words = {"için","gibi","kadar","ama","fakat","ancak","değil","evet","hayır","çok","daha","bir","iki","üç","dört","beş","the","and","for","with","that","this","from","are","was","were","been","being","have","has","had"}
    words = re.findall(r'\b\w{4,}\b', script.lower())
    filtered = [w for w in words if w not in stop_words]
    filtered.sort(key=len, reverse=True)
    return filtered[:count]

def search_pexels(keywords: List[str]) -> Optional[str]:
    headers = {"Authorization": PEXELS_API_KEY}
    # koyu/soyut arka plan şansını artırmak için soyut kelimelere öncelik ver
    for i in range(min(3, len(keywords)), 0, -1):
        query = " ".join(keywords[:i])
        logger.info(f"🔍 Pexels sorgu: '{query}'")
        try:
            resp = requests.get("https://api.pexels.com/videos/search",
                               headers=headers,
                               params={"query": query, "per_page": 4, "orientation": "portrait", "size": "large"},
                               timeout=15)
            resp.raise_for_status()
            videos = resp.json().get("videos", [])
            if videos:
                for vid in videos:
                    for vf in vid["video_files"]:
                        if vf["width"] >= 1080 and vf["height"] >= 1920:
                            return vf["link"]
                best = max(videos[0]["video_files"], key=lambda x: x["width"]*x["height"])
                return best["link"]
        except Exception as e:
            logger.warning(f"Hata: {e}")
            time.sleep(1)
    return None

def fetch_background_video(script: str) -> str:
    keywords = extract_keywords(script)
    # dramatik ton için ekleme yap
    if not keywords:
        keywords = ["dark", "mysterious", "abstract"]
    else:
        keywords = ["dark atmosphere"] + keywords
    url = search_pexels(keywords)
    if not url:
        url = search_pexels(["dark", "gradient", "abstract"])
    if not url:
        raise RuntimeError("Pexels'te uygun video bulunamadı.")
    logger.info(f"⏬ İndiriliyor...")
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        with open(BACKGROUND_FILE, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
    return BACKGROUND_FILE

# ---------- 4. Font İndirme ----------
def ensure_font() -> str:
    if FONT_PATH.exists():
        return str(FONT_PATH.resolve())
    logger.info("🔤 Montserrat Bold indiriliyor...")
    try:
        FONT_DIR.mkdir(exist_ok=True)
        with requests.get(FONT_URL, timeout=15) as r:
            r.raise_for_status()
            with open(FONT_PATH, "wb") as f:
                f.write(r.content)
        return str(FONT_PATH.resolve())
    except Exception:
        return "Arial-Bold"

# ---------- 5. Dinamik, Tempolu Altyazı Chunking ----------
def chunk_timestamps(word_ts):
    if not word_ts: return []
    chunks = []
    cur_words, chunk_start, acc_dur = [], word_ts[0][0], 0.0
    for start, dur, word in word_ts:
        if (len(cur_words) >= MAX_CAPTION_WORDS or (cur_words and acc_dur+dur > MAX_CAPTION_DURATION)):
            chunks.append((chunk_start, acc_dur, " ".join(cur_words)))
            cur_words, chunk_start, acc_dur = [word], start, dur
        else:
            cur_words.append(word)
            acc_dur += dur
    if cur_words:
        chunks.append((chunk_start, acc_dur, " ".join(cur_words)))
    logger.info(f"📝 {len(chunks)} altyazı grubu.")
    return chunks

def generate_captions(chunked_ts):
    if not chunked_ts: return []
    font = ensure_font()
    clips = []
    for start, dur, text in chunked_ts:
        dur += 0.08  # hafif taşma
        txt_clip = (TextClip(text,
                             fontsize=FONT_SIZE,
                             color="white",
                             font=font,
                             stroke_color="black",
                             stroke_width=STROKE_WIDTH,
                             method="caption" if len(text)>12 else "label",
                             size=(VIDEO_SIZE[0]-80, None))
                    .set_start(start)
                    .set_duration(dur)
                    .set_position(("center", "center")))
        clips.append(txt_clip)
    logger.info(f"✅ {len(clips)} altyazı klibi.")
    return clips

# ---------- 6. Müzik Miksajı ----------
def mix_background_music(audio_clip, music_path="bg_music.mp3"):
    if not os.path.exists(music_path): return None
    try:
        bg = AudioFileClip(music_path).fx(volumex, 0.06)  # %6 ses
        bg = audio_loop(bg, duration=audio_clip.duration)
        return CompositeAudioClip([audio_clip, bg])
    except Exception:
        return None

# ---------- 7. Video Montajı ----------
def assemble_video(bg_path, audio_path, chunked_ts, music_path=None):
    logger.info("🎬 Montaj başlıyor...")
    bg_clip = VideoFileClip(bg_path)
    audio_clip = AudioFileClip(audio_path)
    target_dur = audio_clip.duration

    w, h = bg_clip.size
    if w/h < VIDEO_SIZE[0]/VIDEO_SIZE[1]:
        bg_clip = bg_clip.resize(width=VIDEO_SIZE[0])
        bg_clip = crop(bg_clip, y1=(bg_clip.h - VIDEO_SIZE[1])//2, y2=(bg_clip.h + VIDEO_SIZE[1])//2)
    else:
        bg_clip = bg_clip.resize(height=VIDEO_SIZE[1])
        bg_clip = crop(bg_clip, x1=(bg_clip.w - VIDEO_SIZE[0])//2, x2=(bg_clip.w + VIDEO_SIZE[0])//2)
    bg_clip = bg_clip.resize(VIDEO_SIZE)

    if bg_clip.duration < target_dur:
        bg_clip = bg_clip.loop(duration=target_dur)
    else:
        bg_clip = bg_clip.subclip(0, target_dur)

    final_audio = audio_clip
    if music_path:
        mixed = mix_background_music(audio_clip, music_path)
        if mixed: final_audio = mixed
    bg_clip = bg_clip.set_audio(final_audio)

    captions = generate_captions(chunked_ts)
    final = CompositeVideoClip([bg_clip] + captions, size=VIDEO_SIZE)
    final.write_videofile(OUTPUT_VIDEO, codec="libx264", audio_codec="aac",
                         fps=30, preset="medium", threads=4,
                         verbose=False, logger=None)
    return OUTPUT_VIDEO

# ---------- 8. YouTube Yükleme (Refresh Token ile) ----------
def get_youtube_service():
    with open(CLIENT_SECRETS_FILE, "r") as f:
        config = json.load(f)["installed"]
    creds = Credentials(
        token=None,
        refresh_token=YOUTUBE_REFRESH_TOKEN,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=config["client_id"],
        client_secret=config["client_secret"],
        scopes=YOUTUBE_SCOPES
    )
    creds.refresh(Request())
    return build("youtube", "v3", credentials=creds)

def upload_to_youtube(video_path, title, description, tags=None):
    if not os.path.exists(video_path):
        raise FileNotFoundError(video_path)
    if "#shorts" not in title.lower():
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
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False
        }
    }
    logger.info(f"📤 Yükleniyor: {title}")
    media = MediaFileUpload(video_path, mimetype="video/mp4",
                            resumable=True, chunksize=5*1024*1024)
    request = youtube.videos().insert(part="snippet,status", body=body,
                                      media_body=media)
    resp = None
    while resp is None:
        status, resp = request.next_chunk()
        if status:
            logger.info(f"   %{int(status.progress()*100)}")
    video_id = resp["id"]
    url = f"https://youtu.be/{video_id}"
    logger.info(f"✅ Yayında: {url}")
    return url

# ---------- 9. Ana İş Akışı ----------
async def run_pipeline(niche: str):
    try:
        logger.info(f"🎲 Seçilen niş: {niche}")
        script = generate_script(niche)
        logger.info("📜 Senaryo:\n" + script)
        audio, word_ts = await create_voiceover(script)
        chunked = chunk_timestamps(word_ts)
        bg = fetch_background_video(script)
        music = "bg_music.mp3" if os.path.exists("bg_music.mp3") else None
        final_path = assemble_video(bg, audio, chunked, music)
        first_sentence = re.split(r'[.!?]', script)[0].strip()[:50]
        title = f"{niche}: {first_sentence}"
        upload_to_youtube(final_path, title,
                         description=f"🔥 {niche} hakkında çarpıcı gerçekler!\nHer gün yeni shorts için abone ol! 🛎️")
        logger.info("🏁 Tamamlandı.")
    except Exception as e:
        logger.error(f"❌ Hata: {e}\n{traceback.format_exc()}")
        sys.exit(1)

if __name__ == "__main__":
    niche = random.choice(NICHE_POOL)
    asyncio.run(run_pipeline(niche))
