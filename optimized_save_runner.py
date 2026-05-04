#!/usr/bin/env python3
"""Optimized save-only Shorts runner.

Does NOT upload to YouTube. Generates review videos with:
- first-person anonymous confession style
- realistic but fictional witnessed-event feeling
- loose inspiration cards, not restrictive templates
- centered tight subtitle sync
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

DEFAULT_TAGS = [
    "shorts", "youtubeshorts", "viralshorts", "fyp", "horror",
    "mysteryshorts", "unexplained", "darkmystery", "creepymystery", "truecrime",
    "conspiracy", "foundfootage", "scaryshorts", "paranormal", "firstpersonhorror",
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

BANNED_REPETITIONS = [
    "camera 4", "room 314", "sub-basement archives", "project aegis",
    "hidden archive door", "timestamp loop", "classified room log",
    "story archetype", "must include", "avoid repeating",
    "the timestamp was wrong", "this case file should not exist",
]


def clean_script(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(script|text|answer)\s*:\s*", "", text.strip())
    text = re.sub(r"\s+", " ", text).strip().strip('"').strip("'")
    for risky, safer in RISK_REPLACEMENTS.items():
        text = re.sub(rf"\b{re.escape(risky)}\b", safer, text, flags=re.IGNORECASE)
    return text


def build_prompt(niche: str, archetype: dict) -> str:
    return f"""
Write an ENGLISH YouTube Shorts voiceover as a first-person horror confession.
Mood: {niche}

{archetype_prompt_block(archetype)}

Core requirement:
- Write in FIRST PERSON using I / me / my.
- Make it feel like something the narrator personally experienced and is finally confessing.
- It should feel believable like an anonymous story, but do not claim it is a verified real event.
- The inspiration card is only a loose mood. Do not treat it as a checklist. Invent your own original details.

Style rules:
- Do NOT copy prompt wording.
- Do NOT sound like a report, evidence list, police file, or template summary.
- Do NOT repeat old motifs: Camera 4, Room 314, Project Aegis, timestamp wrong, hidden archive door, sub-basement archives.
- Use one ordinary place, one personal object, one sensory detail, and one impossible detail.
- Add subtle conspiracy or coverup only if it fits naturally: changed record, deleted post, anonymous warning, missing name, altered photo.
- The story should have a human feeling: fear, doubt, hesitation, regret, embarrassment, or the feeling that no one believed the narrator.

Structure:
- First sentence: personal hook. Start with something that happened to me, not a generic fact.
- Middle: what happened and why it felt wrong.
- Twist: one impossible reveal.
- Final sentence: a specific question that makes viewers comment.

Rules:
- Target 30-40 seconds spoken.
- Aim for 68-88 words only.
- Short punchy sentences.
- Creative, varied, scary, believable.
- Avoid graphic violence, gore, blood, direct real-person accusations, and medical/vaccine conspiracies.
- No title, no emojis, no bullet points, no stage directions.
Return only the voiceover text.
""".strip()


def ensure_open_question(script: str, archetype: dict) -> str:
    script = clean_script(script)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", script) if s.strip()]
    if sentences and sentences[-1].endswith("?") and len(sentences[-1]) > 18:
        return script
    endings = {
        "late_shift": "So why did it know I was working alone?",
        "old_family_memory": "So who changed the memory before I found it?",
        "roadside_encounter": "So how did he know where I was going?",
        "rented_room": "So who wrote my name before I checked in?",
        "deleted_message": "So who deleted it before I unlocked my phone?",
        "small_town_secret": "So why does everyone pretend it never happened?",
        "childhood_place": "So why was my old name still there?",
        "ordinary_object": "So why did it move when nobody touched it?",
        "conspiracy_hint": "So who changed the record after I saw it?",
        "witness_confession": "So why did nobody else remember seeing it?",
        "urban_legend_personal": "So how did the story know my private nickname?",
        "found_recording": "So who spoke my name on the recording?",
    }
    return script + " " + endings.get(archetype.get("name"), "So why did no one believe me?")


def has_template_leak(script: str) -> bool:
    lowered = script.lower()
    return any(term in lowered for term in BANNED_REPETITIONS)


def first_person_ratio_ok(script: str) -> bool:
    lowered = script.lower()
    return bool(re.search(r"\b(i|me|my|mine|myself)\b", lowered))


def generate_script(niche: str, archetype: dict) -> str:
    from g4f.client import Client
    client = Client()
    prompt = build_prompt(niche, archetype)
    last_error = None
    for attempt in range(5):
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt}],
                timeout=60,
            )
            script = ensure_open_question(response.choices[0].message.content, archetype)
            words = len(script.split())
            if 55 <= words <= 100 and not has_template_leak(script) and first_person_ratio_ok(script):
                return script
            main.logger.warning(
                f"Script rejected words={words} template_leak={has_template_leak(script)} first_person={first_person_ratio_ok(script)}"
            )
        except Exception as exc:
            last_error = exc
            main.logger.warning(f"Script attempt {attempt + 1} failed: {exc}")
    if last_error:
        raise RuntimeError(f"Could not generate script: {last_error}")
    raise RuntimeError("Could not generate first-person non-repetitive script in target range")


async def choose_best_timed_script(niche: str, archetype: dict):
    candidates = []
    for _ in range(4):
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
    return script, audio, word_ts, duration


def title_and_thumbnail(script: str, niche: str):
    first = re.split(r"[.!?]", script)[0].strip()
    lowered = script.lower()
    if "voicemail" in lowered:
        return "I Shouldn't Have Opened That Voicemail #shorts", "THE VOICEMAIL"
    if "radio" in lowered:
        return "I Heard My Name On The Radio #shorts", "THE RADIO SAID MY NAME"
    if "mirror" in lowered:
        return "My Mirror Showed Yesterday #shorts", "THE MIRROR LIED"
    if "photo" in lowered or "picture" in lowered:
        return "I Found Photos That Shouldn't Exist #shorts", "THE PHOTOS LIED"
    if "diary" in lowered:
        return "My Old Diary Knew Tomorrow #shorts", "THE INK WAS WET"
    if "elevator" in lowered:
        return "The Elevator Went To Floor -1 #shorts", "FLOOR -1"
    if len(first) < 16:
        first = horror_runner.THUMBNAIL_STYLE_TITLES.get(niche, "No One Can Explain This")
    return f"{first[:82]} #shorts", "NO ONE BELIEVED ME"


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
        "story_mode": "first_person_anonymous_confession",
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
