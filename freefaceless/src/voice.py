import asyncio
import html
import json
from pathlib import Path
import edge_tts
from .config import CONFIG
from .quality import clean_spoken


def synth(text: str, out_path: Path) -> Path:
    async def generate():
        v = CONFIG["voice"]
        last_error = None
        for attempt in range(3):
            words = []
            try:
                stream = edge_tts.Communicate(text, voice=v["voice"], rate=v.get("rate", "+0%"), pitch=v.get("pitch", "+0Hz"), boundary="WordBoundary")
                with out_path.open("wb") as audio:
                    async for part in stream.stream():
                        if part["type"] == "audio":
                            audio.write(part["data"])
                        elif part["type"] == "WordBoundary":
                            words.append({"word": html.unescape(part["text"]), "start": part["offset"] / 10_000_000,
                                          "end": (part["offset"] + part["duration"]) / 10_000_000})
                received = clean_spoken(" ".join(row["word"] for row in words)).casefold().split()
                if not words or received != clean_spoken(text).casefold().split():
                    raise ValueError("Ses metni ile kelime zamanları aynı değil; tahmini altyazı oluşturulmadı")
                if not out_path.exists() or out_path.stat().st_size == 0:
                    raise ValueError("Ses dosyası boş")
                out_path.with_suffix(".words.json").write_text(json.dumps(words, ensure_ascii=False), encoding="utf-8")
                return
            except Exception as exc:
                last_error = exc
                if attempt < 2:
                    await asyncio.sleep(5 * (attempt + 1))
        raise RuntimeError(f"Aynı sesle üç deneme başarısız: {last_error}")
    asyncio.run(generate())
    return out_path
