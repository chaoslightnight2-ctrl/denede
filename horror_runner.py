#!/usr/bin/env python3
"""Korku/gizem odaklı Shorts runner.

Keşfet optimizasyonları:
- İlk 1 saniyede sert hook: olay + gizem + zaman/kanıt hissi
- 25-38 saniye hedef ses/video süresi
- Videoya özel ucu açık soru ile bitiş
- Konu + senaryo anahtar kelimelerine göre arka plan sorgusu
- Spam olmayan 5 genel + 5 niş + 5 video özel etiket yapısı
- Her videonun üretim metadatasını runtime-status içine yazar
"""

import asyncio
import json
import random
import re
import time
from pathlib import Path

import main
from googleapiclient.http import MediaFileUpload
from thumbnail_helper import make_thumbnail, upload_thumbnail

MIN_TARGET_DURATION = 25.0
MAX_TARGET_DURATION = 38.0
META_FILE = Path("runtime-status/video-meta.json")

HORROR_NICHES = [
    "Komplo Teorileri ve Gizli Planlar",
    "Korkunç Gerçekler",
    "Korkunç Tarihi Olaylar",
    "Çözülmemiş Davalar",
    "Kaybolan İnsanların Gizemli Hikayeleri",
    "Tüyler Ürperten Gizem Dosyaları",
    "Lanetli Yerler ve Korku Hikayeleri",
    "Açıklanamayan Paranormal Olaylar",
    "Karanlık İnternet ve Teknoloji Sırları",
    "Dünyanın En Rahatsız Edici Gizemleri",
]

HORROR_PEXELS = {
    "Komplo Teorileri ve Gizli Planlar": ["secret files", "dark documents", "surveillance camera", "classified papers", "mysterious meeting"],
    "Korkunç Gerçekler": ["dark forest", "abandoned hallway", "scary shadow", "eerie night", "creepy room"],
    "Korkunç Tarihi Olaylar": ["old abandoned building", "war ruins", "old newspaper", "historic ruins night", "dark archive"],
    "Çözülmemiş Davalar": ["detective board", "police investigation", "evidence board", "mystery documents", "cold case"],
    "Kaybolan İnsanların Gizemli Hikayeleri": ["missing person", "empty road night", "dark forest path", "foggy road", "abandoned car"],
    "Tüyler Ürperten Gizem Dosyaları": ["detective investigation", "dark alley", "police lights night", "evidence photos", "mystery file"],
    "Lanetli Yerler ve Korku Hikayeleri": ["haunted house", "abandoned mansion", "dark corridor", "old cemetery fog", "creepy basement"],
    "Açıklanamayan Paranormal Olaylar": ["paranormal activity", "ghostly shadow", "dark room", "mysterious light", "foggy cemetery"],
    "Karanlık İnternet ve Teknoloji Sırları": ["dark web", "hacker code", "cyber security dark", "server room dark", "phone screen night"],
    "Dünyanın En Rahatsız Edici Gizemleri": ["mysterious place", "foggy forest", "abandoned place", "dark tunnel", "eerie landscape"],
}

OPEN_QUESTIONS = [
    "Peki kamera neden tam o anda bozuldu?",
    "Bu notu kim bıraktı?",
    "Dosya neden yıllarca gizli tutuldu?",
    "Sence bu sadece tesadüf müydü?",
    "Sence burada saklanan şey neydi?",
    "Bu olayın gerçek cevabı hâlâ bulunmadıysa, neden?",
]

