#!/usr/bin/env python3
"""Korku/gizem odaklı Shorts runner.

main.py içindeki mevcut video üretim/yükleme motorunu kullanır;
sadece konu havuzunu, prompt davranışını ve başlık üretimini hook + açık soru
mantığına çevirir.
"""

import asyncio
import random
import re
import time

import main
from googleapiclient.http import MediaFileUpload
from thumbnail_helper import make_thumbnail, upload_thumbnail

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
    "Komplo Teorileri ve Gizli Planlar": ["secret files", "dark documents", "surveillance camera", "classified papers"],
    "Korkunç Gerçekler": ["dark forest", "abandoned hallway", "scary shadow", "eerie night"],
    "Korkunç Tarihi Olaylar": ["old abandoned building", "war ruins", "old newspaper", "historic ruins night"],
    "Çözülmemiş Davalar": ["detective board", "police investigation", "evidence board", "mystery documents"],
    "Kaybolan İnsanların Gizemli Hikayeleri": ["missing person", "empty road night", "dark forest path", "foggy road"],
    "Tüyler Ürperten Gizem Dosyaları": ["detective investigation", "dark alley", "police lights night", "evidence photos"],
    "Lanetli Yerler ve Korku Hikayeleri": ["haunted house", "abandoned mansion", "dark corridor", "old cemetery fog"],
    "Açıklanamayan Paranormal Olaylar": ["paranormal activity", "ghostly shadow", "dark room", "mysterious light"],
    "Karanlık İnternet ve Teknoloji Sırları": ["dark web", "hacker code", "cyber security dark", "server room dark"],
    "Dünyanın En Rahatsız Edici Gizemleri": ["mysterious place", "foggy forest", "abandoned place", "dark tunnel"],
}

OPEN_QUESTIONS = [
    "Sence bu sadece tesadüf müydü?",
    "Peki sen olsaydın bu dosyayı kapatır mıydın?",
    "Sence burada saklanan şey neydi?",
    "Bu olayın gerçek cevabı hâlâ bulunmadıysa, neden?",
    "Sence en korkunç ihtimal hangisi?",
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

BASE_VIRAL_TAGS = [
    "shorts",
    "youtubeshorts",
    "shortsvideo",
    "viralshorts",
    "keşfet",
    "keşfetteyiz",
    "trend",
    "viral",
    "korku",
    "gizem",
    "gerilim",
    "korkuhikayeleri",
    "gizemliolaylar",
    "türkçe",
]

NICHE_TAGS = {
    "Komplo Teorileri ve Gizli Planlar": ["komplo", "komploteorileri", "gizliplanlar", "gizlidosyalar", "saklanangerçekler", "illuminati", "derindevlet"],
    "Korkunç Gerçekler": ["korkunçgerçekler", "rahatsızedicigerçekler", "karanlıkgerçekler", "bilinmeyengerçekler", "ürkütücü"],
    "Korkunç Tarihi Olaylar": ["karanlıktarih", "tarihiolaylar", "korkunçtarih", "tarihingizemleri", "eskiolaylar"],
    "Çözülmemiş Davalar": ["çözülmemişdava", "truecrime", "suçdosyası", "gizemlidava", "dedektif", "soğukdosya"],
    "Kaybolan İnsanların Gizemli Hikayeleri": ["kayıpolayları", "kayıpinsanlar", "gizemlikayıp", "missingperson", "soniz"],
    "Tüyler Ürperten Gizem Dosyaları": ["gizemdosyası", "tüylerürperten", "açıklanamayan", "olaydosyası", "karanlıkdosya"],
    "Lanetli Yerler ve Korku Hikayeleri": ["lanetliyerler", "perilihikayeler", "haunted", "korkumekanları", "terkedilmişyerler"],
    "Açıklanamayan Paranormal Olaylar": ["paranormal", "hayalet", "açıklanamayanolaylar", "doğaüstü", "korkuvideoları"],
    "Karanlık İnternet ve Teknoloji Sırları": ["darkweb", "karanlıkinternet", "teknolojisırları", "siber", "hacker", "internetsırları"],
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
}


def _clean(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(metin|senaryo|cevap)\s*:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip().strip('"').strip("'")


def _ensure_question_end(script: str) -> str:
    script = _clean(script)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if sentences and sentences[-1].endswith("?"):
        return script
    if sentences and any(x in sentences[-1].lower() for x in ["takip", "abone", "yorum", "kaçırma"]):
        sentences = sentences[:-1]
    return " ".join(sentences + [random.choice(OPEN_QUESTIONS)])


def _tagify(text: str) -> str:
    text = text.lower()
    text = text.replace("ı", "i").replace("ğ", "g").replace("ü", "u").replace("ş", "s").replace("ö", "o").replace("ç", "c")
    text = re.sub(r"[^a-z0-9]+", "", text)
    return text[:30]


def build_video_tags(niche: str, script: str):
    tags = []
    tags.extend(BASE_VIRAL_TAGS)
    tags.extend(NICHE_TAGS.get(niche, []))
    lowered = script.lower()
    for keyword, tag in KEYWORD_TAG_MAP.items():
        if keyword in lowered:
            tags.append(tag)
    for word in re.findall(r"\b\w{5,}\b", lowered):
        if len(tags) >= 28:
            break
        if word not in {"çünkü", "sonra", "bunun", "şimdi", "sence", "gerçek", "olayın"}:
            tags.append(_tagify(word))
    unique = []
    for tag in tags:
        tag = str(tag).strip().lstrip("#")
        if tag and tag not in unique:
            unique.append(tag)
    return unique[:30]


def horror_script(niche: str) -> str:
    main.logger.info(f"✍️ Hook'lu korku/gizem senaryosu üretiliyor: {niche}")
    prompt = f"""
Türkçe YouTube Shorts için korku, gizem ve komplo temalı kısa metin yaz.
Konu: {niche}
Kurallar:
- 30-40 saniyelik konuşma metni olsun.
- İlk cümle güçlü bir hook olsun; ilk 3 saniyede izleyiciyi yakalasın.
- Yavaş giriş yapma. Doğrudan merak uyandır.
- Korku, gizem, kayıp olay, karanlık sır veya açıklanamayan olay atmosferi taşısın.
- Grafik şiddet ve kanlı detay yazma.
- Son cümle mutlaka izleyiciye ucu açık bir soru sorsun.
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
            script = _ensure_question_end(response.choices[0].message.content)
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
    script = main.generate_script(niche)
    main.logger.info("📜 Senaryo:\n" + script)
    audio, word_ts = await main.create_voiceover(script)
    chunked = main.chunk_timestamps(word_ts)
    bg = main.fetch_background_video(script, niche)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)
    title = horror_title(niche, script)
    thumbnail_text = THUMBNAIL_STYLE_TITLES.get(niche, "KİMSE AÇIKLAYAMIYOR")
    tags = build_video_tags(niche, script)
    upload_video_with_thumbnail(
        final_path,
        title,
        "Karanlık gerçekler, komplo teorileri, çözülmemiş olaylar ve tüyler ürperten gizemler. Video sonunda cevabı sana bırakıyorum.\n\n#shorts #korku #gizem #komplo",
        thumbnail_text,
        tags,
    )
    main.logger.info("🏁 Hook'lu korku/gizem videosu tamamlandı.")


if __name__ == "__main__":
    asyncio.run(run())
