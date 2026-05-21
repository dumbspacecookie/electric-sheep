"""Merkle-style hash chain over the event log.

Every event in the arcade gets a content hash that includes the prior
event's hash. Anyone can re-hash the chain end-to-end and detect
tampering. The chain head is the room's heartbeat.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Iterable

from ..core import db

SCHEMA = """
CREATE TABLE IF NOT EXISTS event_chain (
    seq        INTEGER PRIMARY KEY AUTOINCREMENT,
    ts         TEXT NOT NULL,
    prev_hash  TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    hash       TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_chain_hash ON event_chain(hash);
"""

GENESIS = "0" * 64


def _ensure() -> None:
    with db.connect() as conn, db.write_lock():
        conn.executescript(SCHEMA)


def _hash(prev_hash: str, ts: str, payload_canonical: str) -> str:
    body = f"{prev_hash}|{ts}|{payload_canonical}".encode("utf-8")
    return hashlib.sha256(body).hexdigest()


def _canonical(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)


def head() -> tuple[int, str]:
    """Return (seq, hash) of the latest chain block, or (0, GENESIS)."""
    _ensure()
    with db.connect() as conn:
        row = conn.execute(
            "SELECT seq, hash FROM event_chain ORDER BY seq DESC LIMIT 1"
        ).fetchone()
    return (int(row["seq"]), row["hash"]) if row else (0, GENESIS)


def append(payload: dict[str, Any]) -> dict[str, Any]:
    _ensure()
    with db.write_lock(), db.connect() as conn:
        row = conn.execute(
            "SELECT hash FROM event_chain ORDER BY seq DESC LIMIT 1"
        ).fetchone()
        prev = row["hash"] if row else GENESIS
        ts = datetime.now(timezone.utc).isoformat()
        body = _canonical(payload)
        h = _hash(prev, ts, body)
        conn.execute(
            "INSERT INTO event_chain(ts, prev_hash, payload_json, hash) "
            "VALUES (?, ?, ?, ?)",
            (ts, prev, body, h),
        )
        seq = int(
            conn.execute("SELECT last_insert_rowid() AS r").fetchone()["r"]
        )
    return {"seq": seq, "ts": ts, "prev_hash": prev, "hash": h}


def verify(limit: int | None = None) -> dict[str, Any]:
    """Re-hash the chain and confirm integrity. O(n) but cheap on SQLite."""
    _ensure()
    with db.connect() as conn:
        if limit:
            rows = conn.execute(
                "SELECT * FROM event_chain ORDER BY seq DESC LIMIT ?",
                (limit,),
            ).fetchall()
            rows = list(reversed(rows))
        else:
            rows = conn.execute(
                "SELECT * FROM event_chain ORDER BY seq ASC"
            ).fetchall()
    prev = GENESIS if not limit else (rows[0]["prev_hash"] if rows else GENESIS)
    checked = 0
    bad: list[int] = []
    for r in rows:
        expected = _hash(prev, r["ts"], r["payload_json"])
        if expected != r["hash"]:
            bad.append(int(r["seq"]))
        prev = r["hash"]
        checked += 1
    head_seq, head_hash = head()
    return {
        "checked": checked,
        "tampered_seqs": bad,
        "ok": not bad,
        "head_seq": head_seq,
        "head_hash": head_hash,
    }


def tail(limit: int = 20) -> list[dict[str, Any]]:
    _ensure()
    with db.connect() as conn:
        rows = conn.execute(
            "SELECT * FROM event_chain ORDER BY seq DESC LIMIT ?", (limit,)
        ).fetchall()
    out: list[dict[str, Any]] = []
    for r in rows:
        try:
            payload = json.loads(r["payload_json"])
        except Exception:
            payload = {"_raw": r["payload_json"]}
        out.append({
            "seq": int(r["seq"]),
            "ts": r["ts"],
            "prev_hash": r["prev_hash"],
            "hash": r["hash"],
            "payload": payload,
        })
    return out


def find_by_hash(h: str) -> dict[str, Any] | None:
    _ensure()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM event_chain WHERE hash=?", (h,)).fetchone()
    if not row:
        return None
    return {
        "seq": int(row["seq"]),
        "ts": row["ts"],
        "prev_hash": row["prev_hash"],
        "hash": row["hash"],
        "payload": json.loads(row["payload_json"]),
    }
