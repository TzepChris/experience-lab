"""Aggregate metrics from completed episode records."""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable


def capped_action_cost(success: bool, steps: int, max_episode_steps: int) -> int:
    return steps if success else max_episode_steps


def summarize_runs(runs: Iterable[dict[str, Any]], max_episode_steps: int) -> dict[str, Any]:
    by_method: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_method[run["method"]].append(run)

    methods: dict[str, Any] = {}
    for method, method_runs in sorted(by_method.items()):
        episodes = [ep for run in method_runs for ep in run.get("episodes", [])]
        completed_eps = [ep for ep in episodes if ep.get("status") == "completed"]
        successes = [ep for ep in completed_eps if ep.get("success")]
        n_eps = len(completed_eps)
        methods[method] = {
            "runs": len(method_runs),
            "completed_runs": sum(1 for run in method_runs if run.get("status") == "completed"),
            "interrupted_runs": sum(
                1 for run in method_runs if str(run.get("status", "")).startswith("interrupted")
            ),
            "failed_runs": sum(
                1
                for run in method_runs
                if run.get("status") not in {"completed", "interrupted_time"}
                and not str(run.get("status", "")).startswith("interrupted")
            ),
            "episodes_completed": n_eps,
            "successes": len(successes),
            "success_rate": None if n_eps == 0 else len(successes) / n_eps,
            "mean_capped_action_cost": None
            if n_eps == 0
            else sum(
                capped_action_cost(ep["success"], ep["steps"], max_episode_steps)
                for ep in completed_eps
            )
            / n_eps,
            "mean_successful_steps": None
            if not successes
            else sum(ep["steps"] for ep in successes) / len(successes),
            "mean_return": None
            if n_eps == 0
            else sum(ep["return_sum"] for ep in completed_eps) / n_eps,
            "mean_final_hypothesis_count": _mean(
                [
                    ep["final_hypothesis_count"]
                    for ep in completed_eps
                    if ep.get("final_hypothesis_count") is not None
                ]
            ),
            "belief_changed_runs": sum(1 for run in method_runs if run.get("belief_changed")),
            "total_interactions": sum(ep["steps"] for ep in completed_eps),
            "total_planner_expansions": sum(run.get("planner_expansions", 0) for run in method_runs),
        }
    return {"methods": methods}


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def instance_key(run: dict[str, Any]) -> str:
    if run.get("problem_id"):
        return str(run["problem_id"])
    layout = run.get("layout") or "tiny_two_switch"
    rule = run.get("requested_rule") or run.get("rule")
    perm = run.get("permutation") or [0, 1]
    return f"{layout}|{rule}|perm{','.join(str(i) for i in perm)}"


def physical_key(run: dict[str, Any]) -> str:
    if run.get("physical_problem_id"):
        return str(run["physical_problem_id"])
    layout = run.get("layout") or "tiny_two_switch"
    rule = run.get("requested_rule") or run.get("rule")
    return f"{layout}|{rule}"


def episode_capped_cost(episode: dict[str, Any], max_episode_steps: int) -> int | None:
    if episode.get("status") != "completed":
        return None
    return capped_action_cost(bool(episode.get("success")), int(episode["steps"]), max_episode_steps)


def oracle_episode_costs(
    runs: Iterable[dict[str, Any]],
    max_episode_steps: int,
) -> dict[tuple[str, int], int]:
    """Oracle costs keyed by (problem_id, episode_index). Seed is ignored after checking equality."""
    collected: dict[tuple[str, int], list[int]] = defaultdict(list)
    for run in runs:
        if run.get("method") != "oracle" or run.get("status") != "completed":
            continue
        key = instance_key(run)
        for episode in run.get("episodes", []):
            cost = episode_capped_cost(episode, max_episode_steps)
            if cost is None:
                continue
            collected[(key, int(episode["index"]))].append(cost)
    out: dict[tuple[str, int], int] = {}
    for ident, values in collected.items():
        if any(value != values[0] for value in values):
            raise ValueError(f"oracle costs disagree across seeds for {ident}: {values}")
        out[ident] = values[0]
    return out


def per_instance_rows(
    runs: Iterable[dict[str, Any]],
    max_episode_steps: int,
) -> list[dict[str, Any]]:
    oracle_costs = oracle_episode_costs(runs, max_episode_steps)
    rows: list[dict[str, Any]] = []
    for run in runs:
        problem = instance_key(run)
        physical = physical_key(run)
        for episode in run.get("episodes", []):
            cost = episode_capped_cost(episode, max_episode_steps)
            oracle_cost = oracle_costs.get((problem, int(episode.get("index", 0))))
            excess = None if cost is None or oracle_cost is None else cost - oracle_cost
            rows.append(
                {
                    "problem_id": problem,
                    "physical_problem_id": physical,
                    "layout": run.get("layout"),
                    "requested_rule": run.get("requested_rule") or run.get("rule"),
                    "permutation": run.get("permutation"),
                    "seed": run.get("seed"),
                    "method": run.get("method"),
                    "episode": episode.get("index"),
                    "status": episode.get("status") or run.get("status"),
                    "success": episode.get("success"),
                    "steps": episode.get("steps"),
                    "capped_action_cost": cost,
                    "oracle_cost": oracle_cost,
                    "excess_over_oracle": excess,
                    "first_probe_target": episode.get("first_probe_target"),
                    "probe_targets": episode.get("probe_targets"),
                    "optional_reprobe": episode.get("optional_reprobe"),
                    "extra_probe_actions": episode.get("extra_probe_actions"),
                    "extra_probe_target": episode.get("extra_probe_target"),
                    "used_task_plan": episode.get("used_task_plan"),
                    "run_id": run.get("run_id"),
                }
            )
    return rows
