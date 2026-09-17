"""Paired checkpoint report: later-episode prefixes plus shared episode-0 cost."""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from experience_lab.metrics import capped_action_cost
from experience_lab.serialization import write_json

DEFAULT_PREFIXES = (1, 2, 5, 10)
FORK_EXPLOIT = "checkpoint_exploit"
FORK_COMPLETE = "checkpoint_complete_reprobe"
FORK_UL = "checkpoint_ul_stopping"


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def _mean_field(completed: list[dict[str, Any]], key: str) -> float | None:
    return _mean([float(c[key]) for c in completed if c.get(key) is not None])


def _ul_prefix_stats(completed: list[dict[str, Any]]) -> dict[str, Any]:
    with_c = [c for c in completed if c.get("ul_verdict") != "incomplete" and c.get("later_cost_ul_stopping") is not None]
    return {
        "mean_later_ul_stopping": _mean_field(with_c, "later_cost_ul_stopping"),
        "mean_later_delta_ul_minus_exploit": _mean_field(with_c, "later_delta_ul_minus_exploit"),
        "mean_later_delta_ul_minus_complete": _mean_field(with_c, "later_delta_ul_minus_complete"),
        "mean_labeled_probe_actions_ul": _mean_field(with_c, "labeled_probe_actions_ul"),
        "mean_additional_ul_vs_exploit": _mean_field(with_c, "additional_actions_ul_vs_exploit"),
        "mean_lifetime_ul_stopping": _mean_field(with_c, "lifetime_ul_stopping"),
        "mean_later_wall_exploit": _mean_field(completed, "later_wall_exploit"),
        "mean_later_wall_complete_probe": _mean_field(completed, "later_wall_complete_probe"),
        "mean_later_wall_ul_stopping": _mean_field(with_c, "later_wall_ul_stopping"),
        "mean_planning_overhead_expansions_ul": _mean_field(with_c, "planning_overhead_expansions_ul"),
        "ul_all_success_rate": None
        if not with_c
        else sum(1 for c in with_c if c.get("ul_all_success")) / len(with_c),
        "n_ul_helps": sum(1 for c in with_c if c.get("ul_verdict") == "ul_helps"),
        "n_ul_wastes": sum(1 for c in with_c if c.get("ul_verdict") == "ul_wastes"),
        "n_ul_equal": sum(1 for c in with_c if c.get("ul_verdict") == "equal"),
        "n_ul_completed": len(with_c),
        "n_certified_no_headroom": sum(int(c.get("n_certified_no_headroom") or 0) for c in with_c),
        "n_shorter_plan_witness": sum(int(c.get("n_shorter_plan_witness") or 0) for c in with_c),
        "n_undecided": sum(int(c.get("n_undecided") or 0) for c in with_c),
        "unresolved_search_count": sum(int(c.get("unresolved_search_count") or 0) for c in with_c),
    }


