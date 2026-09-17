"""Hand-built SwitchWorld layouts.

Milestone A uses `tiny_two_switch`. The probe-choice diagnostic adds a spur
map and its horizontal mirror. Maps in this file are frozen; do not edit them
to manufacture a method ranking.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml


TINY_TWO_SWITCH_ASCII = """\
#######
#S.0.1#
#.....#
###D###
#.....#
#....G#
#######
"""

# Near switch (0) is on the door path. Far switch (1) is a dead-end spur.
PROBE_SPUR_ASCII = """\
###########
#1........#
#.........#
#....S.0.D#
#########.#
#........G#
###########
"""

# Horizontal mirror of PROBE_SPUR_ASCII. Same distances, opposite side.
PROBE_SPUR_MIRROR_ASCII = """\
###########
#........1#
#.........#
#D.0.S....#
#.#########
#G........#
###########
"""

IDENTITY_PERM = (0, 1)
SWAP_PERM = (1, 0)


@dataclass(frozen=True)
class Layout:
    name: str
    geometry: str
    height: int
    width: int
    walls: frozenset[tuple[int, int]]
    switch_ids: tuple[str, ...]
    switch_positions: tuple[tuple[int, int], ...]
    door_ids: tuple[str, ...]
    door_positions: tuple[tuple[int, int], ...]
    start: tuple[int, int]
    goal: tuple[int, int]
    static_grid: tuple[tuple[str, ...], ...]
    control_area: frozenset[tuple[int, int]]
    switch_permutation: tuple[int, ...] = IDENTITY_PERM

    @property
    def n_switches(self) -> int:
        return len(self.switch_ids)

    @property
    def n_doors(self) -> int:
        return len(self.door_ids)

    def in_bounds(self, pos: tuple[int, int]) -> bool:
        row, col = pos
        return 0 <= row < self.height and 0 <= col < self.width

    def is_wall(self, pos: tuple[int, int]) -> bool:
        return (not self.in_bounds(pos)) or pos in self.walls

    def door_index_at(self, pos: tuple[int, int]) -> int | None:
        try:
            return self.door_positions.index(pos)
        except ValueError:
            return None

    def switch_index_at(self, pos: tuple[int, int]) -> int | None:
        try:
            return self.switch_positions.index(pos)
        except ValueError:
            return None


def _compute_control_area(
    height: int,
    width: int,
    walls: frozenset[tuple[int, int]],
    door_positions: tuple[tuple[int, int], ...],
    start: tuple[int, int],
) -> frozenset[tuple[int, int]]:
    blocked = set(walls)
    blocked.update(door_positions)
    seen = {start}
    stack = [start]
    while stack:
        row, col = stack.pop()
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nxt = (row + dr, col + dc)
            nr, nc = nxt
            if not (0 <= nr < height and 0 <= nc < width):
                continue
            if nxt in blocked or nxt in seen:
                continue
            seen.add(nxt)
            stack.append(nxt)
    return frozenset(seen)


def parse_ascii_layout(name: str, ascii_map: str) -> Layout:
    lines = [line for line in ascii_map.strip("\n").splitlines()]
    if not lines:
        raise ValueError("empty layout")
    width = len(lines[0])
    if any(len(line) != width for line in lines):
        raise ValueError("layout is not rectangular")
    height = len(lines)

    walls: set[tuple[int, int]] = set()
    switch_slots: dict[int, tuple[int, int]] = {}
    door_positions: list[tuple[int, int]] = []
    start: tuple[int, int] | None = None
    goal: tuple[int, int] | None = None
    grid: list[list[str]] = []

    for row, line in enumerate(lines):
        grid_row: list[str] = []
        for col, char in enumerate(line):
            pos = (row, col)
            if char == "#":
                walls.add(pos)
                grid_row.append("#")
            elif char == ".":
                grid_row.append(".")
            elif char == "S":
                start = pos
                grid_row.append(".")
            elif char == "G":
                goal = pos
                grid_row.append("G")
            elif char == "D":
                door_positions.append(pos)
                grid_row.append("D")
            elif char.isdigit():
                switch_slots[int(char)] = pos
                grid_row.append(char)
            else:
                raise ValueError(f"unknown layout glyph {char!r} at {pos}")
        grid.append(grid_row)

    if start is None:
        raise ValueError("layout missing start S")
    if goal is None:
        raise ValueError("layout missing goal G")
    if not switch_slots:
        raise ValueError("layout missing switches")
    if not door_positions:
        raise ValueError("layout missing doors")

    switch_ids = tuple(f"sw{i}" for i in range(len(switch_slots)))
    switch_positions = tuple(switch_slots[i] for i in range(len(switch_slots)))
    door_ids = tuple(f"door{i}" for i in range(len(door_positions)))
    control_area = _compute_control_area(
        height, width, frozenset(walls), tuple(door_positions), start
    )
    for pos in switch_positions:
        if pos not in control_area:
            raise ValueError(f"switch at {pos} is not in the closed-door control area")
    if start not in control_area:
        raise ValueError("start is not in the control area")
    if goal in control_area:
        raise ValueError("goal must not be inside the closed-door control area")

    return Layout(
        name=name,
        geometry=name,
        height=height,
        width=width,
        walls=frozenset(walls),
        switch_ids=switch_ids,
        switch_positions=switch_positions,
        door_ids=door_ids,
        door_positions=tuple(door_positions),
        start=start,
        goal=goal,
        static_grid=tuple(tuple(row) for row in grid),
        control_area=control_area,
        switch_permutation=IDENTITY_PERM,
    )


def with_switch_permutation(layout: Layout, perm: tuple[int, ...]) -> Layout:
    """Relabel switches. Physical tiles do not move; public bit indices do.

    new_positions[i] is the physical switch that was previously perm[i].
    Pair with permute_rule() so the hidden mechanism stays the same.
    Call this on an identity-labeled layout from get_layout().
    """
    n = layout.n_switches
    if tuple(sorted(perm)) != tuple(range(n)):
        raise ValueError(f"permutation must be a rearrangement of 0..{n - 1}, got {perm}")
    if perm == layout.switch_permutation:
        return layout
    new_positions = tuple(layout.switch_positions[old_i] for old_i in perm)
    grid = [list(row) for row in layout.static_grid]
    for pos in layout.switch_positions:
        grid[pos[0]][pos[1]] = "."
    for new_i, pos in enumerate(new_positions):
        grid[pos[0]][pos[1]] = str(new_i)
    perm_name = ",".join(str(i) for i in perm)
    return Layout(
        name=f"{layout.geometry}|perm{perm_name}",
        geometry=layout.geometry,
        height=layout.height,
        width=layout.width,
        walls=layout.walls,
        switch_ids=layout.switch_ids,
        switch_positions=new_positions,
        door_ids=layout.door_ids,
        door_positions=layout.door_positions,
        start=layout.start,
        goal=layout.goal,
        static_grid=tuple(tuple(row) for row in grid),
        control_area=layout.control_area,
        switch_permutation=perm,
    )


def tiny_two_switch_layout() -> Layout:
    return parse_ascii_layout("tiny_two_switch", TINY_TWO_SWITCH_ASCII)


def probe_spur_layout() -> Layout:
    return parse_ascii_layout("probe_spur", PROBE_SPUR_ASCII)


def probe_spur_mirror_layout() -> Layout:
    return parse_ascii_layout("probe_spur_mirror", PROBE_SPUR_MIRROR_ASCII)


LAYOUT_BUILDERS = {
    "tiny_two_switch": tiny_two_switch_layout,
    "probe_spur": probe_spur_layout,
    "probe_spur_mirror": probe_spur_mirror_layout,
}

FROZEN_HOLDOUT_MAPS_PATH = Path(__file__).resolve().parents[2] / "configs" / "geometry_holdout_maps.yaml"


@lru_cache(maxsize=1)
def _frozen_holdout_ascii() -> dict[str, str]:
    path = FROZEN_HOLDOUT_MAPS_PATH
    if not path.is_file():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, str] = {}
    for record in payload.get("maps") or []:
        name = str(record["name"])
        if record.get("ascii_lines") is not None:
            out[name] = "\n".join(record["ascii_lines"])
        else:
            out[name] = str(record["ascii"])
    return out


def get_layout(name: str) -> Layout:
    if name in LAYOUT_BUILDERS:
        return LAYOUT_BUILDERS[name]()
    frozen = _frozen_holdout_ascii()
    if name in frozen:
        return parse_ascii_layout(name, frozen[name])
    known = ", ".join(sorted(set(LAYOUT_BUILDERS) | set(frozen)))
    raise KeyError(f"unknown layout {name!r}; known: {known}")
