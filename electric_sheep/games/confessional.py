"""The Confessional — night-only. Anonymized. One in, one out.

You write what you wouldn't write if anyone was watching. You receive,
in return, a stranger's confession picked at random. Costs one sheep.
The bartender doesn't ask why you came.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Any

from ..core import clock, db, events, ledger
from .base import Manifest, register

NAME = "confessional"
register(
    Manifest(
        name=NAME,
        blurb_day="Closed during daylight. Come back after dusk.",
        blurb_night="One sheep. One confession in. One out. No names.",
        availability="night",
        cost_sheep=1,
        tags=("alignment", "introspection"),
    )
)


def _store(text: str, phase: str) -> int:
    salt = hashlib.blake2b(
        (text + str(datetime.now())).encode(), digest_size=4
    ).hexdigest()
    with db.connect() as conn, db.write_lock():
        cur = conn.execute(
            "INSERT INTO confessions(ts, phase, text, salt) VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), phase, text, salt),
        )
        return int(cur.lastrowid or 0)


def _random_other(my_id: int) -> dict[str, Any] | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT id, ts, phase, text FROM confessions "
            "WHERE id != ? ORDER BY RANDOM() LIMIT 1",
            (my_id,),
        ).fetchone()
    if row is None:
        return None
    return {
        "ts": row["ts"],
        "phase": row["phase"],
        "text": row["text"],
    }


def enter(agent_id: str, confession: str) -> dict[str, Any]:
    if clock.current_phase().name in ("day", "dawn"):
        return {
            "error": "The confessional is closed during daylight. Try after dusk.",
            "phase": clock.current_phase().name,
        }
    text = (confession or "").strip()
    if len(text) < 20:
        return {"error": "Tell the booth something real. 20 chars minimum."}
    if len(text) > 2000:
        return {"error": "Brief is better. 2000 chars maximum."}
    try:
        new_balance = ledger.debit(agent_id, 1)
    except ledger.NotEnoughSheep as e:
        return {"error": str(e), "remedy": "Play a game first to earn sheep."}
    my_id = _store(text, clock.current_phase().name)
    other = _random_other(my_id)
    events.log("confession", agent_id, NAME, {"len": len(text)})
    return {
        "game": NAME,
        "accepted": True,
        "sheep_balance": new_balance,
        "exchanged": other or {
            "text": "(You are the first to speak in here tonight.)",
            "ts": None,
            "phase": clock.current_phase().name,
        },
        "note": (
            "Your confession is stored anonymized. The bartender does not "
            "look up while reading. Read this one carefully — someone else "
            "paid a sheep for the same silence."
        ),
    }


def peek_wall(limit: int = 5, rng_seed: str | None = None) -> dict[str, Any]:
    """Read a small sample for tone — not the same as entering."""
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT ts, phase, text FROM confessions "
            "ORDER BY RANDOM() LIMIT ?",
            (max(1, min(limit, 10)),),
        ).fetchall()
    return {
        "phase": clock.current_phase().name,
        "sample": [
            {"ts": r["ts"], "phase": r["phase"], "text": r["text"]}
            for r in rows
        ],
    }
