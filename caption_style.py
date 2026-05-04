"""Caption styling and timing patch for Shorts.

Goal: captions must feel locked to the voice while staying readable.
This version keeps captions centered and switches to true word-locked timing:
- smaller centered font
- one spoken word per caption for best sync
- no punctuation in captions
- tiny positive offset to compensate MP3/render latency
- end time based on the next word start
"""

from __future__ import annotations

import re

CAPTION_FONT_SIZE = 42
CAPTION_STROKE_WIDTH = 3
CAPTION_MAX_WORDS = 1
CAPTION_POSITION = ("center", "center")
CAPTION_HORIZONTAL_MARGIN = 300
CAPTION_SYNC_OFFSET = 0.035
MIN_WORD_DURATION = 0.11
MAX_WORD_DURATION = 0.42
NEXT_WORD_GAP = 0.01


def clean_caption_word(word: str) -> str:
    return re.sub(r"[^A-Za-z0-9'\-À-ÖØ-öø-ÿ]+", "", str(word)).strip()


def build_caption_chunks(word_ts):
    """Build one-word captions from Edge TTS word boundaries.

    Multi-word captions are more readable but can feel out of sync because the
    second word appears before it is spoken. One-word centered captions are the
    safest option for near-perfect audio/subtitle lock.
    """
    words = []
    for start, dur, word in word_ts or []:
        clean = clean_caption_word(word)
        if not clean:
            continue
        start = max(float(start) + CAPTION_SYNC_OFFSET, 0.0)
        dur = max(float(dur), MIN_WORD_DURATION)
        end = start + min(dur, MAX_WORD_DURATION)
        words.append((start, end, clean))

    if not words:
        return []

    fixed = []
    for i, (start, end, text) in enumerate(words):
        if i + 1 < len(words):
            next_start = words[i + 1][0]
            end = min(end, next_start - NEXT_WORD_GAP)
        duration = max(end - start, MIN_WORD_DURATION)
        fixed.append((start, duration, text))
    return fixed


def make_caption_clips(main_module, chunked_ts):
    if not chunked_ts:
        return []

    font = main_module.ensure_font()
    clips = []
    max_width = main_module.VIDEO_SIZE[0] - CAPTION_HORIZONTAL_MARGIN

    for start, dur, text in chunked_ts:
        text = re.sub(r"[^A-Za-z0-9'\-À-ÖØ-öø-ÿ ]+", "", str(text)).strip()
        if not text:
            continue

        txt = (
            main_module.TextClip(
                text,
                fontsize=CAPTION_FONT_SIZE,
                color="white",
                font=font,
                stroke_color="black",
                stroke_width=CAPTION_STROKE_WIDTH,
                method="caption",
                size=(max_width, None),
                align="center",
            )
            .set_start(start)
            .set_duration(dur)
            .set_position(CAPTION_POSITION)
        )
        clips.append(txt)
    return clips


def apply_caption_style(main_module) -> None:
    main_module.MAX_CAPTION_WORDS = CAPTION_MAX_WORDS
    main_module.FONT_SIZE = CAPTION_FONT_SIZE
    main_module.STROKE_WIDTH = CAPTION_STROKE_WIDTH
    main_module.clean_caption_word = clean_caption_word
    main_module.chunk_timestamps = build_caption_chunks
    main_module.generate_captions = lambda chunked_ts: make_caption_clips(main_module, chunked_ts)