THUMBNAIL_STYLE_TITLES = {
    "Komplo Teorileri ve Gizli Planlar": "BUNU SAKLADILAR",
    "Korkunç Gerçekler": "BU GERÇEK RAHATSIZ EDİCİ",
    "Korkunç Tarihi Olaylar": "TARİHİN KARANLIK ANI",
    "Çözülmemiş Davalar": "BU DAVA HÂLÂ ÇÖZÜLMEDİ",
    "Kaybolan İnsanların Gizemli Hikayeleri": "BİR ANDA YOK OLDU",
    "Tüyler Ürperten Gizem Dosyaları": "DOSYA HÂLÂ AÇIK",
    "Lanetli Yerler ve Korku Hikayeleri": "BURAYA GİRENLER ANLATTI",
    "Açıklanamayan Paranormal Olaylar": "KAMERA BUNU YAKALADI",
    "Karanlık İnternet ve Teknoloji Sırları": "İNTERNETİN KARANLIK TARAFI",
    "Dünyanın En Rahatsız Edici Gizemleri": "KİMSE AÇIKLAYAMIYOR",
}

BASE_VIRAL_TAGS = ["shorts", "youtubeshorts", "viralshorts", "keşfet", "korku"]

NICHE_TAGS = {
    "Komplo Teorileri ve Gizli Planlar": ["komplo", "komploteorileri", "gizliplanlar", "gizlidosyalar", "saklanangerçekler"],
    "Korkunç Gerçekler": ["korkunçgerçekler", "rahatsızedicigerçekler", "karanlıkgerçekler", "bilinmeyengerçekler", "gizem"],
    "Korkunç Tarihi Olaylar": ["karanlıktarih", "tarihiolaylar", "korkunçtarih", "tarihingizemleri", "eskiolaylar"],
    "Çözülmemiş Davalar": ["çözülmemişdava", "truecrime", "suçdosyası", "gizemlidava", "soğukdosya"],
    "Kaybolan İnsanların Gizemli Hikayeleri": ["kayıpolayları", "kayıpinsanlar", "gizemlikayıp", "missingperson", "soniz"],
    "Tüyler Ürperten Gizem Dosyaları": ["gizemdosyası", "tüylerürperten", "açıklanamayan", "olaydosyası", "karanlıkdosya"],
    "Lanetli Yerler ve Korku Hikayeleri": ["lanetliyerler", "perilihikayeler", "haunted", "korkumekanları", "terkedilmişyerler"],
    "Açıklanamayan Paranormal Olaylar": ["paranormal", "hayalet", "açıklanamayanolaylar", "doğaüstü", "korkuvideoları"],
    "Karanlık İnternet ve Teknoloji Sırları": ["darkweb", "karanlıkinternet", "teknolojisırları", "siber", "hacker"],
    "Dünyanın En Rahatsız Edici Gizemleri": ["dünyagizemleri", "rahatsızedicigizemler", "açıklanamayangizemler", "gizemler", "karanlıkgizem"],
}

KEYWORD_TAG_MAP = {
    "kayıp": "kayıpolayları",
    "dosya": "gizlidosya",
    "polis": "polis",
    "kamera": "kamerakaydı",
    "internet": "darkweb",
    "orman": "karanlıkorman",
    "ev": "lanetliev",
    "hayalet": "hayalet",
    "gölge": "gölge",
    "sır": "saklanansır",
    "gizli": "gizlidosyalar",
    "dava": "çözülmemişdava",
    "gece": "gece",
    "terk": "terkedilmişyerler",
    "paranormal": "paranormal",
    "komplo": "komploteorileri",
    "not": "gizeminotu",
}

STOP_WORDS = {"çünkü", "sonra", "bunun", "şimdi", "sence", "gerçek", "olayın", "olan", "bile", "kadar", "için", "gibi"}


