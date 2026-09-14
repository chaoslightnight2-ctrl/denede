"""Günde 4 farklı nişte Türkçe Shorts üretir ve zamanlı yayınlar.

Her gün 06:00 / 12:00 / 18:00 / 23:00 (Türkiye) slotlarına birer video planlar;
YouTube'a private + publishAt ile yükler, vaktinde otomatik yayınlanır.
Nişler gün gün dönerek 10 nişin tamamı kapsanır; biten slot diğerlerini bozmaz.

Kullanım (freefaceless/ içinde):
  python -m src.daily_batch              # 4 video üret + zamanlı yayınla
  python -m src.daily_batch --no-upload  # kuru test, yükleme YOK
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from . import pipeline
from .config import ROOT
from .script import TURKISH_NICHES

TZ = ZoneInfo("Europe/Istanbul")
SLOTS = [("0600", 6), ("1200", 12), ("1800", 18), ("2300", 23)]
MANIFEST = ROOT / "daily_manifest.json"


def pick_niches(count: int = 4) -> list[str]:
    """Her gün kayan 4'lü niş seti; 5 günde 10 nişin tamamı dönülür."""
    start = (datetime.now(TZ).date().toordinal() * count) % len(TURKISH_NICHES)
    return [TURKISH_NICHES[(start + i) % len(TURKISH_NICHES)] for i in range(count)]


def publish_time(hour: int) -> datetime:
    now = datetime.now(TZ)
    target = datetime.combine(now.date(), time(hour, 0), TZ)
    if target <= now + timedelta(minutes=15):
        target += timedelta(days=1)
    return target


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-upload", action="store_true", help="Yükleme yapma (kuru test)")
    args = ap.parse_args()

    niches = pick_niches()
    manifest = []
    seen_topics: set[str] = set()
    for (slot, hour), niche in zip(SLOTS, niches):
        at = publish_time(hour)
        utc = at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        print(f"[{slot}] {niche} -> {at.isoformat()}", flush=True)
        res = None
        try:
            res = pipeline.run_once(
                niche=niche,
                publish_at=None if args.no_upload else utc,
                upload_to_youtube=not args.no_upload,
            )
            # Aynı gün içinde konu tekrarı olursa tek seferlik yeniden üret.
            if res["topic"] in seen_topics:
                print(f"[{slot}] konu tekrarı ({res['topic']}), yeniden üretiliyor...", flush=True)
                res = pipeline.run_once(
                    niche=niche,
                    publish_at=None if args.no_upload else utc,
                    upload_to_youtube=not args.no_upload,
                    avoid_extra=res["topic"],
                )
            seen_topics.add(res["topic"])
        except Exception as exc:
            print(f"[{slot}] HATA (diğer slotlar devam edecek): {exc}", flush=True)
            manifest.append({"slot": slot, "niche": niche, "ok": False, "error": str(exc)})
            continue
        manifest.append({
            "slot": slot,
            "niche": niche,
            "ok": True,
            "scheduled_publish_at_turkey": at.isoformat(),
            "scheduled_publish_at_utc": None if args.no_upload else utc,
            **res,
        })
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for m in manifest if m["ok"])
    print(f"Bitti: {ok}/4 video.")
    if ok == 0:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
