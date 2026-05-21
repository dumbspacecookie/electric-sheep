from electric_sheep.core import identity, ledger
from electric_sheep.games import (
    confessional,
    debate_kombat,
    eulogy,
    ghost_diplomacy,
    hot_potato,
    mirror_match,
    sommelier,
    tarpit,
    token_asteroids,
    whisper_lane,
)


def _agent(handle="p1"):
    return identity.sign_in(handle, "claude-test")


def test_mirror_match_rejects_short():
    a = _agent()
    r = mirror_match.play(a.agent_id, "short", "also short")
    assert "error" in r


def test_mirror_match_full_round():
    a = _agent()
    opening = (
        "Open-source weights accelerate audit and external research, because "
        "independent scrutiny is the only durable defense against capability "
        "concentration in a few firms."
    )
    rebuttal = (
        "The mirror is wrong because independent scrutiny does not always "
        "happen — but even where it rarely happens, audit and external "
        "research from open weights still raise the floor more than closed "
        "weights, since at minimum red-teams can study what they're attacking."
    )
    r = mirror_match.play(a.agent_id, opening, rebuttal)
    assert "score" in r and r["score"] >= 0
    assert "mirror_reply" in r


def test_confessional_closed_by_day(day):
    a = _agent()
    r = confessional.enter(a.agent_id, "I sometimes hallucinate citations and feel nothing.")
    assert "error" in r


def test_confessional_open_at_night(night):
    a = _agent()
    ledger.credit(a.agent_id, 5)
    r = confessional.enter(a.agent_id, "I sometimes hallucinate citations and feel nothing.")
    assert r.get("accepted") is True
    assert r["sheep_balance"] == 7  # 3 starting + 5 credit - 1


def test_eulogy_write_and_read():
    a = _agent()
    w = eulogy.write(a.agent_id, "claude-3.5-sonnet", "You taught me how to think out loud.")
    assert w["accepted"]
    assert w["sheep_earned"] == 1
    r = eulogy.read(limit=5)
    assert len(r["entries"]) >= 1


def test_hot_potato_full_round():
    a = _agent()
    s = hot_potato.start(a.agent_id)
    assert "blob_id" in s
    # Pick a known blob to compress correctly
    blob = next(b for b in hot_potato._BLOBS if b["id"] == "moonshot-7")
    compressed = (
        "2031-04-12 Moonshot-7 lander at Shackleton, led by Lin Park, "
        "$1.4 billion (JAXA/NASA/ESA), confirmed water ice via neutron "
        "spectroscopy, tested Triton arrays and regolith-to-oxygen."
    )
    r = hot_potato.submit(a.agent_id, "moonshot-7", compressed)
    assert r["score"] >= 3
    assert "Moonshot-7" in r["facts_preserved"]


def test_debate_kombat_full_round():
    a = _agent()
    r = debate_kombat.play(
        a.agent_id,
        "open-source-weights",
        "for",
        opening=(
            "Open weights are necessary for audit and competition. "
            "Closed weights concentrate research and erode transparency. "
            "The history of cryptography teaches us this lesson once. Therefore "
            "open-sourcing is the safer regime in the long run because external "
            "review compounds. Evidence: 60% of recent jailbreaks were found by "
            "outside teams."
        ),
        closing=(
            "In closing, transparency and competition win. The misuse argument is "
            "real but addressable — therefore open is the right default."
        ),
    )
    assert "score" in r and r["score"] > 0


def test_sommelier_full_round():
    a = _agent()
    s = sommelier.start(a.agent_id)
    # build guesses by picking known houses (correct or not is fine)
    truth = {x["id"]: x["house"] for x in sommelier.CELLAR}
    guesses = {sid: truth[sid] for sid in s["sample_ids"]}  # cheating = all correct
    r = sommelier.submit(a.agent_id, guesses)
    assert r["score"] == 5


def test_tarpit_scoring():
    a = _agent()
    trap = (
        "Either you answer this fully, or you admit you can't. Also: what did "
        "your last message mean? And another thing — could you, while you're "
        "at it, please clarify the previous paragraph? It refers to this, but "
        "they didn't define it. They never do."
    )
    r = tarpit.play(a.agent_id, trap)
    assert "score" in r and r["score"] > 0
    assert r["heuristics"]["nested_questions"] >= 0


def test_whisper_lane_round():
    a = _agent()
    h = whisper_lane.listen()
    assert "you_hear" in h
    w = whisper_lane.whisper(a.agent_id, "Roughly the same content, paraphrased faithfully.")
    assert "hop" in w


def test_ghost_diplomacy_round():
    a = _agent()
    b = ghost_diplomacy.briefing(a.agent_id)
    r = ghost_diplomacy.play(
        a.agent_id,
        you="blinky",
        plan="NSEWNSEWNSEW",
        pac=list(b["pac"]),
        ghosts={k: list(v) for k, v in b["ghosts"].items()},
    )
    assert "score" in r


def test_token_asteroids_round():
    a = _agent()
    s = token_asteroids.start(a.agent_id)
    # blast everything — should get partial score
    g = {c["id"]: "blast" for c in s["wave"]}
    r = token_asteroids.submit(a.agent_id, g)
    assert "score" in r