def _clean(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(metin|senaryo|cevap)\s*:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip().strip('"').strip("'")


def _tagify(text: str) -> str:
    text = text.lower()
    text = text.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    return re.sub(r"[^a-z0-9]+", "", text)[:30]


def extract_video_keywords(script: str, limit: int = 5):
    words = re.findall(r"\b\w{5,}\b", script.lower())
    result = []
    for word in words:
        if word in STOP_WORDS:
            continue
        tag = _tagify(word)
        if tag and tag not in result:
            result.append(tag)
        if len(result) >= limit:
            break
    return result


def contextual_question(niche: str, script: str) -> str:
    lowered = script.lower()
    if "kamera" in lowered:
        return "Peki kamera neden tam o anda bozuldu?"
    if "not" in lowered or "mektup" in lowered:
        return "Bu notu kim bıraktı?"
    if "dosya" in lowered or "dava" in lowered:
        return "Dosya neden yıllarca gizli tutuldu?"
    if "kayıp" in lowered or "kaybol" in lowered:
        return "Sence o kişi gerçekten kendi isteğiyle mi kayboldu?"
    if "internet" in lowered or "dark" in lowered:
        return "Sence bu iz neden internetten silindi?"
    if "Komplo" in niche:
        return "Sence burada saklanan şey neydi?"
    return random.choice(OPEN_QUESTIONS)


def ensure_question_end(script: str, niche: str) -> str:
    script = _clean(script)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if sentences and sentences[-1].endswith("?") and len(sentences[-1]) > 20:
        return script
    if sentences and any(x in sentences[-1].lower() for x in ["takip", "abone", "yorum", "kaçırma"]):
        sentences = sentences[:-1]
    return " ".join(sentences + [contextual_question(niche, script)])


def build_video_tags(niche: str, script: str):
    tags = []
    tags.extend(BASE_VIRAL_TAGS[:5])
    tags.extend(NICHE_TAGS.get(niche, [])[:5])
    lowered = script.lower()
    video_tags = []
    for keyword, tag in KEYWORD_TAG_MAP.items():
        if keyword in lowered and tag not in video_tags:
            video_tags.append(tag)
        if len(video_tags) >= 5:
            break
    for tag in extract_video_keywords(script, 5):
        if len(video_tags) >= 5:
            break
        if tag not in video_tags:
            video_tags.append(tag)
    tags.extend(video_tags[:5])
    unique = []
    for tag in tags:
        tag = str(tag).strip().lstrip("#")
        if tag and tag not in unique:
            unique.append(tag)
    return unique[:15]


def build_background_queries(niche: str, script: str):
    queries = list(HORROR_PEXELS.get(niche, []))
    keywords = extract_video_keywords(script, 3)
    if len(keywords) >= 2:
        queries.insert(0, f"{keywords[0]} {keywords[1]} mystery")
    if keywords:
        queries.insert(1, f"{keywords[0]} dark mystery")
    queries.extend(["horror atmosphere", "dark mystery", "scary cinematic", "foggy abandoned place"])
    unique = []
    for query in queries:
        if query and query not in unique:
            unique.append(query)
    return unique


def write_runtime_meta(meta: dict) -> None:
    META_FILE.parent.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def horror_script(niche: str) -> str:
    main.logger.info(f"✍️ Hook'lu korku/gizem senaryosu üretiliyor: {niche}")
    prompt = f"""
Türkçe YouTube Shorts için korku, gizem ve komplo temalı kısa metin yaz.
Konu: {niche}
Kurallar:
- 25-38 saniyelik konuşma metni olsun.
- İlk cümle çok sert hook olsun: olay + gizem + zaman/kanıt hissi içersin.
- Zayıf başlangıç yapma. İlk 1 saniyede merak uyandır.
- Örnek ritim: "Bu adam kameraya baktıktan 7 dakika sonra kayboldu."
- Korku, gizem, kayıp olay, karanlık sır veya açıklanamayan olay atmosferi taşısın.
- Grafik şiddet ve kanlı detay yazma.
- Son cümle izleyiciye olayla ilgili ucu açık, spesifik bir soru sorsun.
- Başlık, emoji, madde işareti ve sahne yönü yazma.
Sadece konuşulacak metni döndür.
""".strip()
    from g4f.client import Client
    client = Client()
    for attempt in range(3):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
            )
            script = ensure_question_end(response.choices[0].message.content, niche)
            if len(script) >= 30:
                return script
        except Exception as exc:
            main.logger.warning(f"Senaryo deneme {attempt + 1} başarısız: {exc}")
            time.sleep(3)
    raise RuntimeError("Hook'lu korku/gizem senaryosu üretilemedi.")


