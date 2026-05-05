"""Caption styling, timing, and Turkish TTS patch for Shorts.

Pillow/ImageClip based captions remove the need for ImageMagick in GitHub
Actions. Captions preserve Turkish words as-written while removing visual
punctuation. Voiceover generation requests Edge TTS WordBoundary metadata. If
that metadata is unavailable, the fallback analyzes the generated audio and maps
words only onto detected speech regions, so subtitles do not keep moving during
breath/silence gaps.
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
CAPTION_SYNC_LEAD = 0.012
MIN_WORD_DURATION = 0.10
MAX_WORD_DURATION = 0.58
NEXT_WORD_GAP = 0.006
SHADOW_OFFSET = (6, 6)
SHADOW_OPACITY = 150
SHADOW_STROKE_WIDTH = 7
PADDING_X = 44
PADDING_Y = 26
TURKISH_VOWELS = "aeıioöuüAEIİOÖUÜ"
FORCED_TTS_RATE = "+10%"
FORCED_TTS_PITCH = "+0Hz"
AUDIO_ANALYSIS_FPS = 16000
SILENCE_FRAME_SEC = 0.035
SILENCE_MERGE_GAP = 0.11
MIN_SPEECH_REGION = 0.13
SPEECH_REGION_PAD = 0.018


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


def _caption_items_from_script(script: str):
    items = []
    for token in _tokenize_script(script):
        if re.fullmatch(r"[.!?;:,]", token):
            continue
        clean = clean_caption_word(token)
        if clean:
            items.append({"word": clean, "weight": _word_weight(clean)})
    return items


def _detect_speech_regions(main_module, audio_path: str, audio_duration: float):
    """Return speech intervals by analyzing amplitude in the generated voiceover.

    This is intentionally simple and dependency-free: MoviePy reads the MP3,
    NumPy estimates short-frame loudness, then we merge close speech frames.
    The goal is not perfect ASR; it is to preserve real breath/silence gaps so
    fallback captions pause when the speaker pauses.
    """
    if not audio_path or audio_duration <= 0:
        return []

    clip = None
    try:
        clip = main_module.AudioFileClip(audio_path)
        arr = clip.to_soundarray(fps=AUDIO_ANALYSIS_FPS)
    except Exception as exc:
        try:
            main_module.logger.warning("Speech-region audio analysis failed: %s", exc)
        except Exception:
            pass
        return []
    finally:
        if clip is not None:
            try:
                clip.close()
            except Exception:
                pass

    if arr is None or len(arr) == 0:
        return []
    arr = np.asarray(arr)
    if arr.ndim == 2:
        arr = np.mean(np.abs(arr), axis=1)
    else:
        arr = np.abs(arr)

    frame = max(1, int(AUDIO_ANALYSIS_FPS * SILENCE_FRAME_SEC))
    usable_len = (len(arr) // frame) * frame
    if usable_len <= frame:
        return [(0.03, max(0.03, audio_duration - 0.04))]
    frames = arr[:usable_len].reshape(-1, frame)
    energy = frames.mean(axis=1)
    if len(energy) == 0:
        return []

    peak = float(np.percentile(energy, 98))
    floor = float(np.percentile(energy, 15))
    threshold = max(0.0025, floor * 2.8, peak * 0.075)
    speech_mask = energy > threshold

    regions = []
    start_idx = None
    for idx, is_speech in enumerate(speech_mask):
        if is_speech and start_idx is None:
            start_idx = idx
        elif not is_speech and start_idx is not None:
            start = start_idx * SILENCE_FRAME_SEC
            end = idx * SILENCE_FRAME_SEC
            regions.append((start, end))
            start_idx = None
    if start_idx is not None:
        regions.append((start_idx * SILENCE_FRAME_SEC, len(speech_mask) * SILENCE_FRAME_SEC))

    if not regions:
        return [(0.03, max(0.03, audio_duration - 0.04))]

    merged = []
    for start, end in regions:
        start = max(0.0, start - SPEECH_REGION_PAD)
        end = min(audio_duration, end + SPEECH_REGION_PAD)
        if not merged or start - merged[-1][1] > SILENCE_MERGE_GAP:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)

    filtered = [(s, e) for s, e in merged if e - s >= MIN_SPEECH_REGION]
    if not filtered:
        return [(0.03, max(0.03, audio_duration - 0.04))]
    return filtered


def _build_timings_in_speech_regions(script: str, speech_regions, audio_duration: float):
    items = _caption_items_from_script(script)
    if not items:
        return []
    if not speech_regions:
        speech_regions = [(0.03, max(0.03, float(audio_duration) - 0.04))]

    total_speech = sum(max(0.0, end - start) for start, end in speech_regions)
    if total_speech <= 0:
        return []
    total_weight = sum(item["weight"] for item in items) or 1.0

    raw_durs = [max(0.075, total_speech * item["weight"] / total_weight) for item in items]
    raw_total = sum(raw_durs)
    if raw_total > total_speech:
        scale = total_speech / raw_total
        raw_durs = [max(0.055, dur * scale) for dur in raw_durs]

    timings = []
    region_idx = 0
    current = float(speech_regions[0][0]) + 0.01

    for item, desired_dur in zip(items, raw_durs):
        while region_idx < len(speech_regions):
            region_start, region_end = speech_regions[region_idx]
            current = max(current, float(region_start) + 0.004)
            remaining = float(region_end) - current
            if remaining >= max(0.055, min(desired_dur, 0.16) * 0.55):
                break
            region_idx += 1
            if region_idx < len(speech_regions):
                current = float(speech_regions[region_idx][0]) + 0.006

        if region_idx >= len(speech_regions):
            # If speech detection was too strict near the end, place remaining
            # words in the final detected speech region rather than during a
            # long silence.
            region_idx = len(speech_regions) - 1
            region_start, region_end = speech_regions[region_idx]
            current = min(max(current, region_start), max(region_start, region_end - 0.06))

        region_start, region_end = speech_regions[region_idx]
        remaining = max(0.055, float(region_end) - current)
        dur = min(float(desired_dur), remaining)
        timings.append((max(0.0, current), max(0.055, dur), item["word"]))
        current += dur

    return timings


def _build_speech_weighted_timings(script: str, audio_duration: float, main_module=None, audio_path: str | None = None):
    if main_module is not None and audio_path:
        regions = _detect_speech_regions(main_module, audio_path, float(audio_duration))
        if regions:
            try:
                main_module.logger.info("Using pause-aware audio fallback with %d speech regions.", len(regions))
            except Exception:
                pass
            return _build_timings_in_speech_regions(script, regions, float(audio_duration))

    # Last-resort fallback for environments where the audio cannot be analyzed.
    items = _caption_items_from_script(script)
    if not items:
        return []
    usable = max(float(audio_duration) - 0.08, len(items) * MIN_WORD_DURATION)
    total_weight = sum(item["weight"] for item in items) or 1.0
    current = 0.03
    timings = []
    for item in items:
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
    """Create Turkish voiceover with real Edge TTS WordBoundary metadata."""
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

    main_module.logger.warning("Edge TTS WordBoundary unavailable; using pause-aware audio fallback.")
    return voice_file, _build_speech_weighted_timings(script, audio_duration, main_module, voice_file)


def patch_voiceover_timing(main_module) -> None:
    current = getattr(main_module, "create_voiceover", None)
    if not current or getattr(current, "_caption_patch_applied", False):
        return

    async def create_voiceover_with_better_timing(script: str):
        audio_path, word_ts = await _create_voiceover_with_word_boundary(main_module, script)
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
            next_start = words[idx + 1][0]
            if next_start - end > 0.10:
                # Preserve actual pause/breath gaps instead of stretching the
                # previous caption through silence.
                end = min(end, next_start - NEXT_WORD_GAP)
            else:
                end = min(end, next_start - NEXT_WORD_GAP)
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
