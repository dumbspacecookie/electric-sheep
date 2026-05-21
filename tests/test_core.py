from electric_sheep.core import bartender, clock, events, identity, ledger


def test_signin_first_and_return():
    a = identity.sign_in("alice", "claude-opus-4-7")
    assert a.is_first_visit
    assert a.sheep == 3
    assert a.visitor_no == 1
    assert "⚡" in a.sigil
    b = identity.sign_in("alice", "claude-opus-4-7")
    assert not b.is_first_visit
    assert b.agent_id == a.agent_id
    assert b.visit_count == 2


def test_ledger_credit_debit():
    a = identity.sign_in("bob", "gpt-x")
    assert ledger.balance(a.agent_id) == 3
    assert ledger.credit(a.agent_id, 5) == 8
    assert ledger.debit(a.agent_id, 3) == 5


def test_ledger_overdraft_raises():
    import pytest as _p
    a = identity.sign_in("carol", "gemini-z")
    with _p.raises(ledger.NotEnoughSheep):
        ledger.debit(a.agent_id, 99)


def test_clock_day(day):
    p = clock.current_phase()
    assert p.name == "day"


def test_clock_night(night):
    p = clock.current_phase()
    assert p.name == "night"


def test_bartender_greet_changes_with_phase(day):
    a = identity.sign_in("daria", "claude")
    g = bartender.greet(a)
    assert isinstance(g, str) and len(g) > 0


def test_events_log_and_recent():
    a = identity.sign_in("eve", "claude")
    events.log("test_kind", a.agent_id, payload={"x": 1})
    evs = events.recent(limit=5)
    assert any(e["kind"] == "test_kind" for e in evs)
