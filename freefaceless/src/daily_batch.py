"""Günde 6 farklı nişte Türkçe Shorts üretir ve zamanlı yayınlar.

Her gün 04:00 / 08:00 / 12:00 / 16:00 / 20:00 / 00:00 (Türkiye) slotlarına birer video planlar;
YouTube'a private + publishAt ile yükler, vaktinde otomatik yayınlanır; 4 kanalda günlük toplam 24 yükleme planlanır.
Nişler gün gün dönerek 15 konu alanının tamamını kapsar; biten slot diğerlerini bozmaz.

Kullanım (freefaceless/ içinde):
  python -m src.daily_batch              # 6 video üret + zamanlı yayınla
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
SLOTS = [("0400", 4), ("0800", 8), ("1200", 12), ("1600", 16), ("2000", 20), ("0000", 0)]
MANIFEST = ROOT / "daily_manifest.json"


def pick_niches(count: int = 6) -> list[str]:
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
    ap.add_argument("--limit", type=int, choices=range(1, 7), default=6,
                    help="Sadece ilk N slotu çalıştır")
    ap.add_argument("--private-smoke", action="store_true",
                    help="Tek bir videoyu gizli yükle, yayın zamanı ayarlama")
    args = ap.parse_args()

    if args.private_smoke:
        args.limit = 1
    niches = pick_niches(args.limit)
    manifest = []
    seen_topics: set[str] = set()
    planned_slots = sorted(
        ((slot, hour, publish_time(hour)) for slot, hour in SLOTS[:args.limit]),
        key=lambda entry: entry[2],
    )
    for (slot, hour, at), niche in zip(planned_slots, niches):
        utc = at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        print(f"[{slot}] {niche} -> {at.isoformat()}", flush=True)
        res = None
        try:
            res = pipeline.run_once(
                niche=niche,
                publish_at=None if args.no_upload or args.private_smoke else utc,
                upload_to_youtube=not args.no_upload,
            )
            # Aynı gün içinde konu tekrarı olursa tek seferlik yeniden üret.
            if res["topic"] in seen_topics:
                print(f"[{slot}] konu tekrarı ({res['topic']}), yeniden üretiliyor...", flush=True)
                res = pipeline.run_once(
                    niche=niche,
                    publish_at=None if args.no_upload or args.private_smoke else utc,
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
    print(f"Bitti: {ok}/{args.limit} video.")
    if ok != args.limit:
        failed = [f"{m['slot']}: {m.get('error', 'video tamamlanmadı')}" for m in manifest if not m.get("ok")]
        details = "; ".join(failed)
        raise SystemExit(f"İstenen {args.limit} videonun tamamı yüklenmedi ({ok}/{args.limit}). Hatalı slotlar: {details}")


if __name__ == "__main__":
    main()
