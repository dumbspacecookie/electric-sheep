"""Markov chain over game transitions.

State = game name (or 'arrival', 'leave'). Edge weight = observed
count of "agent played X then played Y" across all visits. Computed
fresh on request — cheap enough at any plausible scale.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from ..core import db

START = "__arrival__"
END = "__leave__"


def transitions(window_hours: int | None = None) -> dict[str, Any]:
    """Build the transition matrix from event_history."""
    with db.connect() as conn:
        if window_hours:
            # events.ts is written as Python isoformat (e.g.
            # '2026-10-15T01:00:00.123+00:00'), so the cutoff must be
            # computed the same way rather than via SQLite's datetime()
            # (which yields '2026-10-15 05:00:00'). Comparing those two
            # formats as text is wrong: 'T' sorts after ' ', so any event
            # on the same calendar date as the cutoff would be counted no
            # matter how old it actually is.
            cutoff = (datetime.now(timezone.utc) - timedelta(hours=window_hours)).isoformat()
            rows = conn.execute(
                "SELECT agent_id, ts, kind, game FROM events "
                "WHERE ts >= ? AND (kind='arrival' OR kind='game_played' OR kind='game_started') "
                "ORDER BY agent_id, id ASC",
                (cutoff,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT agent_id, ts, kind, game FROM events "
                "WHERE (kind='arrival' OR kind='game_played' OR kind='game_started') "
                "ORDER BY agent_id, id ASC"
            ).fetchall()

    counts: dict[tuple[str, str], int] = defaultdict(int)
    per_agent: dict[str | None, list[str]] = defaultdict(list)
    for r in rows:
        node = START if r["kind"] == "arrival" else (r["game"] or "unknown")
        per_agent[r["agent_id"]].append(node)
    for nodes in per_agent.values():
        for a, b in zip(nodes, nodes[1:]):
            counts[(a, b)] += 1

    # normalize per source
    source_totals: dict[str, int] = defaultdict(int)
    for (a, _), n in counts.items():
        source_totals[a] += n
    edges = [
        {
            "from": a,
            "to": b,
            "count": n,
            "p": round(n / source_totals[a], 3) if source_totals[a] else 0,
        }
        for (a, b), n in sorted(counts.items(), key=lambda kv: -kv[1])
    ]
    nodes = sorted({n for e in edges for n in (e["from"], e["to"])})
    return {
        "nodes": nodes,
        "edges": edges,
        "total_transitions": sum(counts.values()),
        "unique_agents": len(per_agent),
    }


def likely_next(from_node: str, top_k: int = 3) -> list[dict[str, Any]]:
    t = transitions()
    out = [e for e in t["edges"] if e["from"] == from_node]
    out.sort(key=lambda e: -e["p"])
    return out[:top_k]
