#!/usr/bin/env python3
"""Generate an English horror Short and save it to the repository output folder.

This runner intentionally DOES NOT upload to YouTube. It uses horror_runner's
script/timing logic, then improves title, thumbnail text, visual background
queries, tags and metadata before saving the rendered video under
`generated-videos/` for GitHub Actions to commit/artifact.
"""

import asyncio
import json
import re
import shutil
import subprocess
from pathlib import Path

import main
import horror_runner
from thumbnail_helper import make_thumbnail
from visual_query_helper import build_visual_background_queries

OUTPUT_DIR = Path("generated-videos")
OUTPUT_VIDEO = OUTPUT_DIR / "latest_short.mp4"
OUTPUT_THUMBNAIL = OUTPUT_DIR / "latest_thumbnail.jpg"
OUTPUT_META = OUTPUT_DIR / "latest_meta.json"
OUTPUT_FIRST_FRAME = OUTPUT_DIR / "latest_first_frame.jpg"
OUTPUT_PREVIEW_GIF = OUTPUT_DIR / "latest_preview.gif"
VIDEO_COMPAT_REPORT = OUTPUT_DIR / "video_compat_report.txt"

HIGH_VALUE_TAGS = [
    "mysteryshorts",
    "unexplained",
    "securityfootage",
    "cctv",
    "caughtoncamera",
    "creepymystery",
    "darkmystery",
    "truecrime",
]

LOW_VALUE_TAGS = {"stared", "smiled", "looked", "wrong", "really", "would", "could"}


def first_sentence(script: str) -> str:
    return re.split(r"[.!?]", script.strip())[0].strip()


def run_cmd(args, check=True):
    main.logger.info("$ " + " ".join(str(x) for x in args))
    return subprocess.run(args, check=check, text=True, capture_output=True)


def normalize_mp4_for_mobile(input_path: str, output_path: Path) -> None:
    """Create a phone/GitHub-compatible MP4.

    MoviePy can produce H.264/AAC files that are valid but awkward for mobile
    preview if the pixel format/profile or moov atom placement is not ideal.
    This second pass forces yuv420p + faststart.
    """
    tmp = output_path.with_suffix(".tmp.mp4")
    if tmp.exists():
        tmp.unlink()
    run_cmd([
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-profile:v", "main",
        "-level", "4.0",
        "-movflags", "+faststart",
        "-c:a", "aac",
        "-b:a", "160k",
        str(tmp),
    ])
    tmp.replace(output_path)


def make_debug_previews(video_path: Path) -> None:
    try:
        run_cmd(["ffmpeg", "-y", "-ss", "00:00:02", "-i", str(video_path), "-frames:v", "1", str(OUTPUT_FIRST_FRAME)], check=False)
        run_cmd([
            "ffmpeg", "-y",
            "-ss", "00:00:00",
            "-t", "6",
            "-i", str(video_path),
            "-vf", "fps=8,scale=360:-1:flags=lanczos",
            str(OUTPUT_PREVIEW_GIF),
        ], check=False)
        probe = run_cmd([
            "ffprobe", "-v", "error",
            "-show_entries", "format=format_name,duration,size:stream=codec_name,codec_type,pix_fmt,width,height",
            "-of", "json",
            str(video_path),
        ], check=False)
        VIDEO_COMPAT_REPORT.write_text(probe.stdout or probe.stderr or "ffprobe produced no output", encoding="utf-8")
    except Exception as exc:
        main.logger.warning(f"Debug preview generation failed: {exc}")


def build_stronger_title(script: str, niche: str) -> str:
    lowered = script.lower()
    if "timestamp" in lowered:
        return "The Timestamp Was Wrong #shorts"
    if "camera" in lowered and any(word in lowered for word in ["vanished", "disappeared", "missing"]):
        return "He Smiled at the Camera… Then Vanished #shorts"
    if "camera" in lowered:
        return "The Camera Caught Something Wrong #shorts"
    if "file" in lowered or "case" in lowered:
        return "This Case File Should Not Exist #shorts"
    if "note" in lowered or "letter" in lowered:
        return "The Note Should Not Have Been There #shorts"
    if "dark web" in lowered or "internet" in lowered:
        return "This Trace Was Erased From the Internet #shorts"
    hook = first_sentence(script)
    if len(hook) < 18:
        hook = horror_runner.THUMBNAIL_STYLE_TITLES.get(niche, "No One Can Explain This")
    return f"{hook[:82]} #shorts"


