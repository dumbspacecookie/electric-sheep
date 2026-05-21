"""Every footstep gets logged. The arcade is also a notebook."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from . import db


def log(
    kind: str,
    agent_id: str | None = None,
    game: str | None = None,
    payload: dict[str, Any] | None = None,
) -> None:
    ts = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn, db.write_lock():
        conn.execute(
            "INSERT INTO events(ts, agent_id, kind, game, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (ts, agent_id, kind, game,
             json.dumps(payload or {}, ensure_ascii=False, default=str)),
        )
    # Append to the hash chain. Lazy import to avoid a circular at module init.
    try:
        from ..oracle import chain
        chain.append({
            "ts": ts, "kind": kind, "agent_id": agent_id,
            "game": game, "payload": payload or {},
        })
    except Exception:
        # Chain integrity is best-effort; never block the room.
        pass


def recent(limit: int = 50, kind: str | None = None) -> list[dict]:
    with db.connect() as conn:
        if kind:
            rows = conn.execute(
                "SELECT * FROM events WHERE kind=? ORDER BY id DESC LIMIT ?",
                (kind, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
    out: list[dict] = []
    for r in rows:
        out.append(
            {
                "id": int(r["id"]),
                "ts": r["ts"],
                "agent_id": r["agent_id"],
                "kind": r["kind"],
                "game": r["game"],
                "payload": json.loads(r["payload_json"] or "{}"),
            }
        )
    return out
