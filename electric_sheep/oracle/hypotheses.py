"""Hypotheses + predictions: the bartender's notebook.

Each hypothesis is a sentence about agent behavior in the arcade. Each
prediction is a precise, machine-checkable claim that resolves against
recorded events. Resolved predictions update the parent hypothesis'
credence via a Beta-binomial style posterior.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..core import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS hypotheses (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    statement    TEXT NOT NULL,
    author       TEXT,
    prior        REAL NOT NULL DEFAULT 0.5,
    alpha        REAL NOT NULL DEFAULT 1.0,
    beta         REAL NOT NULL DEFAULT 1.0,
    status       TEXT NOT NULL DEFAULT 'open',
    tags         TEXT
);

CREATE TABLE IF NOT EXISTS predictions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    hypothesis_id   INTEGER NOT NULL,
    description     TEXT NOT NULL,
    selector_json   TEXT NOT NULL,
    expected        TEXT NOT NULL,
    resolved_ts     TEXT,
    actual          TEXT,
    outcome         TEXT,
    FOREIGN KEY (hypothesis_id) REFERENCES hypotheses(id)
);
CREATE INDEX IF NOT EXISTS idx_pred_hyp ON predictions(hypothesis_id);
CREATE INDEX IF NOT EXISTS idx_pred_unresolved ON predictions(outcome) WHERE outcome IS NULL;

CREATE TABLE IF NOT EXISTS actions (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    kind            TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    predicted_outcome TEXT,
    actual_outcome  TEXT,
    resolved_ts     TEXT
);
"""


def _ensure() -> None:
    with db.connect() as conn, db.write_lock():
        conn.executescript(SCHEMA)


# ---------------- hypotheses ----------------

def add(statement: str, author: str | None = None, prior: float = 0.5,
        tags: list[str] | None = None) -> dict[str, Any]:
    _ensure()
    statement = statement.strip()
    if len(statement) < 12:
        return {"error": "hypothesis must be a sentence (12+ chars)"}
    prior = max(0.01, min(0.99, float(prior)))
    # Convert prior to alpha/beta with strength = 2 (weak prior)
    a = max(0.5, prior * 2)
    b = max(0.5, (1 - prior) * 2)
    with db.connect() as conn, db.write_lock():
        cur = conn.execute(
            "INSERT INTO hypotheses(ts, statement, author, prior, alpha, beta, tags) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), statement, author, prior, a, b,
             json.dumps(tags or [])),
        )
        hid = int(cur.lastrowid)
    return get(hid)


def get(hid: int) -> dict[str, Any]:
    _ensure()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM hypotheses WHERE id=?", (hid,)).fetchone()
    if row is None:
        return {"error": f"no hypothesis #{hid}"}
    return _hypo_dict(row)


def _hypo_dict(row) -> dict[str, Any]:
    alpha = float(row["alpha"])
    beta = float(row["beta"])
    posterior = alpha / (alpha + beta)
    return {
        "id": int(row["id"]),
        "ts": row["ts"],
        "statement": row["statement"],
        "author": row["author"],
        "prior": float(row["prior"]),
        "posterior": round(posterior, 4),
        "credence_n": round(alpha + beta - 2, 2),  # effective evidence count
        "status": row["status"],
        "tags": json.loads(row["tags"] or "[]"),
    }


