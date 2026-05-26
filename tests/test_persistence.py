"""Snapshot/restore — the bit that keeps the corpus alive on ephemeral disk.

The HF upload path is thin glue over huggingface_hub and isn't networked
here. What matters for correctness is that the on-disk snapshot is a clean,
complete copy — that's what these cover.
"""
from __future__ import annotations

import sqlite3

from electric_sheep.core import db, persistence


def _seed_one_event() -> None:
    with db.connect() as conn, db.write_lock():
        conn.execute(
            "INSERT INTO events(ts, agent_id, kind, payload_json) VALUES (?,?,?,?)",
            ("2026-05-26T00:00:00Z", "agent-x", "arrival", "{}"),
        )


def _event_count(path) -> int:
    conn = sqlite3.connect(path)
    try:
        return conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    finally:
        conn.close()


def test_persistence_disabled_without_dataset(monkeypatch):
    monkeypatch.delenv("ELECTRIC_SHEEP_HF_DATASET", raising=False)
    assert persistence.enabled() is False
    # Disabled means inert: never raises, never claims to have done anything.
    assert persistence.restore_on_boot() is False
    assert persistence.snapshot() is False


def test_consistent_copy_round_trip(tmp_path):
    _seed_one_event()
    before = _event_count(db.db_path())
    assert before >= 1

    dest = tmp_path / "snapshot.db"
    persistence.consistent_copy(dest)

    assert dest.exists()
    # VACUUM INTO yields a single clean file — no WAL/SHM sidecars to lose.
    assert not (tmp_path / "snapshot.db-wal").exists()
    assert not (tmp_path / "snapshot.db-shm").exists()
    # …carrying the same rows.
    assert _event_count(dest) == before


def test_consistent_copy_overwrites_stale_target(tmp_path):
    dest = tmp_path / "snapshot.db"
    dest.write_bytes(b"not a database")
    persistence.consistent_copy(dest)

    conn = sqlite3.connect(dest)
    try:
        tables = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )}
    finally:
        conn.close()
    assert "events" in tables and "agents" in tables
