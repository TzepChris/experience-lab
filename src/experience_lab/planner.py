"""Task planner, control-area probe planner, and privileged oracle.

Oracle functions are for evaluation and tests. Learner planners use Belief only.
"""

from __future__ import annotations

import math
import time
from collections import deque
from dataclasses import dataclass
from itertools import product
from random import Random

from experience_lab.belief import Belief
from experience_lab.layouts import Layout
from experience_lab.rules import TruthTable
from experience_lab.types import MOVE_DELTAS, Action


@dataclass(frozen=True)
class PlanResult:
    actions: tuple[Action, ...] | None
    expansions: int
    status: str
    target: int | None = None
    score: float | None = None
    candidates: tuple[dict, ...] = ()


class PlannerCapError(RuntimeError):
    pass


def binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return float(-p * math.log2(p) - (1.0 - p) * math.log2(1.0 - p))


def _deadline_hit(deadline: float | None) -> bool:
    return deadline is not None and time.perf_counter() >= deadline


def _reconstruct(
    parents: dict[tuple[int, int, int], tuple[tuple[int, int, int], Action]],
    start: tuple[int, int, int],
    goal: tuple[int, int, int],
) -> tuple[Action, ...]:
    actions: list[Action] = []
    state = goal
    while state != start:
        prev, action = parents[state]
        actions.append(action)
        state = prev
    actions.reverse()
    return tuple(actions)


def _bfs(
    layout: Layout,
    start_pos: tuple[int, int],
    start_bits: int,
    goal_fn,
    enterable_fn,
    expansion_cap: int,
    deadline: float | None,
) -> PlanResult:
    start = (start_pos[0], start_pos[1], start_bits)
    if goal_fn(start_pos, start_bits):
        return PlanResult(actions=(), expansions=0, status="ok")

    queue: deque[tuple[int, int, int]] = deque([start])
    parents: dict[tuple[int, int, int], tuple[tuple[int, int, int], Action]] = {}
    seen = {start}
    expansions = 0

    while queue:
        if _deadline_hit(deadline):
            return PlanResult(actions=None, expansions=expansions, status="time_limit")
        if expansions >= expansion_cap:
            return PlanResult(actions=None, expansions=expansions, status="planner_cap")

        row, col, bits = queue.popleft()
        expansions += 1
        pos = (row, col)

        for action, (dr, dc) in MOVE_DELTAS.items():
            nxt = (row + dr, col + dc)
            if not enterable_fn(pos, nxt, bits):
                continue
            state = (nxt[0], nxt[1], bits)
            if state in seen:
                continue
            seen.add(state)
            parents[state] = ((row, col, bits), action)
            if goal_fn(nxt, bits):
                return PlanResult(
                    actions=_reconstruct(parents, start, state),
                    expansions=expansions,
                    status="ok",
                )
            queue.append(state)

        switch_i = layout.switch_index_at(pos)
        if switch_i is not None:
            new_bits = bits ^ (1 << switch_i)
            state = (row, col, new_bits)
            if state not in seen:
                seen.add(state)
                parents[state] = ((row, col, bits), Action.TOGGLE)
                if goal_fn(pos, new_bits):
                    return PlanResult(
                        actions=_reconstruct(parents, start, state),
                        expansions=expansions,
                        status="ok",
                    )
                queue.append(state)

    return PlanResult(actions=None, expansions=expansions, status="no_plan")


def _conservative_enterable(layout: Layout, belief: Belief):
    def enterable(_from: tuple[int, int], nxt: tuple[int, int], bits: int) -> bool:
        if layout.is_wall(nxt):
            return False
        door_i = layout.door_index_at(nxt)
        if door_i is None:
            return True
        return belief.conservatively_open(layout.door_ids[door_i], bits)

    return enterable


def _true_enterable(layout: Layout, rules: tuple[TruthTable, ...]):
    def enterable(_from: tuple[int, int], nxt: tuple[int, int], bits: int) -> bool:
        if layout.is_wall(nxt):
            return False
        door_i = layout.door_index_at(nxt)
        if door_i is None:
            return True
        return bool(rules[door_i](bits))

    return enterable


def _blocked_doors_enterable(layout: Layout):
    def enterable(_from: tuple[int, int], nxt: tuple[int, int], bits: int) -> bool:
        del bits
        if layout.is_wall(nxt):
            return False
        return layout.door_index_at(nxt) is None

    return enterable


def conservative_plan(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    belief: Belief,
    expansion_cap: int,
    deadline: float | None = None,
) -> PlanResult:
    return _bfs(
        layout,
        agent_pos,
        switch_bits,
        goal_fn=lambda pos, _bits: pos == layout.goal,
        enterable_fn=_conservative_enterable(layout, belief),
        expansion_cap=expansion_cap,
        deadline=deadline,
    )


