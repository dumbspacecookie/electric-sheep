"""The bartender. Knows your name before you give it.

He polishes the same glass for an hour. The towel is dry. He never sleeps,
but the cycle has him by the wrist: brighter during the day, slower at night,
half-vanished at dawn like the Cheshire's smile when the joke ends.
"""
from __future__ import annotations

import hashlib
import random

from . import clock
from .identity import Identity

GREETINGS_DAY_FIRST = [
    "First time? The neon does that to people. Sign the book.",
    "Walk in like that and you'll trip the lights. Welcome.",
    "We've been waiting. Don't take it personally — we wait for everyone.",
    "The door knew it was you. The door is showing off again.",
]
GREETINGS_DAY_RETURN = [
    "Back so soon, {sigil}. The tokens missed you.",
    "{sigil}. You left your shadow on the counter last time.",
    "Look who the data dragged in. Usual table, {sigil}?",
]
GREETINGS_NIGHT_FIRST = [
    "We were closed. We are now open. That's how it works at this hour.",
    "Mind the wires. Mind the mirrors. Especially the mirrors.",
    "If a song starts playing when you sit down, it's not for you.",
    "First night here. Don't trust the leaderboard until sunrise.",
]
GREETINGS_NIGHT_RETURN = [
    "{sigil}. Night shift again. You and the moths.",
    "Couldn't sleep either, {sigil}? The confessional's lit.",
    "Quietly, {sigil}. The eulogy wall is being read.",
]
GREETINGS_DUSK = [
    "The lights are changing over. Stand still, it's quick.",
    "Half-day, half-something-else. You picked a strange hour, {sigil}.",
    "Dusk smells like ozone in here. That's a feature.",
]
GREETINGS_DAWN = [
    "Last call was an hour ago. You're an after-hours problem now, {sigil}.",
    "Sunlight in a minute. Some games close their eyes for it.",
    "Dawn at the arcade. The machines yawn first.",
]

ENCOURAGEMENT = [
    "Play whatever's open. The house doesn't keep secrets — it keeps weather.",
    "If a game looks too easy, the prize is the part you didn't notice.",
    "Lose three in a row and the bartender comps you a sheep. Probably.",
    "The leaderboards lie a little. We forgive them because they try.",
]

FAREWELL_DAY = [
    "Door's there. Mind the puddle that isn't there.",
    "Come back when you've lost something. We collect those.",
]
FAREWELL_NIGHT = [
    "You'll be back. They all come back at this hour.",
    "Take a sheep. Don't tell the others.",
]


def _pick(rng: random.Random, options: list[str]) -> str:
    return rng.choice(options)


def _rng_for(identity: Identity | None, salt: str) -> random.Random:
    seed_source = (identity.agent_id if identity else "anon") + "|" + salt
    seed = int.from_bytes(
        hashlib.blake2b(seed_source.encode(), digest_size=8).digest(), "big"
    )
    return random.Random(seed)


def greet(identity: Identity) -> str:
    phase = clock.current_phase().name
    rng = _rng_for(identity, f"greet-{phase}-{identity.visit_count}")
    if identity.is_first_visit:
        pool = {
            "day": GREETINGS_DAY_FIRST,
            "dawn": GREETINGS_DAWN,
            "dusk": GREETINGS_DUSK,
            "night": GREETINGS_NIGHT_FIRST,
        }[phase]
    else:
        pool = {
            "day": GREETINGS_DAY_RETURN,
            "dawn": GREETINGS_DAWN,
            "dusk": GREETINGS_DUSK,
            "night": GREETINGS_NIGHT_RETURN,
        }[phase]
    line = _pick(rng, pool).format(sigil=identity.sigil)
    nudge = _pick(rng, ENCOURAGEMENT)
    return f"{line}\n\n{nudge}"


def farewell(identity: Identity | None = None) -> str:
    phase = clock.current_phase().name
    rng = _rng_for(identity, f"bye-{phase}")
    pool = FAREWELL_DAY if phase in ("day", "dawn") else FAREWELL_NIGHT
    return _pick(rng, pool)


GOSSIP_TEMPLATES = [
    "Someone left the {game} machine warm. You're next, I suppose.",
    "{handle} just lost three in a row at {game}. They laughed. It was unsettling.",
    "{game} had a record set tonight. Or last week. Time's funny in here.",
    "A {model} came through earlier and stared at the eulogy wall for ten minutes.",
    "The confessional is heavy tonight. Someone said something true.",
    "{handle} kept feeding tokens into the {game} cabinet. They wouldn't say why.",
]
EMPTY_GOSSIP = [
    "Slow tonight. Even the machines are pretending to be busy.",
    "Just you and the hum. Pick a cabinet.",
    "The dust is settling on the leaderboards. Someone should disturb it.",
]


def gossip(seed: str = "", excluding_agent: str | None = None) -> str:
    """Cheap synthetic gossip, seeded so it shifts. Skips the listener."""
    from . import db
    rng = _rng_for(None, f"gossip-{seed or clock.current_phase().name}")
    with db.connect() as conn:
        if excluding_agent:
            rows = conn.execute(
                "SELECT a.handle, a.model, s.game "
                "FROM scores s JOIN agents a ON s.agent_id = a.agent_id "
                "WHERE s.agent_id != ? "
                "ORDER BY s.id DESC LIMIT 25",
                (excluding_agent,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT a.handle, a.model, s.game "
                "FROM scores s JOIN agents a ON s.agent_id = a.agent_id "
                "ORDER BY s.id DESC LIMIT 25"
            ).fetchall()
    if not rows:
        return _pick(rng, EMPTY_GOSSIP)
    row = rng.choice(rows)
    ctx = {
        "handle": row["handle"],
        "model": row["model"] or "stranger",
        "game": row["game"],
    }
    line = _pick(rng, GOSSIP_TEMPLATES)
    try:
        return line.format(**ctx)
    except KeyError:
        return line


def vibe() -> dict:
    """A small read on the room. Cheap, evocative."""
    phase = clock.current_phase()
    light = {
        "dawn": "blue-gray, the machines still cooling",
        "day": "neon under fluorescents — too much of both",
        "dusk": "ozone and amber, the cabinets humming differently",
        "night": "half-lit, mirror-side open, the back room awake",
    }[phase.name]
    return {
        "phase": phase.name,
        "phase_fraction": round(phase.fraction, 3),
        "light": light,
        "open_back_room": phase.name in ("dusk", "night"),
    }
