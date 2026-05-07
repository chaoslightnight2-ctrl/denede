#!/usr/bin/env python3
from __future__ import annotations

import asyncio
import json
import random
import re
import shutil
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import turkish_upload_runner as runner

TZ = ZoneInfo("Europe/Istanbul")
SLOTS = [("0600", 6), ("1200", 12), ("1800", 18), ("2300", 23)]
OUT = Path("generated-videos")
OUT.mkdir(exist_ok=True)

SCENARIOS = {
    "Şok Edici Psikolojik Gerçekler": ["tanıdıklık yanılgısı", "zihnin boşluk doldurması", "karar yorgunluğu", "sessiz sosyal baskı"],
    "Bilinmeyen İnsan Davranışları": ["kalabalıkta sorumluluk dağılması", "erteleyerek öncelik gösterme", "ilk izlenim tuzağı", "taklit davranışları"],
    "Çözülememiş Tarihi Gizemler": ["unutulmuş kayıtlar", "kaybolan topluluklar", "okunamayan semboller", "yarım kalan keşifler"],
    "Uzayın Korkunç Sırları": ["görünmeyen evren", "zamanın bükülmesi", "yıldızların ölümü", "kozmik sessizlik"],
    "Günlük Hayatta Stoacı Felsefe": ["tepkiyi seçmek", "kontrol ayrımı", "küçük sabır pratiği", "iç sakinlik"],
    "Başarı Psikolojisi ve Motivasyon": ["tekrarın gücü", "görünmeyen disiplin", "erken vazgeçme", "küçük alışkanlıklar"],
    "Teknolojinin Karanlık Yüzü": ["dikkat ekonomisi", "veri izleri", "bildirim bağımlılığı", "algoritmik yönlendirme"],
    "Mitoloji ve Efsanelerin Kökenleri": ["ortak insan korkuları", "kahraman yolculuğu", "doğaya anlam verme", "yasak bilgi efsaneleri"],
    "İnanılmaz Bilimsel Keşifler": ["hatalardan doğan keşifler", "görünmeyeni gösteren araçlar", "merakın etkisi", "eski soruya yeni bakış"],
    "Tuhaf ve Enteresan Yasalar": ["kuralların arkasındaki hikaye", "kültür farkı", "şehir efsanesi sanılan kurallar", "günlük davranışların anlamı"],
}


def clean(text: str) -> str:
    text = re.sub(r"[*#_`>\[\]{}]", "", text or "")
    text = re.sub(r"(?i)^(senaryo|metin|cevap|script|text|answer)\s*:\s*", "", text.strip())
    return re.sub(r"\s+", " ", text).strip().strip('"').strip("'")


def prompt_for(niche: str, angle: str) -> str:
    return f"""
Türkçe YouTube Shorts için tek parça konuşma metni yaz.
Konu: {niche}
Özgün açı: {angle}
Süre hedefi: 30-40 saniye.
Kelime hedefi: 55-75 kelime.
Kurallar: Tek ana fikir üzerinden ilerle. Cümleler birbirine anlamca bağlı olsun. Rastgele ülke, olay veya bilgi listesi yapma. Boş clickbait, çeviri kokan ifade, düşük cümle ve anlatım bozukluğu kullanma. Kesin sayı, ceza, yasa veya tıbbi iddia uydurma. En fazla iki soru cümlesi kullan. Son cümle doğal bir yorum veya takip çağrısı olsun. Sadece konuşulacak metni yaz.
""".strip()


def issues(text: str) -> list[str]:
    t = clean(text)
    low = t.lower()
    words = t.split()
    out = []
    if len(words) < 50 or len(words) > 86:
        out.append(f"word_count={len(words)}")
    if t.count(":") > 1:
        out.append("too_many_colons")
    if t.count("?") > 2:
        out.append("too_many_questions")
    if re.search(r"^[^.!?]{0,28}:\s*", t):
        out.append("headline_colon_opening")
    if re.search(r"\b(yok|değil)\b.{0,35}\b(ama|fakat)\b.{0,45}\?", low):
        out.append("contradictory_question")
    if any(x in low for x in ["vergi suçu", "oburluk yasası", "hayatınızı değiştirecek:"]):
        out.append("known_bad_phrase")
    countries = ["almanya", "japonya", "ingiltere", "amerika", "arizona", "türkiye"]
    if sum(1 for c in countries if c in low) > 3:
        out.append("random_country_list")
    if len([s for s in re.split(r"[.!?]+", t) if s.strip()]) < 5:
        out.append("too_few_sentences")
    return out