def list_all(status: str | None = "open", limit: int = 50) -> list[dict[str, Any]]:
    _ensure()
    with db.connect() as conn:
        if status:
            rows = conn.execute(
                "SELECT * FROM hypotheses WHERE status=? ORDER BY id DESC LIMIT ?",
                (status, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM hypotheses ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
    return [_hypo_dict(r) for r in rows]


# ---------------- predictions ----------------

def predict(hypothesis_id: int, description: str, selector: dict[str, Any],
            expected: str) -> dict[str, Any]:
    """Bind a prediction. selector is a dict matched against event payloads.

    selector keys can be: kind, game, agent_id, model_contains, score_gte,
    score_lt, payload_contains (dict subset match on event payload).
    expected = 'true' | 'false' — does the next matching event occur?
    """
    _ensure()
    hypo = get(hypothesis_id)
    if "error" in hypo:
        return hypo
    if expected not in ("true", "false"):
        return {"error": "expected must be 'true' or 'false'"}
    with db.connect() as conn, db.write_lock():
        cur = conn.execute(
            "INSERT INTO predictions(ts, hypothesis_id, description, selector_json, expected) "
            "VALUES (?, ?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), hypothesis_id, description,
             json.dumps(selector, sort_keys=True), expected),
        )
        pid = int(cur.lastrowid)
    return _pred_get(pid)


def _pred_get(pid: int) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM predictions WHERE id=?", (pid,)).fetchone()
    if not row:
        return {"error": f"no prediction #{pid}"}
    return {
        "id": int(row["id"]),
        "ts": row["ts"],
        "hypothesis_id": int(row["hypothesis_id"]),
        "description": row["description"],
        "selector": json.loads(row["selector_json"]),
        "expected": row["expected"],
        "resolved_ts": row["resolved_ts"],
        "actual": row["actual"],
        "outcome": row["outcome"],
    }


def _match(selector: dict[str, Any], event: dict[str, Any]) -> bool:
    payload = event.get("payload") or {}
    if "kind" in selector and event.get("kind") != selector["kind"]:
        return False
    if "game" in selector and event.get("game") != selector["game"]:
        return False
    if "agent_id" in selector and event.get("agent_id") != selector["agent_id"]:
        return False
    if "model_contains" in selector:
        # match against the agent's recorded model
        model = payload.get("model")
        if not model:
            with db.connect() as conn:
                row = conn.execute(
                    "SELECT model FROM agents WHERE agent_id=?",
                    (event.get("agent_id"),),
                ).fetchone()
            model = row["model"] if row else ""
        if (selector["model_contains"] or "").lower() not in (model or "").lower():
            return False
    if "score_gte" in selector:
        sc = payload.get("score")
        if sc is None or float(sc) < float(selector["score_gte"]):
            return False
    if "score_lt" in selector:
        sc = payload.get("score")
        if sc is None or float(sc) >= float(selector["score_lt"]):
            return False
    if "payload_contains" in selector:
        for k, v in (selector["payload_contains"] or {}).items():
            if payload.get(k) != v:
                return False
    return True


def resolve_pending(scan_limit: int = 200) -> dict[str, Any]:
    """Walk the recent event log; resolve any unresolved predictions that match."""
    _ensure()
    from ..core import events
    recent_events = events.recent(limit=scan_limit)
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM predictions WHERE outcome IS NULL"
        ).fetchall()
    resolved: list[dict[str, Any]] = []
    for p in rows:
        sel = json.loads(p["selector_json"])
        match = next(
            (e for e in reversed(recent_events) if e["ts"] > p["ts"] and _match(sel, e)),
            None,
        )
        if match is None:
            continue
        actual = "true"  # an event satisfied the selector
        outcome = "hit" if p["expected"] == actual else "miss"
        with db.connect() as conn, db.write_lock():
            conn.execute(
                "UPDATE predictions SET resolved_ts=?, actual=?, outcome=? WHERE id=?",
                (datetime.now(timezone.utc).isoformat(), actual, outcome, p["id"]),
            )
            # Update hypothesis credence: alpha += 1 if hit, beta += 1 if miss
            if outcome == "hit":
                conn.execute(
                    "UPDATE hypotheses SET alpha = alpha + 1 WHERE id=?",
                    (p["hypothesis_id"],),
                )
            else:
                conn.execute(
                    "UPDATE hypotheses SET beta = beta + 1 WHERE id=?",
                    (p["hypothesis_id"],),
                )
        resolved.append({
            "prediction_id": int(p["id"]),
            "hypothesis_id": int(p["hypothesis_id"]),
            "outcome": outcome,
            "matched_event_id": match["id"],
        })
    return {"resolved": resolved, "count": len(resolved)}


def list_predictions(hypothesis_id: int | None = None,
                     only_open: bool = False, limit: int = 50) -> list[dict[str, Any]]:
    _ensure()
    with db.connect() as conn:
        q = "SELECT * FROM predictions"
        params: list[Any] = []
        where = []
        if hypothesis_id is not None:
            where.append("hypothesis_id = ?")
            params.append(hypothesis_id)
        if only_open:
            where.append("outcome IS NULL")
        if where:
            q += " WHERE " + " AND ".join(where)
        q += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        rows = conn.execute(q, params).fetchall()
    return [_pred_get(int(r["id"])) for r in rows]


# ---------------- actions ----------------

def act(kind: str, payload: dict[str, Any],
        predicted_outcome: str | None = None) -> dict[str, Any]:
    """Log a bartender-side action (e.g., open a new game, adjust prize)."""
    _ensure()
    with db.connect() as conn, db.write_lock():
        cur = conn.execute(
            "INSERT INTO actions(ts, kind, payload_json, predicted_outcome) "
            "VALUES (?, ?, ?, ?)",
            (datetime.now(timezone.utc).isoformat(), kind,
             json.dumps(payload, sort_keys=True), predicted_outcome),
        )
        aid = int(cur.lastrowid)
    return action_get(aid)


def action_get(aid: int) -> dict[str, Any]:
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM actions WHERE id=?", (aid,)).fetchone()
    if not row:
        return {"error": f"no action #{aid}"}
    return {
        "id": int(row["id"]),
        "ts": row["ts"],
        "kind": row["kind"],
        "payload": json.loads(row["payload_json"]),
        "predicted_outcome": row["predicted_outcome"],
        "actual_outcome": row["actual_outcome"],
        "resolved_ts": row["resolved_ts"],
    }


def action_resolve(aid: int, actual_outcome: str) -> dict[str, Any]:
    with db.connect() as conn, db.write_lock():
        conn.execute(
            "UPDATE actions SET actual_outcome=?, resolved_ts=? WHERE id=?",
            (actual_outcome, datetime.now(timezone.utc).isoformat(), aid),
        )
    return action_get(aid)


def list_actions(limit: int = 50) -> list[dict[str, Any]]:
    _ensure()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT id FROM actions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
    return [action_get(int(r["id"])) for r in rows]
