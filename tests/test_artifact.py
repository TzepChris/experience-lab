import json
from pathlib import Path

from experience_lab.artifact import (
    BOOTSTRAP_SEED,
    XOR_CHECKPOINT_ID,
    analyze_holdout,
    extract_xor_trace,
    map_units,
    paired_map_bootstrap,
    reconstruct_certificate,
)
from experience_lab.checkpoint_report import FORK_COMPLETE, FORK_EXPLOIT, FORK_UL


def _map_unit(layout: str, later_a: float, later_b: float, later_c: float) -> dict:
    return {
        "layout": layout,
        "n_complete": 20,
        "mean_later_a": later_a,
        "mean_later_b": later_b,
        "mean_later_c": later_c,
        "mean_lifetime_a": later_a + 14,
        "mean_lifetime_b": later_b + 14,
        "mean_lifetime_c": later_c + 14,
    }


def test_reconstruct_certificate_does_not_treat_caps_as_no_headroom():
    assert reconstruct_certificate({"U": 19, "L": 7, "hypotheses": []}) == "shorter_plan_witness"
    assert reconstruct_certificate({"U": 7, "L": 7, "hypotheses": []}) == "certified_no_headroom"
    assert (
        reconstruct_certificate(
            {
                "U": 7,
                "L": 7,
                "hypotheses": [{"status": "ok"}, {"status": "planner_cap"}],
            }
        )
        == "undecided"
    )
    assert reconstruct_certificate({"certificate": "certified_no_headroom", "U": 7, "L": 9}) == (
        "certified_no_headroom"
    )


def test_paired_map_bootstrap_keeps_conditions_inside_each_map():
    units = [
        _map_unit("holdout_01", 10, 9, 8),
        _map_unit("holdout_02", 100, 99, 98),
        _map_unit("holdout_03", 20, 19, 18),
    ]
    result = paired_map_bootstrap(units, replicates=2000, seed=BOOTSTRAP_SEED)
    delta = result["intervals"]["mean_delta_c_minus_a"]
    assert delta["point"] == -2.0
    assert delta["ci95_low"] == -2.0
    assert delta["ci95_high"] == -2.0
    win = result["intervals"]["map_win_rate_c_vs_a"]
    assert win["point"] == 1.0
    assert win["ci95_low"] == 1.0
    assert win["ci95_high"] == 1.0


def test_paired_map_bootstrap_is_seed_reproducible_and_uses_map_means():
    units = [
        _map_unit("holdout_01", 12, 11, 10),
        _map_unit("holdout_02", 20, 16, 18),
        _map_unit("holdout_03", 30, 30, 24),
    ]
    first = paired_map_bootstrap(units, replicates=5000, seed=7)
    second = paired_map_bootstrap(units, replicates=5000, seed=7)
    assert first["intervals"] == second["intervals"]
    assert first["n_maps"] == 3
    assert "i.i.d. draws from this generator" in first["assumption"]
    assert first["intervals"]["mean_later_a"]["point"] == (12 + 20 + 30) / 3
    assert first["intervals"]["mean_delta_c_minus_a"]["point"] == ((10 - 12) + (18 - 20) + (24 - 30)) / 3


def test_map_units_preserve_twenty_paired_cells():
    cells = []
    for layout in ("holdout_01", "holdout_02"):
        for idx in range(20):
            later_a = 10 + idx
            later_c = later_a - 1
            cells.append(
                {
                    "layout": layout,
                    "complete": True,
                    "later_a": later_a,
                    "later_b": later_a,
                    "later_c": later_c,
                    "lifetime_a": later_a + 5,
                    "lifetime_b": later_a + 5,
                    "lifetime_c": later_c + 5,
                    "success_a": True,
                    "success_b": True,
                    "success_c": True,
                    "delta_c_minus_a": later_c - later_a,
                    "delta_c_minus_b": later_c - later_a,
                    "certificates": {},
                    "unresolved_search_count": 0,
                    "planning_overhead_expansions": 0,
                }
            )
    units = map_units(cells)
    assert len(units) == 2
    assert all(unit["n_cells"] == 20 and unit["n_complete"] == 20 for unit in units)
    assert all(unit["c_vs_a"] == "helps" for unit in units)


