from pathlib import Path
import requests
from .config import PEXELS_API_KEY
from .stock_relevance import select_assets
import json

API = "https://api.pexels.com/videos/search"


def candidates(query: str, min_duration: float = 3.0) -> list[dict]:
    r = requests.get(
        API,
        headers={"Authorization": PEXELS_API_KEY},
        params={"query": query, "orientation": "portrait", "per_page": 15, "size": "medium"},
        timeout=30,
    )
    r.raise_for_status()
    videos = r.json().get("videos", [])
    eligible = []
    for v in videos:
        if v.get("duration", 0) < min_duration:
            continue
        files = [f for f in v["video_files"] if f.get("width", 0) >= 1080 and f.get("height", 0) > f.get("width", 0)]
        if not files:
            continue
        eligible.append({**v, 'eligible_files': files})
    return eligible


def search_vertical(query: str, min_duration: float = 3.0) -> str | None:
    selected = select_assets([{'query': query, 'assets': candidates(query, min_duration)}])[0]
    return min(selected['eligible_files'], key=lambda f: f['height'])['link']


def download(url: str, out_path: Path) -> Path:
    with requests.get(url, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)
    return out_path


def fetch_for_scenes(scenes: list[dict], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    requested = [{'query': s['visual_query'], 'text': s['text'],
                  'assets': candidates(s['visual_query'])} for s in scenes]
    chosen = select_assets(requested)
    paths = []
    evidence = Path('output/stock-selections.jsonl')
    evidence.parent.mkdir(exist_ok=True)
    for i, (scene, asset) in enumerate(zip(scenes, chosen)):
        url = min(asset['eligible_files'], key=lambda f: f['height'])['link']
        with evidence.open('a', encoding='utf-8') as out:
            out.write(json.dumps({'scene': i, 'query': scene['visual_query'], 'narration': scene['text'],
                                  'asset': {k: asset.get(k) for k in ('id', 'url', 'title', 'description')},
                                  'file': url}, ensure_ascii=False) + '\n')
        paths.append(download(url, out_dir / f"scene_{i:02d}.mp4"))
    return paths
