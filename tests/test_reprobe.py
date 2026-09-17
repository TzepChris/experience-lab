from pathlib import Path
from random import Random

import yaml

from experience_lab.agents import make_agent
from experience_lab.belief import Belief
from experience_lab.env import SwitchWorld
from experience_lab.layouts import SWAP_PERM, get_layout, probe_spur_layout, with_switch_permutation
from experience_lab.planner import conservative_plan, oracle_plan, select_active_probe
from experience_lab.reprobe_report import prefix_summary_for_run
from experience_lab.rules import initially_closed_rule_names, permute_rule_name, table_by_name
from experience_lab.types import Action


CLOSED_DOOR_RULES = ("x0", "x1", "x0_and_x1", "x0_or_x1", "x0_xor_x1")


def test_initially_closed_family_is_five_rules():
    names = initially_closed_rule_names(2)
    assert names == CLOSED_DOOR_RULES
    for name in names:
        assert table_by_name(2, name)(0) is False
    for name in ("not_x0", "not_x1"):
        assert table_by_name(2, name)(0) is True
        assert name not in names


def test_frozen_reprobe_matrix_matches_closed_door_family():
    config = yaml.safe_load(
        Path("configs/reprobe_closed_door.yaml").read_text(encoding="utf-8")
    )
    assert tuple(config["rules"]) == CLOSED_DOOR_RULES
    assert "x0" in config["rules"] and "x1" in config["rules"]
    assert [0, 1] in config["switch_permutations"]
    assert [1, 0] in config["switch_permutations"]
    assert config["methods"] == [
        "active_retained",
        "active_reprobe_retained",
        "oracle",
    ]
    assert config["prefixes"] == [1, 2, 5, 10]
    assert config["layouts"] == ["tiny_two_switch", "probe_spur", "probe_spur_mirror"]


def test_permutation_preserves_oracle_length_for_closed_family():
    layout = probe_spur_layout()
    swapped = with_switch_permutation(layout, SWAP_PERM)
    for requested in CLOSED_DOOR_RULES:
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


def test_oracle_solves_all_closed_door_rules_on_frozen_maps():
    for name in ("tiny_two_switch", "probe_spur", "probe_spur_mirror"):
        layout = get_layout(name)
        for rule_name in CLOSED_DOOR_RULES:
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


def _belief_with_safe_plan_and_informative_remainder(layout):
    belief = Belief.prior(2, layout.door_ids)
    belief.hypotheses["door0"] = {
        table_by_name(2, "x0_and_x1"),
        table_by_name(2, "x1"),
    }
    belief.update(0, (False,))
    belief.update(1, (False,))
    return belief


def test_exploit_skips_probe_when_safe_plan_exists():
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x1"),))
    obs = env.reset()
    agent = make_agent(layout, "active_retained", seed=1, expansion_cap=10000)
    agent.belief = _belief_with_safe_plan_and_informative_remainder(layout)
    agent.on_episode_start(obs, episode_index=1)
    task = conservative_plan(layout, obs.agent_pos, 0, agent.belief, 10000)
    assert task.status == "ok"
    action = agent.select_action(obs)
    assert action in Action
    assert agent.last_decision.plan_kind == "task"
    assert agent.last_decision.optional_reprobe is False
    assert agent.extra_probe_actions == 0


def test_reprobe_uses_information_per_action_even_when_safe_plan_exists():
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x1"),))
    obs = env.reset()
    agent = make_agent(layout, "active_reprobe_retained", seed=1, expansion_cap=10000)
    agent.belief = _belief_with_safe_plan_and_informative_remainder(layout)
    task = conservative_plan(layout, obs.agent_pos, 0, agent.belief, 10000)
    assert task.status == "ok"
    expected = select_active_probe(
        layout, obs.agent_pos, 0, agent.belief, Random(1), 10000
    )
    agent = make_agent(layout, "active_reprobe_retained", seed=1, expansion_cap=10000)
    agent.belief = _belief_with_safe_plan_and_informative_remainder(layout)
    agent.on_episode_start(obs, episode_index=1)
    action = agent.select_action(obs)
    assert agent.last_decision.plan_kind == "probe"
    assert agent.last_decision.optional_reprobe is True
    assert agent.last_decision.target == expected.target == 2
    assert action in Action


def test_reprobe_not_taken_on_first_episode():
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x1"),))
    obs = env.reset()
    agent = make_agent(layout, "active_reprobe_retained", seed=1, expansion_cap=10000)
    agent.on_episode_start(obs, episode_index=0)
    action = agent.select_action(obs)
    assert action in Action
    assert agent.last_decision.optional_reprobe is False


def test_extra_probe_ends_at_first_toggle_and_is_at_most_one():
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x1"),), max_steps=256)
    agent = make_agent(layout, "active_reprobe_retained", seed=1, expansion_cap=10000)
    obs = env.reset()
    agent.belief = _belief_with_safe_plan_and_informative_remainder(layout)
    agent.on_episode_start(obs, episode_index=1)
    optional_toggles = 0
    optional_actions = 0
    saw_task_after_probe = False
    terminated = False
    while True:
        action = agent.select_action(obs)
        optional = agent.last_decision.optional_reprobe
        kind = agent.last_decision.plan_kind
        if optional:
            optional_actions += 1
        if optional and action is Action.TOGGLE:
            optional_toggles += 1
        if optional_toggles and kind == "task":
            saw_task_after_probe = True
        obs, _reward, terminated, truncated, _info = env.step(action)
        agent.update(obs)
        if terminated or truncated:
            break
    assert terminated
    assert optional_toggles == 1
    assert optional_actions == agent.extra_probe_actions
    assert saw_task_after_probe
    assert agent.extra_probe_actions > 0


def test_reprobe_does_not_call_oracle(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("learner must not call oracle_plan")

    monkeypatch.setattr("experience_lab.planner.oracle_plan", boom)
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x1"),))
    obs = env.reset()
    agent = make_agent(layout, "active_reprobe_retained", seed=1, expansion_cap=10000)
    agent.belief = _belief_with_safe_plan_and_informative_remainder(layout)
    agent.on_episode_start(obs, episode_index=1)
    agent.select_action(obs)


def test_prefix_reports_success_with_cost_and_keeps_failures_expensive():
    run = {
        "status": "completed",
        "episodes": [
            {
                "status": "completed",
                "success": True,
                "steps": 10,
                "extra_probe_actions": 0,
                "optional_reprobe": False,
                "probe_steps": 3,
            },
            {
                "status": "completed",
                "success": False,
                "steps": 4,
                "extra_probe_actions": 5,
                "optional_reprobe": True,
                "probe_steps": 4,
            },
        ],
    }
    rows = prefix_summary_for_run(run, (1, 2), max_episode_steps=256)
    assert rows[0]["all_success"] is True
    assert rows[0]["capped_cost"] == 10
    assert rows[1]["all_success"] is False
    assert rows[1]["capped_cost"] == 10 + 256
    assert rows[1]["extra_probe_actions"] == 5


def test_incomplete_prefix_is_not_a_low_cost():
    run = {
        "status": "interrupted_time",
        "episodes": [
            {
                "status": "completed",
                "success": True,
                "steps": 8,
                "extra_probe_actions": 0,
                "optional_reprobe": False,
                "probe_steps": 2,
            }
        ],
    }
    rows = prefix_summary_for_run(run, (1, 2), max_episode_steps=256)
    assert rows[0]["status"] == "incomplete"
    assert rows[0]["capped_cost"] is None
    assert rows[1]["status"] == "incomplete"
    assert rows[1]["capped_cost"] is None
    assert rows[1]["all_success"] is False
