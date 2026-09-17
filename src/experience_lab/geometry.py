"""Holdout geometry generator. Frozen seeds and draw rules; solvability only.

Method rankings are not an acceptance criterion. Generation RNG is separate
from agent RNG. Learners receive the public grid, not the geometry seed.
"""

from __future__ import annotations

from random import Random
from typing import Any

from experience_lab.env import SwitchWorld
from experience_lab.layouts import Layout, parse_ascii_layout
from experience_lab.planner import oracle_plan
from experience_lab.rules import initially_closed_rule_names, table_by_name

GENERATOR_VERSION = 1
HOLDOUT_SEEDS = tuple(range(1, 21))
CONTROL_WIDTHS = (4, 5, 6, 7, 8)
CONTROL_HEIGHTS = (2, 3, 4)
GOAL_LENGTHS = (2, 3, 4, 5)
SPUR_LENGTHS = (0, 1, 2, 3, 4)
MAX_DRAW_ATTEMPTS = 400
SOLVER_EXPANSION_CAP = 10000


def layout_to_ascii(layout: Layout) -> str:
    grid = [list(row) for row in layout.static_grid]
    sr, sc = layout.start
    grid[sr][sc] = "S"
    return "\n".join("".join(row) for row in grid)


def holdout_layout_name(seed: int) -> str:
    return f"holdout_{seed:02d}"


def _blank_grid(height: int, width: int) -> list[list[str]]:
    return [["#" for _ in range(width)] for _ in range(height)]


def _control_cells(
    spur_len: int,
    ch: int,
    cw: int,
    spur_col: int,
) -> list[tuple[int, int]]:
    cells: list[tuple[int, int]] = []
    control_top = 1 + spur_len
    for row in range(control_top, control_top + ch):
        for col in range(1, cw + 1):
            cells.append((row, col))
    if spur_len > 0:
        for row in range(1, 1 + spur_len):
            cells.append((row, spur_col))
    return cells


def _render_candidate(
    *,
    cw: int,
    ch: int,
    spur_len: int,
    spur_col: int,
    goal_len: int,
    door_col: int,
    start: tuple[int, int],
    switch_0: tuple[int, int],
    switch_1: tuple[int, int],
    mirror: bool,
) -> str:
    control_top = 1 + spur_len
    height = 1 + spur_len + ch + 1 + goal_len + 1
    width = cw + 2
    grid = _blank_grid(height, width)
    for row, col in _control_cells(spur_len, ch, cw, spur_col):
        grid[row][col] = "."
    door_row = control_top + ch
    grid[door_row][door_col] = "D"
    for offset in range(goal_len):
        grid[door_row + 1 + offset][door_col] = "."
    grid[door_row + goal_len][door_col] = "G"
    grid[start[0]][start[1]] = "S"
    grid[switch_0[0]][switch_0[1]] = "0"
    grid[switch_1[0]][switch_1[1]] = "1"
    if mirror:
        grid = [list(reversed(row)) for row in grid]
    return "\n".join("".join(row) for row in grid)


def layout_solvable(layout: Layout, expansion_cap: int = SOLVER_EXPANSION_CAP) -> bool:
    """Oracle reachability for every initially closed two-switch rule. Evaluator only."""
    if layout.n_switches != 2 or layout.n_doors != 1:
        return False
    for rule_name in initially_closed_rule_names(2):
        rule = table_by_name(2, rule_name)
        plan = oracle_plan(layout, layout.start, 0, (rule,), expansion_cap)
        if plan.status != "ok" or plan.actions is None or not plan.actions:
            return False
        env = SwitchWorld(layout=layout, _hidden_rules=(rule,))
        obs = env.reset()
        terminated = False
        for action in plan.actions:
            obs, _reward, terminated, truncated, _info = env.step(action)
            if truncated:
                return False
        if not terminated or obs.agent_pos != layout.goal:
            return False
    return True


def _draw_layout(rng: Random) -> tuple[Layout, dict[str, Any]] | None:
    cw = rng.choice(CONTROL_WIDTHS)
    ch = rng.choice(CONTROL_HEIGHTS)
    spur_len = rng.choice(SPUR_LENGTHS)
    goal_len = rng.choice(GOAL_LENGTHS)
    mirror = bool(rng.choice((False, True)))
    spur_col = rng.randint(1, cw) if spur_len else 1
    door_col = rng.randint(1, cw)
    cells = _control_cells(spur_len, ch, cw, spur_col)
    if len(cells) < 3:
        return None
    start, switch_0, switch_1 = rng.sample(cells, 3)
    ascii_map = _render_candidate(
        cw=cw,
        ch=ch,
        spur_len=spur_len,
        spur_col=spur_col,
        goal_len=goal_len,
        door_col=door_col,
        start=start,
        switch_0=switch_0,
        switch_1=switch_1,
        mirror=mirror,
    )
    params = {
        "control_width": cw,
        "control_height": ch,
        "spur_len": spur_len,
        "spur_col": spur_col,
        "goal_len": goal_len,
        "door_col": door_col,
        "start": list(start),
        "switch_0": list(switch_0),
        "switch_1": list(switch_1),
        "mirror": mirror,
    }
    try:
        layout = parse_ascii_layout("candidate", ascii_map)
    except ValueError:
        return None
    if not layout_solvable(layout):
        return None
    return layout, params


def generate_holdout_layout(seed: int) -> tuple[Layout, dict[str, Any]]:
    """First solvable draw from Random(seed). Raises if the seed exhausts attempts."""
    rng = Random(seed)
    for attempt in range(1, MAX_DRAW_ATTEMPTS + 1):
        drawn = _draw_layout(rng)
        if drawn is None:
            continue
        layout, params = drawn
        name = holdout_layout_name(seed)
        named = parse_ascii_layout(name, layout_to_ascii(layout))
        params = {
            **params,
            "geometry_seed": seed,
            "attempt": attempt,
            "generator_version": GENERATOR_VERSION,
            "ascii": layout_to_ascii(named),
        }
        return named, params
    raise RuntimeError(f"geometry seed {seed} produced no solvable map in {MAX_DRAW_ATTEMPTS} draws")


def freeze_holdout_maps() -> dict[str, Any]:
    maps: list[dict[str, Any]] = []
    for seed in HOLDOUT_SEEDS:
        layout, params = generate_holdout_layout(seed)
        maps.append(
            {
                "name": layout.name,
                "geometry_seed": seed,
                "ascii_lines": params["ascii"].split("\n"),
                "params": {k: v for k, v in params.items() if k != "ascii"},
                "width": layout.width,
                "height": layout.height,
            }
        )
    return {
        "generator_version": GENERATOR_VERSION,
        "seeds": list(HOLDOUT_SEEDS),
        "control_widths": list(CONTROL_WIDTHS),
        "control_heights": list(CONTROL_HEIGHTS),
        "goal_lengths": list(GOAL_LENGTHS),
        "spur_lengths": list(SPUR_LENGTHS),
        "max_draw_attempts": MAX_DRAW_ATTEMPTS,
        "acceptance": "oracle solvability for initially closed two-switch rules; no method ranking",
        "maps": maps,
    }
