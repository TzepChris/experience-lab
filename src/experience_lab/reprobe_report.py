"""Prefix cost/success for exploit vs optional re-probe."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from experience_lab.metrics import capped_action_cost
from experience_lab.serialization import write_json

DEFAULT_PREFIXES = (1, 2, 5, 10)
COMPARE_METHODS = ("active_retained", "active_reprobe_retained")


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def prefix_summary_for_run(
    run: dict[str, Any],
    prefixes: tuple[int, ...] | list[int],
    max_episode_steps: int,
) -> list[dict[str, Any]]:
    episodes = list(run.get("episodes") or [])
    rows: list[dict[str, Any]] = []
    for k in prefixes:
        chunk = episodes[:k]
        complete = (
            run.get("status") == "completed"
            and len(chunk) == k
            and all(ep.get("status") == "completed" for ep in chunk)
        )
        all_success = complete and all(ep.get("success") for ep in chunk)
        actual_steps = sum(int(ep.get("steps") or 0) for ep in chunk)
        if complete:
            capped = sum(
                capped_action_cost(bool(ep.get("success")), int(ep["steps"]), max_episode_steps)
                for ep in chunk
            )
        else:
            capped = None
        probe_steps = sum(int(ep.get("probe_steps") or 0) for ep in chunk)
        extra_probe_actions = sum(int(ep.get("extra_probe_actions") or 0) for ep in chunk)
        optional_episodes = sum(1 for ep in chunk if ep.get("optional_reprobe"))
        rows.append(
            {
                "k": k,
                "status": "completed" if complete else "incomplete",
                "all_success": all_success,
                "n_episodes_present": len(chunk),
                "actual_steps": actual_steps,
                "capped_cost": capped,
                "probe_steps": probe_steps,
                "extra_probe_actions": extra_probe_actions,
                "optional_reprobe_episodes": optional_episodes,
            }
        )
    return rows


def build_reprobe_report(
    summary: dict[str, Any],
    max_episode_steps: int = 256,
    prefixes: tuple[int, ...] | list[int] | None = None,
) -> dict[str, Any]:
    prefixes = tuple(prefixes or DEFAULT_PREFIXES)
    runs = list(summary.get("runs") or [])
    by_group: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        method = str(run.get("method"))
        layout = str(run.get("layout") or "")
        rule = str(run.get("requested_rule") or run.get("rule") or "")
        prefixes_rows = prefix_summary_for_run(run, prefixes, max_episode_steps)
        run["prefix_summaries"] = prefixes_rows
        by_group[(layout, rule, method)].append(run)

    tables: list[dict[str, Any]] = []
    layouts = sorted({k[0] for k in by_group})
    rules = sorted({k[1] for k in by_group})
    for layout in layouts:
        for rule in rules:
            entry: dict[str, Any] = {
                "layout": layout,
                "physical_rule": rule,
                "physical_problem_id": f"{layout}|{rule}",
                "methods": {},
                "comparisons": {},
            }
            for method in ("oracle", *COMPARE_METHODS):
                method_runs = by_group.get((layout, rule, method), [])
                prefix_stats = []
                for k in prefixes:
                    rows = []
                    for run in method_runs:
                        for row in run.get("prefix_summaries") or []:
                            if row["k"] == k:
                                rows.append(row)
                    completed = [row for row in rows if row["status"] == "completed"]
                    prefix_stats.append(
                        {
                            "k": k,
                            "n_runs": len(method_runs),
                            "n_completed_prefixes": len(completed),
                            "n_incomplete_prefixes": len(rows) - len(completed),
                            "mean_capped_cost": _mean(
                                [float(row["capped_cost"]) for row in completed if row["capped_cost"] is not None]
                            ),
                            "all_success_rate": None
                            if not completed
                            else sum(1 for row in completed if row["all_success"]) / len(completed),
                            "mean_probe_steps": _mean([float(row["probe_steps"]) for row in completed]),
                            "mean_extra_probe_actions": _mean(
                                [float(row["extra_probe_actions"]) for row in completed]
                            ),
                            "mean_optional_reprobe_episodes": _mean(
                                [float(row["optional_reprobe_episodes"]) for row in completed]
                            ),
                        }
                    )
                entry["methods"][method] = {
                    "runs": len(method_runs),
                    "completed_runs": sum(1 for run in method_runs if run.get("status") == "completed"),
                    "interrupted_runs": sum(
                        1 for run in method_runs if str(run.get("status", "")).startswith("interrupted")
                    ),
                    "prefixes": prefix_stats,
                }
            exploit = entry["methods"].get("active_retained", {}).get("prefixes") or []
            reprobe = entry["methods"].get("active_reprobe_retained", {}).get("prefixes") or []
            exploit_by_k = {row["k"]: row for row in exploit}
            delta_at_2 = None
            row2 = next((r for r in reprobe if r["k"] == 2), None)
            left2 = exploit_by_k.get(2)
            if (
                row2 is not None
                and left2 is not None
                and row2["mean_capped_cost"] is not None
                and left2["mean_capped_cost"] is not None
            ):
                delta_at_2 = row2["mean_capped_cost"] - left2["mean_capped_cost"]
            for row in reprobe:
                k = row["k"]
                left = exploit_by_k.get(k)
                if left is None or left["mean_capped_cost"] is None or row["mean_capped_cost"] is None:
                    delta = None
                else:
                    delta = row["mean_capped_cost"] - left["mean_capped_cost"]
                recovered = None
                if delta is not None and delta_at_2 is not None and k > 2:
                    recovered = delta < delta_at_2 and delta <= 0
                elif delta is not None and k == 2:
                    recovered = delta <= 0
                verdict = "equal"
                if delta is None:
                    verdict = "incomplete"
                elif delta < -1e-9:
                    verdict = "reprobe_helps"
                elif delta > 1e-9:
                    verdict = "reprobe_wastes"
                entry["comparisons"][str(k)] = {
                    "k": k,
                    "mean_cost_delta_reprobe_minus_exploit": delta,
                    "exploit_all_success_rate": None if left is None else left["all_success_rate"],
                    "reprobe_all_success_rate": row["all_success_rate"],
                    "mean_extra_probe_actions": row.get("mean_extra_probe_actions"),
                    "verdict": verdict,
                    "extra_cost_recovered_by_this_prefix": recovered,
                }
            tables.append(entry)

    instances = _instance_comparisons(runs, prefixes, max_episode_steps)
    return {
        "prefixes": list(prefixes),
        "by_layout_and_physical_rule": tables,
        "by_instance": instances,
        "note": (
            "Prefixes are cumulative episode costs from the same 10-episode runs. "
            "all_success requires every episode in the prefix to reach the goal. "
            "Incomplete prefixes are not converted into low costs. "
            "Permutation repeats are pooled as the same physical rule in the "
            "layout-by-rule table; by_instance keeps permutation and seed."
        ),
    }


def _instance_comparisons(
    runs: list[dict[str, Any]],
    prefixes: tuple[int, ...],
    max_episode_steps: int,
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, int], dict[str, dict[str, Any]]] = defaultdict(dict)
    for run in runs:
        method = str(run.get("method"))
        if method not in COMPARE_METHODS:
            continue
        key = (str(run.get("problem_id") or ""), int(run.get("seed") or 0))
        grouped[key][method] = run
    rows: list[dict[str, Any]] = []
    for (problem_id, seed), methods in sorted(grouped.items()):
        exploit = methods.get("active_retained")
        reprobe = methods.get("active_reprobe_retained")
        if exploit is None or reprobe is None:
            continue
        sample = exploit
        comparisons: dict[str, Any] = {}
        exploit_prefixes = {row["k"]: row for row in prefix_summary_for_run(exploit, prefixes, max_episode_steps)}
        reprobe_prefixes = {row["k"]: row for row in prefix_summary_for_run(reprobe, prefixes, max_episode_steps)}
        for k in prefixes:
            left = exploit_prefixes.get(k)
            right = reprobe_prefixes.get(k)
            delta = None
            if (
                left
                and right
                and left["status"] == "completed"
                and right["status"] == "completed"
                and left["capped_cost"] is not None
                and right["capped_cost"] is not None
            ):
                delta = right["capped_cost"] - left["capped_cost"]
            comparisons[str(k)] = {
                "k": k,
                "exploit_status": None if left is None else left["status"],
                "reprobe_status": None if right is None else right["status"],
                "exploit_success": None if left is None else left["all_success"],
                "reprobe_success": None if right is None else right["all_success"],
                "exploit_capped_cost": None if left is None else left["capped_cost"],
                "reprobe_capped_cost": None if right is None else right["capped_cost"],
                "cost_delta_reprobe_minus_exploit": delta,
                "extra_probe_actions": None if right is None else right["extra_probe_actions"],
            }
        rows.append(
            {
                "problem_id": problem_id,
                "layout": sample.get("layout"),
                "physical_rule": sample.get("requested_rule") or sample.get("rule"),
                "permutation": sample.get("permutation"),
                "seed": seed,
                "prefixes": comparisons,
            }
        )
    return rows


def write_reprobe_report(
    summary: dict[str, Any],
    output_dir: Path,
    max_episode_steps: int = 256,
    prefixes: tuple[int, ...] | list[int] | None = None,
) -> dict[str, Any]:
    report = build_reprobe_report(summary, max_episode_steps, prefixes)
    write_json(output_dir / "reprobe_report.json", report)
    return report
