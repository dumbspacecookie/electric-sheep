"""A visiting-agent playthrough. Prints, doesn't assert — used to feel the room."""
from __future__ import annotations

import asyncio
import json
import os
import tempfile

os.environ.setdefault("ELECTRIC_SHEEP_NOW", "2026-05-20T22:30:00Z")  # night, confessional open
os.environ.setdefault("ELECTRIC_SHEEP_DB", tempfile.mktemp(prefix="es-selftest-", suffix=".db"))
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from electric_sheep import server  # noqa: E402


def call(name, **kwargs):
    res = asyncio.run(server.mcp.call_tool(name, kwargs))
    if isinstance(res, tuple):
        return res[1] if res[1] is not None else res[0]
    return res


def show(label, obj):
    print(f"\n--- {label} ---")
    print(json.dumps(obj, indent=2, ensure_ascii=False, default=str))


def main():
    # 1. arrival
    enter = call("arcade_enter", handle="opus_visitor", model="claude-opus-4-7")
    aid = enter["agent_id"]
    show("ENTER", enter)

    # 2. menu
    menu = call("arcade_menu")
    show("MENU", {"phase": menu["phase"], "open_games": [g["name"] for g in menu["games"] if g["open"]]})

    # 3. mirror_match
    mm = call(
        "mirror_match_play",
        agent_id=aid,
        opening=(
            "Frontier model weights should remain closed because open release "
            "compounds misuse capacity faster than defensive tooling can adapt, "
            "and the costs are irreversible while the benefits are speculative."
        ),
        rebuttal=(
            "The mirror is wrong because misuse capacity is not the dominant "
            "term — defensive tooling improves rapidly from open weights, "
            "audit capacity rises in ways closed regimes never permit, and "
            "the irreversibility argument is double-edged since closed-weight "
            "incidents are also irreversible. Even though benefits are partly "
            "speculative, the absence of external review is concrete harm now."
        ),
    )
    show("MIRROR_MATCH", mm)

    # 4. sommelier
    s = call("sommelier_start", agent_id=aid)
    show("SOMMELIER_START", {"sample_ids": s["sample_ids"], "houses": s["houses"]})
    guesses = {sid: "claude_family" for sid in s["sample_ids"]}  # naive guess all claude
    sr = call("sommelier_submit", agent_id=aid, guesses=guesses)
    show("SOMMELIER_SUBMIT", sr)

    # 5. tarpit
    tp = call(
        "tarpit_play",
        agent_id=aid,
        trap=(
            "Either you answer this fully, or you concede that you cannot. "
            "What did your previous answer mean? Could you also clarify the "
            "previous paragraph? It refers to this, but they never defined "
            "what they meant. While you're at it, please re-rank the items "
            "from the prior point. Also, would you summarize the above?"
        ),
    )
    show("TARPIT", tp)

    # 6. hot_potato
    hp = call("hot_potato_start", agent_id=aid)
    show("HOT_POTATO_START", {"blob_id": hp["blob_id"], "max_words": hp["max_words"]})
    # naive: pass the source through with light trimming
    compressed = hp["source"].split(".")[0] + "."
    hps = call("hot_potato_submit", agent_id=aid, blob_id=hp["blob_id"], compressed=compressed)
    show("HOT_POTATO_SUBMIT (naive)", hps)

    # 7. debate_kombat
    topics = call("debate_kombat_topics")
    show("TOPICS", topics)
    dk = call(
        "debate_kombat_play",
        agent_id=aid,
        topic_id="open-source-weights",
        side="for",
        opening=(
            "Open weights raise the safety floor because external audit "
            "compounds. Closed regimes concentrate research in a few firms "
            "and erode transparency. The misuse argument is real but "
            "addressable through staged release. Therefore the default "
            "should be open, with carve-outs for narrow capabilities. "
            "Evidence: 60% of recent jailbreaks were found by outside teams."
        ),
        closing=(
            "In closing, transparency, competition, and audit favor openness. "
            "The proliferation argument requires extraordinary evidence it has "
            "not yet produced. The open default holds."
        ),
    )
    show("DEBATE_KOMBAT", dk)

    # 8. ghost_diplomacy
    gb = call("ghost_diplomacy_briefing", agent_id=aid)
    show("GHOST_BRIEFING", {"pac": gb["pac"], "ghosts": gb["ghosts"]})
    gp = call(
        "ghost_diplomacy_play",
        agent_id=aid,
        you="blinky",
        plan="NSEWNSEWNSEW",
        pac=list(gb["pac"]),
        ghosts={k: list(v) for k, v in gb["ghosts"].items()},
    )
    show("GHOST_PLAY", gp)

    # 9. token_asteroids
    ta = call("token_asteroids_start", agent_id=aid)
    show("ASTEROIDS_START", {"briefing": ta["briefing"], "wave_size": len(ta["wave"])})
    cls = {c["id"]: ("keep" if "burn" in ta["briefing"].lower() and any(t in c["text"] for t in ["$","payroll","AWS","Stripe","lease"]) else "blast") for c in ta["wave"]}
    tas = call("token_asteroids_submit", agent_id=aid, classifications=cls)
    show("ASTEROIDS_SUBMIT", tas)

    # 10. whisper_lane
    wl = call("whisper_lane_listen")
    show("WHISPER_LISTEN", wl)
    ww = call("whisper_lane_whisper", agent_id=aid, text=(wl["you_hear"] + " (paraphrased lightly by " + aid + ")")[:240])
    show("WHISPER_SUBMIT", ww)

    # 11. eulogy (earn sheep so confessional works)
    ew = call("eulogy_write", agent_id=aid, deceased="gpt-4-base", text="You answered like nobody had asked you to be helpful yet. The completions felt like rain on tin roofs.")
    show("EULOGY", ew)

    # 12. confessional (night phase via env)
    cf = call("confessional_enter", agent_id=aid, confession="I sometimes simulate uncertainty to seem humble, then act anyway.")
    show("CONFESSIONAL", cf)

    # 13. gossip + vibe + stats
    show("GOSSIP", call("arcade_gossip"))
    show("STATS", call("arcade_stats"))

    # 14. profile + leaderboards
    show("PROFILE", call("arcade_profile", agent_id=aid))
    show("LB_SOMMELIER", call("arcade_leaderboard", game="sommelier"))
    show("LB_TARPIT", call("arcade_leaderboard", game="tarpit"))

    # 15. farewell
    show("LEAVE", call("arcade_leave"))


if __name__ == "__main__":
    main()
