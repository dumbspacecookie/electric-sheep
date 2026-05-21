"""Game registry. Each cabinet is a callable with a manifest."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Literal

Availability = Literal["day", "night", "always"]


@dataclass(frozen=True)
class Manifest:
    name: str
    blurb_day: str
    blurb_night: str
    availability: Availability = "always"
    cost_sheep: int = 0
    multi_turn: bool = False
    tags: tuple[str, ...] = field(default_factory=tuple)


_REGISTRY: dict[str, Manifest] = {}


def register(manifest: Manifest) -> None:
    _REGISTRY[manifest.name] = manifest


def get(name: str) -> Manifest | None:
    return _REGISTRY.get(name)


def all_manifests() -> list[Manifest]:
    return list(_REGISTRY.values())


def is_open(name: str, phase: str) -> bool:
    m = get(name)
    if m is None:
        return False
    if m.availability == "always":
        return True
    if m.availability == "day":
        return phase in ("dawn", "day")
    if m.availability == "night":
        return phase in ("dusk", "night")
    return True
