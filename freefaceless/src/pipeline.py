import argparse
import re
from datetime import datetime
from . import script, voice, captions, visuals, assemble, upload, state
from .config import OUTPUT_DIR


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "short"


MIN_VOICE_SECONDS = 28.0
MAX_VOICE_SECONDS = 38.0
TARGET_VOICE_SECONDS = 32.0
MAX_SCRIPT_TRIES = 3


def _pick_script(niche: str | None, avoid_extra: str = "") -> tuple[dict, object, list, float, object]:
    """Süre hedefini tutturan senaryo+seslendirme seçimi (en fazla 3 deneme)."""
    best = None
    for attempt in range(1, MAX_SCRIPT_TRIES + 1):
        data = script.generate(niche=niche, avoid_extra=avoid_extra if attempt > 1 else "")
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work = OUTPUT_DIR / f"{stamp}_{slug(data['topic'])}"
        work.mkdir(parents=True, exist_ok=True)
        voice_mp3 = voice.synth(data["full_text"], work / "voice.mp3")
        words = captions.transcribe_words(voice_mp3)
        duration = float(words[-1]["end"]) if words else 0.0
        print(f"      deneme {attempt}: topic={data['topic']} sure={duration:.1f}sn kelime={len(data['full_text'].split())}", flush=True)
        cand = (abs(TARGET_VOICE_SECONDS - duration), data, work, voice_mp3, words, duration)
        if best is None or cand[0] < best[0]:
            best = cand
        if MIN_VOICE_SECONDS <= duration <= MAX_VOICE_SECONDS:
            return data, work, voice_mp3, words, duration
    _, data, work, voice_mp3, words, duration = best
    if not words:
        raise RuntimeError("Seslendirmeden kelime zaman damgası çıkarılamadı.")
    print(f"      en yakın aday seçildi: sure={duration:.1f}sn", flush=True)
    return data, work, voice_mp3, words, duration


def run_once(niche: str | None = None, publish_at: str | None = None,
             upload_to_youtube: bool = True, avoid_extra: str = "") -> dict:
    print("[1/7] Groq ile senaryo üretiliyor")
    data, work, voice_mp3, words, duration = _pick_script(niche, avoid_extra)
    print(f"      topic: {data['topic']} ({duration:.1f}sn)")
    stamp = work.name.split("_")[0] + "_" + work.name.split("_")[1]

    print("[2-3/7] Seslendirme + kelime zaman damgası hazır")

    print("[4/7] Pexels b-roll")
    scene_videos = visuals.fetch_for_scenes(data["scenes"], work / "broll")

    print("[5/7] Altyazı dosyası")
    from .config import CONFIG as CFG
    ass_path = captions.write_ass(words, work / "captions.ass",
                                  CFG["video"]["width"], CFG["video"]["height"])

    print("[6/7] ffmpeg montaj")
    final = assemble.build(
        scene_videos=scene_videos,
        voice_audio=voice_mp3,
        captions_ass=ass_path,
        words=words,
        scenes=data["scenes"],
        out_path=work / "final.mp4",
        work_dir=work / "ffmpeg",
    )
    print(f"      output: {final}")

    video_id = None
    if upload_to_youtube:
        print("[7/7] YouTube yükleme")
        video_id = upload.upload_video(
            video_path=final,
            title=data["title"],
            description=data["description"],
            tags=data["tags"],
            publish_at=publish_at,
        )
        print(f"      video_id: {video_id} -> https://youtube.com/shorts/{video_id}")

    state.add_topic(data["topic"])
    state.add_published({
        "ts": stamp,
        "topic": data["topic"],
        "title": data["title"],
        "path": str(final),
        "video_id": video_id,
        "publish_at": publish_at,
    })
    return {"video_id": video_id, "path": str(final), "topic": data["topic"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--no-upload", action="store_true", help="Sadece üret, yükleme")
    p.add_argument("--niche", default=None, help="Tek nişe zorla (10 Türkçe nişten biri)")
    p.add_argument("--publish-at", default=None,
                   help="Zamanlı yayın için ISO8601 UTC, örn. 2026-05-20T14:00:00Z")
    args = p.parse_args()
    if args.niche and args.niche not in script.TURKISH_NICHES:
        raise SystemExit(f"Bilinmeyen niş: {args.niche}\nSeçenekler: {', '.join(script.TURKISH_NICHES)}")
    run_once(niche=args.niche, publish_at=args.publish_at,
             upload_to_youtube=not args.no_upload)

    print("\n" + "-" * 60)
    print("Bitti. Orijinal proje: https://github.com/nils44344/FreeFaceless")
    print("-" * 60)


if __name__ == "__main__":
    main()
