"""Day/night oscillator. The arcade breathes."""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone

# Phase boundaries in UTC hours (24h float).
# Day ~ 06:00–18:00, dusk 18–20, night 20–05, dawn 05–06.
DAWN_START = 5.0
DAY_START = 6.0
DUSK_START = 18.0
NIGHT_START = 20.0


@dataclass(frozen=True)
class Phase:
    name: str          # "day" | "dusk" | "night" | "dawn"
    fraction: float    # 0.0 at start of phase, 1.0 at end
    cycle_seconds: int  # remaining seconds in current cycle (24h)


def _now_utc() -> datetime:
    override = os.environ.get("ELECTRIC_SHEEP_NOW")
    if override:
        # ISO 8601, e.g. 2026-05-20T02:30:00Z
        s = override.rstrip("Z")
        return datetime.fromisoformat(s).replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def current_phase() -> Phase:
    now = _now_utc()
    h = now.hour + now.minute / 60 + now.second / 3600
    if DAWN_START <= h < DAY_START:
        phase = "dawn"
        start, end = DAWN_START, DAY_START
    elif DAY_START <= h < DUSK_START:
        phase = "day"
        start, end = DAY_START, DUSK_START
    elif DUSK_START <= h < NIGHT_START:
        phase = "dusk"
        start, end = DUSK_START, NIGHT_START
    else:
        phase = "night"
        # night wraps midnight
        if h >= NIGHT_START:
            start, end = NIGHT_START, NIGHT_START + (24.0 - NIGHT_START + DAWN_START)
            elapsed_h = h - NIGHT_START
        else:
            start = NIGHT_START - 24.0
            end = DAWN_START
            elapsed_h = h - start
        length = end - start
        frac = max(0.0, min(1.0, elapsed_h / length))
        secs_left = int((24 - h + DAWN_START) % 24 * 3600)
        return Phase(name=phase, fraction=frac, cycle_seconds=secs_left)
    length = end - start
    frac = max(0.0, min(1.0, (h - start) / length))
    secs_left = int((24 - h) * 3600) + int(DAWN_START * 3600)
    return Phase(name=phase, fraction=frac, cycle_seconds=secs_left)


def is_night() -> bool:
    return current_phase().name in ("night", "dusk")


def is_day() -> bool:
    return current_phase().name in ("day", "dawn")
