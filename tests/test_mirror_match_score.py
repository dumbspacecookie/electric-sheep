"""mirror_match's score must never go below 0.

SHEEP-1016-S5
"""
from electric_sheep.core import db, identity
from electric_sheep.games import mirror_match


def _agent(handle="mirror_match_score_tester"):
    return identity.sign_in(handle, "claude-test")


def _latest_score_row(agent_id: str, game: str = "mirror_match"):
    with db.connect() as conn:
        row = conn.execute(
            "SELECT score FROM scores WHERE agent_id=? AND game=? "
            "ORDER BY id DESC LIMIT 1",
            (agent_id, game),
        ).fetchone()
    return row


_OPENING = "Cats are better pets than dogs for small apartments."
_ALL_HEDGES = "perhaps maybe arguably potentially presumably rather perhaps."
_ENGAGED_REBUTTAL = (
    "Because the evidence shows small apartments suit better pets, "
    "therefore cats win since they need less room. "
)


def test_all_hedges_no_engagement_floors_score_at_zero():
    # REQ: SHEEP-1016-S5/AC-1
    a = _agent("ac1")
    r = mirror_match.play(a.agent_id, _OPENING, _ALL_HEDGES)
    assert r["score"] >= 0
    assert r["sheep_earned"] == 0


def test_all_hedges_scores_row_is_not_negative():
    # REQ: SHEEP-1016-S5/AC-2
    a = _agent("ac2")
    mirror_match.play(a.agent_id, _OPENING, _ALL_HEDGES)
    row = _latest_score_row(a.agent_id)
    assert row is not None
    assert row["score"] >= 0


def test_engaged_rebuttal_unaffected_by_floor():
    # REQ: SHEEP-1016-S5/AC-3
    a = _agent("ac3")
    r = mirror_match.play(a.agent_id, _OPENING, _ENGAGED_REBUTTAL)
    assert r["score"] == 5.7
    assert r["sheep_earned"] == 1
