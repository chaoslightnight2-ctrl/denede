"""Custom thumbnail helper for generated Shorts.

Creates a 1280x720 JPEG from the generated video and uploads it as the
YouTube thumbnail. This module is intentionally best-effort: thumbnail errors
must not fail a successfully uploaded video.
"""

from __future__ import annotations

import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import VideoFileClip
from googleapiclient.http import MediaFileUpload

THUMBNAIL_FILE = "thumbnail.jpg"
THUMBNAIL_SIZE = (1280, 720)


def _load_font(font_path: str, size: int):
    candidates = [
        font_path,
        "fonts/Montserrat-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        try:
            if candidate and os.path.exists(candidate):
                return ImageFont.truetype(candidate, size)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    words = text.split()
    lines = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        box = draw.textbbox((0, 0), trial, font=font, stroke_width=5)
        if box[2] - box[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines[:3]


def make_thumbnail(video_path: str, thumbnail_text: str, font_path: str, logger=None) -> Optional[str]:
    try:
        clip = VideoFileClip(video_path)
        frame_time = min(0.8, max(clip.duration / 3, 0.1))
        frame = clip.get_frame(frame_time)
        clip.close()

        image = Image.fromarray(frame).convert("RGB").resize(THUMBNAIL_SIZE)
        overlay = Image.new("RGBA", THUMBNAIL_SIZE, (0, 0, 0, 135))
        image = Image.alpha_composite(image.convert("RGBA"), overlay)
        draw = ImageDraw.Draw(image)

        font = _load_font(font_path, 86)
        small_font = _load_font(font_path, 34)
        text = (thumbnail_text or "KİMSE AÇIKLAYAMIYOR").upper()
        lines = _wrap_text(draw, text, font, THUMBNAIL_SIZE[0] - 120)

        y = (THUMBNAIL_SIZE[1] - len(lines) * 96) // 2
        for line in lines:
            box = draw.textbbox((0, 0), line, font=font, stroke_width=6)
            x = (THUMBNAIL_SIZE[0] - (box[2] - box[0])) // 2
            draw.text((x, y), line, font=font, fill="white", stroke_width=6, stroke_fill="black")
            y += 96

        footer = "KORKU • GİZEM • DOSYA"
        box = draw.textbbox((0, 0), footer, font=small_font, stroke_width=2)
        draw.text(
            ((THUMBNAIL_SIZE[0] - (box[2] - box[0])) // 2, THUMBNAIL_SIZE[1] - 78),
            footer,
            font=small_font,
            fill="white",
            stroke_width=2,
            stroke_fill="black",
        )
        image.convert("RGB").save(THUMBNAIL_FILE, "JPEG", quality=92)
        if logger:
            logger.info(f"🖼️ Thumbnail oluşturuldu: {THUMBNAIL_FILE}")
        return THUMBNAIL_FILE
    except Exception as exc:
        if logger:
            logger.warning(f"Thumbnail oluşturulamadı; video yine de devam edecek: {exc}")
        return None


def upload_thumbnail(youtube, video_id: str, thumbnail_path: Optional[str], logger=None) -> bool:
    if not thumbnail_path or not os.path.exists(thumbnail_path):
        return False
    try:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path, mimetype="image/jpeg"),
        ).execute()
        if logger:
            logger.info("🖼️ Thumbnail yüklendi.")
        return True
    except Exception as exc:
        if logger:
            logger.warning(f"Thumbnail yüklenemedi; video yayında kaldı: {exc}")
        return False