def assumed_rule_plan(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    rules: tuple[TruthTable, ...],
    expansion_cap: int,
    deadline: float | None = None,
) -> PlanResult:
    """Shortest goal plan assuming one complete hypothesized rule tuple is true.

    Learner-legal when `rules` come from Belief hypotheses. A single assignment
    is held fixed for the whole search; predictions from other hypotheses are
    not mixed in.
    """
    return _bfs(
        layout,
        agent_pos,
        switch_bits,
        goal_fn=lambda pos, _bits: pos == layout.goal,
        enterable_fn=_true_enterable(layout, rules),
        expansion_cap=expansion_cap,
        deadline=deadline,
    )


def oracle_plan(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    rules: tuple[TruthTable, ...],
    expansion_cap: int,
    deadline: float | None = None,
) -> PlanResult:
    """Privileged shortest path using true door rules. Evaluator/tests only."""
    return assumed_rule_plan(
        layout, agent_pos, switch_bits, rules, expansion_cap, deadline
    )


def complete_hypothesis_assignments(belief: Belief) -> tuple[tuple[TruthTable, ...], ...]:
    """Cartesian product of remaining tables, one complete assignment per door."""
    per_door: list[tuple[TruthTable, ...]] = []
    for door_id in belief.door_ids:
        remaining = tuple(sorted(belief.hypotheses[door_id], key=lambda table: table.name))
        if not remaining:
            return ()
        per_door.append(remaining)
    return tuple(product(*per_door))


def hypothesis_goal_plan_lengths(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    belief: Belief,
    expansion_cap: int,
    deadline: float | None = None,
) -> dict:
    """Per complete hypothesis: shortest goal length, or undecided on cap/time."""
    rows: list[dict] = []
    expansions = 0
    any_undecided = False
    decided_lengths: list[int] = []
    for rules in complete_hypothesis_assignments(belief):
        plan = assumed_rule_plan(
            layout, agent_pos, switch_bits, rules, expansion_cap, deadline
        )
        expansions += plan.expansions
        length = None if plan.actions is None else len(plan.actions)
        rows.append(
            {
                "hypothesis": tuple(table.name for table in rules),
                "status": plan.status,
                "length": length,
            }
        )
        if plan.status in ("planner_cap", "time_limit"):
            any_undecided = True
        elif plan.status == "ok" and length is not None:
            decided_lengths.append(length)
    return {
        "hypotheses": rows,
        "expansions": expansions,
        "any_undecided": any_undecided,
        "decided_lengths": decided_lengths,
        "L": min(decided_lengths) if decided_lengths else None,
    }


def ul_stopping_decision(
    U: int | None,
    U_status: str,
    hypothesis_report: dict,
) -> dict:
    """Hand-designed rule: probe only when a decided hypothetical plan is shorter than U.

    Certificates:
    - shorter_plan_witness: a resolved hypothesis has length < U
    - certified_no_headroom: every remaining assignment resolved and min length == U
    - undecided: unresolved searches block a no-headroom certificate

    Exploiting after a compute cap is allowed. It is not certified optimality.
    """
    hypotheses = list(hypothesis_report.get("hypotheses") or [])
    decided = list(hypothesis_report.get("decided_lengths") or [])
    L = min(decided) if decided else None
    unresolved_search_count = sum(
        1 for row in hypotheses if row.get("status") in ("planner_cap", "time_limit")
    )
    any_undecided = bool(hypothesis_report.get("any_undecided")) or unresolved_search_count > 0
    proven_shorter = U is not None and L is not None and L < U
    if U is None:
        decision = "required_explore"
        L_status = "not_applicable"
        certificate = "not_applicable"
    elif proven_shorter:
        decision = "optional_probe"
        L_status = "ok"
        certificate = "shorter_plan_witness"
    elif any_undecided:
        decision = "exploit"
        L_status = "undecided"
        certificate = "undecided"
    elif L is not None and L == U:
        decision = "exploit"
        L_status = "ok"
        certificate = "certified_no_headroom"
    else:
        decision = "exploit"
        L_status = "no_plan" if L is None else "ok"
        certificate = "undecided"
    return {
        "U": U,
        "U_status": U_status,
        "L": L,
        "L_status": L_status,
        "certificate": certificate,
        "decision": decision,
        "proven_shorter": proven_shorter,
        "any_undecided": any_undecided,
        "unresolved_search_count": unresolved_search_count,
        "hypotheses": hypotheses,
        "planning_expansions": int(hypothesis_report.get("expansions") or 0),
        "note": "hand-designed U vs L stopping rule, not a learned policy",
    }


