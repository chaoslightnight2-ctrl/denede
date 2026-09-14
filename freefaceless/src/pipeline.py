import argparse
import re
from datetime import datetime
from . import script, voice, captions, visuals, assemble, upload, state
from .config import OUTPUT_DIR


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "short"


def run_once(niche: str | None = None, publish_at: str | None = None,
             upload_to_youtube: bool = True) -> dict:
    print("[1/7] Groq ile senaryo üretiliyor")
    data = script.generate(niche=niche)
    print(f"      topic: {data['topic']}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work = OUTPUT_DIR / f"{stamp}_{slug(data['topic'])}"
    work.mkdir(parents=True, exist_ok=True)

    print("[2/7] Seslendirme")
    voice_mp3 = voice.synth(data["full_text"], work / "voice.mp3")

    print("[3/7] faster-whisper kelime zaman damgası")
    words = captions.transcribe_words(voice_mp3)

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
