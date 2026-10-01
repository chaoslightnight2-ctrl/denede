from pathlib import Path
import json
from .config import CONFIG
from .quality import clean_spoken
from .speech_timing import align_caption_starts


def transcribe_words(audio_path: Path) -> list[dict]:
    sidecar = audio_path.with_suffix(".words.json")
    if not sidecar.exists():
        raise ValueError("TTS kelime zamanları bulunamadı; tahmini/Whisper altyazı yok")
    words = json.loads(sidecar.read_text(encoding="utf-8"))
    if not words:
        raise ValueError("TTS kelime zamanları boş")
    for index, word in enumerate(words):
        word["word"] = clean_spoken(word["word"])
        if word["end"] <= word["start"] or (index and word["start"] < words[index - 1]["end"] - .05):
            raise ValueError("TTS kelime zamanları çakışıyor")
    canonical = []
    index = 0
    while index < len(words):
        if index + 1 < len(words) and words[index]["word"].casefold() == "dene" and words[index + 1]["word"].casefold() == "de":
            canonical.append({"word": "Denede", "start": words[index]["start"], "end": words[index + 1]["end"]})
            index += 2
            continue
        canonical.append(words[index])
        index += 1
    return canonical


def _fmt_ts(t: float) -> str:
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = t - h * 3600 - m * 60
    return f"{h:01d}:{m:02d}:{s:05.2f}"


def turkish_upper(text):
    return text.replace('i', 'İ').replace('ı', 'I').upper()


def write_ass(words: list[dict], out_path: Path, video_w: int, video_h: int, audio_path: Path | None = None) -> Path:
    c = CONFIG["captions"]
    chunk_size = c["words_per_caption"]
    margin_v = int(video_h * (1 - c["position_y"]))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{c['font']},{c['font_size']},{c['primary_color']},&H00FFFFFF,{c['outline_color']},&H00000000,-1,0,0,0,100,100,0,0,1,{c['outline']},2,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    chunks = []
    for word in words:
        if not chunks or len(chunks[-1]) >= chunk_size or word['start'] - chunks[-1][-1]['end'] > .35:
            chunks.append([])
        chunks[-1].append(word)
    if (len(chunks) >= 2 and len(chunks[-1]) == 1 and len(chunks[-2]) > 2
            and chunks[-1][0]['start'] - chunks[-2][-1]['end'] <= .35):
        chunks[-1].insert(0, chunks[-2].pop())

    rows = [(chunk[0]["start"], chunk[-1]["end"] - chunk[0]["start"],
             turkish_upper(" ".join(clean_spoken(w["word"]) for w in chunk))) for chunk in chunks]
    if audio_path is not None:
        rows = align_caption_starts(audio_path, rows)
    lines = [f"Dialogue: 0,{_fmt_ts(start)},{_fmt_ts(start + duration)},Default,,0,0,0,,{text}"
             for start, duration, text in rows]

    out_path.write_text(header + "\n".join(lines), encoding="utf-8")
    return out_path
