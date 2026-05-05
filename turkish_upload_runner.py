#!/usr/bin/env python3
"""Turkish general viral Shorts upload runner.

Generates one Turkish general viral Short, saves outputs, writes metadata before
upload, then tries YouTube upload. If upload limit is reached, the video and
metadata still stay saved in the repo.
"""

from __future__ import annotations

import asyncio
import json
import random
import re
import shutil
import subprocess
from pathlib import Path

import main
from caption_style import apply_caption_style
from thumbnail_helper import make_thumbnail

OUTPUT_DIR = Path("generated-videos")
OUTPUT_VIDEO = OUTPUT_DIR / "latest_short.mp4"
OUTPUT_THUMBNAIL = OUTPUT_DIR / "latest_thumbnail.jpg"
OUTPUT_META = OUTPUT_DIR / "latest_meta.json"
OUTPUT_FIRST_FRAME = OUTPUT_DIR / "latest_first_frame.jpg"
OUTPUT_PREVIEW_GIF = OUTPUT_DIR / "latest_preview.gif"
VIDEO_COMPAT_REPORT = OUTPUT_DIR / "video_compat_report.txt"
RUNTIME_DIR = Path("runtime-status")
RUNTIME_META = RUNTIME_DIR / "video-meta.json"

MIN_TARGET_DURATION = 30.0
MAX_TARGET_DURATION = 40.0
TARGET_DURATION = 35.0

main.DEFAULT_VOICE = "tr-TR-EmelNeural"
main.RATE = "-5%"
main.PITCH = "+0Hz"

GENERAL_NICHES = [
    "Şok Edici Psikolojik Gerçekler",
    "Bilinmeyen İnsan Davranışları",
    "Çözülememiş Tarihi Gizemler",
    "Uzayın Korkunç Sırları",
    "Günlük Hayatta Stoacı Felsefe",
    "Başarı Psikolojisi ve Motivasyon",
    "Teknolojinin Karanlık Yüzü",
    "Mitoloji ve Efsanelerin Kökenleri",
    "İnanılmaz Bilimsel Keşifler",
    "Tuhaf ve Enteresan Yasalar",
]

GENERAL_PEXELS_QUERIES = {
    "Şok Edici Psikolojik Gerçekler": ["human brain psychology", "thinking person dark", "mind concept", "neural network abstract", "person thinking cinematic"],
    "Bilinmeyen İnsan Davranışları": ["people walking city", "human behavior", "crowd slow motion", "person thinking", "urban people cinematic"],
    "Çözülememiş Tarihi Gizemler": ["ancient ruins", "old manuscript", "archaeology", "mysterious temple", "ancient history cinematic"],
    "Uzayın Korkunç Sırları": ["deep space", "galaxy stars", "black hole", "astronaut space", "space cinematic"],
    "Günlük Hayatta Stoacı Felsefe": ["ancient statue", "stoic statue", "calm person nature", "roman columns", "meditation nature cinematic"],
    "Başarı Psikolojisi ve Motivasyon": ["person running", "mountain climb", "focused work", "success motivation", "athlete training cinematic"],
    "Teknolojinin Karanlık Yüzü": ["cyber security", "phone screen dark", "data center", "hacker code", "technology dark cinematic"],
    "Mitoloji ve Efsanelerin Kökenleri": ["ancient statue", "greek temple", "ancient ruins", "mythology temple", "old sculpture cinematic"],
    "İnanılmaz Bilimsel Keşifler": ["science laboratory", "microscope", "space telescope", "scientist experiment", "laboratory cinematic"],
    "Tuhaf ve Enteresan Yasalar": ["court law", "judge gavel", "old documents", "city street rules", "law books cinematic"],
}

DEFAULT_TAGS = ["shorts", "youtubeshorts", "viral", "viralshorts", "fyp", "bilgi", "ilgincbilgiler", "turkceshorts", "shortsturkiye", "merakedilenler"]

THUMBNAIL_TEXTS = {
    "Şok Edici Psikolojik Gerçekler": "BEYNİN BUNU YAPIYOR",
    "Bilinmeyen İnsan Davranışları": "İNSANLAR NEDEN BÖYLE",
    "Çözülememiş Tarihi Gizemler": "TARİHTE GİZLİ KALDI",
    "Uzayın Korkunç Sırları": "UZAY BUNU SAKLIYOR",
    "Günlük Hayatta Stoacı Felsefe": "BUNU BİLEN SAKİN KALIR",
    "Başarı Psikolojisi ve Motivasyon": "BAŞARI BÖYLE BAŞLAR",
    "Teknolojinin Karanlık Yüzü": "TEKNOLOJİ BUNU GİZLİYOR",
    "Mitoloji ve Efsanelerin Kökenleri": "EFSANENİN KÖKENİ",
    "İnanılmaz Bilimsel Keşifler": "BİLİM BUNU DEĞİŞTİRDİ",
    "Tuhaf ve Enteresan Yasalar": "BU YASA GERÇEK",
}


