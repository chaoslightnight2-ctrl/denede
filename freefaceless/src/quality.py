"""Strict, fail-closed quality contract for Denede Shorts."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path


FORBIDDEN_SPOKEN = (
    "kaynak", "kaynakça", "haber sitesi", "sitesine göre", "google news",
    "http://", "https://", "www.", ".com", "başlık:", "metin:",
    "senaryo:", "açıklama:", "hashtag:", "```",
)
GENERIC_VISUALS = {"abstract background", "cinematic background", "ancient history", "mystery background"}


def compact(text: str) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def clean_spoken(text: str) -> str:
    value = compact(text)
    value = re.sub(r"https?://\S+|www\.\S+", " ", value, flags=re.I)
    value = re.sub(r"[#*_`~<>\[\]{}()|\\/]", " ", value)
    value = re.sub(r"[“”„«»\"'’‘:;,.!?…—–\-]+", " ", value)
    return compact(re.sub(r"[^\w\s]", " ", value))


def validate_visual_query(query: str) -> str:
    value = compact(query).lower()
    value = compact(re.sub(r"[\"'’‘“”,.:;!?_/-]+", " ", value))
    words = re.findall(r"[a-z0-9]+", value)
    if not 2 <= len(words) <= 6:
        raise ValueError("visual_query 2-6 İngilizce kelime olmalı")
    if value in GENERIC_VISUALS:
        raise ValueError("visual_query konuya özel değil")
    if re.search(r"[^a-z0-9\s-]", value):
        raise ValueError("visual_query yalnızca İngilizce arama kelimeleri içermeli")
    return value


def validate_and_prepare(data: dict) -> dict:
    scenes = data.get("scenes")
    if not isinstance(scenes, list) or not 5 <= len(scenes) <= 7:
        raise ValueError("scenes 5-7 sahne olmalı")
    seen_queries = set()
    clean_scenes = []
    for scene in scenes:
        if not isinstance(scene, dict):
            raise ValueError("sahne nesne olmalı")
        raw = str(scene.get("text", ""))
        if any(marker in raw.casefold() for marker in FORBIDDEN_SPOKEN):
            raise ValueError("Ham sahne metninde kaynak veya çıktı etiketi var")
        text = clean_spoken(raw)
        query = validate_visual_query(scene.get("visual_query", ""))
        if len(text.split()) < 4:
            raise ValueError("sahne konuşması en az 4 kelime olmalı")
        if query in seen_queries:
            raise ValueError("aynı görsel sorgusu birden fazla sahnede kullanıldı")
        seen_queries.add(query)
        clean_scenes.append({"text": text, "visual_query": query})

    spoken = " ".join(scene["text"] for scene in clean_scenes)
    low = spoken.casefold()
    forbidden = [marker for marker in FORBIDDEN_SPOKEN if marker in low]
    if forbidden:
        raise ValueError("konuşma metninde kaynak/çıktı kalıntısı var: " + ", ".join(forbidden))
    if not 55 <= len(spoken.split()) <= 90:
        raise ValueError("konuşma metni 55-90 kelime olmalı")
    if low.count("abone ol") != 1:
        raise ValueError("abonelik çağrısı tam bir kez geçmeli")
    if "denede" not in low:
        raise ValueError("konuşma metninde kanal adı yok")

    data["scenes"] = clean_scenes
    data["spoken_text"] = spoken
    data["full_text"] = spoken
    # Pauses are internal to TTS and never displayed as captions or stored as the
    # AI narration field. This keeps the requested punctuation-free spoken text.
    data["tts_text"] = ". ".join(scene["text"] for scene in clean_scenes) + "."
    data["tts_text"] = re.sub(r"\bDenede\b", "Dene de", data["tts_text"], flags=re.I)
    return data


def validate_rendered_video(path: str | Path) -> None:
    video = Path(path)
    if not video.exists() or video.stat().st_size < 250_000:
        raise ValueError("render edilmiş video yok veya bozuk")
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(video)],
        check=True, capture_output=True, text=True,
    )
    info = json.loads(result.stdout)
    streams = info.get("streams", [])
    picture = next((row for row in streams if row.get("codec_type") == "video"), None)
    sound = next((row for row in streams if row.get("codec_type") == "audio"), None)
    duration = float(info.get("format", {}).get("duration") or 0)
    if not picture or not sound:
        raise ValueError("final videoda görüntü veya ses yok")
    if int(picture.get("height") or 0) <= int(picture.get("width") or 0):
        raise ValueError("final video dikey değil")
    if not 25 <= duration <= 45:
        raise ValueError(f"final video süresi uygunsuz: {duration:.1f} saniye")