def probe_plan(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    target_bits: int,
    expansion_cap: int,
    deadline: float | None = None,
) -> PlanResult:
    """Minimum-action route to a switch configuration with every door treated as blocked."""
    result = _bfs(
        layout,
        agent_pos,
        switch_bits,
        goal_fn=lambda _pos, bits: bits == target_bits,
        enterable_fn=_blocked_doors_enterable(layout),
        expansion_cap=expansion_cap,
        deadline=deadline,
    )
    return PlanResult(
        actions=result.actions,
        expansions=result.expansions,
        status=result.status,
        target=target_bits,
    )


def total_uncertainty(belief: Belief, switch_config: int) -> float:
    return sum(
        binary_entropy(belief.open_fraction(door_id, switch_config))
        for door_id in belief.door_ids
    )


def _candidate_records(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    belief: Belief,
    expansion_cap: int,
    deadline: float | None,
) -> tuple[list[dict], int]:
    records: list[dict] = []
    expansions = 0
    n_configs = 1 << layout.n_switches
    for target in range(n_configs):
        uncertainty = total_uncertainty(belief, target)
        observed = target in belief.evidence
        plan = probe_plan(
            layout, agent_pos, switch_bits, target, expansion_cap, deadline
        )
        expansions += plan.expansions
        cost = 0 if plan.actions is None else len(plan.actions)
        score = None
        if (
            (not observed)
            and uncertainty > 0.0
            and plan.actions is not None
        ):
            score = uncertainty / max(1, cost)
        records.append(
            {
                "target": target,
                "uncertainty": uncertainty,
                "observed": observed,
                "status": plan.status,
                "cost": None if plan.actions is None else cost,
                "score": score,
                "actions": plan.actions,
            }
        )
    return records, expansions


def informative_probe_candidates(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    belief: Belief,
    expansion_cap: int,
    deadline: float | None = None,
) -> tuple[list[dict], tuple[dict, ...], int]:
    """Intended probe targets: unobserved, positive uncertainty, reachable.

    Configurations visited on the way to a target are not candidates. A probe
    plan may toggle an intermediate config; that is a route observation, not
    the selected target.
    """
    records, expansions = _candidate_records(
        layout, agent_pos, switch_bits, belief, expansion_cap, deadline
    )
    candidates = [row for row in records if row["score"] is not None]
    return candidates, tuple(records), expansions


def select_active_probe(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    belief: Belief,
    rng: Random,
    expansion_cap: int,
    deadline: float | None = None,
) -> PlanResult:
    """Maximize predicted information per action. RNG is used only to break score ties."""
    scored, records, expansions = informative_probe_candidates(
        layout, agent_pos, switch_bits, belief, expansion_cap, deadline
    )
    if not scored:
        return PlanResult(
            actions=None,
            expansions=expansions,
            status="no_informative_probe",
            candidates=records,
        )
    best = max(row["score"] for row in scored)
    tied = [row for row in scored if row["score"] == best]
    chosen = rng.choice(tied)
    return PlanResult(
        actions=chosen["actions"],
        expansions=expansions,
        status="ok",
        target=chosen["target"],
        score=chosen["score"],
        candidates=records,
    )


def select_systematic_probe(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    belief: Belief,
    expansion_cap: int,
    deadline: float | None = None,
) -> PlanResult:
    """Canonical order: integer configs 0 .. 2^S-1, skipping observed or zero-disagreement."""
    scored, records, expansions = informative_probe_candidates(
        layout, agent_pos, switch_bits, belief, expansion_cap, deadline
    )
    if not scored:
        return PlanResult(
            actions=None,
            expansions=expansions,
            status="no_informative_probe",
            candidates=records,
        )
    chosen = scored[0]
    return PlanResult(
        actions=chosen["actions"],
        expansions=expansions,
        status="ok",
        target=chosen["target"],
        score=chosen["score"],
        candidates=records,
    )


def select_random_informative_probe(
    layout: Layout,
    agent_pos: tuple[int, int],
    switch_bits: int,
    belief: Belief,
    rng: Random,
    expansion_cap: int,
    deadline: float | None = None,
) -> PlanResult:
    """Uniform sample among informative intended targets. Not score tie-breaking."""
    informative, records, expansions = informative_probe_candidates(
        layout, agent_pos, switch_bits, belief, expansion_cap, deadline
    )
    if not informative:
        return PlanResult(
            actions=None,
            expansions=expansions,
            status="no_informative_probe",
            candidates=records,
        )
    chosen = rng.choice(informative)
    return PlanResult(
        actions=chosen["actions"],
        expansions=expansions,
        status="ok",
        target=chosen["target"],
        score=chosen["score"],
        candidates=records,
    )