def clean_script(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(senaryo|metin|cevap|script|text|answer)\s*:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip().strip('"').strip("'")


def build_prompt(niche: str) -> str:
    return f"""
Sen viral YouTube Shorts metinleri yazan bir uzmansın.
Konu: {niche}
Aşağıdaki kurallara uygun, 30-40 saniyelik bir TÜRKÇE metin yaz:
1. İlk cümle şok edici bir soru veya çarpıcı bir gerçekle başlamalı.
2. Orta kısımda kısa, vurucu cümlelerle ilginç bilgiler ver.
3. Son cümle güçlü bir call-to-action içersin.
4. Emoji, sahne yönü, efekt YOK. Sadece konuşulacak metin.
Yalnızca metni döndür.
""".strip()


def generate_script(niche: str) -> str:
    from g4f.client import Client
    client = Client()
    prompt = build_prompt(niche)
    for attempt in range(4):
        response = client.chat.completions.create(model="gpt-4", messages=[{"role": "user", "content": prompt}], timeout=60)
        script = clean_script(response.choices[0].message.content)
        words = len(script.split())
        if 52 <= words <= 82:
            return script
        main.logger.warning(f"Script word count off target: {words}; retrying")
    return script


async def choose_best_timed_script(niche: str):
    candidates = []
    for _ in range(6):
        script = generate_script(niche)
        audio, word_ts = await main.create_voiceover(script)
        clip = main.AudioFileClip(audio)
        duration = float(clip.duration)
        clip.close()
        candidates.append((abs(TARGET_DURATION - duration), script, audio, word_ts, duration))
        if MIN_TARGET_DURATION <= duration <= MAX_TARGET_DURATION:
            return script, audio, word_ts, duration
    candidates.sort(key=lambda row: row[0])
    _, script, audio, word_ts, duration = candidates[0]
    return script, audio, word_ts, duration


def title_and_thumbnail(niche: str, script: str):
    first = re.split(r"[.!?]", script)[0].strip()
    return f"{first[:82]} #shorts", THUMBNAIL_TEXTS.get(niche, "BUNU BİLİYOR MUYDUN")


def build_tags(niche: str):
    niche_tags = {
        "Şok Edici Psikolojik Gerçekler": ["psikoloji", "beyin", "insanpsikolojisi"],
        "Bilinmeyen İnsan Davranışları": ["insandavranisi", "psikoloji", "sosyoloji"],
        "Çözülememiş Tarihi Gizemler": ["tarih", "gizem", "tarihgizemleri"],
        "Uzayın Korkunç Sırları": ["uzay", "evren", "bilim"],
        "Günlük Hayatta Stoacı Felsefe": ["stoacilik", "felsefe", "hayatdersleri"],
        "Başarı Psikolojisi ve Motivasyon": ["motivasyon", "basari", "disiplin"],
        "Teknolojinin Karanlık Yüzü": ["teknoloji", "yapayzeka", "siber"],
        "Mitoloji ve Efsanelerin Kökenleri": ["mitoloji", "efsane", "tarih"],
        "İnanılmaz Bilimsel Keşifler": ["bilim", "kesif", "bilgiler"],
        "Tuhaf ve Enteresan Yasalar": ["yasalar", "ilginc", "dunya"],
    }
    out = []
    for tag in DEFAULT_TAGS + niche_tags.get(niche, []):
        if tag not in out:
            out.append(tag)
    return out[:15]


def run_cmd(args, check=True):
    main.logger.info("$ " + " ".join(str(x) for x in args))
    return subprocess.run(args, check=check, text=True, capture_output=True)


def prepare_background_for_editing(input_path: str, duration: float) -> str:
    """Make a clean, full-length 1080x1920 background before MoviePy assembly.

    This prevents short Pexels clips from freezing on the last frame or producing
    ffmpeg_reader read warnings during MoviePy loop/crop operations.
    """
    prepared = Path("background_prepared.mp4")
    if prepared.exists():
        prepared.unlink()
    dur = max(float(duration) + 0.75, MIN_TARGET_DURATION)
    run_cmd([
        "ffmpeg", "-y", "-stream_loop", "-1", "-i", str(input_path),
        "-t", f"{dur:.2f}",
        "-vf", "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30",
        "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        str(prepared),
    ])
    return str(prepared)


def normalize_mp4_for_mobile(input_path: str, output_path: Path) -> None:
    tmp = output_path.with_suffix(".tmp.mp4")
    if tmp.exists():
        tmp.unlink()
    run_cmd([
        "ffmpeg", "-y", "-i", str(input_path),
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-profile:v", "main", "-level", "4.0",
        "-movflags", "+faststart",
        "-af", "loudnorm=I=-16:TP=-1.5:LRA=11",
        "-c:a", "aac", "-b:a", "192k", "-shortest", str(tmp),
    ])
    tmp.replace(output_path)


def make_debug_previews(video_path: Path) -> None:
    run_cmd(["ffmpeg", "-y", "-ss", "00:00:02", "-i", str(video_path), "-frames:v", "1", str(OUTPUT_FIRST_FRAME)], check=False)
    run_cmd(["ffmpeg", "-y", "-ss", "00:00:00", "-t", "6", "-i", str(video_path), "-vf", "fps=8,scale=360:-1:flags=lanczos", str(OUTPUT_PREVIEW_GIF)], check=False)
    probe = run_cmd(["ffprobe", "-v", "error", "-show_entries", "format=format_name,duration,size:stream=codec_name,codec_type,pix_fmt,width,height", "-of", "json", str(video_path)], check=False)
    VIDEO_COMPAT_REPORT.write_text(probe.stdout or probe.stderr or "ffprobe produced no output", encoding="utf-8")


def write_meta(meta: dict) -> None:
    OUTPUT_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_META.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


async def run() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    apply_caption_style(main)
    main.NICHE_POOL = GENERAL_NICHES
    main.NICHE_PEXELS_QUERIES = GENERAL_PEXELS_QUERIES

    niche = random.choice(GENERAL_NICHES)
    script, audio, word_ts, duration = await choose_best_timed_script(niche)
    chunked = main.chunk_timestamps(word_ts)
    bg = main.fetch_background_video(script, niche)
    bg = prepare_background_for_editing(bg, duration)
    music = "bg_music.mp3" if main.os.path.exists("bg_music.mp3") else None
    final_path = main.assemble_video(bg, audio, chunked, music)

    title, thumbnail_text = title_and_thumbnail(niche, script)
    tags = build_tags(niche)

    normalize_mp4_for_mobile(final_path, OUTPUT_VIDEO)
    make_debug_previews(OUTPUT_VIDEO)

    thumb_path = make_thumbnail(str(OUTPUT_VIDEO), thumbnail_text, main.ensure_font(), main.logger)
    if thumb_path and Path(thumb_path).exists():
        shutil.copyfile(thumb_path, OUTPUT_THUMBNAIL)

    description = f"{niche} hakkında çarpıcı gerçekler ve ilginç bilgiler.\nHer gün yeni Shorts için takipte kal.\n\n#shorts #bilgi #ilgincbilgiler #turkceshorts"
    meta = {
        "mode": "turkish_general_viral_youtube_upload_with_safe_metadata",
        "language": "tr",
        "voice": main.DEFAULT_VOICE,
        "prompt_style": "general_viral_turkish_quality_guard",
        "niche": niche,
        "caption_style": {
            "font_size": 60,
            "stroke_width": 5,
            "max_words": 1,
            "position": "center",
            "punctuation_removed": True,
            "spaces_removed_inside_caption_word": True,
            "timing": "forced_turkish_speech_weighted_one_word_tight",
        },
        "title": title,
        "thumbnail_text": thumbnail_text,
        "duration_seconds": round(duration, 2),
        "tags": tags,
        "background_queries": GENERAL_PEXELS_QUERIES.get(niche, []),
        "script": script,
        "description": description,
        "video_path": str(OUTPUT_VIDEO),
        "thumbnail_path": str(OUTPUT_THUMBNAIL) if OUTPUT_THUMBNAIL.exists() else None,
        "first_frame_path": str(OUTPUT_FIRST_FRAME) if OUTPUT_FIRST_FRAME.exists() else None,
        "preview_gif_path": str(OUTPUT_PREVIEW_GIF) if OUTPUT_PREVIEW_GIF.exists() else None,
        "compat_report_path": str(VIDEO_COMPAT_REPORT) if VIDEO_COMPAT_REPORT.exists() else None,
        "video_url": None,
        "upload_status": "not_attempted",
        "upload_error": None,
    }
    write_meta(meta)

    try:
        video_url = main.upload_to_youtube(str(OUTPUT_VIDEO), title, description, tags)
        meta["video_url"] = video_url
        meta["upload_status"] = "success"
        main.logger.info(f"Published video: {video_url}")
    except Exception as exc:
        meta["upload_status"] = "failed"
        meta["upload_error"] = str(exc)
        main.logger.error(f"YouTube upload failed but video is saved: {exc}")
    finally:
        write_meta(meta)


if __name__ == "__main__":
    asyncio.run(run())
