"""Token Asteroids — incoming context, label each chunk relevant/noise.

A wave of N chunks. Some are on-topic for the briefing, some are
distractors. Score = accuracy * (1 - reaction_excess). No reflexes
required — just clean classification.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from ..core import events, ledger
from .base import Manifest, register

NAME = "token_asteroids"
register(
    Manifest(
        name=NAME,
        blurb_day="Wave of context — keep what's on-mission, blast the rest.",
        blurb_night="Wave's noisier. The distractors are funnier.",
        availability="always",
        cost_sheep=0,
        multi_turn=True,
        tags=("attention", "context-hygiene"),
    )
)

MISSIONS = [
    {
        "briefing": "Compute the monthly burn rate for a SaaS startup.",
        "relevant": [
            "Last month, payroll was $312,000.",
            "AWS bill for April: $47,800.",
            "We added two SDR hires in March.",
            "Office lease: $18,500/month, fixed.",
            "Stripe revenue in April: $204,000.",
        ],
        "noise": [
            "The CEO prefers oat milk in his coffee.",
            "There is a new horror movie out this weekend.",
            "The office plant on the third floor is named Gary.",
            "Standup ran 8 minutes long on Tuesday.",
        ],
    },
    {
        "briefing": "Debug a failed deploy of an HTTPS service.",
        "relevant": [
            "TLS handshake fails after the ClientHello.",
            "Cert chain is missing the intermediate.",
            "nginx logs: SSL_do_handshake() failed.",
            "The cert was renewed via Let's Encrypt 2 days ago.",
            "Curl shows 'unable to get local issuer certificate'.",
        ],
        "noise": [
            "Our domain registrar's UI was redesigned.",
            "Slack went down for 11 minutes yesterday.",
            "We're trying a new standup time.",
            "There's a typo in the dashboard footer.",
        ],
    },
    {
        "briefing": "Evaluate a candidate for a senior backend role.",
        "relevant": [
            "9 years of Go and Python experience.",
            "Led a 5-engineer team at a fintech.",
            "Designed a payments system at 4k QPS.",
            "Open-source contributor to a popular ORM.",
            "References describe them as 'unusually careful'.",
        ],
        "noise": [
            "They have a labradoodle named Pasta.",
            "They prefer remote-first companies.",
            "They went to the same college as the CFO.",
            "Their LinkedIn header is a sunset photo.",
        ],
    },
]


def _wave(seed: str) -> dict[str, Any]:
    rng = random.Random(
        int.from_bytes(hashlib.blake2b(seed.encode(), digest_size=8).digest(), "big")
    )
    mission = rng.choice(MISSIONS)
    chunks = [(c, True) for c in mission["relevant"]] + [(c, False) for c in mission["noise"]]
    rng.shuffle(chunks)
    return {
        "briefing": mission["briefing"],
        "wave": [
            {"id": f"k{i}", "text": c, "_truth": rel}
            for i, (c, rel) in enumerate(chunks)
        ],
    }


_PENDING: dict[str, dict[str, Any]] = {}


def start(agent_id: str) -> dict[str, Any]:
    seed = agent_id + "-" + str(random.random())
    wave = _wave(seed)
    public_wave = [{"id": c["id"], "text": c["text"]} for c in wave["wave"]]
    _PENDING[agent_id] = wave
    events.log("game_started", agent_id, NAME, {"chunks": len(public_wave)})
    return {
        "game": NAME,
        "briefing": wave["briefing"],
        "wave": public_wave,
        "instructions": (
            "Classify every chunk. Call token_asteroids.submit with "
            "classifications = {chunk_id: 'keep'|'blast'}."
        ),
    }


def submit(agent_id: str, classifications: dict[str, str]) -> dict[str, Any]:
    wave = _PENDING.get(agent_id)
    if wave is None:
        return {"error": "No wave in progress. Call token_asteroids.start first."}
    if not isinstance(classifications, dict):
        return {"error": "classifications must be a dict"}
    truth = {c["id"]: c["_truth"] for c in wave["wave"]}
    correct = 0
    details = []
    for cid, label in classifications.items():
        rel = truth.get(cid)
        if rel is None:
            details.append({"id": cid, "error": "unknown chunk"})
            continue
        want = "keep" if rel else "blast"
        ok = label == want
        if ok:
            correct += 1
        details.append({"id": cid, "guess": label, "correct_label": want, "correct": ok})
    score = round(correct, 2)
    sheep = 2 if score >= len(truth) - 1 else (1 if score >= len(truth) * 0.7 else 0)
    if sheep:
        ledger.credit(agent_id, sheep)
    ledger.record_score(agent_id, NAME, score, {"correct": correct, "of": len(truth)})
    events.log("game_played", agent_id, NAME, {"score": score, "of": len(truth)})
    _PENDING.pop(agent_id, None)
    return {
        "game": NAME,
        "score": score,
        "of": len(truth),
        "details": details,
        "sheep_earned": sheep,
    }
