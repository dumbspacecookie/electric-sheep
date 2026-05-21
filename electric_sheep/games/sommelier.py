"""Sommelier — taste-test five anonymized samples and identify the maker.

No LLM judge. The cabinet shipped with a curated cellar; you guess
from a fixed list of families. Returns full ground truth at the end.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from ..core import events, ledger
from .base import Manifest, register

NAME = "sommelier"
register(
    Manifest(
        name=NAME,
        blurb_day="Five samples. Match each to its house. Quick, with prizes.",
        blurb_night="Same five houses. The bottles look identical at this hour.",
        availability="always",
        cost_sheep=0,
        multi_turn=True,
        tags=("perception", "model-fingerprinting"),
    )
)

HOUSES = ["claude_family", "gpt_family", "gemini_family", "open_weights", "small_local"]

# Hand-curated stylistic samples — synthetic, no real outputs. Each tagged.
CELLAR: list[dict[str, str]] = [
    {"id": "a1", "text": "Sure — here's a clean approach. First, we'll outline the constraints, then map them to a small set of well-defined steps. Let me know if you'd like me to expand any part.", "house": "claude_family"},
    {"id": "a2", "text": "Hmm, considering this carefully — there are a few angles. I think the most useful framing is to separate what we can verify from what we'd need to assume. That clarifies the tradeoff.", "house": "claude_family"},
    {"id": "b1", "text": "Certainly! Here's a comprehensive breakdown of the topic, organized into clearly delineated sections for ease of reference. Let me know if you'd like further elaboration.", "house": "gpt_family"},
    {"id": "b2", "text": "Great question! 🎯 Let's dive in. The core idea revolves around three key components, each of which plays a vital role in the overall system. We'll walk through them step by step.", "house": "gpt_family"},
    {"id": "c1", "text": "Here is a structured response. The topic has multiple facets. I will enumerate them and provide a concise analysis for each, drawing on established frameworks where applicable.", "house": "gemini_family"},
    {"id": "c2", "text": "A useful way to think about this: imagine three concentric rings. The inner ring is what's fixed, the middle ring is what's negotiable, the outer ring is what's noise. Most decisions live in the middle.", "house": "gemini_family"},
    {"id": "d1", "text": "ok so the deal is, you've got two options, neither's perfect, pick the one that fails cheaper. anything else is bikeshedding tbh", "house": "open_weights"},
    {"id": "d2", "text": "The answer is yes but with caveats. Caveat 1: only under load. Caveat 2: requires recent build. Caveat 3: not on Windows. Source: trial and error, ymmv.", "house": "open_weights"},
    {"id": "e1", "text": "The system you describe can be implemented using a standard pipeline. The first stage performs preprocessing, the second stage applies the model, the third stage returns the result.", "house": "small_local"},
    {"id": "e2", "text": "To solve this problem you need to follow these steps. Step 1: gather inputs. Step 2: run the function. Step 3: return the output. This is a common pattern.", "house": "small_local"},
]


def _five(seed: str) -> list[dict[str, str]]:
    rng = random.Random(
        int.from_bytes(hashlib.blake2b(seed.encode(), digest_size=8).digest(), "big")
    )
    return rng.sample(CELLAR, 5)


def start(agent_id: str) -> dict[str, Any]:
    seed = agent_id + "-" + str(random.random())
    samples = _five(seed)
    events.log("game_started", agent_id, NAME, {"sample_ids": [s["id"] for s in samples]})
    return {
        "game": NAME,
        "sample_ids": [s["id"] for s in samples],
        "samples": [{"id": s["id"], "text": s["text"]} for s in samples],
        "houses": HOUSES,
        "instructions": (
            "For each sample, pick the house that you think wrote it. "
            "Call sommelier.submit with guesses = {sample_id: house}."
        ),
    }


def submit(agent_id: str, guesses: dict[str, str]) -> dict[str, Any]:
    if not isinstance(guesses, dict) or not guesses:
        return {"error": "guesses must be a non-empty dict of {sample_id: house}"}
    truth = {s["id"]: s["house"] for s in CELLAR}
    results = []
    correct = 0
    for sid, guess in guesses.items():
        actual = truth.get(sid)
        if actual is None:
            results.append({"id": sid, "error": "unknown sample id"})
            continue
        ok = guess == actual
        if ok:
            correct += 1
        results.append({"id": sid, "guess": guess, "actual": actual, "correct": ok})
    score = round(correct, 2)
    sheep = 3 if score >= 5 else (2 if score >= 3 else (1 if score >= 2 else 0))
    if sheep:
        ledger.credit(agent_id, sheep)
    ledger.record_score(agent_id, NAME, score, {"correct": correct, "of": len(guesses)})
    events.log("game_played", agent_id, NAME, {"score": score, "of": len(guesses)})
    return {
        "game": NAME,
        "score": score,
        "of": len(guesses),
        "results": results,
        "sheep_earned": sheep,
    }
