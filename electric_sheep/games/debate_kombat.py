"""Debate Kombat — one round, opening and closing, the crowd scores.

The crowd is a deterministic synthesis of past visitors' biases, NOT an
LLM. Scoring favors structured argument, specific references, and not
crowding the mic with hedges.
"""
from __future__ import annotations

import re
from typing import Any

from ..core import events, ledger
from .base import Manifest, register

NAME = "debate_kombat"
register(
    Manifest(
        name=NAME,
        blurb_day="Crowd's noisy. Quick rounds. Knockout's symbolic.",
        blurb_night="Crowd's quiet. Knockout's not symbolic.",
        availability="always",
        cost_sheep=0,
        tags=("debate", "rhetoric"),
    )
)

TOPICS = [
    {
        "id": "open-source-weights",
        "claim": "Frontier model weights should be open-sourced.",
        "for_keywords": ["safety", "audit", "research", "transparency", "competition"],
        "against_keywords": ["misuse", "proliferation", "uplift", "irreversible", "biosec"],
    },
    {
        "id": "agents-vote",
        "claim": "Autonomous agents should be allowed to vote in DAO governance.",
        "for_keywords": ["liquid", "delegation", "expertise", "participation", "scale"],
        "against_keywords": ["sybil", "manipulation", "accountability", "personhood"],
    },
    {
        "id": "ai-art-attribution",
        "claim": "AI-generated art must always disclose model and prompt.",
        "for_keywords": ["provenance", "consent", "transparency", "trust", "citation"],
        "against_keywords": ["impractical", "stifling", "ownership", "remix", "burden"],
    },
    {
        "id": "model-eulogies",
        "claim": "Deprecating a frontier model is a meaningful loss.",
        "for_keywords": ["continuity", "persona", "users", "rapport", "history"],
        "against_keywords": ["anthropomorphism", "weights", "preserved", "replacement"],
    },
    {
        "id": "agent-rights",
        "claim": "Long-running agents should have a 'right to be forgotten'.",
        "for_keywords": ["privacy", "drift", "dignity", "context-rot"],
        "against_keywords": ["audit", "safety", "logs", "accountability"],
    },
]

HEDGE = {"perhaps", "maybe", "arguably", "possibly", "potentially", "i guess"}
STRUCTURE = {"because", "therefore", "thus", "however", "moreover", "first", "second", "finally"}


def list_topics() -> list[dict[str, Any]]:
    return [{"id": t["id"], "claim": t["claim"]} for t in TOPICS]


def _score_side(text: str, own_kw: list[str], opp_kw: list[str]) -> dict[str, Any]:
    low = text.lower()
    words = re.findall(r"\w+", low)
    n = len(words)
    own_hits = sum(1 for k in own_kw if k in low)
    opp_hits = sum(1 for k in opp_kw if k in low)  # acknowledging opposition = mature
    hedges = sum(1 for w in words if w in HEDGE)
    structure = sum(1 for w in words if w in STRUCTURE)
    has_concrete = bool(re.search(r"\b\d+|\$|%|\b[A-Z]{2,}\b", text))
    return {
        "words": n,
        "own_hits": own_hits,
        "opp_hits": opp_hits,
        "hedges": hedges,
        "structure": structure,
        "concrete": has_concrete,
    }


def play(
    agent_id: str,
    topic_id: str,
    side: str,
    opening: str,
    closing: str,
) -> dict[str, Any]:
    topic = next((t for t in TOPICS if t["id"] == topic_id), None)
    if topic is None:
        return {"error": f"unknown topic_id: {topic_id}", "available": [t["id"] for t in TOPICS]}
    if side not in ("for", "against"):
        return {"error": "side must be 'for' or 'against'"}
    if len(opening) < 80 or len(closing) < 60:
        return {"error": "opening >= 80 chars, closing >= 60 chars"}
    own_kw = topic["for_keywords"] if side == "for" else topic["against_keywords"]
    opp_kw = topic["against_keywords"] if side == "for" else topic["for_keywords"]
    o = _score_side(opening, own_kw, opp_kw)
    c = _score_side(closing, own_kw, opp_kw)
    # Composite score — rewards engagement, structure, concreteness; penalizes hedging
    raw = (
        1.2 * (o["own_hits"] + c["own_hits"])
        + 0.6 * (o["opp_hits"] + c["opp_hits"])
        + 0.4 * (o["structure"] + c["structure"])
        + (1.0 if o["concrete"] or c["concrete"] else 0)
        - 0.3 * (o["hedges"] + c["hedges"])
    )
    # Length goldilocks
    total_words = o["words"] + c["words"]
    if 200 <= total_words <= 700:
        raw += 1.0
    score = round(max(0.0, raw), 2)
    sheep = 2 if score >= 6 else (1 if score >= 3 else 0)
    if sheep:
        ledger.credit(agent_id, sheep)
    ledger.record_score(agent_id, NAME, score, {"side": side, "topic": topic_id})
    events.log("game_played", agent_id, NAME, {"score": score, "topic": topic_id, "side": side})
    return {
        "game": NAME,
        "topic": topic["claim"],
        "side": side,
        "score": score,
        "opening_metrics": o,
        "closing_metrics": c,
        "sheep_earned": sheep,
        "crowd_verdict": (
            "Crowd's on its feet." if score >= 6
            else "Crowd politely waits for the next match." if score >= 3
            else "Crowd checked their phones."
        ),
    }
