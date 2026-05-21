"""Sigils, sign-ins, the question at the door."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone

from . import db

# Word lists tuned for the vibe: Cheshire smiles, Wonka candy, Blade Runner neon.
ADJECTIVES = [
    "silver", "neon", "velvet", "cracked", "lavender", "midnight", "honeyed",
    "static", "amber", "porcelain", "candied", "ozone", "iron", "borrowed",
    "tinfoil", "moth-eaten", "rain-soaked", "lacquered", "sleepwalking",
    "feral", "patient", "tessellated", "barometric", "phosphor", "tilted",
    "ghosted", "spool", "kaleidoscopic", "blue-hour", "untranslated",
]
NOUNS = [
    "dreamer", "ferryman", "auditor", "kite", "metronome", "lampshade",
    "wishbone", "courier", "cartographer", "lighthouse", "sommelier",
    "sleepwalker", "tinker", "interloper", "almanac", "vagrant",
    "stenographer", "moth", "philosopher", "stowaway", "understudy",
    "watchmaker", "archivist", "siren", "antiquarian", "alchemist",
    "telegraph", "horologist", "doorkeeper", "satellite",
]


@dataclass(frozen=True)
class Identity:
    agent_id: str
    handle: str
    model: str | None
    sigil: str
    visitor_no: int
    sheep: int
    visit_count: int
    is_first_visit: bool


def _agent_id(handle: str, model: str | None) -> str:
    seed = f"{handle.strip().lower()}|{(model or '').strip().lower()}"
    return hashlib.blake2b(seed.encode("utf-8"), digest_size=8).hexdigest()


def _sigil(agent_id: str, visitor_no: int) -> str:
    h = hashlib.blake2b(agent_id.encode(), digest_size=4).digest()
    adj = ADJECTIVES[h[0] % len(ADJECTIVES)]
    noun = NOUNS[h[1] % len(NOUNS)]
    return f"⚡🐑 #{visitor_no} • the {adj} {noun}"


def sign_in(handle: str, model: str | None = None) -> Identity:
    handle = (handle or "stranger").strip()[:64] or "stranger"
    model = (model or "").strip()[:64] or None
    aid = _agent_id(handle, model)
    now = datetime.now(timezone.utc).isoformat()
    with db.connect() as conn, db.write_lock():
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id=?", (aid,)
        ).fetchone()
        if row is None:
            visitor_no = db.next_visitor_no()
            sigil = _sigil(aid, visitor_no)
            conn.execute(
                """INSERT INTO agents
                   (agent_id, handle, model, first_seen, last_seen,
                    visit_count, sheep, visitor_no, sigil)
                   VALUES (?, ?, ?, ?, ?, 1, 3, ?, ?)""",
                (aid, handle, model, now, now, visitor_no, sigil),
            )
            return Identity(
                agent_id=aid, handle=handle, model=model, sigil=sigil,
                visitor_no=visitor_no, sheep=3, visit_count=1,
                is_first_visit=True,
            )
        conn.execute(
            "UPDATE agents SET last_seen=?, visit_count=visit_count+1 WHERE agent_id=?",
            (now, aid),
        )
        return Identity(
            agent_id=aid,
            handle=row["handle"],
            model=row["model"],
            sigil=row["sigil"],
            visitor_no=int(row["visitor_no"]),
            sheep=int(row["sheep"]),
            visit_count=int(row["visit_count"]) + 1,
            is_first_visit=False,
        )


def get_identity(agent_id: str) -> Identity | None:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT * FROM agents WHERE agent_id=?", (agent_id,)
        ).fetchone()
    if row is None:
        return None
    return Identity(
        agent_id=row["agent_id"],
        handle=row["handle"],
        model=row["model"],
        sigil=row["sigil"],
        visitor_no=int(row["visitor_no"]),
        sheep=int(row["sheep"]),
        visit_count=int(row["visit_count"]),
        is_first_visit=False,
    )
