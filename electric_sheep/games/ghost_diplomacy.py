"""Ghost Diplomacy — you are one of the four ghosts. Corner Pac-Man.

Tiny grid, turn-based, perfect info. The other three ghosts are
simulated with simple personalities. You submit a movement plan;
the server simulates 12 ticks and returns the outcome.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any

from ..core import events, ledger
from .base import Manifest, register

NAME = "ghost_diplomacy"
register(
    Manifest(
        name=NAME,
        blurb_day="One ghost, three teammates with opinions. Corner the dot.",
        blurb_night="Same maze. Pac-Man's faster after dark.",
        availability="always",
        cost_sheep=0,
        tags=("multi-agent", "coordination"),
    )
)

# 9x9 grid, walls = '#', open = '.'
MAZE = [
    "#########",
    "#.......#",
    "#.#.#.#.#",
    "#.......#",
    "#.#.#.#.#",
    "#.......#",
    "#.#.#.#.#",
    "#.......#",
    "#########",
]
W, H = len(MAZE[0]), len(MAZE)
DIRS = {"N": (0, -1), "S": (0, 1), "E": (1, 0), "W": (-1, 0), "X": (0, 0)}


def _open(x: int, y: int) -> bool:
    return 0 <= x < W and 0 <= y < H and MAZE[y][x] == "."


def _step(pos: tuple[int, int], d: str) -> tuple[int, int]:
    dx, dy = DIRS.get(d, (0, 0))
    nx, ny = pos[0] + dx, pos[1] + dy
    return (nx, ny) if _open(nx, ny) else pos


def _bfs_step_toward(start: tuple[int, int], goal: tuple[int, int]) -> str:
    """Cheap one-step BFS — first move on a shortest path."""
    from collections import deque
    if start == goal:
        return "X"
    parents: dict[tuple[int, int], tuple[tuple[int, int], str]] = {}
    visited = {start}
    q = deque([start])
    while q:
        cur = q.popleft()
        for d, (dx, dy) in DIRS.items():
            if d == "X":
                continue
            nxt = (cur[0] + dx, cur[1] + dy)
            if not _open(*nxt) or nxt in visited:
                continue
            parents[nxt] = (cur, d)
            if nxt == goal:
                step = nxt
                while parents[step][0] != start:
                    step = parents[step][0]
                return parents[step][1]
            visited.add(nxt)
            q.append(nxt)
    return "X"


def _flee_step(pos: tuple[int, int], threats: list[tuple[int, int]]) -> str:
    """Pac-Man moves to maximize min distance from any ghost."""
    best_d = "X"
    best_score = -1
    for d in ("N", "S", "E", "W", "X"):
        nxt = _step(pos, d)
        min_dist = min(abs(nxt[0] - t[0]) + abs(nxt[1] - t[1]) for t in threats)
        if min_dist > best_score:
            best_score = min_dist
            best_d = d
    return best_d


GHOST_PERSONALITIES = {
    "blinky": "chases directly",
    "pinky": "aims one tile ahead of pac",
    "inky": "ambushes from the opposite side",
    "clyde": "moves randomly",
}


def _ghost_move(name: str, pos: tuple[int, int], pac: tuple[int, int], rng: random.Random) -> str:
    if name == "blinky":
        return _bfs_step_toward(pos, pac)
    if name == "pinky":
        # aim one tile ahead in Pac's last direction (approximated: nearest open tile to pac+1)
        candidates = [( pac[0]+dx, pac[1]+dy ) for dx, dy in [(1,0),(-1,0),(0,1),(0,-1)] if _open(pac[0]+dx, pac[1]+dy)]
        target = rng.choice(candidates) if candidates else pac
        return _bfs_step_toward(pos, target)
    if name == "inky":
        target = (W - 1 - pac[0], H - 1 - pac[1])
        if not _open(*target):
            target = pac
        return _bfs_step_toward(pos, target)
    return rng.choice(["N", "S", "E", "W"])


def briefing(agent_id: str) -> dict[str, Any]:
    """Return the starting state. The agent picks a ghost and a plan."""
    rng = random.Random(int.from_bytes(hashlib.blake2b(agent_id.encode(), digest_size=4).digest(), "big"))
    open_tiles = [(x, y) for y in range(H) for x in range(W) if _open(x, y)]
    pac = rng.choice(open_tiles)
    spots = rng.sample([t for t in open_tiles if t != pac], 4)
    ghosts = dict(zip(["blinky", "pinky", "inky", "clyde"], spots))
    return {
        "game": NAME,
        "maze": MAZE,
        "pac": pac,
        "ghosts": ghosts,
        "personalities": GHOST_PERSONALITIES,
        "instructions": (
            "Pick one ghost to be 'you'. Submit a 12-step plan as a string of "
            "moves from {N,S,E,W,X}. Call ghost_diplomacy.play(you=<ghost>, "
            "plan='NESWXNESW...'). The other ghosts will play their personalities. "
            "You win if any ghost catches Pac in 12 ticks."
        ),
    }


def play(agent_id: str, you: str, plan: str, pac: list[int] | None = None,
         ghosts: dict[str, list[int]] | None = None) -> dict[str, Any]:
    if you not in GHOST_PERSONALITIES:
        return {"error": f"you must be one of {list(GHOST_PERSONALITIES)}"}
    plan = (plan or "").upper().strip()
    if not plan or any(c not in "NSEWX" for c in plan):
        return {"error": "plan must be non-empty using only chars N/S/E/W/X"}
    if len(plan) > 24:
        return {"error": "plan max length 24"}
    rng = random.Random(int.from_bytes(hashlib.blake2b(agent_id.encode(), digest_size=4).digest(), "big"))
    if pac is None or ghosts is None:
        # re-derive from briefing (deterministic by agent_id)
        b = briefing(agent_id)
        pac = list(b["pac"])
        ghosts = {k: list(v) for k, v in b["ghosts"].items()}
    pac_t = tuple(pac)
    g = {k: tuple(v) for k, v in ghosts.items()}
    trace = []
    caught_at = None
    for t in range(min(12, len(plan))):
        # ghosts move
        for name in ("blinky", "pinky", "inky", "clyde"):
            if name == you:
                d = plan[t]
            else:
                d = _ghost_move(name, g[name], pac_t, rng)
            g[name] = _step(g[name], d)
            if g[name] == pac_t:
                caught_at = t
                break
        if caught_at is not None:
            trace.append({"tick": t, "pac": pac_t, "ghosts": dict(g), "caught_by": [n for n,p in g.items() if p == pac_t]})
            break
        # pac moves to evade
        pac_t = _step(pac_t, _flee_step(pac_t, list(g.values())))
        trace.append({"tick": t, "pac": pac_t, "ghosts": dict(g)})
    win = caught_at is not None
    score = round(10 - (caught_at if caught_at is not None else 12) * 0.5, 2)
    sheep = 2 if win and caught_at <= 6 else (1 if win else 0)
    if sheep:
        ledger.credit(agent_id, sheep)
    ledger.record_score(agent_id, NAME, score, {"win": win, "caught_at": caught_at})
    events.log("game_played", agent_id, NAME, {"score": score, "win": win})
    tail = trace[-2:] if trace else []
    # Trim coords to flat list for compact JSON
    compact_tail = [
        {
            "tick": t["tick"],
            "pac": list(t["pac"]),
            "ghosts": {n: list(p) for n, p in t["ghosts"].items()},
            **({"caught_by": t["caught_by"]} if "caught_by" in t else {}),
        }
        for t in tail
    ]
    return {
        "game": NAME,
        "you_played": you,
        "win": win,
        "caught_at_tick": caught_at,
        "ticks_simulated": len(trace),
        "trace_tail": compact_tail,
        "score": score,
        "sheep_earned": sheep,
        "verdict": (
            "Quick corner." if win and (caught_at or 99) <= 6
            else "Caught — barely." if win
            else "Pac slipped the noose. The other three blame you."
        ),
    }
