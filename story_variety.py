"""Story variety helper for horror Shorts.

Prevents the generator from repeating the same phrasing, setting, and evidence.
Each run chooses a concrete archetype with a unique setting/object/evidence
bundle instead of echoing the prompt words directly.
"""

from __future__ import annotations

import random

STORY_ARCHETYPES = [
    {
        "name": "found_tape",
        "direction": "a moldy VHS found inside a sealed wall of an old motel",
        "must_include": "a room number scratched off the tape label a voice counting backward and a final frame showing the viewer from behind",
        "avoid": "security camera timestamp hidden archive door sub-basement case file Project Aegis",
    },
    {
        "name": "missing_person_last_message",
        "direction": "a missing hiker whose phone sends one last audio message from inside a dry well",
        "must_include": "a wrong GPS pin a child's humming in the background and mud on a phone that was supposedly never found",
        "avoid": "archive server classified room timestamp loop camera 4",
    },
    {
        "name": "cursed_object",
        "direction": "an antique mirror bought from an estate sale that starts reflecting yesterday instead of the room",
        "must_include": "a handwritten warning a reflection doing something late and a name appearing in dust",
        "avoid": "server logs cctv timestamp classified file camera footage",
    },
    {
        "name": "dark_web_listing",
        "direction": "a deleted dark web listing selling a photograph of a future crime scene before it exists",
        "must_include": "a username a strange price an archived screenshot and one detail matching the next morning's news",
        "avoid": "camera 4 room 314 sub-basement archive hidden door",
    },
    {
        "name": "small_town_broadcast",
        "direction": "a local radio station that plays an emergency warning from a town that disappeared decades ago",
        "must_include": "frequency numbers a repeated phrase static and a caller who knows the listener's address",
        "avoid": "case file cctv hidden door timestamp archive",
    },
    {
        "name": "conspiracy_archive",
        "direction": "a leaked folder about a school basement experiment covered up by changing yearbook photos",
        "must_include": "redacted class photo an anonymous source a renamed experiment and one student who appears in every decade",
        "avoid": "camera timestamp empty room hidden door Project Aegis",
    },
    {
        "name": "abandoned_place_log",
        "direction": "an explorer log from an abandoned train station where the arrival board updates by itself",
        "must_include": "a platform number wet footprints a train that never arrives and a ticket stamped tomorrow",
        "avoid": "server footage project archive timestamp classified room",
    },
    {
        "name": "paranormal_witness_report",
        "direction": "an apartment witness report about knocking from the ceiling of a top-floor room",
        "must_include": "three knocks a landlord's old record a ceiling stain shaped like a hand and a neighbor who should not exist",
        "avoid": "government archive classified files cctv timestamp camera 4",
    },
    {
        "name": "family_photo_box",
        "direction": "a family finds a box of photos showing them in places they have never visited",
        "must_include": "one beach photo winter clothing a stranger in every picture and a date written after tomorrow",
        "avoid": "security camera archive timestamp hidden lab",
    },
    {
        "name": "numbers_station",
        "direction": "a numbers station broadcast that reads coordinates to ordinary houses at 3 AM",
        "must_include": "five numbers a repeated lullaby a map pin and a house light turning on exactly after the code",
        "avoid": "case file hidden door timestamp cctv",
    },
    {
        "name": "elevator_floor",
        "direction": "an office elevator opens to a floor that is not listed in the building plans",
        "must_include": "floor minus one a carpet smell a desk with fresh coffee and an employee badge from 1986",
        "avoid": "camera 4 archive timestamp redacted file",
    },
    {
        "name": "childhood_diary",
        "direction": "a childhood diary predicts adult events in handwriting that changes every night",
        "must_include": "a locked drawer a page dated next week a crossed-out name and ink that is still wet",
        "avoid": "surveillance footage cctv archive door server logs",
    },
]


def choose_archetype():
    return random.choice(STORY_ARCHETYPES)


def archetype_prompt_block(archetype: dict) -> str:
    return f"""
Unique story seed for this video: {archetype['name']}
Use this concrete idea: {archetype['direction']}
Include these exact-style story elements naturally: {archetype['must_include']}
Do not use or paraphrase these repeated motifs: {archetype['avoid']}
The final script must sound like a fresh micro-horror story not a template summary.
""".strip()
