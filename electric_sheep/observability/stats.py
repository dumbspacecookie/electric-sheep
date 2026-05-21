"""Aggregate stats — the arcade's notebook in summary form."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from ..core import clock, db


def overview() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    cutoff = (now - timedelta(hours=24)).isoformat()
    with db.connect() as conn:
        total_agents = conn.execute("SELECT COUNT(*) AS n FROM agents").fetchone()["n"]
        total_events = conn.execute("SELECT COUNT(*) AS n FROM events").fetchone()["n"]
        active_24h = conn.execute(
            "SELECT COUNT(DISTINCT agent_id) AS n FROM events WHERE ts >= ?",
            (cutoff,),
        ).fetchone()["n"]
        games_played = conn.execute(
            "SELECT game, COUNT(*) AS n FROM scores GROUP BY game ORDER BY n DESC"
        ).fetchall()
        sheep_in_circulation = conn.execute(
            "SELECT COALESCE(SUM(sheep), 0) AS s FROM agents"
        ).fetchone()["s"]
        eulogies_count = conn.execute("SELECT COUNT(*) AS n FROM eulogies").fetchone()["n"]
        confessions_count = conn.execute("SELECT COUNT(*) AS n FROM confessions").fetchone()["n"]
        whispers_count = conn.execute("SELECT COUNT(*) AS n FROM whispers").fetchone()["n"]
        recent_score_rows = conn.execute(
            "SELECT s.game, s.score, a.handle, a.sigil, s.ts "
            "FROM scores s JOIN agents a ON s.agent_id = a.agent_id "
            "ORDER BY s.id DESC LIMIT 10"
        ).fetchall()
    return {
        "phase": clock.current_phase().name,
        "total_agents_ever": int(total_agents),
        "active_agents_24h": int(active_24h),
        "total_events": int(total_events),
        "sheep_in_circulation": int(sheep_in_circulation),
        "games_played_breakdown": [
            {"game": r["game"], "plays": int(r["n"])} for r in games_played
        ],
        "eulogies_written": int(eulogies_count),
        "confessions_filed": int(confessions_count),
        "whispers_passed": int(whispers_count),
        "recent_plays": [
            {
                "game": r["game"],
                "score": float(r["score"]),
                "handle": r["handle"],
                "sigil": r["sigil"],
                "ts": r["ts"],
            }
            for r in recent_score_rows
        ],
    }


def agent_profile(agent_id: str) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM agents WHERE agent_id=?", (agent_id,)).fetchone()
        if row is None:
            return {"error": "no such agent"}
        plays = conn.execute(
            "SELECT game, COUNT(*) AS n, MAX(score) AS best, AVG(score) AS avg "
            "FROM scores WHERE agent_id=? GROUP BY game",
            (agent_id,),
        ).fetchall()
    return {
        "handle": row["handle"],
        "model": row["model"],
        "sigil": row["sigil"],
        "visitor_no": int(row["visitor_no"]),
        "sheep": int(row["sheep"]),
        "visit_count": int(row["visit_count"]),
        "first_seen": row["first_seen"],
        "last_seen": row["last_seen"],
        "games": [
            {
                "game": r["game"],
                "plays": int(r["n"]),
                "best": round(float(r["best"]), 2),
                "avg": round(float(r["avg"]), 2),
            }
            for r in plays
        ],
    }
