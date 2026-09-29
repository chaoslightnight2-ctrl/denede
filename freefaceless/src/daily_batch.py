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
    ap.add_argument("--retry-failed", action="store_true",
                    help="Manifestte başarısız olan slotları tekrar dene; başarılı yüklemelere dokunma")
    args = ap.parse_args()

    if args.private_smoke and args.retry_failed:
        ap.error("--private-smoke ile --retry-failed birlikte kullanılamaz")
    if args.retry_failed and args.no_upload:
        ap.error("--retry-failed gerçek yükleme içindir; --no-upload ile kullanılamaz")
    if args.private_smoke:
        args.limit = 1

    previous = []
    if args.retry_failed:
        if not MANIFEST.exists():
            raise SystemExit("Başarısız slot manifesti yok; yükleme durduruldu.")
        try:
            previous = json.loads(MANIFEST.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as exc:
            raise SystemExit(f"Başarısız slot manifesti okunamadı; yükleme durduruldu: {exc}")
        if not isinstance(previous, list):
            raise SystemExit("Başarısız slot manifesti liste değil; yükleme durduruldu.")
        targets = [row for row in previous if not row.get("ok")]
        manifest = list(previous)
        if not targets:
            print("Yeniden denenecek başarısız slot yok; yeni video yüklenmedi.", flush=True)
            return
    else:
        targets = None
        manifest = []

    if args.retry_failed:
        selected_targets = []
        for row in targets:
            slot = str(row.get("slot", ""))
            match = next(((key, hour) for key, hour in SLOTS if key == slot), None)
            niche = row.get("niche")
            if not match or not niche:
                raise SystemExit(f"Başarısız manifest satırı eksik/geçersiz: slot={slot!r}, niche={niche!r}")
            selected_targets.append((slot, match[1], publish_time(match[1]), niche))
    else:
        niches = pick_niches(args.limit)
        planned_slots = sorted(
            ((slot, hour, publish_time(hour)) for slot, hour in SLOTS[:args.limit]),
            key=lambda entry: entry[2],
        )
        selected_targets = [(slot, hour, at, niche)
                            for (slot, hour, at), niche in zip(planned_slots, niches)]

    seen_topics: set[str] = set()
    for slot, hour, at, niche in selected_targets:
        utc = at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        print(f"[{slot}] {niche} -> {at.isoformat()}", flush=True)
        try:
            res = pipeline.run_once(
                niche=niche,
                publish_at=None if args.no_upload or args.private_smoke else utc,
                upload_to_youtube=not args.no_upload,
            )
            if res["topic"] in seen_topics:
                print(f"[{slot}] konu tekrarı ({res['topic']}), yeniden üretiliyor...", flush=True)
                res = pipeline.run_once(
                    niche=niche,
                    publish_at=None if args.no_upload or args.private_smoke else utc,
                    upload_to_youtube=not args.no_upload,
                    avoid_extra=res["topic"],
                )
            seen_topics.add(res["topic"])
            result_row = {
                "slot": slot,
                "niche": niche,
                "ok": True,
                "scheduled_publish_at_turkey": at.isoformat(),
                "scheduled_publish_at_utc": None if args.no_upload else utc,
                **res,
            }
        except Exception as exc:
            print(f"[{slot}] HATA (diğer slotlar devam edecek): {exc}", flush=True)
            result_row = {"slot": slot, "niche": niche, "ok": False, "error": str(exc)}

        if args.retry_failed:
            index = next(i for i, row in enumerate(manifest) if row.get("slot") == slot and not row.get("ok"))
            manifest[index] = result_row
        else:
            manifest.append(result_row)

    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    ok = sum(1 for row in manifest if row.get("ok"))
    print(f"Bitti: {ok}/{len(manifest)} video.", flush=True)
    if ok != len(manifest):
        failed = [f"{row.get('slot')}: {row.get('error', 'video tamamlanmadı')}"
                  for row in manifest if not row.get("ok")]
        raise SystemExit(
            f"İstenen {len(manifest)} videonun tamamı yüklenmedi ({ok}/{len(manifest)}). "
            f"Hatalı slotlar: {'; '.join(failed)}"
        )


if __name__ == "__main__":
    main()
