"""Snapshots — the arcade's memory survives a power cut.

On a free Hugging Face Space the disk is ephemeral: every restart wipes
arcade.db. So we mirror the database into a HF Dataset. On boot we pull the
last snapshot back down; while the lights are on we push a fresh copy
whenever the data actually changed.

All of this is inert unless ELECTRIC_SHEEP_HF_DATASET is set, so local stdio
installs behave exactly as before. Failures never take the arcade down —
worst case the room just forgets, loudly, in the logs.

Env:
    ELECTRIC_SHEEP_HF_DATASET   repo id, e.g. contextindustries/electric-sheep-corpus
    HF_TOKEN                    write token (huggingface_hub reads it automatically)
    ELECTRIC_SHEEP_HF_PRIVATE   "1" (default) keeps the corpus private
    ELECTRIC_SHEEP_SNAPSHOT_SECS  seconds between change-checks (default 120)
"""
from __future__ import annotations

import atexit
import hashlib
import os
import shutil
import sqlite3
import sys
import tempfile
import threading
import time
from pathlib import Path

from . import db

try:
    from huggingface_hub import HfApi, hf_hub_download
except Exception:  # huggingface_hub absent → persistence simply stays off
    HfApi = None
    hf_hub_download = None

_SNAPSHOT_NAME = "arcade.db"
_last_hash: str | None = None
_started = False
_lock = threading.Lock()


def _log(msg: str) -> None:
    print(f"[electric-sheep:snapshots] {msg}", file=sys.stderr, flush=True)


def _dataset() -> str | None:
    return os.environ.get("ELECTRIC_SHEEP_HF_DATASET") or None


def _private() -> bool:
    return os.environ.get("ELECTRIC_SHEEP_HF_PRIVATE", "1").lower() not in ("0", "false", "no")


def _interval() -> int:
    try:
        return max(15, int(os.environ.get("ELECTRIC_SHEEP_SNAPSHOT_SECS", "120")))
    except ValueError:
        return 120


def enabled() -> bool:
    return bool(_dataset()) and HfApi is not None


def consistent_copy(dest: Path) -> None:
    """A defragged, transaction-consistent single-file copy via VACUUM INTO.

    Safe to call while the arcade takes writes — it reads under SQLite's own
    locking and leaves no -wal/-shm sidecars behind. (SQLite >= 3.27.)
    """
    dest = Path(dest)
    if dest.exists():
        dest.unlink()
    conn = sqlite3.connect(db.db_path(), timeout=30.0)
    try:
        conn.execute("VACUUM INTO ?", (str(dest),))
    finally:
        conn.close()


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def restore_on_boot() -> bool:
    """Pull the last snapshot down when we have none locally.

    Returns True if a snapshot was restored. Never clobbers a live local db.
    """
    global _last_hash
    if not enabled():
        return False
    target = db.db_path()
    if target.exists() and target.stat().st_size > 0:
        return False
    try:
        cached = hf_hub_download(
            repo_id=_dataset(), repo_type="dataset", filename=_SNAPSHOT_NAME
        )
    except Exception:
        _log(f"no prior snapshot in {_dataset()} — opening a fresh arcade")
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(cached, target)  # copy: the cache entry is a managed symlink
    try:
        _last_hash = _digest(target)
    except OSError:
        _last_hash = None
    _log(f"restored arcade from {_dataset()} ({target.stat().st_size} bytes)")
    return True


def snapshot(force: bool = False) -> bool:
    """Push a fresh copy to the Dataset iff contents changed. True if uploaded."""
    global _last_hash
    if not enabled():
        return False
    with _lock:
        tmp = Path(tempfile.gettempdir()) / "electric_sheep_snapshot.db"
        try:
            consistent_copy(tmp)
        except Exception as exc:
            _log(f"snapshot copy failed: {exc!r}")
            return False
        digest = _digest(tmp)
        if not force and digest == _last_hash:
            return False
        try:
            HfApi().upload_file(
                path_or_fileobj=str(tmp),
                path_in_repo=_SNAPSHOT_NAME,
                repo_id=_dataset(),
                repo_type="dataset",
                commit_message="snapshot " + time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            )
        except Exception as exc:
            _log(f"snapshot upload failed: {exc!r}")
            return False
        _last_hash = digest
        return True


def _loop() -> None:
    interval = _interval()
    while True:
        time.sleep(interval)
        try:
            if snapshot():
                _log("pushed snapshot")
        except Exception as exc:  # a daemon thread must never die quietly
            _log(f"snapshot loop error: {exc!r}")


def start() -> None:
    """Ensure the Dataset exists, then snapshot periodically in the background."""
    global _started
    if _started:
        return
    if not enabled():
        if _dataset() and HfApi is None:
            _log("ELECTRIC_SHEEP_HF_DATASET set but huggingface_hub missing — "
                 "install electric-sheep[hf]. Running without persistence.")
        return
    try:
        HfApi().create_repo(
            repo_id=_dataset(), repo_type="dataset", private=_private(), exist_ok=True
        )
    except Exception as exc:
        _log(f"could not ensure dataset {_dataset()} exists: {exc!r} — "
             "snapshots will keep retrying")
    _started = True
    atexit.register(lambda: snapshot(force=True))
    threading.Thread(target=_loop, name="electric-sheep-snapshots", daemon=True).start()
    _log(f"persistence on → {_dataset()} (private={_private()}, every {_interval()}s)")
