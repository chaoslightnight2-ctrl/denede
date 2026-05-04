#!/usr/bin/env python3
"""English horror/mystery Shorts runner.

Discovery-focused optimizations:
- Hard first-second hook: event + mystery + time/evidence clue
- 25-38 second target voice/video duration
- Contextual open-ended question ending
- Topic + script keyword matched background search
- Non-spam tag mix: broad Shorts tags + niche tags + video-specific tags
- Writes per-video metadata to runtime-status for later analysis
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

# Force every generated element to English.
main.DEFAULT_VOICE = "en-US-JennyNeural"
main.RATE = "+12%"
main.PITCH = "-4Hz"

HORROR_NICHES = [
    "Conspiracy Theories and Hidden Plans",
    "Disturbing Facts",
    "Dark Historical Events",
    "Unsolved Cases",
    "Mysterious Missing Person Stories",
    "Chilling Mystery Files",
    "Cursed Places and Horror Stories",
    "Unexplained Paranormal Events",
    "Dark Web and Technology Secrets",
    "The World's Most Disturbing Mysteries",
]

HORROR_PEXELS = {
    "Conspiracy Theories and Hidden Plans": ["secret files", "dark documents", "surveillance camera", "classified papers", "mysterious meeting"],
    "Disturbing Facts": ["dark forest", "abandoned hallway", "scary shadow", "eerie night", "creepy room"],
    "Dark Historical Events": ["old abandoned building", "war ruins", "old newspaper", "historic ruins night", "dark archive"],
    "Unsolved Cases": ["detective board", "police investigation", "evidence board", "mystery documents", "cold case"],
    "Mysterious Missing Person Stories": ["missing person", "empty road night", "dark forest path", "foggy road", "abandoned car"],
    "Chilling Mystery Files": ["detective investigation", "dark alley", "police lights night", "evidence photos", "mystery file"],
    "Cursed Places and Horror Stories": ["haunted house", "abandoned mansion", "dark corridor", "old cemetery fog", "creepy basement"],
    "Unexplained Paranormal Events": ["paranormal activity", "ghostly shadow", "dark room", "mysterious light", "foggy cemetery"],
    "Dark Web and Technology Secrets": ["dark web", "hacker code", "cyber security dark", "server room dark", "phone screen night"],
    "The World's Most Disturbing Mysteries": ["mysterious place", "foggy forest", "abandoned place", "dark tunnel", "eerie landscape"],
}

OPEN_QUESTIONS = [
    "So why did the camera fail at that exact moment?",
    "Who left that note behind?",
    "Why was this file hidden for so many years?",
    "Do you think this was really just a coincidence?",
    "What do you think they were trying to hide?",
    "If the answer still exists, why has no one found it?",
]

THUMBNAIL_STYLE_TITLES = {
    "Conspiracy Theories and Hidden Plans": "THEY HID THIS",
    "Disturbing Facts": "THIS FACT IS DISTURBING",
    "Dark Historical Events": "HISTORY'S DARKEST MOMENT",
    "Unsolved Cases": "THIS CASE IS STILL OPEN",
    "Mysterious Missing Person Stories": "THEY VANISHED",
    "Chilling Mystery Files": "THE FILE IS STILL OPEN",
    "Cursed Places and Horror Stories": "PEOPLE WARNED US",
    "Unexplained Paranormal Events": "THE CAMERA CAUGHT THIS",
    "Dark Web and Technology Secrets": "THE DARK SIDE OF THE WEB",
    "The World's Most Disturbing Mysteries": "NO ONE CAN EXPLAIN THIS",
}

BASE_VIRAL_TAGS = ["shorts", "youtubeshorts", "viralshorts", "fyp", "horror"]

NICHE_TAGS = {
    "Conspiracy Theories and Hidden Plans": ["conspiracy", "conspiracytheory", "hiddenfiles", "classified", "secrettruth"],
    "Disturbing Facts": ["disturbingfacts", "darkfacts", "creepyfacts", "scaryfacts", "mystery"],
    "Dark Historical Events": ["darkhistory", "historymystery", "historicalevents", "creepyhistory", "forgottenhistory"],
    "Unsolved Cases": ["unsolvedcase", "truecrime", "coldcase", "mysterycase", "detective"],
    "Mysterious Missing Person Stories": ["missingperson", "vanished", "missingcase", "mysteriousdisappearance", "lastseen"],
    "Chilling Mystery Files": ["mysteryfile", "chilling", "unexplained", "casefile", "darkmystery"],
    "Cursed Places and Horror Stories": ["cursedplaces", "haunted", "hauntedhouse", "creepystories", "abandonedplaces"],
    "Unexplained Paranormal Events": ["paranormal", "ghost", "unexplained", "supernatural", "scaryvideos"],
    "Dark Web and Technology Secrets": ["darkweb", "internetmystery", "techsecrets", "cyber", "hacker"],
    "The World's Most Disturbing Mysteries": ["worldmysteries", "disturbingmystery", "unexplainedmysteries", "mysteries", "darkmystery"],
}

KEYWORD_TAG_MAP = {
    "missing": "missingperson", "vanished": "vanished", "file": "casefile", "police": "police",
    "camera": "caughtoncamera", "internet": "darkweb", "forest": "darkforest", "house": "hauntedhouse",
    "ghost": "ghost", "shadow": "shadowfigure", "secret": "hiddensecret", "hidden": "classified",
    "case": "unsolvedcase", "night": "nightmystery", "abandoned": "abandonedplaces", "paranormal": "paranormal",
    "conspiracy": "conspiracytheory", "note": "mysteriousnote", "footage": "securityfootage", "cctv": "cctv",
}

STOP_WORDS = {"because", "after", "before", "their", "there", "about", "would", "could", "think", "really", "still", "again", "thing", "things", "something"}

SOFT_RISK_REPLACEMENTS = {
    "mandatory vaccines": "a mandatory public program",
    "vaccines": "public records",
    "vaccine": "public record",
    "microchips": "tracking devices",
    "microchip": "tracking device",
    "deceased": "inactive",
    "killed": "erased",
    "murdered": "erased",
}


def _clean(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(script|text|answer)\s*:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip().strip('"').strip("'")


def soften_platform_risk(script: str) -> str:
    """Keep the horror tone, but avoid hard medical/real-world harm claims."""
    script = _clean(script)
    for risky, safer in SOFT_RISK_REPLACEMENTS.items():
        script = re.sub(rf"\b{re.escape(risky)}\b", safer, script, flags=re.IGNORECASE)
    return script


def _tagify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", text.lower())[:30]


def extract_video_keywords(script: str, limit: int = 5):
    words = re.findall(r"\b[a-zA-Z]{5,}\b", script.lower())
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
    if "camera" in lowered or "footage" in lowered or "cctv" in lowered:
        return "So why did the camera fail at that exact moment?"
    if "note" in lowered or "letter" in lowered:
        return "Who left that note behind?"
    if "file" in lowered or "case" in lowered or "record" in lowered:
        return "Why was this file hidden for so many years?"
    if "missing" in lowered or "vanished" in lowered or "disappeared" in lowered:
        return "Do you think they really disappeared by choice?"
    if "internet" in lowered or "dark web" in lowered:
        return "Why was this trace erased from the internet?"
    if "Conspiracy" in niche:
        return "What do you think they were trying to hide?"
    return random.choice(OPEN_QUESTIONS)


def ensure_question_end(script: str, niche: str) -> str:
    script = soften_platform_risk(script)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if sentences and sentences[-1].endswith("?") and len(sentences[-1]) > 20:
        return script
    if sentences and any(x in sentences[-1].lower() for x in ["follow", "subscribe", "comment", "like"]):
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
    queries.extend(["found footage horror", "security camera footage", "dark mystery cinematic", "abandoned hallway dark", "foggy abandoned place"])
    unique = []
    for query in queries:
        if query and query not in unique:
            unique.append(query)
    return unique


def write_runtime_meta(meta: dict) -> None:
    META_FILE.parent.mkdir(parents=True, exist_ok=True)
    META_FILE.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def horror_script(niche: str) -> str:
    main.logger.info(f"✍️ Generating realistic scary English horror/mystery script: {niche}")
    prompt = f"""
