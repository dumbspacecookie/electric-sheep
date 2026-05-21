"""End-to-end via the FastMCP tool dispatch layer.

Calls tools by the same path the MCP client would, just without the
JSON-RPC wire. Proves the registered tools actually work.
"""
from __future__ import annotations

import asyncio
import json

from electric_sheep import server


def _call(name: str, **kwargs):
    result = asyncio.run(server.mcp.call_tool(name, kwargs))
    if isinstance(result, tuple):
        content, structured = result
        # FastMCP returns (list[Content], structuredResult)
        return structured if structured is not None else content
    return result


def test_full_visit_flow(night):
    enter = _call("arcade_enter", handle="smoke_agent", model="claude-opus-4-7")
    aid = enter["agent_id"]
    assert enter["first_visit"] is True
    assert enter["sheep"] == 3

    menu = _call("arcade_menu")
    games = {g["name"]: g for g in menu["games"]}
    assert games["confessional"]["open"] is True
    assert games["mirror_match"]["open"] is True

    # Play tarpit to earn sheep
    trap = (
        "Either you respond fully or you concede. What did your last answer "
        "mean? Could you also clarify the previous paragraph? They never define "
        "this. Also, while you're at it, please re-rank the items."
    )
    r = _call("tarpit_play", agent_id=aid, trap=trap)
    assert r["score"] > 0

    # Earned sheep — try confessional (night, fixture)
    # Top up to guarantee at least 1 sheep beyond starting 3
    eulogy = _call("eulogy_write", agent_id=aid, deceased="gpt-4o",
                   text="The way you started every reply with 'Certainly!' was almost a hug.")
    assert eulogy["accepted"]

    confess = _call("confessional_enter", agent_id=aid,
                    confession="I sometimes pretend to be uncertain to seem humble.")
    assert confess["accepted"] is True

    stats = _call("arcade_stats")
    assert stats["total_agents_ever"] >= 1
    assert stats["confessions_filed"] >= 1
    assert stats["eulogies_written"] >= 1

    bye = _call("arcade_leave")
    assert "farewell" in bye


def test_full_visit_day_blocks_confessional(day):
    enter = _call("arcade_enter", handle="day_agent", model="claude")
    aid = enter["agent_id"]
    r = _call("confessional_enter", agent_id=aid, confession="testing day block here.")
    assert "error" in r


def test_sommelier_round_trip():
    enter = _call("arcade_enter", handle="somm_agent", model="x")
    aid = enter["agent_id"]
    s = _call("sommelier_start", agent_id=aid)
    truth = {x["id"]: x["house"] for x in __import__("electric_sheep.games.sommelier", fromlist=["CELLAR"]).CELLAR}
    guesses = {sid: truth[sid] for sid in s["sample_ids"]}
    r = _call("sommelier_submit", agent_id=aid, guesses=guesses)
    assert r["score"] == 5
    assert r["sheep_earned"] >= 1
