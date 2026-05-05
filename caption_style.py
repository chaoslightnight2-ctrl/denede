"""Caption styling and timing patch for Shorts.

Pillow/ImageClip based captions remove the need for ImageMagick in GitHub
Actions. This keeps dependency installation fast while improving subtitles:
- centered captions
- slightly larger white text with black stroke and soft shadow
- no punctuation
- one current spoken word per caption
- tighter Edge TTS word-start timing with a small perceptual lead
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
from moviepy.editor import ImageClip
from PIL import Image, ImageDraw, ImageFont

CAPTION_FONT_SIZE = 62
CAPTION_STROKE_WIDTH = 5
CAPTION_MAX_WORDS = 1
CAPTION_POSITION = ("center", "center")
CAPTION_HORIZONTAL_MARGIN = 220
CAPTION_SYNC_LEAD = 0.045
MIN_WORD_DURATION = 0.18
MAX_WORD_HOLD = 0.62
NEXT_WORD_GAP = 0.002
SHADOW_OFFSET = (6, 6)
SHADOW_OPACITY = 150
SHADOW_STROKE_WIDTH = 7
PADDING_X = 42
PADDING_Y = 26


def clean_caption_word(word: str) -> str:
    return re.sub(r"[^A-Za-z0-9\-À-ÖØ-öø-ÿ]+", "", str(word)).strip()


def build_caption_chunks(word_ts):
    words = []
    for start, dur, word in word_ts or []:
        clean = clean_caption_word(word)
        if not clean:
            continue
        raw_start = float(start)
        raw_dur = max(float(dur), MIN_WORD_DURATION)
        start = max(raw_start - CAPTION_SYNC_LEAD, 0.0)
        natural_end = raw_start + raw_dur
        words.append((start, natural_end, clean))

    if not words:
        return []

    fixed = []
    for i, (start, natural_end, text) in enumerate(words):
        if i + 1 < len(words):
            # Hold current word until the next word is almost starting.
            # This reduces visible gaps without showing the next word early.
            next_start = max(words[i + 1][0], start + MIN_WORD_DURATION)
            end = min(natural_end, next_start - NEXT_WORD_GAP)
        else:
            end = natural_end
        end = max(end, start + MIN_WORD_DURATION)
        end = min(end, start + MAX_WORD_HOLD)
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
        text = re.sub(r"[^A-Za-z0-9\-À-ÖØ-öø-ÿ ]+", "", str(text)).strip()
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
