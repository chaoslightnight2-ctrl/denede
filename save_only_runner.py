#!/usr/bin/env python3
"""Generate an English horror Short and save it to the repository output folder.

This runner intentionally DOES NOT upload to YouTube. It uses horror_runner's
script, timing, title, tag and metadata logic, then stores the rendered video
plus metadata under generated-videos/ for GitHub Actions to commit/artifact.
"""

import asyncio
import json
import shutil
from pathlib import Path

import main
import horror_runner
from thumbnail_helper import make_thumbnail
from visual_query_helper import build_visual_background_queries

OUTPUT_DIR = Path("generated-videos")
OUTPUT_VIDEO = OUTPUT_DIR / "latest_short.mp4"
OUTPUT_THUMBNAIL = OUTPUT_DIR / "latest_thumbnail.jpg"
OUTPUT_META = OUTPUT_DIR / "latest_meta.json"


async def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    main.NICHE_POOL = horror_runner.HORROR_NICHES
    main.NICHE_PEXELS_QUERIES = horror_runner.HORROR_PEXELS
    main.generate_script = horror_runner.horror_script

    niche = horror_runner.random.choice(horror_runner.HORROR_NICHES)
    script, audio, word_ts, duration = await horror_runner.generate_timed_script(niche)
    main.logger.info("📜 Script:\n" + script)

    chunked = main.chunk_timestamps(word_ts)
    base_background_queries = horror_runner.build_background_queries(niche, script)
    background_queries = build_visual_background_queries(niche, script, base_background_queries)
    main.NICHE_PEXELS_QUERIES[niche] = background_queries
    main.logger.info("🎥 Visual background queries: " + " | ".join(background_queries))

    bg = main.fetch_background_video(script, niche)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)

    title = horror_runner.horror_title(niche, script)
    thumbnail_text = horror_runner.THUMBNAIL_STYLE_TITLES.get(niche, "NO ONE CAN EXPLAIN THIS")
    tags = horror_runner.build_video_tags(niche, script)

    shutil.copyfile(final_path, OUTPUT_VIDEO)
    thumb_path = make_thumbnail(final_path, thumbnail_text, main.ensure_font(), main.logger)
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
        "video_url": None,
    }
    OUTPUT_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    horror_runner.write_runtime_meta(meta)

    main.logger.info(f"✅ Video saved to repo output: {OUTPUT_VIDEO}")
    main.logger.info(f"🧾 Metadata saved: {OUTPUT_META}")


if __name__ == "__main__":
    asyncio.run(run())
