"""Caption styling, timing, and Turkish TTS patch for Shorts.

Pillow/ImageClip based captions remove the need for ImageMagick in GitHub
Actions. Captions preserve Turkish words as-written while removing visual
punctuation. Voiceover generation requests Edge TTS WordBoundary metadata so
caption timing can use real word timings instead of a rough fallback.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import numpy as np
from moviepy.editor import ImageClip
from PIL import Image, ImageDraw, ImageFont

CAPTION_FONT_SIZE = 60
CAPTION_STROKE_WIDTH = 5
CAPTION_MAX_WORDS = 1
CAPTION_POSITION = ("center", "center")
CAPTION_HORIZONTAL_MARGIN = 180
CAPTION_SYNC_LEAD = 0.015
MIN_WORD_DURATION = 0.10
MAX_WORD_DURATION = 0.56
NEXT_WORD_GAP = 0.006
SHADOW_OFFSET = (6, 6)
SHADOW_OPACITY = 150
SHADOW_STROKE_WIDTH = 7
PADDING_X = 44
PADDING_Y = 26
TURKISH_VOWELS = "aeıioöuüAEIİOÖUÜ"
FORCED_TTS_RATE = "+10%"
FORCED_TTS_PITCH = "+0Hz"


def normalize_caption_source(text: str) -> str:
    """Remove visible punctuation without rewriting the actual words.

    Keep suffix letters. Example:
      Türkiye'de -> Türkiyede
      %5'i -> yüzde 5i
    """
    text = str(text or "")
    replacements = {
        "…": " ",
        "%": " yüzde ",
        "&": " ve ",
        "+": " artı ",
        "=": " eşittir ",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    text = re.sub(r"['’`]", "", text)
    text = re.sub(r"[\"“”‘’()\[\]{}<>]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def clean_caption_word(word: str) -> str:
    word = normalize_caption_source(word)
    word = re.sub(r"[^A-Za-z0-9À-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü\-]+", "", word)
    return word.strip()


def _tokenize_script(script: str):
    script = normalize_caption_source(script)
    return re.findall(r"[A-Za-z0-9À-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü\-]+|[.!?;:,]", script or "")


def _word_weight(word: str) -> float:
    clean = clean_caption_word(word)
    if not clean:
        return 0.0
    vowels = sum(1 for ch in clean if ch in TURKISH_VOWELS)
    return max(0.78, 0.46 + vowels * 0.43 + len(clean) * 0.036)


def _build_speech_weighted_timings(script: str, audio_duration: float):
    tokens = _tokenize_script(script)
    items = []
    pending_pause = 0.0
    for token in tokens:
        if re.fullmatch(r"[.!?]", token):
            pending_pause += 0.12
            continue
        if re.fullmatch(r"[;:,]", token):
            pending_pause += 0.05
            continue
        clean = clean_caption_word(token)
        if clean:
            items.append({"word": clean, "weight": _word_weight(clean), "pause_before": pending_pause})
            pending_pause = 0.0

    if not items:
        return []

    total_pause = sum(item["pause_before"] for item in items)
    usable = max(float(audio_duration) - 0.08 - total_pause, len(items) * MIN_WORD_DURATION)
    total_weight = sum(item["weight"] for item in items) or 1.0

    current = 0.03
    timings = []
    for item in items:
        current += item["pause_before"]
        dur = max(MIN_WORD_DURATION, usable * item["weight"] / total_weight)
        timings.append((current, dur, item["word"]))
        current += dur
    return timings


def _script_caption_words(script: str):
    return [clean_caption_word(token) for token in _tokenize_script(script) if clean_caption_word(token)]


def _looks_like_low_quality_fallback(word_ts, audio_duration: float, script: str = "") -> bool:
    if not word_ts or len(word_ts) < 4 or audio_duration <= 0:
        return True

    starts = [float(x[0]) for x in word_ts]
    durs = [float(x[1]) for x in word_ts]
    span = max(starts) + max(durs[-1], MIN_WORD_DURATION) - min(starts)
    script_words = _script_caption_words(script)
    ts_words = [clean_caption_word(x[2]) for x in word_ts if clean_caption_word(x[2])]
    same_count = bool(script_words) and abs(len(script_words) - len(ts_words)) <= 2
    starts_near_zero = min(starts) <= 0.08
    fills_audio = span >= audio_duration * 0.68
    artificial_full_span = same_count and starts_near_zero and fills_audio
    very_short_avg = (sum(durs) / max(len(durs), 1)) < 0.20
    return artificial_full_span or (fills_audio and very_short_avg)


async def _create_voiceover_with_word_boundary(main_module, script: str):
    """Create Turkish voiceover with real Edge TTS WordBoundary metadata.

    Newer edge-tts defaults to sentence metadata unless WordBoundary is
    requested explicitly. The old main.create_voiceover wrapper only accepted
    WordBoundary chunks, so it often fell back to rough artificial timings.
    """
    import edge_tts

    voice_file = getattr(main_module, "VOICEOVER_FILE", "voiceover.mp3")
    word_timestamps = []

    kwargs = {
        "rate": getattr(main_module, "RATE", FORCED_TTS_RATE),
        "pitch": getattr(main_module, "PITCH", FORCED_TTS_PITCH),
    }
    try:
        communicate = edge_tts.Communicate(
            script,
            getattr(main_module, "DEFAULT_VOICE", "tr-TR-EmelNeural"),
            boundary="WordBoundary",
            **kwargs,
        )
    except TypeError:
        main_module.logger.warning("edge-tts boundary option unavailable; using compatibility mode.")
        communicate = edge_tts.Communicate(
            script,
            getattr(main_module, "DEFAULT_VOICE", "tr-TR-EmelNeural"),
            **kwargs,
        )

    with open(voice_file, "wb") as audio_file:
        async for chunk in communicate.stream():
            chunk_type = chunk.get("type")
            if chunk_type == "audio":
                audio_file.write(chunk["data"])
            elif chunk_type == "WordBoundary":
                clean = clean_caption_word(chunk.get("text", ""))
                if clean:
                    word_timestamps.append((chunk["offset"] / 10_000_000, chunk["duration"] / 10_000_000, clean))

    if not os.path.exists(voice_file) or os.path.getsize(voice_file) == 0:
        raise RuntimeError("Ses dosyası oluşturulamadı.")

    clip = main_module.AudioFileClip(voice_file)
    audio_duration = float(clip.duration)
    clip.close()

    if word_timestamps:
        main_module.logger.info("Using Edge TTS WordBoundary subtitle timing: %d words.", len(word_timestamps))
        return voice_file, word_timestamps

    main_module.logger.warning("Edge TTS WordBoundary unavailable; using Turkish speech-weighted fallback.")
    return voice_file, _build_speech_weighted_timings(script, audio_duration)


def patch_voiceover_timing(main_module) -> None:
    current = getattr(main_module, "create_voiceover", None)
    if not current or getattr(current, "_caption_patch_applied", False):
        return

    async def create_voiceover_with_better_timing(script: str):
        audio_path, word_ts = await _create_voiceover_with_word_boundary(main_module, script)
        try:
            clip = main_module.AudioFileClip(audio_path)
            audio_duration = float(clip.duration)
            clip.close()
        except Exception:
            audio_duration = 0.0
        if audio_duration > 0 and _looks_like_low_quality_fallback(word_ts, audio_duration, script):
            main_module.logger.warning("Using Turkish speech-weighted subtitle timing guard.")
            word_ts = _build_speech_weighted_timings(script, audio_duration)
        else:
            word_ts = [(s, d, clean_caption_word(w)) for s, d, w in word_ts if clean_caption_word(w)]
        return audio_path, word_ts

    create_voiceover_with_better_timing._caption_patch_applied = True
    main_module.create_voiceover = create_voiceover_with_better_timing


def build_caption_chunks(word_ts):
    fixed = []
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

    for idx, (start, end, text) in enumerate(words):
        if idx + 1 < len(words):
            end = min(end, words[idx + 1][0] - NEXT_WORD_GAP)
        end = max(end, start + MIN_WORD_DURATION)
        end = min(end, start + MAX_WORD_DURATION)
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
    text = re.sub(r"\s+", "", str(text)).strip()
    font = _load_font(font_path)
    probe = Image.new("RGBA", (max_width, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(probe)
    stroke_probe = max(SHADOW_STROKE_WIDTH, CAPTION_STROKE_WIDTH)
    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_probe)

    available = max_width - 2 * PADDING_X - SHADOW_OFFSET[0] - 8
    while bbox[2] - bbox[0] > available and getattr(font, "size", CAPTION_FONT_SIZE) > 38:
        font = ImageFont.truetype(getattr(font, "path", "DejaVuSans-Bold.ttf"), getattr(font, "size", CAPTION_FONT_SIZE) - 4)
        bbox = draw.textbbox((0, 0), text, font=font, stroke_width=stroke_probe)

    text_w = max(1, bbox[2] - bbox[0])
    text_h = max(1, bbox[3] - bbox[1])
    img_w = min(max_width, text_w + 2 * PADDING_X + SHADOW_OFFSET[0])
    img_h = text_h + 2 * PADDING_Y + SHADOW_OFFSET[1]

    image = Image.new("RGBA", (img_w, img_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    x = img_w // 2
    y = PADDING_Y - bbox[1]

    draw.text((x + SHADOW_OFFSET[0], y + SHADOW_OFFSET[1]), text, font=font, anchor="ma",
              fill=(0, 0, 0, SHADOW_OPACITY), stroke_width=SHADOW_STROKE_WIDTH,
              stroke_fill=(0, 0, 0, SHADOW_OPACITY))
    draw.text((x, y), text, font=font, anchor="ma", fill=(255, 255, 255, 255),
              stroke_width=CAPTION_STROKE_WIDTH, stroke_fill=(0, 0, 0, 255))
    return np.array(image)


def make_caption_clips(main_module, chunked_ts):
    if not chunked_ts:
        return []

    font_path = main_module.ensure_font()
    clips = []
    max_width = main_module.VIDEO_SIZE[0] - CAPTION_HORIZONTAL_MARGIN

    for start, dur, text in chunked_ts:
        text = normalize_caption_source(text)
        text = re.sub(r"[^A-Za-z0-9À-ÖØ-öø-ÿÇĞİÖŞÜçğıöşü\-]+", "", str(text)).strip()
        if not text:
            continue
        image = _render_caption_image(text, font_path, max_width)
        clip = ImageClip(image, transparent=True).set_start(start).set_duration(dur).set_position(CAPTION_POSITION)
        clips.append(clip)
    return clips


def apply_caption_style(main_module) -> None:
    main_module.DEFAULT_VOICE = "tr-TR-EmelNeural"
    main_module.RATE = FORCED_TTS_RATE
    main_module.PITCH = FORCED_TTS_PITCH
    main_module.MAX_CAPTION_WORDS = CAPTION_MAX_WORDS
    main_module.FONT_SIZE = CAPTION_FONT_SIZE
    main_module.STROKE_WIDTH = CAPTION_STROKE_WIDTH
    main_module.clean_caption_word = clean_caption_word
    main_module.chunk_timestamps = build_caption_chunks
    main_module.generate_captions = lambda chunked_ts: make_caption_clips(main_module, chunked_ts)
    patch_voiceover_timing(main_module)
