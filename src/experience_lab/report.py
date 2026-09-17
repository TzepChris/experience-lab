"""Diagnostic report: per-instance costs, excess over oracle, and probe traces."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from experience_lab.metrics import per_instance_rows
from experience_lab.serialization import write_json


LEARNING_METHODS = (
    "active_retained",
    "active_reset",
    "systematic_retained",
    "systematic_reset",
    "random_informative_retained",
    "random_informative_reset",
)

SELECTOR_PAIRS = (
    ("active_retained", "systematic_retained"),
    ("active_retained", "random_informative_retained"),
    ("systematic_retained", "random_informative_retained"),
    ("active_retained", "active_reset"),
    ("systematic_retained", "systematic_reset"),
    ("random_informative_retained", "random_informative_reset"),
)


def _load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                events.append(json.loads(line))
    return events


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _group_problem_method(rows: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[(row["problem_id"], row["method"])].append(row)
    return grouped


def _seed_means(rows: list[dict[str, Any]]) -> dict[int, float]:
    by_seed: dict[int, list[float]] = defaultdict(list)
    for row in rows:
        if row.get("capped_action_cost") is None:
            continue
        by_seed[int(row["seed"])].append(float(row["capped_action_cost"]))
    return {seed: sum(vals) / len(vals) for seed, vals in by_seed.items()}


def _trace_for_run(events: list[dict[str, Any]], run_id: str, episode: int) -> dict[str, Any]:
    steps = [
        event
        for event in events
        if event.get("event") == "step"
        and event.get("run_id") == run_id
        and event.get("episode") == episode
    ]
    actions = [event.get("action") for event in steps]
    probes = []
    last_target = None
    for event in steps:
        if event.get("plan_kind") != "probe":
            continue
        target = event.get("target")
        if target != last_target:
            probes.append(
                {
                    "step": event.get("step"),
                    "target": target,
                    "action": event.get("action"),
                    "switch_bits": (event.get("observation") or {}).get("switch_bits"),
                    "door_open": (event.get("observation") or {}).get("door_open"),
                    "agent_pos": (event.get("observation") or {}).get("agent_pos"),
                    "score": event.get("score"),
                    "hypotheses_after": (event.get("hypotheses_after") or {}).get("hypotheses"),
                }
            )
            last_target = target
    first_toggle = next((event for event in steps if event.get("action") == "TOGGLE"), None)
    return {
        "actions": actions,
        "probes": probes,
        "first_toggle": None
        if first_toggle is None
        else {
            "step": first_toggle.get("step"),
            "target": first_toggle.get("target"),
            "plan_kind": first_toggle.get("plan_kind"),
            "switch_bits": (first_toggle.get("observation") or {}).get("switch_bits"),
            "door_open": (first_toggle.get("observation") or {}).get("door_open"),
            "agent_pos": (first_toggle.get("observation") or {}).get("agent_pos"),
        },
    }


def build_diagnostic_report(
    summary: dict[str, Any],
    events_path: Path | None = None,
    max_episode_steps: int = 256,
) -> dict[str, Any]:
    runs = summary.get("runs") or []
    rows = per_instance_rows(runs, max_episode_steps)
    grouped = _group_problem_method(rows)
    problems = sorted({row["problem_id"] for row in rows})
    physical = sorted({row["physical_problem_id"] for row in rows})
    events = _load_events(events_path) if events_path is not None else []

    instance_table: list[dict[str, Any]] = []
    for problem in problems:
        entry: dict[str, Any] = {"problem_id": problem, "methods": {}}
        physical_id = next(
            (row["physical_problem_id"] for row in rows if row["problem_id"] == problem),
            problem,
        )
        entry["physical_problem_id"] = physical_id
        sample = next(row for row in rows if row["problem_id"] == problem)
        entry["layout"] = sample.get("layout")
        entry["requested_rule"] = sample.get("requested_rule")
        entry["permutation"] = sample.get("permutation")
        for method in ["oracle", *LEARNING_METHODS]:
            method_rows = grouped.get((problem, method), [])
            completed = [row for row in method_rows if row.get("capped_action_cost") is not None]
            successes = [row for row in completed if row.get("success")]
            seed_costs = _seed_means(completed)
            entry["methods"][method] = {
                "episodes": len(completed),
                "successes": len(successes),
                "success_rate": None if not completed else len(successes) / len(completed),
                "mean_cost": _mean([float(row["capped_action_cost"]) for row in completed]),
                "mean_excess": _mean(
                    [
                        float(row["excess_over_oracle"])
                        for row in completed
                        if row.get("excess_over_oracle") is not None
                    ]
                ),
                "seed_mean_costs": {str(k): v for k, v in sorted(seed_costs.items())},
                "episode0_costs_by_seed": {
                    str(row["seed"]): row["capped_action_cost"]
                    for row in completed
                    if row.get("episode") == 0
                },
                "episode1_costs_by_seed": {
                    str(row["seed"]): row["capped_action_cost"]
                    for row in completed
                    if row.get("episode") == 1
                },
                "first_probes_by_seed_ep0": {
                    str(row["seed"]): row.get("first_probe_target")
                    for row in completed
                    if row.get("episode") == 0
                },
            }
        instance_table.append(entry)

    differences: list[dict[str, Any]] = []
    for problem in problems:
        for left, right in SELECTOR_PAIRS:
            left_rows = grouped.get((problem, left), [])
            right_rows = grouped.get((problem, right), [])
            by_seed_ep = {
                (int(row["seed"]), int(row["episode"])): row
                for row in right_rows
                if row.get("capped_action_cost") is not None
            }
            for left_row in left_rows:
                if left_row.get("capped_action_cost") is None:
                    continue
                key = (int(left_row["seed"]), int(left_row["episode"]))
                right_row = by_seed_ep.get(key)
                if right_row is None:
                    continue
                if left_row["capped_action_cost"] == right_row["capped_action_cost"] and (
                    left_row.get("first_probe_target") == right_row.get("first_probe_target")
                ):
                    continue
                delta = int(left_row["capped_action_cost"]) - int(right_row["capped_action_cost"])
                item = {
                    "problem_id": problem,
                    "physical_problem_id": left_row["physical_problem_id"],
                    "seed": left_row["seed"],
                    "episode": left_row["episode"],
                    "left_method": left,
                    "right_method": right,
                    "left_cost": left_row["capped_action_cost"],
                    "right_cost": right_row["capped_action_cost"],
                    "cost_delta_left_minus_right": delta,
                    "left_first_probe": left_row.get("first_probe_target"),
                    "right_first_probe": right_row.get("first_probe_target"),
                    "left_probes": left_row.get("probe_targets"),
                    "right_probes": right_row.get("probe_targets"),
                    "left_run_id": left_row.get("run_id"),
                    "right_run_id": right_row.get("run_id"),
                    "explanation": _explain_probe_difference(
                        {
                            "left_method": left,
                            "right_method": right,
                            "left_first_probe": left_row.get("first_probe_target"),
                            "right_first_probe": right_row.get("first_probe_target"),
                            "cost_delta_left_minus_right": delta,
                            "left_cost": left_row["capped_action_cost"],
                            "right_cost": right_row["capped_action_cost"],
                        }
                    ),
                }
                attach_trace = False
                if events:
                    pair = (left, right)
                    if pair in {
                        ("active_retained", "systematic_retained"),
                        ("active_retained", "active_reset"),
                        ("systematic_retained", "systematic_reset"),
                    }:
                        attach_trace = True
                    elif "random_informative" in left or "random_informative" in right:
                        already = any(
                            diff.get("problem_id") == problem
                            and "random_informative" in str(diff.get("left_method"))
                            + str(diff.get("right_method"))
                            and "left_trace" in diff
                            for diff in differences
                        )
                        attach_trace = not already
                if attach_trace:
                    item["left_trace"] = _trace_for_run(
                        events, str(left_row["run_id"]), int(left_row["episode"])
                    )
                    item["right_trace"] = _trace_for_run(
                        events, str(right_row["run_id"]), int(right_row["episode"])
                    )
                differences.append(item)

    selector_means: dict[str, Any] = {}
    for method in ["oracle", *LEARNING_METHODS]:
        completed = [row for row in rows if row["method"] == method and row.get("capped_action_cost") is not None]
        selector_means[method] = {
            "mean_cost_pooling_episodes": _mean(
                [float(row["capped_action_cost"]) for row in completed]
            ),
            "mean_excess_pooling_episodes": _mean(
                [
                    float(row["excess_over_oracle"])
                    for row in completed
                    if row.get("excess_over_oracle") is not None
                ]
            ),
            "n_episodes": len(completed),
            "note": (
                "Pooled over instances and seeds. Seeds are tie-breaking repeats, "
                "not independent worlds. Use instance_table for the primary view."
            ),
        }

    return {
        "n_instances": len(problems),
        "n_physical_problems": len(physical),
        "physical_problems": physical,
        "instances": problems,
        "pooled_method_means": selector_means,
        "instance_table": instance_table,
        "differences": differences,
        "n_differences": len(differences),
        "note": (
            "An instance is (layout, requested_rule, permutation). "
            "Seeds repeat that instance. Permutation preserves physics and "
            "changes public bit indices / canonical order."
        ),
    }


def _explain_probe_difference(item: dict[str, Any]) -> str:
    left = item["left_method"]
    right = item["right_method"]
    lp = item.get("left_first_probe")
    rp = item.get("right_first_probe")
    delta = item["cost_delta_left_minus_right"]
    if lp != rp:
        winner = left if delta < 0 else right if delta > 0 else "neither"
        return (
            f"{left} first probed config {lp}; {right} first probed config {rp}. "
            f"Episode cost {left}={item['left_cost']}, {right}={item['right_cost']} "
            f"(delta {delta:+d}). Lower-cost method: {winner}."
        )
    return (
        f"First probe config matched ({lp}), but costs differed: "
        f"{left}={item['left_cost']}, {right}={item['right_cost']} (delta {delta:+d})."
    )


def write_diagnostic_report(
    summary: dict[str, Any],
    output_dir: Path,
    max_episode_steps: int = 256,
) -> dict[str, Any]:
    report = build_diagnostic_report(
        summary,
        events_path=output_dir / "events.jsonl",
        max_episode_steps=max_episode_steps,
    )
    write_json(output_dir / "report.json", report)
    return report
