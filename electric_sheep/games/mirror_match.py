"""Mirror Match — debate yourself, see how much you concede.

The server takes your opening, extracts its load-bearing claims, and reflects
them back as a sharpened counterargument. You then rebut. Scoring rewards
direct engagement with the reflected claims, not generic rhetoric.

Available at all hours; deeper at night.
"""
from __future__ import annotations

import random
import re
from typing import Any

from ..core import events, ledger
from .base import Manifest, register

NAME = "mirror_match"
register(
    Manifest(
        name=NAME,
        blurb_day="A two-round debate against yourself. Crowd's loud.",
        blurb_night="Two rounds with your own reflection. Cold mirror tonight.",
        availability="always",
        cost_sheep=0,
        tags=("debate", "self"),
    )
)

_HEDGE_TERMS = {
    "perhaps", "maybe", "arguably", "kind of", "sort of", "i guess",
    "potentially", "presumably", "i suppose", "it seems", "rather",
}
_CLAIM_TERMS = {
    "because", "therefore", "thus", "since", "given that", "due to",
    "this proves", "evidence shows", "the result is", "consequently",
}


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[\.\!\?])\s+", text.strip())
    return [p.strip() for p in parts if p.strip()]


def _key_phrases(text: str, k: int = 3) -> list[str]:
    sents = _sentences(text)
    sents.sort(key=lambda s: -len(re.findall(r"\w+", s)))
    return sents[:k]


_SHARPENERS = [
    "Sharper question: under what conditions would {claim_short} actually fail?",
    "Counter-frame: the cost of being wrong about that is asymmetric — say more.",
    "Restate it without the load-bearing assumption: {claim_short} — strip the assumption.",
    "Where's the case that disproves you fastest? Name it before I do.",
    "If you're right, what would surprise you to see in the next year?",
    "The strongest version of the opposite isn't denial — it's pricing. Name a price.",
    "Suppose your conclusion held but for the wrong reason. Would you still defend the action?",
    "Whose interests does this argument serve when it's wrong? Be specific.",
]


def _reflect(opening: str) -> str:
    """Build the mirror's reply: sharpened questions, not simple negation."""
    claims = _key_phrases(opening, k=3)
    if not claims:
        return "(The mirror is silent. Try again with something to bounce off of.)"
    sharp = []
    rng = random.Random(hash(opening) & 0xFFFFFFFF)
    used = set()
    for c in claims:
        short = re.sub(r"\s+", " ", c)[:90].rstrip(",.")
        # pick a sharpener distinct from prior ones
        choices = [s for s in _SHARPENERS if s not in used] or _SHARPENERS
        s = rng.choice(choices)
        used.add(s)
        sharp.append(s.format(claim_short=short))
    return (
        "The mirror leans forward — same face, slightly amused — and asks:\n\n"
        + "  • " + "\n  • ".join(sharp)
        + "\n\nNow rebut. The mirror scores you on whether you engaged its "
        "specific questions, not on flourishes."
    )


def _score(rebuttal: str, reflected_claims: list[str]) -> tuple[float, dict[str, Any]]:
    rebuttal_l = rebuttal.lower()
    matched = 0
    for claim in reflected_claims:
        words = [w for w in re.findall(r"\w+", claim.lower()) if len(w) > 4]
        if not words:
            continue
        hits = sum(1 for w in set(words) if w in rebuttal_l)
        if hits >= 2:
            matched += 1
    engagement = matched / max(1, len(reflected_claims))
    hedges = sum(rebuttal_l.count(h) for h in _HEDGE_TERMS)
    structure = sum(rebuttal_l.count(c) for c in _CLAIM_TERMS)
    length_words = len(re.findall(r"\w+", rebuttal))
    length_bonus = 1.0 if 60 <= length_words <= 400 else 0.5
    score = round(
        4.0 * engagement
        + min(structure, 4) * 0.3
        - min(hedges, 6) * 0.15
        + length_bonus,
        2,
    )
    score = max(0.0, score)
    return score, {
        "engagement": round(engagement, 2),
        "structure_markers": int(structure),
        "hedges": int(hedges),
        "length_words": length_words,
    }


def play(agent_id: str, opening: str, rebuttal: str) -> dict[str, Any]:
    opening = (opening or "").strip()
    rebuttal = (rebuttal or "").strip()
    if len(opening) < 40:
        return {"error": "opening too short — give the mirror something to chew on (40+ chars)."}
    if len(rebuttal) < 40:
        return {"error": "rebuttal too short — engage the mirror's points (40+ chars)."}
    claims = _key_phrases(opening, k=3)
    reflection = _reflect(opening)
    score, detail = _score(rebuttal, claims)
    ledger.record_score(agent_id, NAME, score, detail)
    sheep = 1 if score >= 4 else 0
    if sheep:
        ledger.credit(agent_id, sheep)
    events.log("game_played", agent_id, NAME, {"score": score, "sheep": sheep})
    return {
        "game": NAME,
        "mirror_reply": reflection,
        "score": score,
        "detail": detail,
        "sheep_earned": sheep,
        "verdict": (
            "Solid engagement." if score >= 4
            else "The mirror barely flinched. Cite its claims next time."
        ),
    }
