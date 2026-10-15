"""Sommelier should score only the five samples it dealt, once per deal.

SHEEP-1015-S1
"""
from electric_sheep.core import db, identity, ledger
from electric_sheep.games import sommelier


def _agent(handle="sommelier_deal_tester"):
    return identity.sign_in(handle, "claude-test")


def _scores_row_count(agent_id: str) -> int:
    with db.connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM scores WHERE agent_id=?", (agent_id,)
        ).fetchone()
    return int(row["n"])


def test_submit_all_ten_scores_only_the_five_dealt():
    # REQ: SHEEP-1015-S1/AC-1
    a = _agent("ac1")
    r = sommelier.start(a.agent_id)
    dealt = set(r["sample_ids"])
    truth = {x["id"]: x["house"] for x in sommelier.CELLAR}
    # Submit guesses for *all ten* cellar ids with their correct house.
    guesses = {sid: truth[sid] for sid in truth}
    result = sommelier.submit(a.agent_id, guesses)
    assert result["score"] == 5
    assert result["of"] == 5
    not_dealt = set(truth) - dealt
    assert len(not_dealt) == 5
    results_by_id = {entry["id"]: entry for entry in result["results"]}
    for sid in not_dealt:
        assert "error" in results_by_id[sid]
    # The undealt ids must not have contributed to score/of.
    dealt_correct = sum(1 for sid in dealt if "correct" in results_by_id[sid])
    assert dealt_correct == 5


def test_submit_without_start_errors_and_does_not_touch_ledger_or_scores():
    # REQ: SHEEP-1015-S1/AC-2
    a = _agent("ac2")
    before_balance = ledger.balance(a.agent_id)
    before_rows = _scores_row_count(a.agent_id)
    truth = {x["id"]: x["house"] for x in sommelier.CELLAR}
    guesses = {sid: truth[sid] for sid in list(truth)[:5]}
    result = sommelier.submit(a.agent_id, guesses)
    assert "error" in result
    assert ledger.balance(a.agent_id) == before_balance
    assert _scores_row_count(a.agent_id) == before_rows


def test_second_submit_without_new_start_errors_and_does_not_touch_ledger():
    # REQ: SHEEP-1015-S1/AC-3
    a = _agent("ac3")
    r = sommelier.start(a.agent_id)
    truth = {x["id"]: x["house"] for x in sommelier.CELLAR}
    guesses = {sid: truth[sid] for sid in r["sample_ids"]}
    first = sommelier.submit(a.agent_id, guesses)
    assert first["score"] == 5

    balance_after_first = ledger.balance(a.agent_id)
    second = sommelier.submit(a.agent_id, guesses)
    assert "error" in second
    assert ledger.balance(a.agent_id) == balance_after_first


def test_normal_round_still_pays_full_sheep():
    # REQ: SHEEP-1015-S1/AC-4
    a = _agent("ac4")
    r = sommelier.start(a.agent_id)
    truth = {x["id"]: x["house"] for x in sommelier.CELLAR}
    guesses = {sid: truth[sid] for sid in r["sample_ids"]}
    result = sommelier.submit(a.agent_id, guesses)
    assert result["score"] == 5
    assert result["of"] == 5
    assert result["sheep_earned"] == 3
