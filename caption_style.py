"""Caption styling and timing patch for Shorts.

Goal: captions must feel naturally synced with the voice while staying readable.
This version removes the artificial positive delay and uses Edge TTS word-starts
as the source of truth:
- larger centered font
- one current spoken word per caption
- no punctuation in captions
- starts very slightly early for human perception
- stays visible until just before the next spoken word
"""

from __future__ import annotations

import re

CAPTION_FONT_SIZE = 56
CAPTION_STROKE_WIDTH = 4
CAPTION_MAX_WORDS = 1
CAPTION_POSITION = ("center", "center")
CAPTION_HORIZONTAL_MARGIN = 260
# A tiny negative lead usually feels better than a late subtitle. Positive
# offsets made captions visibly late on rendered MP4s.
CAPTION_SYNC_LEAD = 0.025
MIN_WORD_DURATION = 0.16
MAX_WORD_HOLD = 0.78
NEXT_WORD_GAP = 0.006


def clean_caption_word(word: str) -> str:
    return re.sub(r"[^A-Za-z0-9'\-À-ÖØ-öø-ÿ]+", "", str(word)).strip()


def build_caption_chunks(word_ts):
    """Build one-word captions using next-word timing.

    Edge TTS gives a start time for each spoken word. The most stable subtitle
    timing is:
      caption_start = word_start - tiny lead
      caption_end   = next_word_start - tiny gap
    This avoids both late subtitles and future words appearing too early.
    """
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
            next_start = words[i + 1][0]
            end = min(natural_end, next_start - NEXT_WORD_GAP)
        else:
            end = natural_end

        # If Edge reports a very short duration, keep the word visible long
        # enough to read, but never let long pauses freeze one word forever.
        end = max(end, start + MIN_WORD_DURATION)
        end = min(end, start + MAX_WORD_HOLD)
        fixed.append((start, end - start, text))
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
