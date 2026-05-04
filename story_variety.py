"""Loose inspiration helper for first-person horror Shorts.

These are NOT rigid story templates. They are only loose inspiration cards so
stories feel varied without forcing repeated prompt-like wording.
"""

from __future__ import annotations

import random

STORY_ARCHETYPES = [
    {"name": "late_shift", "vibe": "a night shift worker noticing one small impossible detail at work"},
    {"name": "old_family_memory", "vibe": "a family memory that changes after someone finds an old object"},
    {"name": "roadside_encounter", "vibe": "a lonely road or gas station encounter that feels normal until one detail is wrong"},
    {"name": "rented_room", "vibe": "a motel room apartment or rental where the narrator finds evidence someone knew they were coming"},
    {"name": "deleted_message", "vibe": "a message photo voicemail or post that disappears but leaves one trace behind"},
    {"name": "small_town_secret", "vibe": "a local rumor from a small town that the narrator personally witnessed"},
    {"name": "childhood_place", "vibe": "a school playground basement attic or childhood place that should have changed but did not"},
    {"name": "ordinary_object", "vibe": "a normal object like a mirror radio diary cassette toy key photo or elevator button behaving wrong"},
    {"name": "conspiracy_hint", "vibe": "a subtle coverup involving changed records missing names or a warning from an anonymous person"},
    {"name": "witness_confession", "vibe": "a first person confession from someone who saw something and never reported it"},
    {"name": "urban_legend_personal", "vibe": "an urban legend the narrator thought was fake until one personal detail matched"},
    {"name": "found_recording", "vibe": "a recording found by the narrator that contains a sound or sentence that should not be there"},
]

SENSORY_DETAIL_BANK = [
    "the smell of wet carpet",
    "a phone vibrating with no notification",
    "a hallway light flickering only once",
    "cold air from a closed room",
    "a name written in fresh dust",
    "a voice under static",
    "footsteps stopping when the narrator stops",
    "an old photo with one new face",
    "a door that is warm to the touch",
    "a radio signal cutting through silence",
    "a timestamp that is less important than the sound behind it",
    "a stranger knowing a private nickname",
]

AVOID_MOTIFS = [
    "Camera 4",
    "Room 314",
    "Project Aegis",
    "sub-basement archives",
    "the timestamp was wrong",
    "hidden archive door",
    "classified room log",
    "case file should not exist",
]


def choose_archetype():
    card = random.choice(STORY_ARCHETYPES).copy()
    card["sensory_details"] = random.sample(SENSORY_DETAIL_BANK, k=3)
    card["avoid"] = AVOID_MOTIFS
    return card


def archetype_prompt_block(archetype: dict) -> str:
    details = "; ".join(archetype.get("sensory_details", []))
    avoid = "; ".join(archetype.get("avoid", []))
    return f"""
Loose inspiration only: {archetype['name']}
Vibe: {archetype['vibe']}
Optional sensory inspiration: {details}
Avoid these overused motifs entirely: {avoid}
Use your own original names places objects and twist. Do not copy the inspiration wording directly.
""".strip()
