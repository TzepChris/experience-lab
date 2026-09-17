"""Build v0.1 tables and figures from saved checkpoint summaries.

Does not rerun learners or change A/B/C. Bootstrap resamples whole maps.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experience_lab import __version__
from experience_lab.checkpoint_report import FORK_COMPLETE, FORK_EXPLOIT, FORK_UL
from experience_lab.metrics import capped_action_cost
from experience_lab.serialization import write_json

HOLDOUT_K = 10
BOOTSTRAP_SEED = 20260918
BOOTSTRAP_REPLICATES = 10_000
XOR_CHECKPOINT_ID = "probe_spur|x0_xor_x1|perm1,0|seed1|systematic_retained"


def load_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def later_prefix_cost(episodes: list[dict[str, Any]], k: int, max_steps: int) -> int | None:
    chunk = episodes[:k]
    if len(chunk) != k:
        return None
    if any(ep.get("status") != "completed" for ep in chunk):
        return None
    if not all(ep.get("success") for ep in chunk):
        return sum(
            capped_action_cost(bool(ep.get("success")), int(ep["steps"]), max_steps)
            for ep in chunk
        )
    return sum(int(ep["steps"]) for ep in chunk)


def later_all_success(episodes: list[dict[str, Any]], k: int) -> bool:
    chunk = episodes[:k]
    return (
        len(chunk) == k
        and all(ep.get("status") == "completed" for ep in chunk)
        and all(ep.get("success") for ep in chunk)
    )


def reconstruct_certificate(stop: dict[str, Any]) -> str | None:
    if stop.get("certificate"):
        return str(stop["certificate"])
    U = stop.get("U")
    L = stop.get("L")
    hyps = stop.get("hypotheses") or []
    unresolved = any(row.get("status") in ("planner_cap", "time_limit") for row in hyps)
    if stop.get("decision") is None and U is None:
        return None
    if U is None:
        return "not_applicable"
    if L is not None and U is not None and L < U:
        return "shorter_plan_witness"
    if unresolved or stop.get("any_undecided") or stop.get("L_status") == "undecided":
        return "undecided"
    if L is not None and L == U:
        return "certified_no_headroom"
    return "undecided"


def pair_cells(summary: dict[str, Any], k: int = HOLDOUT_K, max_steps: int = 256) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for pair in summary.get("pairs") or []:
        forks = pair.get("forks") or {}
        costs: dict[str, int | None] = {}
        success: dict[str, bool] = {}
        for fork_name in (FORK_EXPLOIT, FORK_COMPLETE, FORK_UL):
            episodes = list((forks.get(fork_name) or {}).get("episodes") or [])
            costs[fork_name] = later_prefix_cost(episodes, k, max_steps)
            success[fork_name] = later_all_success(episodes, k)
        c_eps = list((forks.get(FORK_UL) or {}).get("episodes") or [])
        certs = Counter()
        unresolved = 0
        overhead = 0
        for ep in c_eps[:k]:
            stop = ep.get("stopping_log") or {}
            cert = reconstruct_certificate(stop)
            if cert:
                certs[cert] += 1
            if stop.get("unresolved_search_count") is not None:
                unresolved += int(stop["unresolved_search_count"])
            else:
                hyps = stop.get("hypotheses") or []
                unresolved += sum(
                    1 for row in hyps if row.get("status") in ("planner_cap", "time_limit")
                )
            overhead += int(stop.get("planning_expansions") or 0)
        a = costs[FORK_EXPLOIT]
        b = costs[FORK_COMPLETE]
        c = costs[FORK_UL]
        ep0 = pair.get("episode0_cost")
        complete = (
            pair.get("status") == "completed"
            and a is not None
            and b is not None
            and c is not None
        )
        rows.append(
            {
                "checkpoint_id": pair.get("checkpoint_id"),
                "layout": pair.get("layout"),
                "requested_rule": pair.get("requested_rule") or pair.get("rule"),
                "permutation": tuple(pair.get("permutation") or []),
                "source_method": pair.get("source_method"),
                "acquisition_bucket": pair.get("starting_condition"),
                "status": pair.get("status"),
                "complete": complete,
                "episode0_cost": ep0,
                "oracle_episode0_cost": pair.get("oracle_episode0_cost"),
                "later_a": a,
                "later_b": b,
                "later_c": c,
                "lifetime_a": None if ep0 is None or a is None else int(ep0) + a,
                "lifetime_b": None if ep0 is None or b is None else int(ep0) + b,
                "lifetime_c": None if ep0 is None or c is None else int(ep0) + c,
                "success_a": success[FORK_EXPLOIT],
                "success_b": success[FORK_COMPLETE],
                "success_c": success[FORK_UL],
                "delta_c_minus_a": None if a is None or c is None else c - a,
                "delta_c_minus_b": None if b is None or c is None else c - b,
                "delta_b_minus_a": None if a is None or b is None else b - a,
                "certificates": dict(certs),
                "unresolved_search_count": unresolved,
                "planning_overhead_expansions": overhead,
            }
        )
    return rows


def _outcome(delta: float | None) -> str:
    if delta is None:
        return "incomplete"
    if delta < -1e-9:
        return "helps"
    if delta > 1e-9:
        return "wastes"
    return "equal"


def map_units(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for cell in cells:
        grouped[str(cell.get("layout") or "")].append(cell)
    units: list[dict[str, Any]] = []
    for layout, rows in sorted(grouped.items()):
        complete = [row for row in rows if row["complete"]]
        n = len(complete)
        mean_a = sum(row["later_a"] for row in complete) / n if n else None
        mean_b = sum(row["later_b"] for row in complete) / n if n else None
        mean_c = sum(row["later_c"] for row in complete) / n if n else None
        mean_life_a = sum(row["lifetime_a"] for row in complete) / n if n else None
        mean_life_b = sum(row["lifetime_b"] for row in complete) / n if n else None
        mean_life_c = sum(row["lifetime_c"] for row in complete) / n if n else None
        units.append(
            {
                "layout": layout,
                "n_cells": len(rows),
                "n_complete": n,
                "n_incomplete": len(rows) - n,
                "mean_later_a": mean_a,
                "mean_later_b": mean_b,
                "mean_later_c": mean_c,
                "mean_lifetime_a": mean_life_a,
                "mean_lifetime_b": mean_life_b,
                "mean_lifetime_c": mean_life_c,
                "mean_delta_c_minus_a": None if mean_a is None or mean_c is None else mean_c - mean_a,
                "mean_delta_c_minus_b": None if mean_b is None or mean_c is None else mean_c - mean_b,
                "success_a": all(row["success_a"] for row in complete) if complete else False,
                "success_b": all(row["success_b"] for row in complete) if complete else False,
                "success_c": all(row["success_c"] for row in complete) if complete else False,
                "c_vs_a": _outcome(None if mean_a is None or mean_c is None else mean_c - mean_a),
                "c_vs_b": _outcome(None if mean_b is None or mean_c is None else mean_c - mean_b),
                "planning_overhead_expansions": (
                    sum(row["planning_overhead_expansions"] for row in complete) / n if n else None
                ),
                "unresolved_search_count": sum(row["unresolved_search_count"] for row in complete),
            }
        )
    return units


def paired_map_bootstrap(
    units: list[dict[str, Any]],
    *,
    replicates: int = BOOTSTRAP_REPLICATES,
    seed: int = BOOTSTRAP_SEED,
) -> dict[str, Any]:
    """Resample maps with replacement; keep all paired cells inside each map."""
    complete = [u for u in units if u["n_complete"] and u["mean_later_a"] is not None]
    n = len(complete)
    if n == 0:
        return {"n_maps": 0, "replicates": replicates, "seed": seed, "intervals": {}}
    a = np.array([float(u["mean_later_a"]) for u in complete], dtype=float)
    b = np.array([float(u["mean_later_b"]) for u in complete], dtype=float)
    c = np.array([float(u["mean_later_c"]) for u in complete], dtype=float)
    life_a = np.array([float(u["mean_lifetime_a"]) for u in complete], dtype=float)
    life_b = np.array([float(u["mean_lifetime_b"]) for u in complete], dtype=float)
    life_c = np.array([float(u["mean_lifetime_c"]) for u in complete], dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, n, size=(replicates, n))
    delta_ca = c - a
    delta_cb = c - b
    delta_ba = b - a
    stats = {
        "mean_later_a": a[draws].mean(axis=1),
        "mean_later_b": b[draws].mean(axis=1),
        "mean_later_c": c[draws].mean(axis=1),
        "mean_lifetime_a": life_a[draws].mean(axis=1),
        "mean_lifetime_b": life_b[draws].mean(axis=1),
        "mean_lifetime_c": life_c[draws].mean(axis=1),
        "mean_delta_c_minus_a": delta_ca[draws].mean(axis=1),
        "mean_delta_c_minus_b": delta_cb[draws].mean(axis=1),
        "mean_delta_b_minus_a": delta_ba[draws].mean(axis=1),
        "map_win_rate_c_vs_a": (c[draws] < a[draws] - 1e-9).mean(axis=1),
        "map_win_rate_c_vs_b": (c[draws] < b[draws] - 1e-9).mean(axis=1),
    }
    points = {
        "mean_later_a": float(a.mean()),
        "mean_later_b": float(b.mean()),
        "mean_later_c": float(c.mean()),
        "mean_lifetime_a": float(life_a.mean()),
        "mean_lifetime_b": float(life_b.mean()),
        "mean_lifetime_c": float(life_c.mean()),
        "mean_delta_c_minus_a": float(delta_ca.mean()),
        "mean_delta_c_minus_b": float(delta_cb.mean()),
        "mean_delta_b_minus_a": float(delta_ba.mean()),
        "map_win_rate_c_vs_a": float((c < a - 1e-9).mean()),
        "map_win_rate_c_vs_b": float((c < b - 1e-9).mean()),
    }
    intervals = {}
    for name, series in stats.items():
        lo, hi = np.quantile(series, [0.025, 0.975])
        intervals[name] = {
            "point": points[name],
            "ci95_low": float(lo),
            "ci95_high": float(hi),
        }
    return {
        "n_maps": n,
        "replicates": replicates,
        "seed": seed,
        "method": "percentile interval from paired bootstrap over maps",
        "assumption": (
            "Maps are treated as i.i.d. draws from this generator. All 20 paired "
            "conditions stay with the map. The interval is uncertainty within the "
            "generator, not over other map families, switch counts, or rule families."
        ),
        "intervals": intervals,
    }


def cell_outcome_counts(cells: list[dict[str, Any]]) -> dict[str, Any]:
    complete = [row for row in cells if row["complete"]]
    vs_a = Counter(_outcome(row["delta_c_minus_a"]) for row in complete)
    vs_b = Counter(_outcome(row["delta_c_minus_b"]) for row in complete)
    by_source: dict[str, dict[str, Any]] = {}
    for source in sorted({str(row["source_method"]) for row in complete}):
        subset = [row for row in complete if row["source_method"] == source]
        deltas = [row["delta_c_minus_a"] for row in subset]
        by_source[source] = {
            "n": len(subset),
            "mean_delta_c_minus_a": sum(deltas) / len(deltas),
            "helps": sum(1 for row in subset if _outcome(row["delta_c_minus_a"]) == "helps"),
            "equal": sum(1 for row in subset if _outcome(row["delta_c_minus_a"]) == "equal"),
            "wastes": sum(1 for row in subset if _outcome(row["delta_c_minus_a"]) == "wastes"),
        }
    by_bucket: dict[str, dict[str, Any]] = {}
    for bucket in sorted({str(row["acquisition_bucket"] or "") for row in complete}):
        subset = [row for row in complete if str(row["acquisition_bucket"] or "") == bucket]
        by_bucket[bucket] = {
            "n": len(subset),
            "mean_delta_b_minus_a": sum(row["delta_b_minus_a"] for row in subset) / len(subset),
            "mean_delta_c_minus_a": sum(row["delta_c_minus_a"] for row in subset) / len(subset),
            "helps": sum(1 for row in subset if _outcome(row["delta_c_minus_a"]) == "helps"),
            "equal": sum(1 for row in subset if _outcome(row["delta_c_minus_a"]) == "equal"),
            "wastes": sum(1 for row in subset if _outcome(row["delta_c_minus_a"]) == "wastes"),
        }
    certs = Counter()
    unresolved = 0
    overhead = 0
    for row in complete:
        for name, count in (row["certificates"] or {}).items():
            certs[name] += int(count)
        unresolved += int(row["unresolved_search_count"])
        overhead += int(row["planning_overhead_expansions"])
    for name in ("certified_no_headroom", "shorter_plan_witness", "undecided"):
        certs.setdefault(name, 0)
    return {
        "n_complete": len(complete),
        "n_incomplete": sum(1 for row in cells if not row["complete"]),
        "success_a": sum(1 for row in complete if row["success_a"]) / len(complete) if complete else None,
        "success_b": sum(1 for row in complete if row["success_b"]) / len(complete) if complete else None,
        "success_c": sum(1 for row in complete if row["success_c"]) / len(complete) if complete else None,
        "c_vs_a": dict(vs_a),
        "c_vs_b": dict(vs_b),
        "by_source": by_source,
        "by_acquisition_bucket": by_bucket,
        "certificates": dict(certs),
        "unresolved_search_count": unresolved,
        "mean_planning_overhead_expansions": overhead / len(complete) if complete else None,
        "mean_later_a": sum(row["later_a"] for row in complete) / len(complete) if complete else None,
        "mean_later_b": sum(row["later_b"] for row in complete) / len(complete) if complete else None,
        "mean_later_c": sum(row["later_c"] for row in complete) / len(complete) if complete else None,
        "mean_lifetime_a": sum(row["lifetime_a"] for row in complete) / len(complete) if complete else None,
        "mean_lifetime_b": sum(row["lifetime_b"] for row in complete) / len(complete) if complete else None,
        "mean_lifetime_c": sum(row["lifetime_c"] for row in complete) / len(complete) if complete else None,
    }


def extract_xor_trace(summary: dict[str, Any], checkpoint_id: str = XOR_CHECKPOINT_ID) -> dict[str, Any]:
    pair = next((p for p in summary.get("pairs") or [] if p.get("checkpoint_id") == checkpoint_id), None)
    if pair is None:
        raise KeyError(f"XOR checkpoint {checkpoint_id} not in summary")
    forks = pair.get("forks") or {}
    episodes_c = list((forks.get(FORK_UL) or {}).get("episodes") or [])
    episodes_b = list((forks.get(FORK_COMPLETE) or {}).get("episodes") or [])
    episodes_a = list((forks.get(FORK_EXPLOIT) or {}).get("episodes") or [])

    def _ep(ep: dict[str, Any], later_index: int) -> dict[str, Any]:
        stop = ep.get("stopping_log") or {}
        log = ep.get("extra_probe_log") or {}
        return {
            "later_index": later_index,
            "steps": ep.get("steps"),
            "success": ep.get("success"),
            "U": stop.get("U"),
            "L": stop.get("L"),
            "certificate": reconstruct_certificate(stop),
            "decision": stop.get("decision"),
            "planning_expansions": stop.get("planning_expansions"),
            "extra_probe_actions": ep.get("extra_probe_actions"),
            "intended_target": log.get("intended_target"),
            "target_reached": log.get("target_reached"),
            "configs_after_toggles": log.get("configs_after_toggles"),
            "hypotheses_after": log.get("hypotheses_after"),
        }

    later_a = [_ep(ep, i) for i, ep in enumerate(episodes_a[:3])]
    later_b = [_ep(ep, i) for i, ep in enumerate(episodes_b[:3])]
    later_c = [_ep(ep, i) for i, ep in enumerate(episodes_c[:3])]
    return {
        "checkpoint_id": checkpoint_id,
        "starting_condition": pair.get("starting_condition"),
        "episode0_cost": pair.get("episode0_cost"),
        "oracle_episode0_cost": pair.get("oracle_episode0_cost"),
        "belief_after_episode0": pair.get("belief_after_episode0"),
        "later_a": later_a,
        "later_b": later_b,
        "later_c": later_c,
        "k10_later_a": later_prefix_cost(episodes_a, 10, 256),
        "k10_later_b": later_prefix_cost(episodes_b, 10, 256),
        "k10_later_c": later_prefix_cost(episodes_c, 10, 256),
        "why_c_skips_unnecessary_probe": _xor_skip_reason(pair, later_c, later_b),
        "note": (
            "C probes when a remaining complete hypothesis has a shorter plan than "
            "the conservative route, then skips further probes once U equals L."
        ),
    }


def _xor_skip_reason(
    pair: dict[str, Any],
    later_c: list[dict[str, Any]],
    later_b: list[dict[str, Any]],
) -> str:
    belief = pair.get("belief_after_episode0") or {}
    remaining0 = ((belief.get("hypotheses") or {}).get("door0")) or []
    c0 = later_c[0] if later_c else {}
    c1 = later_c[1] if len(later_c) > 1 else {}
    b1 = later_b[1] if len(later_b) > 1 else {}
    after0 = ((c0.get("hypotheses_after") or {}).get("door0")) or []
    return (
        f"After episode 0 cost {pair.get('episode0_cost')} "
        f"(oracle {pair.get('oracle_episode0_cost')}), remaining hypotheses were "
        f"{remaining0}. C later-0 had U={c0.get('U')} and L={c0.get('L')} "
        f"({c0.get('certificate')}), so it ran the completed-target probe to "
        f"config {c0.get('intended_target')} and finished in {c0.get('steps')} "
        f"actions. Remaining hypotheses became {after0}. C later-1 had "
        f"U={c1.get('U')} and L={c1.get('L')} ({c1.get('certificate')}), so it "
        f"exploited with {c1.get('extra_probe_actions')} extra-probe actions. "
        f"B later-1 still probed target {b1.get('intended_target')} "
        f"(OR-vs-XOR distinguisher) and used {b1.get('steps')} actions."
    )


def analyze_holdout(summary: dict[str, Any], manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    cells = pair_cells(summary)
    units = map_units(cells)
    bootstrap = paired_map_bootstrap(units)
    outcomes = cell_outcome_counts(cells)
    expected_cells = 20 * 5 * 2 * 2
    map_vs_a = Counter(u["c_vs_a"] for u in units)
    map_vs_b = Counter(u["c_vs_b"] for u in units)
    return {
        "package_version": __version__,
        "k": HOLDOUT_K,
        "n_pairs_scheduled": summary.get("total_scheduled_pairs"),
        "n_pairs_completed_status": summary.get("completed_pairs"),
        "n_cells": len(cells),
        "expected_cells": expected_cells,
        "n_maps": len(units),
        "cells_per_complete_map": 20,
        "batch_status": summary.get("status"),
        "wall_seconds": summary.get("wall_seconds"),
        "max_wall_seconds": summary.get("max_wall_seconds"),
        "hardware": summary.get("hardware") or (manifest or {}).get("hardware"),
        "dependencies": (manifest or {}).get("dependencies"),
        "git": (manifest or {}).get("git"),
        "config": (manifest or {}).get("config"),
        "maps": units,
        "map_outcomes": {"c_vs_a": dict(map_vs_a), "c_vs_b": dict(map_vs_b)},
        "bootstrap": bootstrap,
        "paired_cells": outcomes,
        "reconcile": {
            "pairs_match_expected": len(cells) == expected_cells,
            "scheduled_match_cells": summary.get("total_scheduled_pairs") == len(cells),
            "completed_status_match": summary.get("completed_pairs") == outcomes["n_complete"],
            "all_pairs_complete": outcomes["n_incomplete"] == 0 and all(u["n_incomplete"] == 0 for u in units),
            "maps_have_20_cells": all(u["n_cells"] == 20 for u in units),
            "success_all_one": outcomes["success_a"] == 1.0
            and outcomes["success_b"] == 1.0
            and outcomes["success_c"] == 1.0,
            "map_mean_equals_cell_mean": (
                abs((outcomes["mean_later_a"] or 0) - (bootstrap["intervals"]["mean_later_a"]["point"])) < 1e-9
            ),
            "paired_cell_c_vs_a_sum": sum((outcomes["c_vs_a"] or {}).values()) == outcomes["n_complete"],
        },
    }


def write_figures(analysis: dict[str, Any], figure_dir: Path) -> list[str]:
    figure_dir.mkdir(parents=True, exist_ok=True)
    maps = analysis["maps"]
    labels = [str(m["layout"]).replace("holdout_", "") for m in maps]
    a = [m["mean_later_a"] for m in maps]
    b = [m["mean_later_b"] for m in maps]
    c = [m["mean_later_c"] for m in maps]
    delta = [m["mean_delta_c_minus_a"] for m in maps]
    x = np.arange(len(labels))
    width = 0.26

    fig, ax = plt.subplots(figsize=(11, 4.2))
    ax.bar(x - width, a, width, label="A exploit", color="#6b7280")
    ax.bar(x, b, width, label="B complete probe", color="#3b82f6")
    ax.bar(x + width, c, width, label="C U vs L stop", color="#059669")
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Geometry seed")
    ax.set_ylabel("Mean later actions (k=10)")
    ax.set_title("Holdout k=10 later action cost by map (mean of 20 paired cells)")
    ax.legend()
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    means_path = figure_dir / "fig1_map_later_cost.png"
    fig.savefig(means_path, dpi=140)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(11, 3.8))
    colors = ["#059669" if v < 0 else "#b45309" for v in delta]
    ax.bar(x, delta, color=colors)
    ax.axhline(0.0, color="#111827", linewidth=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_xlabel("Geometry seed")
    ax.set_ylabel("C minus A later actions")
    ax.set_title("Per-map C−A later-cost difference (negative: C uses fewer actions)")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    delta_path = figure_dir / "fig2_map_delta_c_minus_a.png"
    fig.savefig(delta_path, dpi=140)
    plt.close(fig)

    outcomes = analysis["paired_cells"]["c_vs_a"]
    fig, ax = plt.subplots(figsize=(5.5, 3.6))
    names = ["helps", "equal", "wastes"]
    values = [int(outcomes.get(name, 0)) for name in names]
    ax.bar(names, values, color=["#059669", "#6b7280", "#b45309"])
    ax.set_ylabel("Paired cells (n=400)")
    ax.set_title("C vs A paired-cell outcomes at k=10")
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    for i, val in enumerate(values):
        ax.text(i, val + 4, str(val), ha="center", va="bottom")
    fig.tight_layout()
    cells_path = figure_dir / "fig3_paired_cell_outcomes.png"
    fig.savefig(cells_path, dpi=140)
    plt.close(fig)
    return [means_path.name, delta_path.name, cells_path.name]


def _fmt(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "NA"
    return f"{value:.{digits}f}"


def write_tables_markdown(analysis: dict[str, Any], xor_trace: dict[str, Any], path: Path) -> None:
    boot = analysis["bootstrap"]["intervals"]
    cells = analysis["paired_cells"]
    rec = analysis["reconcile"]
    map_out = analysis["map_outcomes"]
    vs_a = cells["c_vs_a"]
    vs_b = cells["c_vs_b"]
    certs = cells["certificates"]
    assumption = analysis["bootstrap"]["assumption"]
    lines = [
        "# v0.1 generated tables",
        "",
        "Generated from saved `summary.json` files. Do not edit by hand.",
        "A/B/C were not modified to produce these numbers.",
        "",
        "## Reconciliation",
        "",
        f"Scheduled pairs {analysis['n_pairs_scheduled']}; parsed cells {analysis['n_cells']};",
        f"expected 400. Completed status {analysis['n_pairs_completed_status']};",
        f"complete cells {cells['n_complete']}; incomplete {cells['n_incomplete']}.",
        f"Maps {analysis['n_maps']}; 20 cells per map: {rec['maps_have_20_cells']}.",
        f"Success A/B/C all 1.0: {rec['success_all_one']}.",
        f"Mean of map means equals grand cell mean: {rec['map_mean_equals_cell_mean']}.",
        f"Paired-cell C vs A counts sum to n: {rec['paired_cell_c_vs_a_sum']}.",
        "",
        "## Holdout map-level means and paired bootstrap",
        "",
        "Sampling unit: geometry map. Bootstrap: 10,000 resamples of 20 maps with",
        "replacement; all 20 paired conditions stay inside the resampled map.",
        f"Seed `{BOOTSTRAP_SEED}`. {assumption}",
        "",
        "| estimand | point | 95% CI |",
        "| --- | ---: | --- |",
        f"| mean of map means, later A | {_fmt(boot['mean_later_a']['point'])} | {_fmt(boot['mean_later_a']['ci95_low'])} to {_fmt(boot['mean_later_a']['ci95_high'])} |",
        f"| mean of map means, later B | {_fmt(boot['mean_later_b']['point'])} | {_fmt(boot['mean_later_b']['ci95_low'])} to {_fmt(boot['mean_later_b']['ci95_high'])} |",
        f"| mean of map means, later C | {_fmt(boot['mean_later_c']['point'])} | {_fmt(boot['mean_later_c']['ci95_low'])} to {_fmt(boot['mean_later_c']['ci95_high'])} |",
        f"| mean of map means, lifetime A | {_fmt(boot['mean_lifetime_a']['point'])} | {_fmt(boot['mean_lifetime_a']['ci95_low'])} to {_fmt(boot['mean_lifetime_a']['ci95_high'])} |",
        f"| mean of map means, lifetime B | {_fmt(boot['mean_lifetime_b']['point'])} | {_fmt(boot['mean_lifetime_b']['ci95_low'])} to {_fmt(boot['mean_lifetime_b']['ci95_high'])} |",
        f"| mean of map means, lifetime C | {_fmt(boot['mean_lifetime_c']['point'])} | {_fmt(boot['mean_lifetime_c']['ci95_low'])} to {_fmt(boot['mean_lifetime_c']['ci95_high'])} |",
        f"| C−A map-mean later delta | {_fmt(boot['mean_delta_c_minus_a']['point'])} | {_fmt(boot['mean_delta_c_minus_a']['ci95_low'])} to {_fmt(boot['mean_delta_c_minus_a']['ci95_high'])} |",
        f"| C−B map-mean later delta | {_fmt(boot['mean_delta_c_minus_b']['point'])} | {_fmt(boot['mean_delta_c_minus_b']['ci95_low'])} to {_fmt(boot['mean_delta_c_minus_b']['ci95_high'])} |",
        f"| map win rate C vs A | {_fmt(boot['map_win_rate_c_vs_a']['point'], 2)} | {_fmt(boot['map_win_rate_c_vs_a']['ci95_low'], 2)} to {_fmt(boot['map_win_rate_c_vs_a']['ci95_high'], 2)} |",
        f"| map win rate C vs B | {_fmt(boot['map_win_rate_c_vs_b']['point'], 2)} | {_fmt(boot['map_win_rate_c_vs_b']['ci95_low'], 2)} to {_fmt(boot['map_win_rate_c_vs_b']['ci95_high'], 2)} |",
        "",
        "## Map-level wins, ties, losses",
        "",
        f"C vs A: helps={map_out['c_vs_a'].get('helps', 0)}, "
        f"equal={map_out['c_vs_a'].get('equal', 0)}, "
        f"wastes={map_out['c_vs_a'].get('wastes', 0)}.",
        f"C vs B: helps={map_out['c_vs_b'].get('helps', 0)}, "
        f"equal={map_out['c_vs_b'].get('equal', 0)}, "
        f"wastes={map_out['c_vs_b'].get('wastes', 0)}.",
        "",
        "## Per-map later means",
        "",
        "| map | A | B | C | C−A | C−B | overhead |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for unit in analysis["maps"]:
        lines.append(
            f"| {unit['layout']} | {_fmt(unit['mean_later_a'], 2)} | {_fmt(unit['mean_later_b'], 2)} | "
            f"{_fmt(unit['mean_later_c'], 2)} | {_fmt(unit['mean_delta_c_minus_a'], 2)} | "
            f"{_fmt(unit['mean_delta_c_minus_b'], 2)} | "
            f"{_fmt(unit['planning_overhead_expansions'], 0)} |"
        )
    lines.extend(
        [
            "",
            "## Paired-cell C vs A (descriptive; not the sampling unit)",
            "",
            f"n={cells['n_complete']} complete, {cells['n_incomplete']} incomplete. "
            f"helps={vs_a.get('helps', 0)}, equal={vs_a.get('equal', 0)}, wastes={vs_a.get('wastes', 0)}.",
            f"C vs B: helps={vs_b.get('helps', 0)}, equal={vs_b.get('equal', 0)}, wastes={vs_b.get('wastes', 0)}.",
            f"Cell-mean later: A {_fmt(cells['mean_later_a'])}, B {_fmt(cells['mean_later_b'])}, "
            f"C {_fmt(cells['mean_later_c'])}.",
            f"Cell-mean lifetime: A {_fmt(cells['mean_lifetime_a'])}, B {_fmt(cells['mean_lifetime_b'])}, "
            f"C {_fmt(cells['mean_lifetime_c'])}.",
            "",
            "| acquisition | n | C−A mean later | helps | equal | wastes |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for source, row in (cells["by_source"] or {}).items():
        lines.append(
            f"| {source} | {row['n']} | {_fmt(row['mean_delta_c_minus_a'])} | "
            f"{row['helps']} | {row['equal']} | {row['wastes']} |"
        )
    lines.extend(
        [
            "",
            "| acquisition bucket | n | B−A | C−A | helps | equal | wastes |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for bucket, row in (cells["by_acquisition_bucket"] or {}).items():
        lines.append(
            f"| {bucket or 'unlabeled'} | {row['n']} | {_fmt(row['mean_delta_b_minus_a'])} | "
            f"{_fmt(row['mean_delta_c_minus_a'])} | {row['helps']} | {row['equal']} | {row['wastes']} |"
        )
    lines.extend(
        [
            "",
            "## C certificates (later k=10 decisions)",
            "",
            f"certified_no_headroom={certs.get('certified_no_headroom', 0)}, "
            f"shorter_plan_witness={certs.get('shorter_plan_witness', 0)}, "
            f"undecided={certs.get('undecided', 0)}.",
            f"Unresolved hypothesis searches: {cells['unresolved_search_count']}.",
            f"Mean C planning expansions per pair: {_fmt(cells['mean_planning_overhead_expansions'], 0)}.",
            "",
            "## XOR development trace",
            "",
            f"Checkpoint `{xor_trace['checkpoint_id']}`. "
            f"Starting condition `{xor_trace.get('starting_condition')}`.",
            f"Episode 0 cost {xor_trace['episode0_cost']} (oracle {xor_trace['oracle_episode0_cost']}).",
            f"k=10 later cost A {xor_trace['k10_later_a']}, B {xor_trace['k10_later_b']}, "
            f"C {xor_trace['k10_later_c']}.",
            "",
            xor_trace["why_c_skips_unnecessary_probe"],
            "",
            "| later | A steps | B steps / target | C steps / U / L / decision / target |",
            "| ---: | ---: | --- | --- |",
        ]
    )
    later_a = xor_trace.get("later_a") or []
    later_b = xor_trace.get("later_b") or []
    later_c = xor_trace.get("later_c") or []
    for i in range(min(3, len(later_a), len(later_b), len(later_c))):
        a = later_a[i]
        b = later_b[i]
        c = later_c[i]
        lines.append(
            f"| {i} | {a.get('steps')} | {b.get('steps')} / {b.get('intended_target')} | "
            f"{c.get('steps')} / {c.get('U')} / {c.get('L')} / {c.get('decision')} / "
            f"{c.get('intended_target')} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_v01_artifact(
    *,
    holdout_dir: Path,
    development_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    holdout_summary = load_summary(holdout_dir / "summary.json")
    holdout_manifest = load_manifest(holdout_dir / "manifest.json")
    development_summary = load_summary(development_dir / "summary.json")
    development_manifest = load_manifest(development_dir / "manifest.json")
    analysis = analyze_holdout(holdout_summary, holdout_manifest)
    xor_trace = extract_xor_trace(development_summary)
    output_dir.mkdir(parents=True, exist_ok=True)
    figure_dir = output_dir / "figures"
    figures = write_figures(analysis, figure_dir)
    write_json(output_dir / "holdout_stats.json", analysis)
    write_json(output_dir / "xor_trace.json", xor_trace)
    write_tables_markdown(analysis, xor_trace, output_dir / "tables.md")
    versions = {
        "package_version": __version__,
        "holdout_git": holdout_manifest.get("git"),
        "holdout_dependencies": holdout_manifest.get("dependencies"),
        "holdout_hardware": holdout_manifest.get("hardware"),
        "holdout_wall_seconds": holdout_summary.get("wall_seconds"),
        "development_git": development_manifest.get("git"),
        "development_dependencies": development_manifest.get("dependencies"),
        "development_wall_seconds": development_summary.get("wall_seconds"),
        "lockfile": "requirements.lock.txt",
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_replicates": BOOTSTRAP_REPLICATES,
        "figures": figures,
        "note": "A/B/C were not modified to produce this package.",
    }
    write_json(output_dir / "versions.json", versions)
    return {"analysis": analysis, "xor_trace": xor_trace, "versions": versions, "output_dir": str(output_dir)}