def _episode(steps: int, *, probe=0, target=None, after=None, stop=None, success=True):
    return {
        "status": "completed",
        "success": success,
        "steps": steps,
        "extra_probe_actions": probe,
        "extra_probe_log": {
            "intended_target": target,
            "target_reached": target is not None,
            "configs_after_toggles": [target] if target is not None else [],
            "hypotheses_after": after,
        },
        "stopping_log": stop or {},
    }


def test_extract_xor_trace_explains_skipped_distinguisher():
    summary = {
        "pairs": [
            {
                "checkpoint_id": XOR_CHECKPOINT_ID,
                "starting_condition": "expensive_systematic",
                "episode0_cost": 19,
                "oracle_episode0_cost": 7,
                "belief_after_episode0": {"hypotheses": {"door0": ["x0", "x0_or_x1", "x0_xor_x1"]}},
                "forks": {
                    FORK_EXPLOIT: {
                        "episodes": [_episode(19) for _ in range(10)],
                    },
                    FORK_COMPLETE: {
                        "episodes": [
                            _episode(7, probe=3, target=2, after={"door0": ["x0_or_x1", "x0_xor_x1"]}),
                            _episode(25, probe=12, target=3, after={"door0": ["x0_xor_x1"]}),
                            *[_episode(7) for _ in range(8)],
                        ]
                    },
                    FORK_UL: {
                        "episodes": [
                            _episode(
                                7,
                                probe=3,
                                target=2,
                                after={"door0": ["x0_or_x1", "x0_xor_x1"]},
                                stop={"U": 19, "L": 7, "decision": "optional_probe", "planning_expansions": 179},
                            ),
                            _episode(
                                7,
                                probe=0,
                                stop={"U": 7, "L": 7, "decision": "exploit", "planning_expansions": 80},
                            ),
                            *[_episode(7, stop={"U": 7, "L": 7, "decision": "exploit"}) for _ in range(8)],
                        ]
                    },
                },
            }
        ]
    }
    trace = extract_xor_trace(summary)
    assert trace["k10_later_a"] == 190
    assert trace["k10_later_b"] == 88
    assert trace["k10_later_c"] == 70
    assert trace["later_c"][0]["certificate"] == "shorter_plan_witness"
    assert trace["later_c"][1]["certificate"] == "certified_no_headroom"
    assert "OR-vs-XOR distinguisher" in trace["why_c_skips_unnecessary_probe"]
    assert "U=7" in trace["why_c_skips_unnecessary_probe"]
    assert "L=7" in trace["why_c_skips_unnecessary_probe"]
    assert "target 3" in trace["why_c_skips_unnecessary_probe"]


def test_saved_summaries_reconcile_if_present():
    holdout = Path("results/checkpoint_geometry_holdout/summary.json")
    development = Path("results/checkpoint_ul_stopping/summary.json")
    if not holdout.is_file() or not development.is_file():
        return
    analysis = analyze_holdout(json.loads(holdout.read_text(encoding="utf-8")), {})
    assert analysis["n_cells"] == 400
    assert analysis["n_maps"] == 20
    assert all(analysis["reconcile"].values())
    vs_a = analysis["paired_cells"]["c_vs_a"]
    assert vs_a.get("helps", 0) + vs_a.get("equal", 0) + vs_a.get("wastes", 0) == 400
    trace = extract_xor_trace(json.loads(development.read_text(encoding="utf-8")))
    assert trace["checkpoint_id"] == XOR_CHECKPOINT_ID
    assert trace["later_c"][0]["decision"] == "optional_probe"
    assert trace["later_c"][1]["decision"] == "exploit"
    assert trace["later_c"][1]["extra_probe_actions"] == 0