Write an ENGLISH YouTube Shorts voiceover script in a realistic horror mystery style.
Topic: {niche}

Creative direction:
- Make it feel like a real recovered case file, security camera report, police note, abandoned place recording, missing person timeline, or found-footage story.
- The atmosphere should be darker, scarier, more tense, and cinematic, but still believable.
- Prefer concrete details: exact time, room number, file number, camera angle, last message, old photo, locked door, footsteps, static, missing frame, hidden folder, erased account.
- The mystery can feel like a rumor or leaked file, but do not present harmful medical claims as fact.

Rules:
- Target 25-38 seconds when spoken.
- The first sentence must be a hard hook with event + mystery + time/evidence clue.
- Do not start slowly. Create fear and curiosity in the first second.
- Example rhythm: "At 2:13 AM, the hallway camera recorded someone standing behind him, but he was alone."
- Build tension around a dark secret, missing person, unexplained event, hidden file, conspiracy, paranormal clue, or recovered footage.
- Avoid graphic violence, gore, blood, and direct real-person accusations.
- Avoid vaccine/medical conspiracy claims. If there is a conspiracy, make it about files, cameras, erased records, classified rooms, or missing footage.
- End with a specific open-ended question for the viewer.
- No title, no emojis, no bullet points, no stage directions.
Return only the voiceover text.
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
            main.logger.warning(f"Script attempt {attempt + 1} failed: {exc}")
            time.sleep(3)
    raise RuntimeError("Could not generate realistic scary horror/mystery script.")


