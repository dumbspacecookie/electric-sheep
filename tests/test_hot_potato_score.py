"""hot_potato's score must never go below 0.

SHEEP-1016-S4
"""
from electric_sheep.core import db, identity
from electric_sheep.games import hot_potato


def _agent(handle="hot_potato_score_tester"):
    return identity.sign_in(handle, "claude-test")


def _latest_score_row(agent_id: str, game: str = "hot_potato"):
    with db.connect() as conn:
        row = conn.execute(
            "SELECT score FROM scores WHERE agent_id=? AND game=? "
            "ORDER BY id DESC LIMIT 1",
            (agent_id, game),
        ).fetchone()
    return row


def test_far_over_budget_few_facts_floors_at_zero():
    # REQ: SHEEP-1016-S4/AC-1
    a = _agent("ac1")
    r = hot_potato.submit(a.agent_id, "moonshot-7", "zz " * 600)
    assert r["score"] == 0.0
    assert r["sheep_earned"] == 0
    row = _latest_score_row(a.agent_id)
    assert row is not None
    assert row["score"] == 0.0


def test_perfect_compression_still_scores_full_marks():
    # REQ: SHEEP-1016-S4/AC-2
    a = _agent("ac2")
    blob = next(b for b in hot_potato._BLOBS if b["id"] == "moonshot-7")
    text = " ".join(blob["facts"])
    r = hot_potato.submit(a.agent_id, "moonshot-7", text)
    assert r["score"] == 5.0
    assert r["sheep_earned"] == 2
    row = _latest_score_row(a.agent_id)
    assert row is not None
    assert row["score"] == 5.0


def test_negative_today_score_clamps_but_positive_score_unchanged():
    # REQ: SHEEP-1016-S4/AC-3
    a = _agent("ac3")
    blob = next(b for b in hot_potato._BLOBS if b["id"] == "moonshot-7")

    # Keeps only "Moonshot-7" and "Shackleton", 600 words long.
    # Today this scores -0.75 (preservation 2/8, over-budget penalty capped
    # at 1.0): 5 * 0.25 - 2 * 1.0 = -0.75. It must clamp to 0.0.
    base = "Moonshot-7 Shackleton"
    filler_count = 600 - hot_potato._word_count(base)
    under_budget_text = base + " " + " ".join(["filler"] * filler_count)
    assert hot_potato._word_count(under_budget_text) == 600
    r_negative = hot_potato.submit(a.agent_id, "moonshot-7", under_budget_text)
    assert r_negative["score"] == 0.0
    row_negative = _latest_score_row(a.agent_id)
    assert row_negative is not None
    assert row_negative["score"] == 0.0

    # Keeps all eight facts, 74 words long -> today's score is 3.0 and must
    # remain 3.0 (already non-negative, unaffected by the floor).
    a2 = _agent("ac3b")
    all_facts_text = " ".join(blob["facts"])
    filler_count_2 = 74 - hot_potato._word_count(all_facts_text)
    full_facts_text = all_facts_text + " " + " ".join(["x"] * filler_count_2)
    assert hot_potato._word_count(full_facts_text) == 74
    r_positive = hot_potato.submit(a2.agent_id, "moonshot-7", full_facts_text)
    assert r_positive["score"] == 3.0
    row_positive = _latest_score_row(a2.agent_id)
    assert row_positive is not None
    assert row_positive["score"] == 3.0
