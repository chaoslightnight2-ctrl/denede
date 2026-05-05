"""Caption styling and timing patch for Shorts.

Pillow/ImageClip based captions remove the need for ImageMagick in GitHub
Actions. This version also fixes the biggest sync issue we saw in logs: Edge TTS
sometimes returns no WordBoundary data for Turkish, so main.py falls back to a
rough character split. Here we replace that with a speech-weighted Turkish
fallback based on the real audio duration.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from moviepy.editor import ImageClip
from PIL import Image, ImageDraw, ImageFont

CAPTION_FONT_SIZE = 60
CAPTION_STROKE_WIDTH = 5
CAPTION_MAX_WORDS = 2
CAPTION_POSITION = ("center", "center")
CAPTION_HORIZONTAL_MARGIN = 200
CAPTION_SYNC_LEAD = 0.018
MIN_WORD_DURATION = 0.13
MIN_CHUNK_DURATION = 0.28
MAX_CHUNK_DURATION = 0.95
NEXT_CHUNK_GAP = 0.006
SHADOW_OFFSET = (6, 6)
SHADOW_OPACITY = 150
SHADOW_STROKE_WIDTH = 7
PADDING_X = 44
PADDING_Y = 26
TURKISH_VOWELS = "aeıioöuüAEIİOÖUÜ"


def clean_caption_word(word: str) -> str:
    return re.sub(r"[^A-Za-z0-9\-À-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü]+", "", str(word)).strip()


def _tokenize_script(script: str):
    # Keep sentence punctuation as timing hints, but remove it from visible text.
    tokens = re.findall(r"[A-Za-z0-9À-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü\-]+|[.!?;:,]", script or "")
    return tokens


def _word_weight(word: str) -> float:
    clean = clean_caption_word(word)
    if not clean:
        return 0.0
    vowels = sum(1 for ch in clean if ch in TURKISH_VOWELS)
    # Turkish TTS duration follows syllables/vowels better than raw length.
    return max(0.75, 0.45 + vowels * 0.42 + len(clean) * 0.035)


def _build_speech_weighted_timings(script: str, audio_duration: float):
    tokens = _tokenize_script(script)
    items = []
    pending_pause = 0.0
    for token in tokens:
        if re.fullmatch(r"[.!?]", token):
            pending_pause += 0.18
            continue
        if re.fullmatch(r"[;:,]", token):
            pending_pause += 0.09
            continue
        clean = clean_caption_word(token)
        if clean:
            items.append({"word": clean, "weight": _word_weight(clean), "pause_before": pending_pause})
            pending_pause = 0.0

    if not items:
        return []

    total_pause = sum(item["pause_before"] for item in items)
    usable = max(float(audio_duration) - 0.12 - total_pause, len(items) * MIN_WORD_DURATION)
    total_weight = sum(item["weight"] for item in items) or 1.0

    current = 0.04
    timings = []
    for item in items:
        current += item["pause_before"]
        dur = max(MIN_WORD_DURATION, usable * item["weight"] / total_weight)
        timings.append((current, dur, item["word"]))
        current += dur
    return timings


def _looks_like_low_quality_fallback(word_ts, audio_duration: float) -> bool:
    # In the logs Edge returned no word boundaries, and main.py generated a full
    # coverage proportional fallback. Use our stronger Turkish fallback whenever
    # timing density/coverage looks synthetic or too short for readable captions.
    if not word_ts:
        return True
    if len(word_ts) < 4:
        return True
    starts = [float(x[0]) for x in word_ts]
    durs = [float(x[1]) for x in word_ts]
    span = max(starts) + max(durs[-1], MIN_WORD_DURATION) - min(starts)
    avg_dur = sum(durs) / max(len(durs), 1)
    if span > audio_duration * 0.82 and avg_dur < 0.24:
        return True
    return False


def patch_voiceover_timing(main_module) -> None:
    original = getattr(main_module, "create_voiceover", None)
    if not original or getattr(original, "_caption_patch_applied", False):
        return

    async def create_voiceover_with_better_timing(script: str):
        audio_path, word_ts = await original(script)
        try:
            clip = main_module.AudioFileClip(audio_path)
            audio_duration = float(clip.duration)
            clip.close()
        except Exception:
            audio_duration = 0.0
        if audio_duration > 0 and _looks_like_low_quality_fallback(word_ts, audio_duration):
            main_module.logger.warning("Using speech-weighted Turkish subtitle timing fallback.")
            word_ts = _build_speech_weighted_timings(script, audio_duration)
        return audio_path, word_ts

    create_voiceover_with_better_timing._caption_patch_applied = True
    main_module.create_voiceover = create_voiceover_with_better_timing


def build_caption_chunks(word_ts):
    words = []
    for start, dur, word in word_ts or []:
        clean = clean_caption_word(word)
        if not clean:
            continue
        raw_start = float(start)
        raw_dur = max(float(dur), MIN_WORD_DURATION)
        start = max(raw_start - CAPTION_SYNC_LEAD, 0.0)
        end = raw_start + raw_dur
        words.append((start, end, clean))

    if not words:
        return []

    chunks = []
    i = 0
    while i < len(words):
        start = words[i][0]
        texts = [words[i][2]]
        end = words[i][1]
        # Group two short neighbouring words. This reads better and hides tiny
        # artificial timing errors, while still staying close to the voice.
        if i + 1 < len(words):
            next_start, next_end, next_text = words[i + 1]
            projected = next_end - start
            if projected <= MAX_CHUNK_DURATION and len(next_text) <= 12:
                texts.append(next_text)
                end = next_end
                i += 1
        chunks.append((start, end, " ".join(texts)))
        i += 1

    fixed = []
    for idx, (start, end, text) in enumerate(chunks):
        if idx + 1 < len(chunks):
            end = min(end, chunks[idx + 1][0] - NEXT_CHUNK_GAP)
        end = max(end, start + MIN_CHUNK_DURATION)
        end = min(end, start + MAX_CHUNK_DURATION)
        fixed.append((start, end - start, text))
    return fixed


def _load_font(font_path: str):
    try:
        if font_path and Path(font_path).exists():
            return ImageFont.truetype(font_path, CAPTION_FONT_SIZE)
    except Exception:
        pass
    try:
        return ImageFont.truetype("DejaVuSans-Bold.ttf", CAPTION_FONT_SIZE)
    except Exception:
        return ImageFont.load_default()


def _render_caption_image(text: str, font_path: str, max_width: int):
    font = _load_font(font_path)
    probe = Image.new("RGBA", (max_width, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=max(SHADOW_STROKE_WIDTH, CAPTION_STROKE_WIDTH))
    text_w = min(max_width - 2 * PADDING_X, max(1, bbox[2] - bbox[0]))
    text_h = max(1, bbox[3] - bbox[1])
    img_w = min(max_width, text_w + 2 * PADDING_X + SHADOW_OFFSET[0])
    img_h = text_h + 2 * PADDING_Y + SHADOW_OFFSET[1]

    image = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    x = img_w // 2
    y = PADDING_Y - bbox[1]

    draw.text(
        (x + SHADOW_OFFSET[0], y + SHADOW_OFFSET[1]),
        text,
        font=font,
        anchor="ma",
        fill=(0, 0, 0, SHADOW_OPACITY),
        stroke_width=SHADOW_STROKE_WIDTH,
        stroke_fill=(0, 0, 0, SHADOW_OPACITY),
    )
    draw.text(
        (x, y),
        text,
        font=font,
        anchor="ma",
        fill=(255, 255, 255, 255),
        stroke_width=CAPTION_STROKE_WIDTH,
        stroke_fill=(0, 0, 0, 255),
    )
    return np.array(image)


def make_caption_clips(main_module, chunked_ts):
    if not chunked_ts:
        return []

    font_path = main_module.ensure_font()
    clips = []
    max_width = main_module.VIDEO_SIZE[0] - CAPTION_HORIZONTAL_MARGIN

    for start, dur, text in chunked_ts:
        text = re.sub(r"[^A-Za-z0-9\-À-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü\- ]+", "", str(text)).strip()
        if not text:
            continue
        image = _render_caption_image(text, font_path, max_width)
        clip = ImageClip(image, transparent=True).set_start(start).set_duration(dur).set_position(CAPTION_POSITION)
        clips.append(clip)
    return clips


def apply_caption_style(main_module) -> None:
    main_module.MAX_CAPTION_WORDS = CAPTION_MAX_WORDS
    main_module.FONT_SIZE = CAPTION_FONT_SIZE
    main_module.STROKE_WIDTH = CAPTION_STROKE_WIDTH
    main_module.clean_caption_word = clean_caption_word
    main_module.chunk_timestamps = build_caption_chunks
    main_module.generate_captions = lambda chunked_ts: make_caption_clips(main_module, chunked_ts)
    patch_voiceover_timing(main_module)