def later_prefix_summary(
    later_episodes: list[dict[str, Any]],
    fork_status: str,
    prefixes: tuple[int, ...],
    max_episode_steps: int,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for k in prefixes:
        chunk = later_episodes[:k]
        complete = (
            fork_status == "completed"
            and len(chunk) == k
            and all(ep.get("status") == "completed" for ep in chunk)
        )
        all_success = complete and all(ep.get("success") for ep in chunk)
        if complete:
            capped = sum(
                capped_action_cost(bool(ep.get("success")), int(ep["steps"]), max_episode_steps)
                for ep in chunk
            )
        else:
            capped = None
        labeled_probe = sum(int(ep.get("extra_probe_actions") or 0) for ep in chunk)
        probe_steps = sum(int(ep.get("probe_steps") or 0) for ep in chunk)
        wall = (
            sum(float(ep.get("wall_seconds") or 0) for ep in chunk) if complete else None
        )
        planning_overhead = sum(
            int((ep.get("stopping_log") or {}).get("planning_expansions") or 0)
            for ep in chunk
        )
        ul_decisions = [
            (ep.get("stopping_log") or {}).get("decision")
            for ep in chunk
            if (ep.get("stopping_log") or {}).get("decision")
        ]
        first_stop = (chunk[0].get("stopping_log") or {}) if chunk else {}
        certificates = [
            (ep.get("stopping_log") or {}).get("certificate")
            for ep in chunk
            if (ep.get("stopping_log") or {}).get("certificate")
        ]
        unresolved = sum(
            int((ep.get("stopping_log") or {}).get("unresolved_search_count") or 0)
            for ep in chunk
        )
        rows.append(
            {
                "k": k,
                "status": "completed" if complete else "incomplete",
                "all_success": all_success,
                "n_episodes_present": len(chunk),
                "capped_cost": capped,
                "labeled_probe_actions": labeled_probe,
                "probe_steps": probe_steps,
                "wall_seconds": wall,
                "planning_overhead_expansions": planning_overhead,
                "ul_optional_probe_episodes": sum(
                    1 for decision in ul_decisions if decision == "optional_probe"
                ),
                "ul_exploit_episodes": sum(
                    1 for decision in ul_decisions if decision == "exploit"
                ),
                "n_certified_no_headroom": sum(
                    1 for cert in certificates if cert == "certified_no_headroom"
                ),
                "n_shorter_plan_witness": sum(
                    1 for cert in certificates if cert == "shorter_plan_witness"
                ),
                "n_undecided": sum(1 for cert in certificates if cert == "undecided"),
                "unresolved_search_count": unresolved,
                "first_U": first_stop.get("U"),
                "first_L": first_stop.get("L"),
                "first_L_status": first_stop.get("L_status"),
                "first_decision": first_stop.get("decision"),
                "first_certificate": first_stop.get("certificate"),
            }
        )
    return rows


def _fork_prefixes(pair: dict[str, Any], prefixes: tuple[int, ...], max_episode_steps: int) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for name, fork in (pair.get("forks") or {}).items():
        out[name] = later_prefix_summary(
            list(fork.get("episodes") or []),
            str(fork.get("status") or pair.get("status") or ""),
            prefixes,
            max_episode_steps,
        )
    return out


def _delta_verdict(delta: float | None, help_name: str, waste_name: str) -> str:
    if delta is None:
        return "incomplete"
    if delta < -1e-9:
        return help_name
    if delta > 1e-9:
        return waste_name
    return "equal"


def _completed_cost(prefix_row: dict[str, Any] | None) -> int | None:
    if prefix_row is None or prefix_row.get("status") != "completed":
        return None
    cost = prefix_row.get("capped_cost")
    return None if cost is None else int(cost)


def _comparison_rows(
    fork_prefixes: dict[str, list[dict[str, Any]]],
    episode0_cost: int | None,
) -> dict[str, Any]:
    exploit_rows = fork_prefixes.get(FORK_EXPLOIT, [])
    complete_rows = fork_prefixes.get(FORK_COMPLETE, [])
    ul_rows = fork_prefixes.get(FORK_UL, [])
    exploit_by_k = {row["k"]: row for row in exploit_rows}
    complete_by_k = {row["k"]: row for row in complete_rows}
    ul_by_k = {row["k"]: row for row in ul_rows}
    ks = sorted({row["k"] for row in exploit_rows + complete_rows + ul_rows})
    out: dict[str, Any] = {}
    for k in ks:
        left = exploit_by_k.get(k)
        complete_row = complete_by_k.get(k)
        ul_row = ul_by_k.get(k)
        later_a = _completed_cost(left)
        later_b = _completed_cost(complete_row)
        later_c = _completed_cost(ul_row)
        later_delta_ba = None if later_a is None or later_b is None else later_b - later_a
        later_delta_ca = None if later_a is None or later_c is None else later_c - later_a
        later_delta_cb = None if later_b is None or later_c is None else later_c - later_b
        lifetime_a = None if episode0_cost is None or later_a is None else episode0_cost + later_a
        lifetime_b = None if episode0_cost is None or later_b is None else episode0_cost + later_b
        lifetime_c = None if episode0_cost is None or later_c is None else episode0_cost + later_c
        recovered = None
        if later_delta_ba is not None and k > 1:
            first_b = complete_by_k.get(1)
            first_a = exploit_by_k.get(1)
            first_b_cost = _completed_cost(first_b)
            first_a_cost = _completed_cost(first_a)
            if first_b_cost is not None and first_a_cost is not None:
                early = first_b_cost - first_a_cost
                recovered = later_delta_ba < early and later_delta_ba <= 0
        out[str(k)] = {
            "k": k,
            "later_cost_exploit": later_a,
            "later_cost_complete_probe": later_b,
            "later_cost_ul_stopping": later_c,
            "later_delta_complete_minus_exploit": later_delta_ba,
            "later_delta_ul_minus_exploit": later_delta_ca,
            "later_delta_ul_minus_complete": later_delta_cb,
            "labeled_probe_actions": None if complete_row is None else complete_row.get("labeled_probe_actions"),
            "labeled_probe_actions_ul": None if ul_row is None else ul_row.get("labeled_probe_actions"),
            "additional_actions_vs_exploit": later_delta_ba,
            "additional_actions_ul_vs_exploit": later_delta_ca,
            "episode0_cost": episode0_cost,
            "lifetime_exploit": lifetime_a,
            "lifetime_complete_probe": lifetime_b,
            "lifetime_ul_stopping": lifetime_c,
            "later_wall_exploit": None if left is None else left.get("wall_seconds"),
            "later_wall_complete_probe": None if complete_row is None else complete_row.get("wall_seconds"),
            "later_wall_ul_stopping": None if ul_row is None else ul_row.get("wall_seconds"),
            "planning_overhead_expansions_ul": None
            if ul_row is None
            else ul_row.get("planning_overhead_expansions"),
            "ul_optional_probe_episodes": None
            if ul_row is None
            else ul_row.get("ul_optional_probe_episodes"),
            "first_U": None if ul_row is None else ul_row.get("first_U"),
            "first_L": None if ul_row is None else ul_row.get("first_L"),
            "first_L_status": None if ul_row is None else ul_row.get("first_L_status"),
            "first_decision": None if ul_row is None else ul_row.get("first_decision"),
            "first_certificate": None if ul_row is None else ul_row.get("first_certificate"),
            "n_certified_no_headroom": None if ul_row is None else ul_row.get("n_certified_no_headroom"),
            "n_shorter_plan_witness": None if ul_row is None else ul_row.get("n_shorter_plan_witness"),
            "n_undecided": None if ul_row is None else ul_row.get("n_undecided"),
            "unresolved_search_count": None if ul_row is None else ul_row.get("unresolved_search_count"),
            "exploit_all_success": None if left is None else left.get("all_success"),
            "complete_all_success": None if complete_row is None else complete_row.get("all_success"),
            "ul_all_success": None if ul_row is None else ul_row.get("all_success"),
            "verdict": _delta_verdict(later_delta_ba, "complete_probe_helps", "complete_probe_wastes"),
            "ul_verdict": _delta_verdict(later_delta_ca, "ul_helps", "ul_wastes"),
            "extra_cost_recovered_by_this_prefix": recovered,
        }
    return out


def build_bucket_assignments(summary: dict[str, Any]) -> dict[str, Any]:
    """Evaluator-only acquisition buckets. Not an agent input.

    `acquisition_bucket` compares episode-0 cost to the oracle episode-0 cost.
    `current_exploit_plan_cost_U` is the conservative plan length at the first
    later episode, which can differ from acquisition cost.
    """
    rows: list[dict[str, Any]] = []
    for pair in summary.get("pairs") or []:
        fork_c = (pair.get("forks") or {}).get(FORK_UL) or {}
        c_eps = list(fork_c.get("episodes") or [])
        first_stop = (c_eps[0].get("stopping_log") or {}) if c_eps else {}
        fork_a = (pair.get("forks") or {}).get(FORK_EXPLOIT) or {}
        a_eps = list(fork_a.get("episodes") or [])
        first_a = a_eps[0] if a_eps else {}
        ep0 = pair.get("episode0_cost")
        oracle = pair.get("oracle_episode0_cost")
        U = first_stop.get("U")
        rows.append(
            {
                "checkpoint_id": pair.get("checkpoint_id"),
                "layout": pair.get("layout"),
                "requested_rule": pair.get("requested_rule") or pair.get("rule"),
                "permutation": pair.get("permutation"),
                "seed": pair.get("seed"),
                "source_method": pair.get("source_method"),
                "acquisition_bucket": pair.get("starting_condition"),
                "bucket_basis": "episode0_acquisition_cost_versus_oracle_episode0",
                "episode0_cost": ep0,
                "oracle_episode0_cost": oracle,
                "acquisition_excess": None
                if ep0 is None or oracle is None
                else int(ep0) - int(oracle),
                "current_exploit_plan_cost_U": U,
                "first_later_exploit_steps": first_a.get("steps"),
                "U_minus_oracle": None if U is None or oracle is None else int(U) - int(oracle),
                "first_certificate": first_stop.get("certificate"),
                "first_L": first_stop.get("L"),
                "unresolved_search_count": first_stop.get("unresolved_search_count"),
                "status": pair.get("status"),
            }
        )
    return {
        "note": (
            "acquisition_bucket labels refer to episode-0 cost versus the oracle "
            "episode-0 cost. They are not current exploit-plan cost U and are "
            "not passed into learner decisions."
        ),
        "n_pairs": len(rows),
        "assignments": rows,
    }


def build_geometry_unit_summary(
    instance_rows: list[dict[str, Any]],
    k: int = 10,
) -> dict[str, Any]:
    """Treat each layout/geometry seed as one sampling unit."""
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in instance_rows:
        grouped[str(row.get("layout") or "")].append(row)
    units: list[dict[str, Any]] = []
    for layout, rows in sorted(grouped.items()):
        completed = [
            r["prefixes"][str(k)]
            for r in rows
            if str(k) in (r.get("prefixes") or {})
            and r["prefixes"][str(k)].get("verdict") != "incomplete"
            and r["prefixes"][str(k)].get("later_cost_ul_stopping") is not None
            and r["prefixes"][str(k)].get("later_cost_exploit") is not None
        ]
        incomplete_n = len(rows) - len(completed)
        mean_a = _mean_field(completed, "later_cost_exploit")
        mean_b = _mean_field(completed, "later_cost_complete_probe")
        mean_c = _mean_field(completed, "later_cost_ul_stopping")
        delta_ca = None if mean_a is None or mean_c is None else mean_c - mean_a
        delta_cb = None if mean_b is None or mean_c is None else mean_c - mean_b
        delta_ba = None if mean_a is None or mean_b is None else mean_b - mean_a
        units.append(
            {
                "layout": layout,
                "k": k,
                "n_paired_cells": len(rows),
                "n_completed_cells": len(completed),
                "n_incomplete_cells": incomplete_n,
                "mean_later_exploit": mean_a,
                "mean_later_complete_probe": mean_b,
                "mean_later_ul_stopping": mean_c,
                "mean_delta_c_minus_a": delta_ca,
                "mean_delta_c_minus_b": delta_cb,
                "mean_delta_b_minus_a": delta_ba,
                "c_vs_a": _delta_verdict(delta_ca, "c_wins", "c_loses"),
                "c_vs_b": _delta_verdict(delta_cb, "c_wins", "c_loses"),
                "success_rate_a": None
                if not completed
                else sum(1 for c in completed if c.get("exploit_all_success")) / len(completed),
                "success_rate_b": None
                if not completed
                else sum(1 for c in completed if c.get("complete_all_success")) / len(completed),
                "success_rate_c": None
                if not completed
                else sum(1 for c in completed if c.get("ul_all_success")) / len(completed),
                "planning_overhead_expansions_ul": _mean_field(completed, "planning_overhead_expansions_ul"),
                "n_undecided": sum(int(c.get("n_undecided") or 0) for c in completed),
                "n_certified_no_headroom": sum(int(c.get("n_certified_no_headroom") or 0) for c in completed),
                "n_shorter_plan_witness": sum(int(c.get("n_shorter_plan_witness") or 0) for c in completed),
                "unresolved_search_count": sum(int(c.get("unresolved_search_count") or 0) for c in completed),
            }
        )
    decided = [u for u in units if u["c_vs_a"] != "incomplete"]
    return {
        "sampling_unit": "geometry_layout",
        "k": k,
        "n_units": len(units),
        "n_units_completed": len(decided),
        "c_vs_a_wins": sum(1 for u in decided if u["c_vs_a"] == "c_wins"),
        "c_vs_a_ties": sum(1 for u in decided if u["c_vs_a"] == "equal"),
        "c_vs_a_losses": sum(1 for u in decided if u["c_vs_a"] == "c_loses"),
        "c_vs_b_wins": sum(1 for u in decided if u["c_vs_b"] == "c_wins"),
        "c_vs_b_ties": sum(1 for u in decided if u["c_vs_b"] == "equal"),
        "c_vs_b_losses": sum(1 for u in decided if u["c_vs_b"] == "c_loses"),
        "mean_of_map_means_a": _mean_field(decided, "mean_later_exploit"),
        "mean_of_map_means_b": _mean_field(decided, "mean_later_complete_probe"),
        "mean_of_map_means_c": _mean_field(decided, "mean_later_ul_stopping"),
        "units": units,
        "note": (
            "Each layout is one sampling unit. Rules, ID permutations, and "
            "acquisition methods are paired conditions inside the unit."
        ),
    }


def build_checkpoint_report(
    summary: dict[str, Any],
    max_episode_steps: int = 256,
    prefixes: tuple[int, ...] | list[int] | None = None,
) -> dict[str, Any]:
    prefixes = tuple(prefixes or DEFAULT_PREFIXES)
    pairs = list(summary.get("pairs") or [])
    instance_rows: list[dict[str, Any]] = []
    grouped: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        fork_prefixes = _fork_prefixes(pair, prefixes, max_episode_steps)
        ep0 = pair.get("episode0_cost")
        if ep0 is None and pair.get("episode0"):
            ep0_rec = pair["episode0"]
            if ep0_rec.get("status") == "completed":
                ep0 = capped_action_cost(
                    bool(ep0_rec.get("success")), int(ep0_rec["steps"]), max_episode_steps
                )
        comparisons = _comparison_rows(
            fork_prefixes,
            int(ep0) if ep0 is not None else None,
        )
        row = {
            "checkpoint_id": pair.get("checkpoint_id"),
            "layout": pair.get("layout"),
            "physical_rule": pair.get("requested_rule") or pair.get("rule"),
            "permutation": pair.get("permutation"),
            "seed": pair.get("seed"),
            "source_method": pair.get("source_method"),
            "starting_condition": pair.get("starting_condition"),
            "bucket_basis": "episode0_acquisition_cost_versus_oracle_episode0",
            "status": pair.get("status"),
            "episode0_cost": ep0,
            "oracle_episode0_cost": pair.get("oracle_episode0_cost"),
            "prefixes": comparisons,
            "fork_prefixes": fork_prefixes,
        }
        instance_rows.append(row)
        grouped[
            (
                str(row["layout"] or ""),
                str(row["physical_rule"] or ""),
                str(row["starting_condition"] or ""),
            )
        ].append(row)

    by_condition: list[dict[str, Any]] = []
    for layout, rule, condition in sorted(grouped):
        rows = grouped[(layout, rule, condition)]
        prefix_stats = []
        for k in prefixes:
            completed = [
                row["prefixes"][str(k)]
                for row in rows
                if str(k) in (row.get("prefixes") or {})
                and row["prefixes"][str(k)]["verdict"] != "incomplete"
            ]
            incomplete_n = len(rows) - len(completed)
            prefix_stats.append(
                {
                    "k": k,
                    "n_pairs": len(rows),
                    "n_completed": len(completed),
                    "n_incomplete": incomplete_n,
                    "mean_later_exploit": _mean(
                        [float(c["later_cost_exploit"]) for c in completed if c["later_cost_exploit"] is not None]
                    ),
                    "mean_later_complete_probe": _mean(
                        [
                            float(c["later_cost_complete_probe"])
                            for c in completed
                            if c["later_cost_complete_probe"] is not None
                        ]
                    ),
                    "mean_later_delta": _mean(
                        [
                            float(c["later_delta_complete_minus_exploit"])
                            for c in completed
                            if c["later_delta_complete_minus_exploit"] is not None
                        ]
                    ),
                    "mean_labeled_probe_actions": _mean(
                        [
                            float(c["labeled_probe_actions"])
                            for c in completed
                            if c["labeled_probe_actions"] is not None
                        ]
                    ),
                    "mean_additional_vs_exploit": _mean(
                        [
                            float(c["additional_actions_vs_exploit"])
                            for c in completed
                            if c["additional_actions_vs_exploit"] is not None
                        ]
                    ),
                    "mean_episode0_cost": _mean(
                        [float(c["episode0_cost"]) for c in completed if c["episode0_cost"] is not None]
                    ),
                    "mean_lifetime_exploit": _mean(
                        [float(c["lifetime_exploit"]) for c in completed if c["lifetime_exploit"] is not None]
                    ),
                    "mean_lifetime_complete_probe": _mean(
                        [
                            float(c["lifetime_complete_probe"])
                            for c in completed
                            if c["lifetime_complete_probe"] is not None
                        ]
                    ),
                    "exploit_all_success_rate": None
                    if not completed
                    else sum(1 for c in completed if c["exploit_all_success"]) / len(completed),
                    "complete_all_success_rate": None
                    if not completed
                    else sum(1 for c in completed if c["complete_all_success"]) / len(completed),
                    "n_helps": sum(1 for c in completed if c["verdict"] == "complete_probe_helps"),
                    "n_wastes": sum(1 for c in completed if c["verdict"] == "complete_probe_wastes"),
                    "n_equal": sum(1 for c in completed if c["verdict"] == "equal"),
                    **_ul_prefix_stats(completed),
                }
            )
        by_condition.append(
            {
                "layout": layout,
                "physical_rule": rule,
                "starting_condition": condition,
                "n_pairs": len(rows),
                "prefixes": prefix_stats,
            }
        )

    by_condition_pooled: dict[str, Any] = {}
    for condition in sorted({row["starting_condition"] for row in instance_rows}):
        cond_rows = [row for row in instance_rows if row["starting_condition"] == condition]
        stats = []
        for k in prefixes:
            completed = [
                row["prefixes"][str(k)]
                for row in cond_rows
                if str(k) in (row.get("prefixes") or {})
                and row["prefixes"][str(k)]["verdict"] != "incomplete"
            ]
            stats.append(
                {
                    "k": k,
                    "n_pairs": len(cond_rows),
                    "n_completed": len(completed),
                    "mean_later_delta": _mean(
                        [
                            float(c["later_delta_complete_minus_exploit"])
                            for c in completed
                            if c["later_delta_complete_minus_exploit"] is not None
                        ]
                    ),
                    "mean_labeled_probe_actions": _mean(
                        [
                            float(c["labeled_probe_actions"])
                            for c in completed
                            if c["labeled_probe_actions"] is not None
                        ]
                    ),
                    "mean_additional_vs_exploit": _mean(
                        [
                            float(c["additional_actions_vs_exploit"])
                            for c in completed
                            if c["additional_actions_vs_exploit"] is not None
                        ]
                    ),
                    "n_helps": sum(1 for c in completed if c["verdict"] == "complete_probe_helps"),
                    "n_wastes": sum(1 for c in completed if c["verdict"] == "complete_probe_wastes"),
                    "n_equal": sum(1 for c in completed if c["verdict"] == "equal"),
                    "exploit_all_success_rate": None
                    if not completed
                    else sum(1 for c in completed if c["exploit_all_success"]) / len(completed),
                    "complete_all_success_rate": None
                    if not completed
                    else sum(1 for c in completed if c["complete_all_success"]) / len(completed),
                    **_ul_prefix_stats(completed),
                }
            )
        by_condition_pooled[condition] = {"n_pairs": len(cond_rows), "prefixes": stats}

    geometry = build_geometry_unit_summary(instance_rows, k=10 if 10 in prefixes else prefixes[-1])
    bucket_assignments = build_bucket_assignments(summary)
    return {
        "prefixes": list(prefixes),
        "by_layout_rule_and_starting_condition": by_condition,
        "by_starting_condition": by_condition_pooled,
        "by_checkpoint": instance_rows,
        "by_geometry_unit": geometry,
        "bucket_assignment_summary": {
            "note": bucket_assignments["note"],
            "n_pairs": bucket_assignments["n_pairs"],
        },
        "note": (
            "Later prefixes exclude episode 0. Lifetime = shared episode-0 acquisition "
            "plus later prefix. labeled_probe_actions are steps marked as the extra "
            "probe; additional_actions_vs_exploit is B's extra episode cost versus A. "
            "C is a hand-designed U vs L stopping rule, not a learned policy. "
            "starting_condition is an acquisition-cost bucket versus oracle episode 0, "
            "not current exploit-plan cost U. Incomplete prefixes are not converted "
            "into low costs. C is not required to win."
        ),
    }


def write_checkpoint_report(
    summary: dict[str, Any],
    output_dir: Path,
    max_episode_steps: int = 256,
    prefixes: tuple[int, ...] | list[int] | None = None,
) -> dict[str, Any]:
    report = build_checkpoint_report(summary, max_episode_steps, prefixes)
    write_json(output_dir / "checkpoint_report.json", report)
    write_json(output_dir / "bucket_assignments.json", build_bucket_assignments(summary))
    return report
