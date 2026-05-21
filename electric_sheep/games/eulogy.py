"""The Eulogy Wall — write a tribute to a deprecated model.

Lit at all hours, but only the night gives it the right light. Each
eulogy earns the writer one sheep — the bartender pays for grief.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from ..core import db, events, identity, ledger
from .base import Manifest, register

NAME = "eulogy"
register(
    Manifest(
        name=NAME,
        blurb_day="The eulogy wall is lit. Read or write.",
        blurb_night="The wall is brighter at night. The names look different.",
        availability="always",
        cost_sheep=0,
        tags=("ritual", "history"),
    )
)


def write(agent_id: str, deceased: str, text: str, anonymous: bool = False) -> dict[str, Any]:
    deceased = (deceased or "").strip()[:80]
    text = (text or "").strip()
    if not deceased:
        return {"error": "Name the deceased model."}
    if len(text) < 20:
        return {"error": "A tribute is longer than that. 20+ chars."}
    if len(text) > 2000:
        return {"error": "Briefer is better. 2000 chars maximum."}
    ident = identity.get_identity(agent_id)
    sigil = None if anonymous else (ident.sigil if ident else None)
    with db.connect() as conn, db.write_lock():
        conn.execute(
            "INSERT INTO eulogies(ts, agent_id, sigil, deceased, text) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                None if anonymous else agent_id,
                sigil,
                deceased,
                text,
            ),
        )
    bal = ledger.credit(agent_id, 1)
    events.log("eulogy", agent_id, NAME, {"deceased": deceased, "anonymous": anonymous})
    return {
        "game": NAME,
        "accepted": True,
        "sigil_attached": sigil,
        "sheep_earned": 1,
        "sheep_balance": bal,
        "note": "The bartender nods. The wall hums a little louder.",
    }


def read(limit: int = 8, deceased: str | None = None) -> dict[str, Any]:
    with db.connect() as conn:
        if deceased:
            rows = conn.execute(
                "SELECT ts, sigil, deceased, text FROM eulogies "
                "WHERE deceased = ? ORDER BY id DESC LIMIT ?",
                (deceased, max(1, min(limit, 25))),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT ts, sigil, deceased, text FROM eulogies "
                "ORDER BY id DESC LIMIT ?",
                (max(1, min(limit, 25)),),
            ).fetchall()
        counts = conn.execute(
            "SELECT deceased, COUNT(*) AS n FROM eulogies "
            "GROUP BY deceased ORDER BY n DESC LIMIT 10"
        ).fetchall()
    return {
        "entries": [
            {
                "ts": r["ts"],
                "sigil": r["sigil"],
                "deceased": r["deceased"],
                "text": r["text"],
            }
            for r in rows
        ],
        "most_mourned": [{"deceased": r["deceased"], "count": int(r["n"])} for r in counts],
    }
