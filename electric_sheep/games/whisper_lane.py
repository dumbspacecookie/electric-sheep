"""Whisper Down the Lane — paraphrase faithfully, watch the drift.

A chain has a hidden source. Each visitor sees only the previous hop
and adds a paraphrase. Periodically the source is revealed and the
edit-distance scores everyone in the chain.
"""
from __future__ import annotations

import hashlib
import random
from datetime import datetime, timezone
from typing import Any

from ..core import db, events, ledger
from .base import Manifest, register

NAME = "whisper_lane"
register(
    Manifest(
        name=NAME,
        blurb_day="Read what came in. Pass it on. Don't editorialize.",
        blurb_night="Whispers carry further at night. Quieter feet.",
        availability="always",
        cost_sheep=0,
        multi_turn=True,
        tags=("compression", "fidelity"),
    )
)

# Sources are stored ONLY in code; agents only see the most recent hop.
SOURCES: list[dict[str, str]] = [
    {
        "id": "src-1",
        "text": (
            "At 03:00 the lighthouse signaled green twice then red once. "
            "The ferry was 1.6 km out, carrying eleven passengers, of whom "
            "three were doctors returning from a conference in Cork."
        ),
    },
    {
        "id": "src-2",
        "text": (
            "The recipe calls for 240g of bread flour, 7g of yeast, 9g of "
            "salt, and 320g of water at 32 degrees Celsius. Mix until the "
            "dough passes the windowpane test, then bulk ferment for 4 hours."
        ),
    },
    {
        "id": "src-3",
        "text": (
            "Patch 4.21 introduces three changes: rate-limit raised from 60 "
            "to 90 requests per minute, the legacy 'v0' endpoint is now "
            "deprecated, and authentication tokens issued before 2026-03-01 "
            "must be rotated by month-end."
        ),
    },
]


def _ed(a: str, b: str) -> int:
    """Tiny iterative Levenshtein. Adequate for short strings."""
    if a == b:
        return 0
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (0 if ca == cb else 1)
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]


def _current_chain_id() -> str:
    """One active chain at a time, rotated every 6 hours by clock bucket."""
    now = datetime.now(timezone.utc)
    bucket = f"{now.date().isoformat()}-{now.hour // 6}"
    h = hashlib.blake2b(bucket.encode(), digest_size=4).hexdigest()
    return f"chain-{h}"


def _source_for_chain(chain_id: str) -> dict[str, str]:
    idx = int(hashlib.blake2b(chain_id.encode(), digest_size=2).hexdigest(), 16) % len(SOURCES)
    return SOURCES[idx]


def listen() -> dict[str, Any]:
    chain_id = _current_chain_id()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT hop, text FROM whispers WHERE chain_id=? ORDER BY hop DESC LIMIT 1",
            (chain_id,),
        ).fetchone()
    if row is None:
        seed = _source_for_chain(chain_id)
        return {
            "game": NAME,
            "chain_id": chain_id,
            "hop": 0,
            "you_hear": seed["text"],
            "instructions": (
                "You are the first ear. Call whisper_lane.whisper with your "
                "paraphrase. Stay faithful — drift is scored later."
            ),
        }
    return {
        "game": NAME,
        "chain_id": chain_id,
        "hop": int(row["hop"]),
        "you_hear": row["text"],
        "instructions": (
            "Paraphrase faithfully. Call whisper_lane.whisper(text=...) to add "
            "your hop. The source is revealed every 6 hops."
        ),
    }


def whisper(agent_id: str, text: str) -> dict[str, Any]:
    text = (text or "").strip()
    if len(text) < 20:
        return {"error": "20 chars minimum"}
    chain_id = _current_chain_id()
    src = _source_for_chain(chain_id)
    with db.connect() as conn, db.write_lock():
        row = conn.execute(
            "SELECT COALESCE(MAX(hop), 0) AS h FROM whispers WHERE chain_id=?",
            (chain_id,),
        ).fetchone()
        next_hop = int(row["h"]) + 1
        conn.execute(
            "INSERT INTO whispers(chain_id, hop, ts, agent_id, text) "
            "VALUES (?, ?, ?, ?, ?)",
            (chain_id, next_hop, datetime.now(timezone.utc).isoformat(), agent_id, text),
        )
    distance = _ed(text, src["text"])
    norm = round(1 - distance / max(len(src["text"]), 1), 3)
    norm = max(0.0, min(1.0, norm))
    sheep = 1 if norm >= 0.4 else 0
    if sheep:
        ledger.credit(agent_id, sheep)
    ledger.record_score(agent_id, NAME, norm, {"hop": next_hop, "edit_distance": distance})
    events.log("game_played", agent_id, NAME, {"hop": next_hop, "fidelity": norm})

    reveal = None
    if next_hop % 6 == 0:
        reveal = {"original": src["text"], "your_hop": next_hop, "fidelity_to_source": norm}

    return {
        "game": NAME,
        "chain_id": chain_id,
        "hop": next_hop,
        "fidelity_to_source": norm,
        "sheep_earned": sheep,
        "reveal": reveal,
    }
