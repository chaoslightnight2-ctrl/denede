"""Caption styling and timing patch for Shorts.

Keeps subtitles readable without covering the scary visuals:
- smaller font
- up to 3-word caption chunks
- no punctuation in captions
- lower-center placement
- timing based on real Edge TTS word boundaries
"""

from __future__ import annotations

import re

CAPTION_FONT_SIZE = 44
CAPTION_STROKE_WIDTH = 3
CAPTION_MAX_WORDS = 3
CAPTION_MAX_DURATION = 0.95
CAPTION_Y = 1080
CAPTION_HORIZONTAL_MARGIN = 220


def clean_caption_word(word: str) -> str:
    # Remove punctuation such as commas, dots, question marks, quotes, brackets.
    # Keep letters, numbers, apostrophes and hyphens so words like don't stay readable.
    return re.sub(r"[^A-Za-z0-9'\-À-ÖØ-öø-ÿ]+", "", str(word)).strip()


def build_caption_chunks(word_ts):
    if not word_ts:
        return []

    cleaned_words = []
    for start, dur, word in word_ts:
        clean = clean_caption_word(word)
        if clean:
            cleaned_words.append((float(start), float(dur), clean))

    if not cleaned_words:
        return []

    chunks = []
    cur_words = []
    chunk_start = cleaned_words[0][0]
    chunk_end = cleaned_words[0][0]

    for start, dur, word in cleaned_words:
        word_end = max(start + dur, start + 0.12)
        projected_duration = word_end - chunk_start

        if cur_words and (len(cur_words) >= CAPTION_MAX_WORDS or projected_duration > CAPTION_MAX_DURATION):
            chunks.append((chunk_start, max(chunk_end - chunk_start, 0.16), " ".join(cur_words)))
            cur_words = [word]
            chunk_start = start
            chunk_end = word_end
        else:
            cur_words.append(word)
            chunk_end = word_end

    if cur_words:
        chunks.append((chunk_start, max(chunk_end - chunk_start, 0.16), " ".join(cur_words)))

    # Close each caption just before the next caption starts. This avoids overlap
    # and makes subtitles feel synced with the actual speech rhythm.
    fixed = []
    for i, (start, dur, text) in enumerate(chunks):
        end = start + dur
        if i + 1 < len(chunks):
            end = min(end, chunks[i + 1][0] - 0.02)
        fixed.append((start, max(end - start, 0.12), text))
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
