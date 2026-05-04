#!/usr/bin/env python3
"""Optimized save-only Shorts runner.

This runner does NOT upload to YouTube. It is for reviewing generated videos
without hitting YouTube API/upload limits.

Focus:
- stronger story variety with concrete creative seeds
- no repeated prompt-template phrasing
- tighter centered caption sync
- mobile-compatible MP4 export
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import main
import horror_runner
from caption_style import apply_caption_style
from story_variety import archetype_prompt_block, choose_archetype
from thumbnail_helper import make_thumbnail
from visual_query_helper import build_visual_background_queries

OUTPUT_DIR = Path("generated-videos")
OUTPUT_VIDEO = OUTPUT_DIR / "latest_short.mp4"
OUTPUT_THUMBNAIL = OUTPUT_DIR / "latest_thumbnail.jpg"
OUTPUT_META = OUTPUT_DIR / "latest_meta.json"
OUTPUT_FIRST_FRAME = OUTPUT_DIR / "latest_first_frame.jpg"
OUTPUT_PREVIEW_GIF = OUTPUT_DIR / "latest_preview.gif"
VIDEO_COMPAT_REPORT = OUTPUT_DIR / "video_compat_report.txt"

MIN_TARGET_DURATION = 30.0
MAX_TARGET_DURATION = 40.0
TARGET_DURATION = 35.0

main.DEFAULT_VOICE = "en-US-JennyNeural"
main.RATE = "+10%"
main.PITCH = "-5Hz"

TITLE_RULES = [
    ("voicemail", "The Last Voicemail Was Not Human #shorts", "THE LAST VOICEMAIL"),
    ("radio", "This Broadcast Should Not Exist #shorts", "THE BROADCAST RETURNED"),
    ("mirror", "The Mirror Changed Overnight #shorts", "THE MIRROR CHANGED"),
    ("photo", "These Photos Should Not Exist #shorts", "THE PHOTOS LIED"),
    ("dark web", "This Page Predicted Everything #shorts", "IT PREDICTED THIS"),
    ("cassette", "The Tape Recorded One Extra Voice #shorts", "ONE EXTRA VOICE"),
    ("tape", "The Tape Recorded One Extra Voice #shorts", "ONE EXTRA VOICE"),
    ("radio station", "The Broadcast Came From Nowhere #shorts", "THE SIGNAL RETURNED"),
    ("train", "The Train Never Arrived #shorts", "THE TICKET SAID TOMORROW"),
    ("elevator", "The Elevator Opened To Nowhere #shorts", "FLOOR -1"),
    ("diary", "The Diary Knew Tomorrow #shorts", "THE INK WAS WET"),
    ("file", "This Case File Should Not Exist #shorts", "THIS FILE WAS HIDDEN"),
    ("footage", "The Missing Footage Came Back #shorts", "THE FOOTAGE RETURNED"),
    ("timestamp", "The Timestamp Was Wrong #shorts", "THE TIMESTAMP WAS WRONG"),
]

DEFAULT_TAGS = [
    "shorts", "youtubeshorts", "viralshorts", "fyp", "horror",
    "mysteryshorts", "unexplained", "darkmystery", "creepymystery", "truecrime",
    "conspiracy", "foundfootage", "scaryshorts", "casefile", "paranormal",
]

RISK_REPLACEMENTS = {
    "mandatory vaccines": "a mandatory public program",
    "vaccines": "public records",
    "vaccine": "public record",
    "microchips": "tracking devices",
    "microchip": "tracking device",
    "deceased": "inactive",
    "killed": "erased",
    "murdered": "erased",
}


def clean_script(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(script|text|answer)\s*:\s*", "", text.strip())
    text = re.sub(r"\s+", " ", text).strip().strip('"').strip("'")
    for risky, safer in RISK_REPLACEMENTS.items():
        text = re.sub(rf"\b{re.escape(risky)}\b", safer, text, flags=re.IGNORECASE)
    return text


def build_prompt(niche: str, archetype: dict) -> str:
    return f"""
Write an ENGLISH YouTube Shorts voiceover script as a fresh cinematic micro-horror story.
Topic mood: {niche}

{archetype_prompt_block(archetype)}

Style rules:
- Do NOT copy the wording of the prompt.
- Do NOT say phrases like "case file" "classified room" "security camera" unless the chosen seed naturally requires them.
- Do NOT repeat the Camera 4 timestamp hidden door formula.
- Make it sound like a creepy story a person would actually tell, not a list of evidence.
- Use sensory details: smell, sound, texture, weather, silence, old objects, strange messages.
- Use one weird specific object and one impossible detail.
- Keep conspiracy energy subtle through coverups, changed records, deleted pages, anonymous warnings, or photos that should not exist.

