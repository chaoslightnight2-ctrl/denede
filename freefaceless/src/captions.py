from pathlib import Path
import json
from .config import CONFIG
from .quality import clean_spoken


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


def write_ass(words: list[dict], out_path: Path, video_w: int, video_h: int) -> Path:
    c = CONFIG["captions"]
    chunk_size = c["words_per_caption"]
    margin_v = int(video_h * (1 - c["position_y"]))

    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {video_w}
PlayResY: {video_h}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{c['font']},{c['font_size']},{c['primary_color']},&H00FFFFFF,{c['outline_color']},&H00000000,-1,0,0,0,100,100,0,0,1,{c['outline']},2,2,40,40,{margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

    chunks = [words[i:i + chunk_size] for i in range(0, len(words), chunk_size)]
    if len(chunks) >= 2 and len(chunks[-1]) == 1 and len(chunks[-2]) > 2:
        chunks[-1].insert(0, chunks[-2].pop())

    lines = []
    for chunk in chunks:
        start = _fmt_ts(chunk[0]["start"])
        end = _fmt_ts(chunk[-1]["end"])
        text = turkish_upper(" ".join(clean_spoken(w["word"]) for w in chunk))
        lines.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}")

    out_path.write_text(header + "\n".join(lines), encoding="utf-8")
    return out_path