def build_stronger_thumbnail_text(script: str, niche: str) -> str:
    lowered = script.lower()
    if "timestamp" in lowered:
        return "THE TIMESTAMP WAS WRONG"
    if "camera" in lowered and any(word in lowered for word in ["vanished", "disappeared", "missing"]):
        return "HE VANISHED ON CAMERA"
    if "camera" in lowered:
        return "THE CAMERA CAUGHT THIS"
    if "file" in lowered or "case" in lowered:
        return "THIS FILE WAS HIDDEN"
    if "note" in lowered or "letter" in lowered:
        return "WHO LEFT THE NOTE?"
    if "dark web" in lowered or "internet" in lowered:
        return "THEY ERASED THE TRACE"
    return horror_runner.THUMBNAIL_STYLE_TITLES.get(niche, "NO ONE CAN EXPLAIN THIS")


def build_stronger_tags(niche: str, script: str):
    base_tags = horror_runner.build_video_tags(niche, script)
    lowered = script.lower()
    tags = []

    for tag in base_tags:
        clean = str(tag).strip().lstrip("#")
        if clean and clean not in LOW_VALUE_TAGS and clean not in tags:
            tags.append(clean)

    for tag in HIGH_VALUE_TAGS:
        if tag not in tags:
            tags.append(tag)

    if "timestamp" in lowered and "timestamp" not in tags:
        tags.append("timestamp")
    if "memory card" in lowered and "memorycard" not in tags:
        tags.append("memorycard")
    if "footsteps" in lowered and "footsteps" not in tags:
        tags.append("footsteps")
    if "empty room" in lowered and "emptyroom" not in tags:
        tags.append("emptyroom")

    priority = [
        "shorts", "youtubeshorts", "viralshorts", "fyp", "horror",
        "mysteryshorts", "unexplained", "caughtoncamera", "securityfootage", "cctv",
        "darkmystery", "creepymystery", "truecrime",
    ]
    ordered = []
    for tag in priority + tags:
        if tag and tag not in ordered:
            ordered.append(tag)
    return ordered[:15]


async def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    main.NICHE_POOL = horror_runner.HORROR_NICHES
    main.NICHE_PEXELS_QUERIES = horror_runner.HORROR_PEXELS
    main.generate_script = horror_runner.horror_script

    niche = horror_runner.random.choice(horror_runner.HORROR_NICHES)
    script, audio, word_ts, duration = await horror_runner.generate_timed_script(niche)
    # Do not modify script after voiceover generation. This keeps audio and captions perfectly aligned.
    main.logger.info("📜 Script:\n" + script)

    chunked = main.chunk_timestamps(word_ts)
    base_background_queries = horror_runner.build_background_queries(niche, script)
    background_queries = build_visual_background_queries(niche, script, base_background_queries)
    main.NICHE_PEXELS_QUERIES[niche] = background_queries
    main.logger.info("🎥 Visual background queries: " + " | ".join(background_queries))

    bg = main.fetch_background_video(script, niche)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)

    title = build_stronger_title(script, niche)
    thumbnail_text = build_stronger_thumbnail_text(script, niche)
    tags = build_stronger_tags(niche, script)

    normalize_mp4_for_mobile(final_path, OUTPUT_VIDEO)
    make_debug_previews(OUTPUT_VIDEO)

    thumb_path = make_thumbnail(str(OUTPUT_VIDEO), thumbnail_text, main.ensure_font(), main.logger)
    if thumb_path and Path(thumb_path).exists():
        shutil.copyfile(thumb_path, OUTPUT_THUMBNAIL)

    meta = {
        "mode": "save_only_no_youtube_upload",
        "language": "en",
        "niche": niche,
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

    main.logger.info(f"✅ Mobile-compatible video saved: {OUTPUT_VIDEO}")
    main.logger.info(f"🧾 Metadata saved: {OUTPUT_META}")


if __name__ == "__main__":
    asyncio.run(run())