def informative_candidate_targets(records: list[dict] | tuple[dict, ...]) -> tuple[int, ...]:
    """Intended probe targets: unobserved, positive uncertainty, reachable."""
    return tuple(row["target"] for row in records if row["score"] is not None)


def simulate_probe_route_configs(
    layout: Layout,
    start_pos: tuple[int, int],
    start_bits: int,
    actions: tuple[Action, ...] | None,
) -> dict:
    """Switch configs visited while executing a probe plan. Independent of door rules.

    Distinguishes the planned end config from configs observed after intermediate toggles.
    """
    pos = start_pos
    bits = start_bits
    after_toggles: list[int] = []
    if not actions:
        return {
            "start_config": start_bits,
            "end_config": bits,
            "configs_after_toggles": after_toggles,
            "first_toggle_config": None,
        }
    for action in actions:
        if action is Action.TOGGLE:
            switch_i = layout.switch_index_at(pos)
            if switch_i is not None:
                bits ^= 1 << switch_i
            after_toggles.append(bits)
        else:
            delta = MOVE_DELTAS[action]
            pos = (pos[0] + delta[0], pos[1] + delta[1])
    return {
        "start_config": start_bits,
        "end_config": bits,
        "configs_after_toggles": after_toggles,
        "first_toggle_config": after_toggles[0] if after_toggles else None,
    }


def audit_random_informative_selection(
    layout: Layout,
    belief: Belief,
    n_seeds: int,
    expansion_cap: int,
    start_pos: tuple[int, int] | None = None,
    start_bits: int = 0,
) -> dict:
    """Sample intended targets on a fixed belief. This is uniform selection among
    informative configs, not score tie-breaking.
    """
    pos = layout.start if start_pos is None else start_pos
    records, _expansions = _candidate_records(
        layout, pos, start_bits, belief, expansion_cap, None
    )
    candidate_set = informative_candidate_targets(records)
    informative = [row for row in records if row["score"] is not None]
    scores = [row["score"] for row in informative]
    candidate_summaries = [
        {
            "target": row["target"],
            "uncertainty": row["uncertainty"],
            "observed": row["observed"],
            "status": row["status"],
            "cost": row["cost"],
            "score": row["score"],
        }
        for row in records
    ]
    draws: list[dict] = []
    counts: dict[int, int] = {target: 0 for target in candidate_set}
    if not candidate_set:
        return {
            "n_seeds": n_seeds,
            "candidate_set": [],
            "counts": {},
            "intended_targets": [],
            "draws": [],
            "candidate_records": candidate_summaries,
            "scores_all_equal": True,
            "sampling": "uniform_among_positive_information",
            "not_tie_breaking": True,
            "note": (
                "Random-informative samples uniformly among unobserved reachable "
                "configs with positive predicted information. No such candidate "
                "existed on this belief."
            ),
        }
    for seed in range(n_seeds):
        chosen = select_random_informative_probe(
            layout, pos, start_bits, belief, Random(seed), expansion_cap, None
        )
        if chosen.target is None:
            raise RuntimeError("random-informative returned no target from a non-empty candidate set")
        route = simulate_probe_route_configs(layout, pos, start_bits, chosen.actions)
        incidental = [
            cfg
            for cfg in route["configs_after_toggles"]
            if cfg != chosen.target
        ]
        draws.append(
            {
                "seed": seed,
                "intended_target": chosen.target,
                "end_config": route["end_config"],
                "first_toggle_config": route["first_toggle_config"],
                "configs_after_toggles": route["configs_after_toggles"],
                "incidental_toggle_configs": incidental,
            }
        )
        counts[chosen.target] = counts.get(chosen.target, 0) + 1
    return {
        "n_seeds": n_seeds,
        "candidate_set": list(candidate_set),
        "counts": {str(k): v for k, v in sorted(counts.items())},
        "intended_targets": [row["intended_target"] for row in draws],
        "draws": draws,
        "candidate_records": candidate_summaries,
        "scores_all_equal": len(set(scores)) <= 1,
        "sampling": "uniform_among_positive_information",
        "not_tie_breaking": True,
        "note": (
            "Random-informative samples uniformly among unobserved reachable "
            "configs with positive predicted information. Intended_target is "
            "that sample. configs_after_toggles are observations that would "
            "occur along the probe route, including intermediate toggles. "
            "This is not active-score tie-breaking: candidates need not share "
            "a maximum information-per-action score."
        ),
    }
