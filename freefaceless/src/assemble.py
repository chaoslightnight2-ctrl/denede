import json
import subprocess
from pathlib import Path
from .config import CONFIG, ROOT


def _run(cmd: list[str]):
    p = subprocess.run(cmd, capture_output=True, text=True, errors="replace")
    if p.returncode != 0:
        tail = (p.stderr or "")[-4000:]
        raise RuntimeError(
            f"Command failed (exit {p.returncode}): {cmd[0]} ...\n--- ffmpeg stderr ---\n{tail}"
        )


def probe_duration(path: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "json", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(json.loads(r.stdout)["format"]["duration"])


def _scene_durations(words: list[dict], scenes: list[dict], audio_duration: float | None = None) -> list[float]:
    if not words or not scenes:
        raise ValueError("Sahne veya gerçek kelime zamanı yok")
    from .quality import clean_spoken
    expected = clean_spoken(" ".join(scene["text"] for scene in scenes)).casefold().split()
    actual = clean_spoken(" ".join(word["word"] for word in words)).casefold().split()
    if actual != expected:
        raise ValueError("Sahne metni gerçek TTS kelimeleriyle uyuşmuyor")
    starts = [0.0]
    cursor = 0
    for scene in scenes[:-1]:
        cursor += len(clean_spoken(scene["text"]).split())
        starts.append(float(words[cursor]["start"]))
    end = audio_duration if audio_duration is not None else float(words[-1]["end"])
    boundaries = starts + [end]
    durations = [stop - start for start, stop in zip(boundaries, boundaries[1:])]
    if any(duration <= 0 for duration in durations):
        raise ValueError("Sahne süreleri geçersiz")
    return durations


def _prep_scene_clip(src: Path, target_dur: float, out_path: Path, w: int, h: int, fps: int):
    src_dur = probe_duration(src)
    from .stock_frames import visible_start
    offset = visible_start(src, src_dur)
    if offset:
        trimmed = out_path.with_name(out_path.stem + '_visible.mp4')
        _run(['ffmpeg', '-y', '-ss', str(offset), '-i', str(src), '-an',
              '-c:v', 'libx264', '-preset', 'fast', '-crf', '20', str(trimmed)])
        src = trimmed
        src_dur = probe_duration(src)
    vf = (
        f"scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},setsar=1,fps={fps}"
    )
    if src_dur >= target_dur:
        _run([
            "ffmpeg", "-y", "-ss", "0", "-t", f"{target_dur:.3f}", "-i", str(src),
            "-vf", vf, "-an", "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p", str(out_path),
        ])
    else:
        loops = int(target_dur // src_dur) + 1
        _run([
            "ffmpeg", "-y", "-stream_loop", str(loops), "-i", str(src),
            "-t", f"{target_dur:.3f}", "-vf", vf, "-an",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-pix_fmt", "yuv420p", str(out_path),
        ])


def build(
    scene_videos: list[Path],
    voice_audio: Path,
    captions_ass: Path,
    words: list[dict],
    scenes: list[dict],
    out_path: Path,
    work_dir: Path,
) -> Path:
    v = CONFIG["video"]
    w, h, fps = v["width"], v["height"], v["fps"]
    work_dir.mkdir(parents=True, exist_ok=True)

    audio_duration = probe_duration(voice_audio)
    durations = _scene_durations(words, scenes, audio_duration)
    prepped = []
    for i, (src, dur) in enumerate(zip(scene_videos, durations)):
        out = work_dir / f"prep_{i:02d}.mp4"
        _prep_scene_clip(src, dur, out, w, h, fps)
        prepped.append(out)

    concat_list = work_dir / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{p.as_posix()}'" for p in prepped),
        encoding="utf-8",
    )

    silent = work_dir / "silent.mp4"
    _run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy", str(silent),
    ])

    # Uyarlama: assets/fonts yoksa fontsdir atlanır (orijinalde klasör varsayılırdı).
    ass_arg = str(captions_ass).replace("\\", "/").replace(":", "\\:")
    vf_sub = f"tpad=stop_mode=clone:stop_duration=1,subtitles='{ass_arg}'"
    fonts_dir = ROOT / "assets" / "fonts"
    if fonts_dir.exists():
        fonts_arg = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
        vf_sub += f":fontsdir='{fonts_arg}'"
    _run([
        "ffmpeg", "-y", "-i", str(silent), "-i", str(voice_audio),
        "-vf", vf_sub,
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
        "-t", f"{audio_duration:.3f}", "-movflags", "+faststart",
        str(out_path),
    ])
    if probe_duration(out_path) < audio_duration - 0.2:
        raise ValueError("Final video sesin sonunu kesiyor; yükleme engellendi")
    return out_path