Structure:
- First sentence: instant hook with a concrete object, time, place, or message.
- Middle: 2-3 unsettling details.
- Twist: one impossible reveal.
- Final sentence: a specific open question.

Rules:
- Target 30-40 seconds spoken.
- Aim for 70-90 words only.
- Short punchy sentences.
- Scary, creative, different, believable.
- Avoid graphic violence gore blood direct real-person accusations and medical/vaccine conspiracies.
- No title no emojis no bullet points no stage directions.
Return only the voiceover text.
""".strip()


def ensure_open_question(script: str, archetype: dict) -> str:
    script = clean_script(script)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if sentences and sentences[-1].endswith("?") and len(sentences[-1]) > 18:
        return script
    endings = {
        "found_tape": "So who was holding the camera at the end?",
        "missing_person_last_message": "So who sent the final message from their phone?",
        "cursed_object": "So why did the object move after the room was locked?",
        "dark_web_listing": "So how did the page know what would happen next?",
        "small_town_broadcast": "So why does no one remember hearing the warning?",
        "conspiracy_archive": "So who changed the record overnight?",
        "abandoned_place_log": "So who stamped the ticket for tomorrow?",
        "paranormal_witness_report": "So what was standing in the reflection?",
        "family_photo_box": "So who took the photos before the trip happened?",
        "numbers_station": "So why did the last number point to their house?",
        "elevator_floor": "So who was drinking the fresh coffee on floor minus one?",
        "childhood_diary": "So who wrote tomorrow's page in wet ink?",
    }
    return script + " " + endings.get(archetype.get("name"), "So what do you think they were hiding?")


def has_template_leak(script: str) -> bool:
    lowered = script.lower()
    banned_pairs = [
        "camera 4", "room 314", "sub-basement archives", "project aegis",
        "hidden archive door", "timestamp loop", "classified room log",
        "story archetype", "must include", "avoid repeating",
    ]
    return any(term in lowered for term in banned_pairs)


def generate_script(niche: str, archetype: dict) -> str:
    from g4f.client import Client
    client = Client()
    prompt = build_prompt(niche, archetype)
    last_error = None
    for attempt in range(4):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
            )
            script = ensure_open_question(response.choices[0].message.content, archetype)
            words = len(script.split())
            if 55 <= words <= 100 and not has_template_leak(script):
                return script
            main.logger.warning(f"Script rejected words={words} template_leak={has_template_leak(script)}")
        except Exception as exc:
            last_error = exc
            main.logger.warning(f"Script attempt {attempt + 1} failed: {exc}")
    if last_error:
        raise RuntimeError(f"Could not generate script: {last_error}")
    raise RuntimeError("Could not generate non-repetitive script in target range")


async def choose_best_timed_script(niche: str, archetype: dict):
    candidates = []
    for attempt in range(4):
        script = generate_script(niche, archetype)
        audio, word_ts = await main.create_voiceover(script)
        clip = main.AudioFileClip(audio)
        duration = float(clip.duration)
        clip.close()
        candidates.append((abs(TARGET_DURATION - duration), script, audio, word_ts, duration))
        if MIN_TARGET_DURATION <= duration <= MAX_TARGET_DURATION:
            return script, audio, word_ts, duration
        main.logger.warning(f"Duration outside target: {duration:.2f}s retrying")
    candidates.sort(key=lambda row: row[0])
    _, script, audio, word_ts, duration = candidates[0]
    main.logger.warning(f"Using closest duration candidate: {duration:.2f}s")
    return script, audio, word_ts, duration


def title_and_thumbnail(script: str, niche: str):
    lowered = script.lower()
    for key, title, thumb in TITLE_RULES:
        if key in lowered:
            return title, thumb
    first = re.split(r"[.!?]", script)[0].strip()
    if len(first) < 16:
        first = horror_runner.THUMBNAIL_STYLE_TITLES.get(niche, "No One Can Explain This")
    return f"{first[:82]} #shorts", horror_runner.THUMBNAIL_STYLE_TITLES.get(niche, "NO ONE CAN EXPLAIN THIS")


def build_tags(niche: str, script: str):
    tags = list(DEFAULT_TAGS)
    tags.extend(horror_runner.NICHE_TAGS.get(niche, [])[:5])
    lowered = script.lower()
    for word, tag in horror_runner.KEYWORD_TAG_MAP.items():
        if word in lowered and tag not in tags:
            tags.append(tag)
    out = []
    for tag in tags:
        tag = str(tag).strip().lstrip("#")
        if tag and tag not in out:
            out.append(tag)
    return out[:15]


def run_cmd(args, check=True):
    main.logger.info("$ " + " ".join(str(x) for x in args))
    return subprocess.run(args, check=check, text=True, capture_output=True)


def normalize_mp4_for_mobile(input_path: str, output_path: Path) -> None:
    tmp = output_path.with_suffix(".tmp.mp4")
    if tmp.exists():
        tmp.unlink()
    run_cmd([
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "main", "-level", "4.0",
        "-movflags", "+faststart", "-c:a", "aac", "-b:a", "160k", str(tmp),
    ])
    tmp.replace(output_path)


def make_debug_previews(video_path: Path) -> None:
    run_cmd(["ffmpeg", "-y", "-ss", "00:00:02", "-i", str(video_path), "-frames:v", "1", str(OUTPUT_FIRST_FRAME)], check=False)
    run_cmd(["ffmpeg", "-y", "-ss", "00:00:00", "-t", "6", "-i", str(video_path), "-vf", "fps=8,scale=360:-1:flags=lanczos", str(OUTPUT_PREVIEW_GIF)], check=False)
    probe = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=format_name,duration,size:stream=codec_name,codec_type,pix_fmt,width,height", "-of", "json", str(video_path)], check=False)
    VIDEO_COMPAT_REPORT.write_text(probe.stdout or probe.stderr or "ffprobe produced no output", encoding="utf-8")


async def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    apply_caption_style(main)

    niche = random.choice(horror_runner.HORROR_NICHES)
    archetype = choose_archetype()
    main.logger.info(f"Niche: {niche}")
    main.logger.info(f"Archetype: {archetype['name']}")

    script, audio, word_ts, duration = await choose_best_timed_script(niche, archetype)
    main.logger.info("Script:\n" + script)

    chunked = main.chunk_timestamps(word_ts)
    base_background_queries = horror_runner.build_background_queries(niche, script)
    background_queries = build_visual_background_queries(niche, script, base_background_queries)
    main.NICHE_PEXELS_QUERIES = horror_runner.HORROR_PEXELS
    main.NICHE_PEXELS_QUERIES[niche] = background_queries

    bg = main.fetch_background_video(script, niche)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)

    title, thumbnail_text = title_and_thumbnail(script, niche)
    tags = build_tags(niche, script)

    normalize_mp4_for_mobile(final_path, OUTPUT_VIDEO)
    make_debug_previews(OUTPUT_VIDEO)

    thumb_path = make_thumbnail(str(OUTPUT_VIDEO), thumbnail_text, main.ensure_font(), main.logger)
    if thumb_path and Path(thumb_path).exists():
        shutil.copyfile(thumb_path, OUTPUT_THUMBNAIL)

    meta = {
        "mode": "optimized_save_only_no_youtube_upload",
        "language": "en",
        "niche": niche,
        "archetype": archetype,
        "caption_style": {
            "font_size": 42,
            "stroke_width": 3,
            "max_words": 2,
            "position": "center",
            "punctuation_removed": True,
            "timing": "edge_word_boundary_tight",
        },
        "title": title,
        "thumbnail_text": thumbnail_text,
        "duration_seconds": round(duration, 2),
        "tags": tags,
        "background_queries": background_queries,
        "base_background_queries": base_background_queries,
        "script": script,
        "video_path": str(OUTPUT_VIDEO),
        "thumbnail_path": str(OUTPUT_THUMBNAIL) if OUTPUT_THUMBNAIL.exists() else None,
        "first_frame_path": str(OUTPUT_FIRST_FRAME) if OUTPUT_FIRST_FRAME.exists() else None,
        "preview_gif_path": str(OUTPUT_PREVIEW_GIF) if OUTPUT_PREVIEW_GIF.exists() else None,
        "compat_report_path": str(VIDEO_COMPAT_REPORT) if VIDEO_COMPAT_REPORT.exists() else None,
        "video_url": None,
    }
    OUTPUT_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    horror_runner.write_runtime_meta(meta)
    main.logger.info(f"Saved video: {OUTPUT_VIDEO}")


if __name__ == "__main__":
    asyncio.run(run())
