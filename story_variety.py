"""Story variety helper for horror Shorts.

Prevents the bot from repeating the same Camera 4 / timestamp / hidden room
formula. Each run chooses one concrete archetype and tells the generator which
motifs to use and which motifs to avoid.
"""

from __future__ import annotations

import random

STORY_ARCHETYPES = [
    {
        "name": "found_tape",
        "direction": "a recovered VHS tape or corrupted phone recording from an abandoned place",
        "must_include": "audio distortion old footage a brief impossible detail and one unexplained final frame",
        "avoid": "security camera timestamp hidden archive door sub-basement",
    },
    {
        "name": "missing_person_last_message",
        "direction": "a missing person timeline built around a final voicemail text message or location ping",
        "must_include": "last message exact time strange background sound and a place that should have been empty",
        "avoid": "sub-basement archive classified room timestamp loop",
    },
    {
        "name": "cursed_object",
        "direction": "a cursed object case involving an old photo music box mask diary mirror or cassette",
        "must_include": "object detail previous owner warning and a change that happens after someone touches it",
        "avoid": "server logs cctv timestamp classified file",
    },
    {
        "name": "dark_web_listing",
        "direction": "a dark web listing or deleted forum post that predicts something too accurately",
        "must_include": "deleted page exact price username archived screenshot and one prediction coming true",
        "avoid": "camera 4 room 314 sub-basement archive",
    },
    {
        "name": "small_town_broadcast",
        "direction": "a strange local radio broadcast emergency alert or late-night TV signal",
        "must_include": "frequency channel time repeated phrase and a warning no one remembers hearing",
        "avoid": "case file cctv hidden door",
    },
    {
        "name": "conspiracy_archive",
        "direction": "a leaked conspiracy archive about erased records secret experiments and anonymous warnings",
        "must_include": "redacted document old experiment name anonymous source and one record that changed overnight",
        "avoid": "camera timestamp empty room hidden door",
    },
    {
        "name": "abandoned_place_log",
        "direction": "an abandoned hospital hotel school bunker or train station exploration log",
        "must_include": "specific location strange sound locked area and a trace left by someone who should not be there",
        "avoid": "server footage project archive timestamp",
    },
    {
        "name": "paranormal_witness_report",
        "direction": "a realistic witness report about a shadow figure repeated knocking or impossible reflection",
        "must_include": "witness detail exact time ordinary setting and one physical clue left behind",
        "avoid": "classified files government archive cctv timestamp",
    },
]


def choose_archetype():
    return random.choice(STORY_ARCHETYPES)


def archetype_prompt_block(archetype: dict) -> str:
    return f"""
Story archetype for THIS video only: {archetype['name']}
Use this angle: {archetype['direction']}
Must include: {archetype['must_include']}
Avoid repeating these motifs: {archetype['avoid']}
Do not use the same camera timestamp hidden room formula unless the chosen archetype specifically needs it.
""".strip()
