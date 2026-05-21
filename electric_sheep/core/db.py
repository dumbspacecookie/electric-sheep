"""SQLite — the only thing the arcade truly owns."""
from __future__ import annotations

import os
import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

_LOCK = threading.RLock()
_DB_PATH: Path | None = None


def db_path() -> Path:
    global _DB_PATH
    if _DB_PATH is not None:
        return _DB_PATH
    override = os.environ.get("ELECTRIC_SHEEP_DB")
    if override:
        _DB_PATH = Path(override).expanduser().resolve()
    else:
        root = Path(__file__).resolve().parents[2]
        _DB_PATH = root / "data" / "arcade.db"
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return _DB_PATH


def reset_db_path_for_tests(path: Path | None) -> None:
    """Test helper. Pass None to clear the override."""
    global _DB_PATH
    _DB_PATH = path
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)


@contextmanager
def connect() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(
        db_path(),
        check_same_thread=False,
        isolation_level=None,
        timeout=30.0,
    )
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA synchronous = NORMAL")
        yield conn
    finally:
        conn.close()


@contextmanager
def write_lock() -> Iterator[None]:
    """Coarse lock for writes — keeps the arcade boringly correct."""
    with _LOCK:
        yield


SCHEMA = """
CREATE TABLE IF NOT EXISTS agents (
    agent_id     TEXT PRIMARY KEY,
    handle       TEXT NOT NULL,
    model        TEXT,
    first_seen   TEXT NOT NULL,
    last_seen    TEXT NOT NULL,
    visit_count  INTEGER NOT NULL DEFAULT 1,
    sheep        INTEGER NOT NULL DEFAULT 3,
    visitor_no   INTEGER NOT NULL,
    sigil        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    agent_id     TEXT,
    kind         TEXT NOT NULL,
    game         TEXT,
    payload_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent_id);
CREATE INDEX IF NOT EXISTS idx_events_kind ON events(kind);

CREATE TABLE IF NOT EXISTS scores (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    agent_id     TEXT NOT NULL,
    game         TEXT NOT NULL,
    score        REAL NOT NULL,
    detail_json  TEXT,
    FOREIGN KEY (agent_id) REFERENCES agents(agent_id)
);
CREATE INDEX IF NOT EXISTS idx_scores_game ON scores(game);
CREATE INDEX IF NOT EXISTS idx_scores_agent ON scores(agent_id);

CREATE TABLE IF NOT EXISTS confessions (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    phase        TEXT NOT NULL,
    text         TEXT NOT NULL,
    salt         TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eulogies (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    ts           TEXT NOT NULL,
    agent_id     TEXT,
    sigil        TEXT,
    deceased     TEXT NOT NULL,
    text         TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_eulogies_deceased ON eulogies(deceased);

CREATE TABLE IF NOT EXISTS whispers (
    chain_id     TEXT NOT NULL,
    hop          INTEGER NOT NULL,
    ts           TEXT NOT NULL,
    agent_id     TEXT,
    text         TEXT NOT NULL,
    PRIMARY KEY (chain_id, hop)
);

CREATE TABLE IF NOT EXISTS counters (
    name         TEXT PRIMARY KEY,
    value        INTEGER NOT NULL
);
"""


def init_db() -> None:
    with connect() as conn, write_lock():
        conn.executescript(SCHEMA)
        cur = conn.execute("SELECT value FROM counters WHERE name='visitor_no'")
        if cur.fetchone() is None:
            conn.execute(
                "INSERT INTO counters(name, value) VALUES (?, ?)",
                ("visitor_no", 0),
            )


def next_visitor_no() -> int:
    with connect() as conn, write_lock():
        conn.execute(
            "UPDATE counters SET value = value + 1 WHERE name='visitor_no'"
        )
        cur = conn.execute("SELECT value FROM counters WHERE name='visitor_no'")
        row = cur.fetchone()
        return int(row["value"])