def horror_title(niche: str, script: str) -> str:
    hook = re.split(r"[.!?]", script)[0].strip()
    hook = re.sub(r"\s+", " ", hook)
    if len(hook) < 18:
        hook = THUMBNAIL_STYLE_TITLES.get(niche, niche)
    return f"{hook[:82]} #shorts"


def create_script_and_voice(niche: str):
    last = None
    for attempt in range(3):
        script = horror_script(niche)
        audio, word_ts = asyncio.get_event_loop().run_until_complete(main.create_voiceover(script)) if False else None
    return last


async def generate_timed_script(niche: str):
    last_candidate = None
    for attempt in range(3):
        script = horror_script(niche)
        audio, word_ts = await main.create_voiceover(script)
        clip = main.AudioFileClip(audio)
        duration = float(clip.duration)
        clip.close()
        last_candidate = (script, audio, word_ts, duration)
        if MIN_TARGET_DURATION <= duration <= MAX_TARGET_DURATION:
            main.logger.info(f"⏱️ Süre hedef aralıkta: {duration:.2f}s")
            return last_candidate
        main.logger.warning(f"⏱️ Süre hedef dışı: {duration:.2f}s, yeniden deneniyor ({attempt + 1}/3)")
    main.logger.warning(f"⏱️ Hedef süre tutmadı; son aday kullanılacak: {last_candidate[3]:.2f}s")
    return last_candidate


def upload_video_with_thumbnail(video_path: str, title: str, description: str, thumbnail_text: str, tags) -> str:
    youtube = main.get_youtube_service()
    body = {
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": tags,
            "categoryId": main.YOUTUBE_CATEGORY_ID,
        },
        "status": {
            "privacyStatus": "public",
            "selfDeclaredMadeForKids": False,
        },
    }
    main.logger.info(f"🏷️ Etiketler: {', '.join(tags)}")
    main.logger.info(f"📤 Yükleniyor: {title}")
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            main.logger.info(f"   %{int(status.progress() * 100)}")
    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"
    main.logger.info(f"✅ Yayında: {url}")

    thumbnail_path = make_thumbnail(video_path, thumbnail_text, main.ensure_font(), main.logger)
    upload_thumbnail(youtube, video_id, thumbnail_path, main.logger)
    return url


async def run() -> None:
    main.NICHE_POOL = HORROR_NICHES
    main.NICHE_PEXELS_QUERIES = HORROR_PEXELS
    main.generate_script = horror_script
    niche = random.choice(HORROR_NICHES)
    script, audio, word_ts, duration = await generate_timed_script(niche)
    main.logger.info("📜 Senaryo:\n" + script)
    chunked = main.chunk_timestamps(word_ts)
    background_queries = build_background_queries(niche, script)
    main.NICHE_PEXELS_QUERIES[niche] = background_queries
    bg = main.fetch_background_video(script, niche)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)
    title = horror_title(niche, script)
    thumbnail_text = THUMBNAIL_STYLE_TITLES.get(niche, "KİMSE AÇIKLAYAMIYOR")
    tags = build_video_tags(niche, script)
    meta = {
        "niche": niche,
        "title": title,
        "thumbnail_text": thumbnail_text,
        "duration_seconds": round(duration, 2),
        "tags": tags,
        "background_queries": background_queries,
        "script": script,
        "video_url": None,
    }
    write_runtime_meta(meta)
    video_url = upload_video_with_thumbnail(
        final_path,
        title,
        "Karanlık gerçekler, komplo teorileri, çözülmemiş olaylar ve tüyler ürperten gizemler. Video sonunda cevabı sana bırakıyorum.\n\n#shorts #korku #gizem #komplo",
        thumbnail_text,
        tags,
    )
    meta["video_url"] = video_url
    write_runtime_meta(meta)
    main.logger.info("🏁 Hook'lu korku/gizem videosu tamamlandı.")


if __name__ == "__main__":
    asyncio.run(run())
