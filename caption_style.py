"""Caption styling and timing patch for Shorts.

Goal: captions must feel locked to the voice while staying readable.
This version avoids huge single words and avoids long unsynced phrases:
- smaller font
- 1-2 word chunks, never 3-word laggy blocks
- no punctuation in captions
- lower-center placement
- chunk end is based on actual word end and next chunk start
"""

from __future__ import annotations

import re

CAPTION_FONT_SIZE = 42
CAPTION_STROKE_WIDTH = 3
CAPTION_MAX_WORDS = 2
CAPTION_MAX_DURATION = 0.62
CAPTION_Y = 1120
CAPTION_HORIZONTAL_MARGIN = 260
MIN_WORD_DURATION = 0.10
MIN_CHUNK_DURATION = 0.10
NEXT_CHUNK_GAP = 0.012


def clean_caption_word(word: str) -> str:
    return re.sub(r"[^A-Za-z0-9'\-À-ÖØ-öø-ÿ]+", "", str(word)).strip()


def build_caption_chunks(word_ts):
    """Build tight 1-2 word captions from Edge TTS word boundaries.

    Showing three words at once can look clean, but it often feels early because
    words 2-3 appear before they are spoken. Two words is the best compromise:
    readable, smaller, and still very close to the voice timing.
    """
    cleaned_words = []
    for start, dur, word in word_ts or []:
        clean = clean_caption_word(word)
        if not clean:
            continue
        start = float(start)
        dur = float(dur)
        end = max(start + dur, start + MIN_WORD_DURATION)
        cleaned_words.append((start, end, clean))

    if not cleaned_words:
        return []

    raw_chunks = []
    cur_words = []
    chunk_start = None
    chunk_end = None

    for start, end, word in cleaned_words:
        if chunk_start is None:
            cur_words = [word]
            chunk_start = start
            chunk_end = end
            continue

        projected_duration = end - chunk_start
        next_is_too_long = projected_duration > CAPTION_MAX_DURATION
        next_has_too_many_words = len(cur_words) >= CAPTION_MAX_WORDS

        if next_has_too_many_words or next_is_too_long:
            raw_chunks.append((chunk_start, chunk_end, " ".join(cur_words)))
            cur_words = [word]
            chunk_start = start
            chunk_end = end
        else:
            cur_words.append(word)
            chunk_end = end

    if cur_words:
        raw_chunks.append((chunk_start, chunk_end, " ".join(cur_words)))

    fixed = []
    for i, (start, end, text) in enumerate(raw_chunks):
        if i + 1 < len(raw_chunks):
            end = min(end, raw_chunks[i + 1][0] - NEXT_CHUNK_GAP)
        duration = max(end - start, MIN_CHUNK_DURATION)
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
            .set_position(("center", CAPTION_Y))
        )
        clips.append(txt)
    return clips


def apply_caption_style(main_module) -> None:
    main_module.MAX_CAPTION_WORDS = CAPTION_MAX_WORDS
    main_module.MAX_CAPTION_DURATION = CAPTION_MAX_DURATION
    main_module.FONT_SIZE = CAPTION_FONT_SIZE
    main_module.STROKE_WIDTH = CAPTION_STROKE_WIDTH
    main_module.clean_caption_word = clean_caption_word
    main_module.chunk_timestamps = build_caption_chunks
    main_module.generate_captions = lambda chunked_ts: make_caption_clips(main_module, chunked_ts)
