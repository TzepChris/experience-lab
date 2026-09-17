from random import Random

from experience_lab.belief import Belief
from experience_lab.env import SwitchWorld
from experience_lab.layouts import (
    SWAP_PERM,
    get_layout,
    probe_spur_layout,
    probe_spur_mirror_layout,
    tiny_two_switch_layout,
    with_switch_permutation,
)
from experience_lab.planner import oracle_plan, probe_plan, select_active_probe, select_systematic_probe
from experience_lab.rules import permute_rule_name, table_by_name


def _probe_cost(layout, target: int) -> int:
    plan = probe_plan(layout, layout.start, 0, target, expansion_cap=10000)
    assert plan.actions is not None
    return len(plan.actions)


def test_tiny_control_layout_still_exists():
    layout = tiny_two_switch_layout()
    assert layout.geometry == "tiny_two_switch"
    assert layout.n_switches == 2
    assert layout.start in layout.control_area
    assert layout.goal not in layout.control_area


def test_spur_and_mirror_keep_switches_in_control_area():
    for builder in (probe_spur_layout, probe_spur_mirror_layout):
        layout = builder()
        for pos in layout.switch_positions:
            assert pos in layout.control_area
        assert layout.start in layout.control_area
        assert layout.goal not in layout.control_area
        assert layout.door_positions[0] not in layout.control_area


def test_spur_near_probe_is_cheaper_than_far_probe():
    for layout in (probe_spur_layout(), probe_spur_mirror_layout()):
        near = _probe_cost(layout, 1)
        far = _probe_cost(layout, 2)
        assert near < far
        assert near == _probe_cost(probe_spur_layout(), 1)
        assert far == _probe_cost(probe_spur_layout(), 2)


def test_mirror_matches_spur_probe_and_oracle_costs():
    spur = probe_spur_layout()
    mirrored = probe_spur_mirror_layout()
    assert _probe_cost(spur, 1) == _probe_cost(mirrored, 1)
    assert _probe_cost(spur, 2) == _probe_cost(mirrored, 2)
    for rule_name in ("x0_and_x1", "x0_xor_x1", "x0"):
        rule = table_by_name(2, rule_name)
        a = oracle_plan(spur, spur.start, 0, (rule,), 10000)
        b = oracle_plan(mirrored, mirrored.start, 0, (rule,), 10000)
        assert a.actions is not None and b.actions is not None
        assert len(a.actions) == len(b.actions)


def test_permutation_preserves_oracle_length():
    layout = probe_spur_layout()
    swapped = with_switch_permutation(layout, SWAP_PERM)
    for requested in ("x0", "x1", "x0_and_x1", "x0_or_x1", "x0_xor_x1"):
        applied = permute_rule_name(requested, 2, SWAP_PERM)
        identity_plan = oracle_plan(
            layout, layout.start, 0, (table_by_name(2, requested),), 10000
        )
        swapped_plan = oracle_plan(
            swapped, swapped.start, 0, (table_by_name(2, applied),), 10000
        )
        assert identity_plan.actions is not None
        assert swapped_plan.actions is not None
        assert len(identity_plan.actions) == len(swapped_plan.actions)


def test_swap_makes_systematic_probe_the_far_switch():
    layout = with_switch_permutation(probe_spur_layout(), SWAP_PERM)
    belief = Belief.prior(2, layout.door_ids)
    belief.update(0, (False,))
    active = select_active_probe(layout, layout.start, 0, belief, Random(0), 10000)
    systematic = select_systematic_probe(layout, layout.start, 0, belief, 10000)
    assert _probe_cost(layout, 1) > _probe_cost(layout, 2)
    assert systematic.target == 1
    assert active.target == 2


def test_oracle_solves_all_frozen_rules_on_new_maps():
    for name in ("probe_spur", "probe_spur_mirror"):
        layout = get_layout(name)
        for rule_name in ("x0", "x1", "x0_and_x1", "x0_or_x1", "x0_xor_x1"):
            rule = table_by_name(2, rule_name)
            plan = oracle_plan(layout, layout.start, 0, (rule,), 10000)
            assert plan.status == "ok"
            env = SwitchWorld(layout=layout, _hidden_rules=(rule,))
            obs = env.reset()
            terminated = False
            for action in plan.actions or ():
                obs, _, terminated, truncated, _ = env.step(action)
                assert not truncated
            assert terminated
            assert obs.agent_pos == layout.goal