def horror_title(niche: str, script: str) -> str:
    hook = re.split(r"[.!?]", script)[0].strip()
    hook = re.sub(r"\s+", " ", hook)
    if len(hook) < 18:
        hook = THUMBNAIL_STYLE_TITLES.get(niche, niche)
    return f"{hook[:82]} #shorts"


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
            main.logger.info(f"⏱️ Duration in target range: {duration:.2f}s")
            return last_candidate
        main.logger.warning(f"⏱️ Duration outside target: {duration:.2f}s, retrying ({attempt + 1}/3)")
    main.logger.warning(f"⏱️ Target duration not met; using last candidate: {last_candidate[3]:.2f}s")
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
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False},
    }
    main.logger.info(f"🏷️ Tags: {', '.join(tags)}")
    main.logger.info(f"📤 Uploading: {title}")
    media = MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            main.logger.info(f"   %{int(status.progress() * 100)}")
    video_id = response["id"]
    url = f"https://youtu.be/{video_id}"
    main.logger.info(f"✅ Published: {url}")
    thumbnail_path = make_thumbnail(video_path, thumbnail_text, main.ensure_font(), main.logger)
    upload_thumbnail(youtube, video_id, thumbnail_path, main.logger)
    return url


async def run() -> None:
    main.NICHE_POOL = HORROR_NICHES
    main.NICHE_PEXELS_QUERIES = HORROR_PEXELS
    main.generate_script = horror_script
    niche = random.choice(HORROR_NICHES)
    script, audio, word_ts, duration = await generate_timed_script(niche)
    main.logger.info("📜 Script:\n" + script)
    chunked = main.chunk_timestamps(word_ts)
    background_queries = build_background_queries(niche, script)
    main.NICHE_PEXELS_QUERIES[niche] = background_queries
    bg = main.fetch_background_video(script, niche)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)
    title = horror_title(niche, script)
    thumbnail_text = THUMBNAIL_STYLE_TITLES.get(niche, "NO ONE CAN EXPLAIN THIS")
    tags = build_video_tags(niche, script)
    meta = {
        "language": "en",
        "style": "realistic_scary_case_file_found_footage",
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
        "Dark mysteries, recovered footage, hidden files, unsolved cases, and disturbing stories. The final question is yours to answer.\n\n#shorts #horror #mystery #conspiracy #truecrime",
        thumbnail_text,
        tags,
    )
    meta["video_url"] = video_url
    write_runtime_meta(meta)
    main.logger.info("🏁 English realistic horror/mystery Short completed.")


if __name__ == "__main__":
    asyncio.run(run())
