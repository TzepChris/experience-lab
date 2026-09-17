"""Public types shared across Experience Lab.

Hidden rules, seeds, and oracle paths are not part of Observation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping


class Action(Enum):
    NORTH = "NORTH"
    SOUTH = "SOUTH"
    EAST = "EAST"
    WEST = "WEST"
    TOGGLE = "TOGGLE"


MOVE_DELTAS: Mapping[Action, tuple[int, int]] = {
    Action.NORTH: (-1, 0),
    Action.SOUTH: (1, 0),
    Action.EAST: (0, 1),
    Action.WEST: (0, -1),
}

ACTIONS: tuple[Action, ...] = (
    Action.NORTH,
    Action.SOUTH,
    Action.EAST,
    Action.WEST,
    Action.TOGGLE,
)

STEP_COST = 0.01
GOAL_REWARD = 1.0
DEFAULT_MAX_STEPS = 256


def bits_to_int(bits: tuple[bool, ...]) -> int:
    value = 0
    for i, bit in enumerate(bits):
        if bit:
            value |= 1 << i
    return value


def int_to_bits(value: int, width: int) -> tuple[bool, ...]:
    return tuple(bool((value >> i) & 1) for i in range(width))


@dataclass(frozen=True)
class Observation:
    """Immutable public observation. This is the only world state a learner may see."""

    width: int
    height: int
    static_grid: tuple[tuple[str, ...], ...]
    switch_ids: tuple[str, ...]
    door_ids: tuple[str, ...]
    switch_positions: tuple[tuple[int, int], ...]
    door_positions: tuple[tuple[int, int], ...]
    agent_pos: tuple[int, int]
    goal_pos: tuple[int, int]
    switch_bits: tuple[bool, ...]
    door_open: tuple[bool, ...]
    step_index: int


PUBLIC_OBSERVATION_FIELDS = frozenset(Observation.__dataclass_fields__)
