import argparse
import json
import re
import os
from datetime import datetime
from zoneinfo import ZoneInfo
from .publish_schedule import next_slot
from . import script, voice, captions, visuals, assemble, upload, state
from .quality import validate_rendered_video
from .config import OUTPUT_DIR


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "short"


MIN_VOICE_SECONDS = 18.0
MAX_VOICE_SECONDS = 30.0
TARGET_VOICE_SECONDS = 24.0
MAX_SCRIPT_TRIES = 3


def _pick_script(niche: str | None, avoid_extra: str = "") -> tuple[dict, object, list, float, object]:
    """Süre hedefini tutturan senaryo+seslendirme seçimi (en fazla 3 deneme)."""
    best = None
    for attempt in range(1, MAX_SCRIPT_TRIES + 1):
        data = script.generate(niche=niche, avoid_extra=avoid_extra)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        work = OUTPUT_DIR / f"{stamp}_{slug(data['topic'])}"
        work.mkdir(parents=True, exist_ok=True)
        # Preserve the exact source, original response and prepared speech before
        # TTS, so a render failure cannot erase the evidence for manual review.
        (work / 'script.json').write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
        voice_mp3 = voice.synth(data["tts_text"], work / "voice.mp3")
        words = captions.transcribe_words(voice_mp3)
        duration = float(words[-1]["end"]) if words else 0.0
        print(f"      deneme {attempt}: topic={data['topic']} sure={duration:.1f}sn kelime={len(data['full_text'].split())}", flush=True)
        cand = (abs(TARGET_VOICE_SECONDS - duration), data, work, voice_mp3, words, duration)
        if best is None or cand[0] < best[0]:
            best = cand
        if MIN_VOICE_SECONDS <= duration <= MAX_VOICE_SECONDS:
            return data, work, voice_mp3, words, duration
    raise RuntimeError(f"Üç aynı Groq denemesi ses süresini 18-30 saniyeye sığdıramadı; en yakın aday kullanılmadı")


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
                                  CFG["video"]["width"], CFG["video"]["height"], audio_path=voice_mp3)

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
    validate_rendered_video(final)
    print(f"      output: {final}")

    video_id = None
    if upload_to_youtube:
        # Refresh stale scheduled times after any provider wait and rendering.
        if publish_at:
            at = next_slot(datetime.now(ZoneInfo('Europe/Istanbul')), state.load().get('published', []),
                           int(os.getenv('DAILY_VIDEO_COUNT', '3')),
                           preferred=datetime.fromisoformat(publish_at.replace('Z', '+00:00')))
            publish_at = at.astimezone(ZoneInfo('UTC')).isoformat().replace('+00:00', 'Z')
        print("[7/7] YouTube yükleme")
        video_id = upload.upload_video(
            video_path=final,
            title=data["title"],
            description=data["description"],
            tags=data["tags"],
            publish_at=publish_at,
        )
        print(f"      video_id: {video_id} -> https://youtube.com/shorts/{video_id}")

    if upload_to_youtube:
        state.add_topic(data["topic"])
    if upload_to_youtube:
        state.add_published({
        "ts": stamp,
        "topic": data["topic"],
        "audience_bucket": data.get("audience_bucket"),
        "hook_style": data.get("hook_style"),
        "title": data["title"],
        "path": str(final),
        "video_id": video_id,
        "publish_at": publish_at,
        "upload_status": "api_insert_confirmed",
        "run_id": os.getenv('GITHUB_RUN_ID'),
    })
    receipt = {}
    if upload_to_youtube:
        from .upload_checkpoint import checkpoint
        checkpoint(['state.json'])
        from .youtube_receipt import confirm
        # ID already persisted above; a failed readback must not repeat insert.
        try:
            receipt = confirm(upload.get_service(), video_id)
        except Exception as exc:
            receipt = {"upload_status": "youtube_rejected" if isinstance(exc, ValueError) else "api_insert_confirmed",
                       "verification_error": str(exc)}
    if upload_to_youtube:
        current = state.load()
        for row in current["published"]:
            if row.get("video_id") == video_id:
                row.update(receipt)
        state.save(current)
    return {"video_id": video_id, "path": str(final), "topic": data["topic"], "title": data["title"], "narration": data["spoken_text"], "publish_at": publish_at, **receipt}


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
