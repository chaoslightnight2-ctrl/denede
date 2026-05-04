"""Runtime hardening for GitHub Actions.

Python imports this file automatically at startup when it is present on sys.path.
It replaces MoviePy's ImageMagick-based TextClip with a PIL-backed clip so
subtitles render reliably in CI and stay centered on 1080x1920 Shorts videos.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger(__name__)


def _load_font(font, fontsize):
    candidates = []
    if font:
        candidates.append(str(font))
    candidates.extend([
        "fonts/Montserrat-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ])
    for candidate in candidates:
        try:
            if Path(candidate).exists() or candidate.startswith("/"):
                return ImageFont.truetype(candidate, fontsize)
        except Exception:
            pass
    return ImageFont.load_default()


def _wrap_text(draw, text, font, max_width):
    words = str(text).split()
    if not words:
        return ""
    lines = []
    current = ""
    for word in words:
        trial = word if not current else current + " " + word
        box = draw.textbbox((0, 0), trial, font=font)
        if box[2] - box[0] <= max_width or not current:
            current = trial
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return "\n".join(lines)


def _make_pil_textclip():
    from moviepy.editor import ImageClip

    class PILTextClip(ImageClip):
        def __init__(self, txt, fontsize=70, color="white", font=None,
                     stroke_color="black", stroke_width=0, method="label",
                     size=None, align="center", transparent=True, **kwargs):
            max_width = None
            if size and size[0]:
                max_width = int(size[0])
            canvas_width = max_width or 1080
            canvas_height = 420
            pil_font = _load_font(font, int(fontsize))

            scratch = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(scratch)
            text = str(txt).upper()
            if method == "caption" and max_width:
                text = _wrap_text(draw, text, pil_font, max_width)

            box = draw.multiline_textbbox((0, 0), text, font=pil_font, stroke_width=int(stroke_width), spacing=8)
            text_width = box[2] - box[0]
            text_height = box[3] - box[1]
            pad = max(int(fontsize * 0.25), int(stroke_width) + 12)
            image_width = max(canvas_width, text_width + pad * 2)
            image_height = max(text_height + pad * 2, int(fontsize * 1.7))
            image = Image.new("RGBA", (image_width, image_height), (0, 0, 0, 0))
            draw = ImageDraw.Draw(image)
            x = (image_width - text_width) / 2
            y = (image_height - text_height) / 2
            draw.multiline_text(
                (x, y), text, font=pil_font, fill=color,
                stroke_width=int(stroke_width), stroke_fill=stroke_color,
                align=align, spacing=8,
            )
            super().__init__(np.array(image), transparent=transparent)

    return PILTextClip


try:
    import moviepy.editor as editor
    import moviepy.video.VideoClip as video_clip

    patched = _make_pil_textclip()
    editor.TextClip = patched
    video_clip.TextClip = patched
    log.info("MoviePy TextClip patched with PILTextClip")
except Exception as exc:
    log.warning("Could not patch MoviePy TextClip: %s", exc)
