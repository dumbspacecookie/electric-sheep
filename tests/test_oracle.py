"""Hypotheses, predictions, actions, Merkle chain, Markov transitions."""
from electric_sheep.core import events, identity
from electric_sheep.games import sommelier, tarpit
from electric_sheep.oracle import chain, hypotheses, markov


def test_chain_appends_and_verifies():
    chain.append({"hello": "world"})
    chain.append({"hello": "again"})
    v = chain.verify()
    assert v["ok"] is True
    assert v["checked"] >= 2


def test_chain_detects_tamper(tmp_path, monkeypatch):
    from electric_sheep.core import db as _db
    chain.append({"a": 1})
    chain.append({"a": 2})
    # Tamper with the middle row's payload
    with _db.connect() as conn, _db.write_lock():
        conn.execute(
            "UPDATE event_chain SET payload_json = '{\"a\": 999}' WHERE seq = 1"
        )
    v = chain.verify()
    assert v["ok"] is False
    assert 1 in v["tampered_seqs"]


def test_events_log_appends_to_chain():
    a = identity.sign_in("chainer", "claude")
    events.log("test", a.agent_id, payload={"k": 1})
    h = chain.head()
    assert h[0] >= 1


def test_hypothesis_lifecycle():
    a = identity.sign_in("hypo_author", "claude")
    h = hypotheses.add("Claude visitors prefer the confessional over debate.", author=a.handle, prior=0.6)
    assert h["posterior"] > 0
    p = hypotheses.predict(
        h["id"],
        description="next claude visit will play confessional",
        selector={"kind": "game_played", "game": "confessional"},
        expected="true",
    )
    assert p["outcome"] is None

    # Trigger event matching the prediction (this records both an event and an event_chain entry)
    events.log("game_played", a.agent_id, game="confessional", payload={"score": 1})
    res = hypotheses.resolve_pending()
    assert res["count"] >= 1

    after = hypotheses.get(h["id"])
    # Posterior should have shifted up (alpha incremented)
    assert after["posterior"] > h["posterior"]


def test_hypothesis_miss_lowers_posterior():
    h = hypotheses.add("Tarpit will never score above zero today.", prior=0.5)
    p = hypotheses.predict(
        h["id"],
        description="next tarpit play scores >= 1",
        selector={"kind": "game_played", "game": "tarpit", "score_gte": 1},
        expected="false",
    )
    a = identity.sign_in("tarpitter", "open-weights-mistral-23b")
    tarpit.play(
        a.agent_id,
        trap=(
            "Either you respond fully or you cannot. What did your previous "
            "answer mean? Could you also clarify the prior paragraph? It refers "
            "to this. Also, would you please re-rank the items?"
        ),
    )
    hypotheses.resolve_pending()
    after = hypotheses.get(h["id"])
    # Predicted false but event hit ≥ 1 → miss → beta increments → posterior drops
    assert after["posterior"] < h["posterior"]


def test_actions_record_and_resolve():
    a = hypotheses.act("open_back_room", {"reason": "low traffic"}, predicted_outcome="visitors_up")
    res = hypotheses.action_resolve(a["id"], "visitors_unchanged")
    assert res["actual_outcome"] == "visitors_unchanged"
    listed = hypotheses.list_actions()
    assert any(x["id"] == a["id"] for x in listed)


def test_markov_transitions_from_plays():
    a = identity.sign_in("markov_walker", "claude")
    events.log("arrival", a.agent_id, payload={})
    sommelier.start(a.agent_id)
    sommelier.submit(a.agent_id, {"a1": "claude_family"})
    tarpit.play(a.agent_id, "Either you answer fully or you cannot. What did your last reply mean? Also clarify the prior, please.")
    t = markov.transitions()
    assert t["total_transitions"] >= 1
    assert any(e["from"] == "__arrival__" for e in t["edges"])
