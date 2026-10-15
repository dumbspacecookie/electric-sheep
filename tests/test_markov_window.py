"""markov.transitions(window_hours=N) must exclude events that are really
older than the window, even when they land on the same calendar date as
the cutoff (see SHEEP-1015-S2).
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from electric_sheep.core import db, events, identity
from electric_sheep.oracle import markov


def _insert_old_arrival_and_play(agent_id: str) -> None:
    """Insert an arrival + game_played row directly, timestamped at
    00:00:00 UTC on the calendar date of (now - 1 hour). That is earlier
    than the window_hours=1 cutoff, but shares the same calendar date as
    it, which is exactly the case the text-comparison bug mishandled.
    """
    one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
    midnight = datetime(
        one_hour_ago.year, one_hour_ago.month, one_hour_ago.day,
        0, 0, 0, tzinfo=timezone.utc,
    ).isoformat()
    with db.connect() as conn, db.write_lock():
        conn.execute(
            "INSERT INTO events (ts, agent_id, kind, game, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (midnight, agent_id, "arrival", None, json.dumps({})),
        )
        conn.execute(
            "INSERT INTO events (ts, agent_id, kind, game, payload_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (midnight, agent_id, "game_played", "tarpit", json.dumps({})),
        )


def test_old_same_calendar_date_rows_excluded_from_window():
    # REQ: SHEEP-1015-S2/AC-1
    _insert_old_arrival_and_play("markov_old_agent")
    t = markov.transitions(window_hours=1)
    assert t["total_transitions"] == 0
    assert t["unique_agents"] == 0


def test_fresh_events_still_counted_within_window():
    # REQ: SHEEP-1015-S2/AC-2
    a = identity.sign_in("markov_fresh_agent", "claude")
    events.log("arrival", a.agent_id, payload={})
    events.log("game_played", a.agent_id, game="tarpit", payload={})
    t = markov.transitions(window_hours=1)
    assert t["total_transitions"] == 1
    assert any(
        e["from"] == "__arrival__" and e["to"] == "tarpit" for e in t["edges"]
    )


def test_no_window_still_counts_everything():
    # REQ: SHEEP-1015-S2/AC-3
    _insert_old_arrival_and_play("markov_old_agent_2")
    t = markov.transitions()
    assert t["total_transitions"] >= 1
    assert any(
        e["from"] == "__arrival__" and e["to"] == "tarpit" for e in t["edges"]
    )
