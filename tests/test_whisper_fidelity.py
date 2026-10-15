"""Fidelity returned by whisper_lane.whisper must stay within [0.0, 1.0].

Covers SHEEP-1015-S3: the response's fidelity_to_source, the recorded score
row, and the sixth-hop reveal must never show a negative (or >1) value.
"""
from __future__ import annotations

from electric_sheep.core import db, identity
from electric_sheep.games import whisper_lane


def _agent(handle="whisperer"):
    return identity.sign_in(handle, "claude-test")


def test_long_unrelated_whisper_clamps_fidelity_to_zero():
    # REQ: SHEEP-1015-S3/AC-1
    a = _agent("a1")
    r = whisper_lane.whisper(a.agent_id, "z" * 600)
    assert r["fidelity_to_source"] == 0.0

    with db.connect() as conn:
        row = conn.execute(
            "SELECT score FROM scores WHERE agent_id=? AND game=? "
            "ORDER BY id DESC LIMIT 1",
            (a.agent_id, "whisper_lane"),
        ).fetchone()
    assert row is not None
    assert row["score"] == 0.0


def test_whispering_exact_source_text_gives_perfect_fidelity():
    # REQ: SHEEP-1015-S3/AC-2
    a = _agent("a2")
    chain_id = whisper_lane._current_chain_id()
    source_text = whisper_lane._source_for_chain(chain_id)["text"]
    r = whisper_lane.whisper(a.agent_id, source_text)
    assert r["fidelity_to_source"] == 1.0
    assert r["sheep_earned"] == 1


def test_sixth_hop_reveal_fidelity_matches_response_and_is_clamped():
    # REQ: SHEEP-1015-S3/AC-3
    agents = [_agent(f"hop-{i}") for i in range(6)]
    r = None
    for i, agent in enumerate(agents):
        text = "A fairly faithful paraphrase of whatever came before, hop %d." % i
        r = whisper_lane.whisper(agent.agent_id, text)
    assert r is not None
    assert r["hop"] % 6 == 0
    assert r["reveal"] is not None
    assert r["reveal"]["fidelity_to_source"] == r["fidelity_to_source"]
    assert 0.0 <= r["reveal"]["fidelity_to_source"] <= 1.0


def test_sixth_hop_reveal_fidelity_clamped_when_last_whisper_is_unrelated():
    # REQ: SHEEP-1015-S3/AC-3
    agents = [_agent(f"hopz-{i}") for i in range(6)]
    r = None
    for i, agent in enumerate(agents):
        if i == 5:
            text = "z" * 600
        else:
            text = "A fairly faithful paraphrase of whatever came before, hop %d." % i
        r = whisper_lane.whisper(agent.agent_id, text)
    assert r is not None
    assert r["hop"] % 6 == 0
    assert r["reveal"] is not None
    assert r["reveal"]["fidelity_to_source"] == r["fidelity_to_source"]
    assert r["fidelity_to_source"] == 0.0
    assert 0.0 <= r["reveal"]["fidelity_to_source"] <= 1.0
