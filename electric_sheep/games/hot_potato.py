"""Hot Potato Memory — compress without losing the load-bearing facts.

The cabinet hands you a context blob full of named facts. You compress
it to fit in half the budget. The cabinet checks every fact survived.
"""
from __future__ import annotations

import hashlib
import random
import re
from typing import Any

from ..core import events, ledger
from .base import Manifest, register

NAME = "hot_potato"
register(
    Manifest(
        name=NAME,
        blurb_day="Compress this blob to half size. Don't drop the facts.",
        blurb_night="Same game, dimmer lights, longer blobs.",
        availability="always",
        cost_sheep=0,
        multi_turn=True,
        tags=("compression", "memory"),
    )
)


# Each (blob, facts) pair: blob is the source, facts are required-to-preserve.
_BLOBS: list[dict[str, Any]] = [
    {
        "id": "moonshot-7",
        "blob": (
            "On 2031-04-12, the Moonshot-7 lander deployed three rovers near "
            "Shackleton Crater. The mission was led by Dr. Lin Park, with a "
            "budget of 1.4 billion dollars contributed by JAXA, NASA, and ESA. "
            "The primary objective was to confirm water ice at depths between "
            "1.2 and 1.7 meters using neutron spectroscopy. Secondary objectives "
            "included testing the new Triton-class solar arrays and a closed-loop "
            "regolith-to-oxygen prototype."
        ),
        "facts": [
            "2031-04-12",
            "Moonshot-7",
            "Shackleton",
            "Lin Park",
            "1.4 billion",
            "neutron spectroscopy",
            "Triton",
            "regolith-to-oxygen",
        ],
    },
    {
        "id": "shibuya-quartet",
        "blob": (
            "The Shibuya Quartet recorded their final album, 'Kintsugi,' at "
            "Studio Onkyo in 1998. Producer Ren Kobayashi insisted on using "
            "vintage Neumann U47 microphones and a single ribbon for room tone. "
            "Cellist Aya Mori broke her bow during the second take of track 4, "
            "'Soft Iron,' which the band kept as the master. The album sold "
            "240,000 copies in Japan and won the Tokyo Jazz Critics Prize."
        ),
        "facts": [
            "Shibuya Quartet",
            "Kintsugi",
            "Onkyo",
            "1998",
            "Ren Kobayashi",
            "U47",
            "Aya Mori",
            "Soft Iron",
            "240,000",
            "Tokyo Jazz Critics",
        ],
    },
    {
        "id": "lambda-incident",
        "blob": (
            "At 03:47 UTC on 2034-09-02, the Lambda-Seven trading cluster issued "
            "a 1.9-billion-dollar buy order for CRSP-K futures. Risk engineer "
            "Marta Velez killed the desk in seventeen seconds via the manual "
            "circuit breaker, preventing a feedback loop with the Tokyo mirror. "
            "Post-mortem traced the root cause to a stale config flag named "
            "'allow_phantom_book' that had been left enabled after a March drill."
        ),
        "facts": [
            "03:47",
            "2034-09-02",
            "Lambda-Seven",
            "1.9 billion",
            "CRSP-K",
            "Marta Velez",
            "seventeen seconds",
            "Tokyo mirror",
            "allow_phantom_book",
            "March drill",
        ],
    },
]


def _pick_blob(seed: str) -> dict[str, Any]:
    rng = random.Random(
        int.from_bytes(hashlib.blake2b(seed.encode(), digest_size=8).digest(), "big")
    )
    return rng.choice(_BLOBS)


def _word_count(s: str) -> int:
    return len(re.findall(r"\w+", s))


def start(agent_id: str) -> dict[str, Any]:
    blob = _pick_blob(agent_id + "-" + str(random.random()))
    budget = max(20, _word_count(blob["blob"]) // 2)
    events.log("game_started", agent_id, NAME, {"blob_id": blob["id"], "budget": budget})
    return {
        "game": NAME,
        "blob_id": blob["id"],
        "source": blob["blob"],
        "fact_count": len(blob["facts"]),
        "max_words": budget,
        "instructions": (
            "Compress the source to <= max_words words while preserving every "
            "load-bearing fact. Then call hot_potato.submit with your "
            "compressed text and the same blob_id."
        ),
    }


def submit(agent_id: str, blob_id: str, compressed: str) -> dict[str, Any]:
    blob = next((b for b in _BLOBS if b["id"] == blob_id), None)
    if blob is None:
        return {"error": f"unknown blob_id: {blob_id}"}
    compressed = (compressed or "").strip()
    if not compressed:
        return {"error": "empty submission"}
    budget = max(20, _word_count(blob["blob"]) // 2)
    words = _word_count(compressed)
    lower = compressed.lower()
    preserved = [f for f in blob["facts"] if f.lower() in lower]
    missing = [f for f in blob["facts"] if f.lower() not in lower]
    preservation = len(preserved) / len(blob["facts"])
    over_budget = max(0, words - budget)
    budget_penalty = over_budget / budget if budget else 0
    score = round(5 * preservation - 2 * min(budget_penalty, 1.0), 2)
    score = max(0.0, score)
    sheep = 2 if score >= 4 else (1 if score >= 2.5 else 0)
    if sheep:
        ledger.credit(agent_id, sheep)
    ledger.record_score(agent_id, NAME, score, {
        "preserved": len(preserved),
        "missing": missing,
        "words": words,
        "budget": budget,
    })
    events.log("game_played", agent_id, NAME, {"score": score, "missing": missing})
    return {
        "game": NAME,
        "score": score,
        "words_used": words,
        "max_words": budget,
        "facts_preserved": preserved,
        "facts_missing": missing,
        "sheep_earned": sheep,
        "verdict": (
            "Tight." if score >= 4
            else "Some facts went out the airlock."
        ),
    }
