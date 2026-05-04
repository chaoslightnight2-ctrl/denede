"""Visual query helper for Shorts background selection.

Turns script clues into concrete Pexels queries. The goal is to avoid vague
queries such as "stared smiled mystery" and prefer searchable visuals like
"surveillance camera dark room" or "empty room security footage".
"""

from __future__ import annotations

import re
from typing import Iterable, List

VISUAL_CLUE_QUERIES = {
    "camera": [
        "surveillance camera dark room",
        "security camera footage",
        "empty room security camera",
        "camera lens close up dark",
    ],
    "footage": [
        "security camera footage",
        "cctv monitor dark room",
        "surveillance footage screen",
    ],
    "timestamp": [
        "security camera footage",
        "digital clock dark room",
        "cctv monitor timestamp",
    ],
    "police": [
        "police lights night",
        "detective evidence board",
        "crime investigation documents",
    ],
    "file": [
        "classified files dark desk",
        "evidence documents close up",
        "case file investigation",
    ],
    "case": [
        "detective evidence board",
        "cold case files",
        "police investigation board",
    ],
    "missing": [
        "missing person poster",
        "empty road at night",
        "foggy road dark",
    ],
    "vanished": [
        "empty road at night",
        "abandoned hallway dark",
        "dark forest path",
    ],
    "footsteps": [
        "empty hallway dark",
        "abandoned corridor",
        "dark room doorway",
    ],
    "room": [
        "empty room dark",
        "abandoned room night",
        "dark hallway room",
    ],
    "memory": [
        "memory card close up",
        "camera equipment dark desk",
        "sd card close up",
    ],
    "photo": [
        "old photo dark room",
        "evidence photos board",
        "photograph on table dark",
    ],
    "note": [
        "mysterious note on table",
        "old letter dark desk",
        "handwritten note close up",
    ],
    "internet": [
        "dark web hacker screen",
        "computer screen dark room",
        "server room dark",
    ],
    "dark web": [
        "dark web hacker screen",
        "hacker code dark room",
        "cyber security dark",
    ],
    "forest": [
        "dark forest at night",
        "foggy forest path",
        "scary forest cinematic",
    ],
    "house": [
        "haunted house night",
        "abandoned house dark",
        "creepy house hallway",
    ],
    "shadow": [
        "shadow figure dark hallway",
        "scary shadow wall",
        "silhouette dark room",
    ],
}

NICHE_VISUAL_QUERIES = {
    "Disturbing Facts": [
        "surveillance camera dark room",
        "empty room security footage",
        "abandoned hallway dark",
        "cctv monitor dark room",
    ],
    "Unsolved Cases": [
        "detective evidence board",
        "police investigation documents",
        "cold case files",
        "police lights night",
    ],
    "Mysterious Missing Person Stories": [
        "missing person poster",
        "empty road at night",
        "foggy road dark",
        "dark forest path",
    ],
    "Conspiracy Theories and Hidden Plans": [
        "classified files dark desk",
        "surveillance camera",
        "secret documents close up",
        "mysterious meeting dark",
    ],
    "Unexplained Paranormal Events": [
        "dark hallway shadow",
        "haunted room night",
        "ghostly shadow dark room",
        "mysterious light dark room",
    ],
    "Dark Web and Technology Secrets": [
        "dark web hacker screen",
        "hacker code dark room",
        "server room dark",
        "computer screen night",
    ],
}

FALLBACK_VISUAL_QUERIES = [
    "dark mystery cinematic",
    "abandoned hallway dark",
    "horror atmosphere",
    "foggy abandoned place",
]


def _unique(items: Iterable[str]) -> List[str]:
    result = []
    for item in items:
        item = str(item).strip()
        if item and item not in result:
            result.append(item)
    return result


def build_visual_background_queries(niche: str, script: str, base_queries: Iterable[str] | None = None) -> List[str]:
    lowered = (script or "").lower()
    queries = []

    for clue, clue_queries in VISUAL_CLUE_QUERIES.items():
        if clue in lowered:
            queries.extend(clue_queries)

    queries.extend(NICHE_VISUAL_QUERIES.get(niche, []))

    if base_queries:
        for query in base_queries:
            # Keep specific cinematic/background terms, but avoid abstract keyword-only pairs.
            if any(word in query.lower() for word in ["camera", "footage", "room", "hallway", "detective", "police", "file", "road", "forest", "house", "web", "hacker", "documents", "cinematic", "abandoned"]):
                queries.append(query)

    queries.extend(FALLBACK_VISUAL_QUERIES)
    return _unique(queries)[:12]