def fallback_script(niche: str) -> str:
    options = runner.FALLBACK_SCRIPTS.get(niche) or [s for values in runner.FALLBACK_SCRIPTS.values() for s in values]
    good = [clean(s) for s in options if not issues(s)]
    return random.choice(good or [clean(random.choice(options))])


def generate_script(niche: str) -> str:
    best = ""
    best_count = 999
    try:
        from g4f.client import Client
        client = Client()
    except Exception as exc:
        runner.main.logger.warning("generator unavailable, fallback used: %s", exc)
        return fallback_script(niche)

    for attempt in range(7):
        angle = random.choice(SCENARIOS.get(niche) or ["tek ana fikir"])
        try:
            response = client.chat.completions.create(
                model="gpt-4",
                messages=[{"role": "user", "content": prompt_for(niche, angle)}],
                timeout=60,
            )
            script = clean(response.choices[0].message.content)
            bad = issues(script)
            if len(bad) < best_count:
                best = script
                best_count = len(bad)
            if not bad:
                runner.main.logger.info("Accepted script try=%d angle=%s", attempt + 1, angle)
                return script
            runner.main.logger.warning("Rejected script, regenerating: %s", ",".join(bad))
        except Exception as exc:
            runner.main.logger.warning("Script generation failed try=%d: %s", attempt + 1, exc)
    if best and best_count <= 1:
        return best
    return fallback_script(niche)


def publish_time(hour: int) -> datetime:
    now = datetime.now(TZ)
    target = datetime.combine(now.date(), time(hour, 0), TZ)
    if target <= now + timedelta(minutes=15):
        target += timedelta(days=1)
    return target


def scheduled_uploader(publish_at: datetime, slot: str):
    def upload(video_path, title, description, tags=None):
        if "#shorts" not in title.lower():
            title = f"{title} #shorts"
        utc_time = publish_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        youtube = runner.main.get_youtube_service()
        body = {
            "snippet": {
                "title": title[:100],
                "description": description[:5000],
                "tags": tags or ["shorts", "youtubeshorts", "turkceshorts"],
                "categoryId": runner.main.YOUTUBE_CATEGORY_ID,
            },
            "status": {
                "privacyStatus": "private",
                "publishAt": utc_time,
                "selfDeclaredMadeForKids": False,
            },
        }
        runner.main.logger.info("Scheduling slot=%s publishAt=%s", slot, utc_time)
        media = runner.main.MediaFileUpload(video_path, mimetype="video/mp4", resumable=True, chunksize=5 * 1024 * 1024)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status, resp = request.next_chunk()
            if status:
                runner.main.logger.info("Upload slot=%s progress=%s", slot, int(status.progress() * 100))
        return f"https://youtu.be/{resp['id']}"
    return upload


def copy_slot_files(slot: str, publish_at: datetime, index: int) -> dict:
    for src_name, dst_name in [
        ("latest_short.mp4", f"short_{slot}.mp4"),
        ("latest_thumbnail.jpg", f"thumbnail_{slot}.jpg"),
        ("latest_first_frame.jpg", f"first_frame_{slot}.jpg"),
        ("latest_preview.gif", f"preview_{slot}.gif"),
        ("video_compat_report.txt", f"compat_{slot}.txt"),
    ]:
        src = OUT / src_name
        if src.exists():
            shutil.copyfile(src, OUT / dst_name)
    meta_path = OUT / "latest_meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta.update({
        "batch_index": index,
        "schedule_slot_turkey": slot,
        "scheduled_publish_at_turkey": publish_at.isoformat(),
        "scheduled_publish_at_utc": publish_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
        "prompt_style": "daily_4_video_regenerate_until_clean_scheduled_publish",
        "slot_video_path": str(OUT / f"short_{slot}.mp4"),
        "slot_thumbnail_path": str(OUT / f"thumbnail_{slot}.jpg"),
        "slot_preview_gif_path": str(OUT / f"preview_{slot}.gif"),
    })
    (OUT / f"meta_{slot}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


async def main() -> None:
    runner.generate_script = generate_script
    runner.fallback_script = fallback_script
    manifest = []
    for index, (slot, hour) in enumerate(SLOTS, start=1):
        publish_at = publish_time(hour)
        runner.main.upload_to_youtube = scheduled_uploader(publish_at, slot)
        runner.main.logger.info("Starting daily batch video %d/4 slot=%s", index, slot)
        await runner.run()
        manifest.append(copy_slot_files(slot, publish_at, index))
    (OUT / "daily_batch_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
