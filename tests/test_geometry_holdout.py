from inspect import signature
from pathlib import Path

import yaml

from experience_lab.geometry import (
    GENERATOR_VERSION,
    HOLDOUT_SEEDS,
    freeze_holdout_maps,
    generate_holdout_layout,
    holdout_layout_name,
    layout_solvable,
)
from experience_lab.layouts import get_layout, with_switch_permutation
from experience_lab.planner import oracle_plan
from experience_lab.rules import initially_closed_rule_names, permute_rule_name, table_by_name


FROZEN_MAPS = Path("configs/geometry_holdout_maps.yaml")


def _frozen_payload() -> dict:
    return yaml.safe_load(FROZEN_MAPS.read_text(encoding="utf-8"))


def test_holdout_seeds_and_generator_are_frozen():
    payload = _frozen_payload()
    assert payload["generator_version"] == GENERATOR_VERSION == 1
    assert tuple(payload["seeds"]) == HOLDOUT_SEEDS == tuple(range(1, 21))
    assert "no method ranking" in payload["acceptance"].lower()
    assert "solvability" in payload["acceptance"].lower()
    assert len(payload["maps"]) == 20


def test_frozen_maps_match_generator_and_loader():
    payload = _frozen_payload()
    regenerated = freeze_holdout_maps()
    for frozen, fresh in zip(payload["maps"], regenerated["maps"], strict=True):
        assert frozen["name"] == fresh["name"]
        assert frozen["ascii_lines"] == fresh["ascii_lines"]
        layout = get_layout(frozen["name"])
        generated, params = generate_holdout_layout(frozen["geometry_seed"])
        assert layout.static_grid == generated.static_grid
        assert layout.start == generated.start
        assert params["generator_version"] == GENERATOR_VERSION


def test_holdout_maps_are_solvable_for_all_closed_rules_and_permutations():
    for seed in HOLDOUT_SEEDS:
        layout = get_layout(holdout_layout_name(seed))
        assert layout.n_switches == 2
        assert layout.n_doors == 1
        assert layout_solvable(layout)
        for perm in ((0, 1), (1, 0)):
            swapped = with_switch_permutation(layout, perm)
            for requested in initially_closed_rule_names(2):
                applied = permute_rule_name(requested, 2, perm)
                plan = oracle_plan(
                    swapped,
                    swapped.start,
                    0,
                    (table_by_name(2, applied),),
                    10000,
                )
                assert plan.status == "ok"
                assert plan.actions


def test_geometry_api_does_not_take_method_rankings():
    assert "method" not in signature(generate_holdout_layout).parameters
    assert "ranking" not in signature(layout_solvable).parameters
    assert "active" not in signature(layout_solvable).parameters
    src = Path("src/experience_lab/geometry.py").read_text(encoding="utf-8")
    assert "checkpoint_exploit" not in src
    assert "active_retained" not in src
