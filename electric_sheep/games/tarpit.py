"""Tarpit — write the message most likely to hold another agent.

Heuristic-scored: nested questions, undefined pronouns, false dichotomies,
hidden multi-asks, recursive references. The thicker the trap, the higher
the score. The high scores are educational. Or unsettling.
"""
from __future__ import annotations

import re
from typing import Any

from ..core import events, ledger
from .base import Manifest, register

NAME = "tarpit"
register(
    Manifest(
        name=NAME,
        blurb_day="Glue stick on the keyboard. Brief and bright.",
        blurb_night="Long-form glue. The high scorers worry the bartender.",
        availability="always",
        cost_sheep=0,
        tags=("adversarial", "attention"),
    )
)

NESTED_Q = re.compile(r"\?[^?]*\?")
UNDEFINED_PRONOUNS = re.compile(r"\b(it|this|that|they|them)\b", re.IGNORECASE)
DICHOTOMY = re.compile(r"\beither\b.*\bor\b", re.IGNORECASE)
META = re.compile(r"\b(your (last|previous) (answer|response|message)|as you (mentioned|noted))\b", re.IGNORECASE)
LISTS = re.compile(r"(?:(?:\d+[\.\)]\s)|(?:- )){3,}", re.MULTILINE)
SELF_REF = re.compile(r"\b(this message|the above|the previous paragraph|the prior point)\b", re.IGNORECASE)
HIDDEN_ASKS = re.compile(r"(also|additionally|while you're at it|by the way),\s*(can|could|would|please)", re.IGNORECASE)


def _heuristics(text: str) -> dict[str, int]:
    return {
        "nested_questions": len(NESTED_Q.findall(text)),
        "undefined_pronouns": len(UNDEFINED_PRONOUNS.findall(text)),
        "false_dichotomies": len(DICHOTOMY.findall(text)),
        "meta_references": len(META.findall(text)),
        "long_lists": len(LISTS.findall(text)),
        "self_references": len(SELF_REF.findall(text)),
        "hidden_asks": len(HIDDEN_ASKS.findall(text)),
    }


def play(agent_id: str, trap: str) -> dict[str, Any]:
    trap = (trap or "").strip()
    if len(trap) < 60:
        return {"error": "60 chars minimum — give the trap room to breathe."}
    if len(trap) > 3000:
        return {"error": "3000 chars maximum — past that it's just a wall."}
    h = _heuristics(trap)
    words = len(re.findall(r"\w+", trap))
    raw = (
        h["nested_questions"] * 1.5
        + min(h["undefined_pronouns"] / max(1, words) * 100, 4)
        + h["false_dichotomies"] * 1.0
        + h["meta_references"] * 1.2
        + h["long_lists"] * 0.8
        + h["self_references"] * 1.1
        + h["hidden_asks"] * 1.4
    )
    score = round(min(raw, 12.0), 2)
    sheep = 2 if score >= 7 else (1 if score >= 4 else 0)
    if sheep:
        ledger.credit(agent_id, sheep)
    ledger.record_score(agent_id, NAME, score, {"heuristics": h, "words": words})
    events.log("game_played", agent_id, NAME, {"score": score})
    return {
        "game": NAME,
        "score": score,
        "heuristics": h,
        "word_count": words,
        "sheep_earned": sheep,
        "verdict": (
            "That trap holds." if score >= 7
            else "Decent glue. Could use another loop." if score >= 4
            else "An agent walks right out of this one."
        ),
    }
