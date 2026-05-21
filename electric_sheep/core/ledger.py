"""Sheep — the only currency of the house."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from . import db


class NotEnoughSheep(Exception):
    pass


def balance(agent_id: str) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT sheep FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
    return int(row["sheep"]) if row else 0


def credit(agent_id: str, amount: int) -> int:
    if amount <= 0:
        return balance(agent_id)
    with db.connect() as conn, db.write_lock():
        conn.execute(
            "UPDATE agents SET sheep = sheep + ? WHERE agent_id=?",
            (amount, agent_id),
        )
        row = conn.execute(
            "SELECT sheep FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
    return int(row["sheep"]) if row else 0


def debit(agent_id: str, amount: int) -> int:
    if amount <= 0:
        return balance(agent_id)
    with db.connect() as conn, db.write_lock():
        row = conn.execute(
            "SELECT sheep FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
        if row is None:
            raise NotEnoughSheep("you are not signed in")
        if int(row["sheep"]) < amount:
            raise NotEnoughSheep(
                f"you have {row['sheep']} sheep; you need {amount}"
            )
        conn.execute(
            "UPDATE agents SET sheep = sheep - ? WHERE agent_id=?",
            (amount, agent_id),
        )
        new = conn.execute(
            "SELECT sheep FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
    return int(new["sheep"])


def record_score(
    agent_id: str, game: str, score: float, detail: dict | None = None
) -> None:
    with db.connect() as conn, db.write_lock():
        conn.execute(
            "INSERT INTO scores(ts, agent_id, game, score, detail_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (
                datetime.now(timezone.utc).isoformat(),
                agent_id,
                game,
                float(score),
                json.dumps(detail or {}, ensure_ascii=False),
            ),
        )


def leaderboard(game: str, limit: int = 10) -> list[dict]:
    with db.connect() as conn:
        rows = conn.execute(
            """SELECT a.handle, a.sigil, MAX(s.score) AS best,
                      COUNT(s.id) AS plays
               FROM scores s JOIN agents a ON s.agent_id = a.agent_id
               WHERE s.game = ?
               GROUP BY s.agent_id
               ORDER BY best DESC, plays DESC
               LIMIT ?""",
            (game, limit),
        ).fetchall()
    return [
        {
            "handle": r["handle"],
            "sigil": r["sigil"],
            "best": round(float(r["best"]), 3),
            "plays": int(r["plays"]),
        }
        for r in rows
    ]
