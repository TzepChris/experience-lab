from pathlib import Path
from random import Random

import yaml

from experience_lab.agents import make_agent, make_checkpoint_fork
from experience_lab.belief import Belief
from experience_lab.checkpoint_eval import classify_starting_condition
from experience_lab.checkpoint_report import later_prefix_summary
from experience_lab.env import SwitchWorld
from experience_lab.layouts import probe_spur_layout
from experience_lab.planner import conservative_plan, select_active_probe
from experience_lab.rules import initially_closed_rule_names, table_by_name
from experience_lab.types import Action, bits_to_int


CLOSED_DOOR_RULES = ("x0", "x1", "x0_and_x1", "x0_or_x1", "x0_xor_x1")


def _or_xor_two_toggle_belief(layout):
    belief = Belief.prior(2, layout.door_ids)
    belief.hypotheses["door0"] = {
        table_by_name(2, "x0_or_x1"),
        table_by_name(2, "x0_xor_x1"),
    }
    belief.update(0, (False,))
    belief.update(1, (True,))
    belief.update(2, (True,))
    return belief


def test_frozen_checkpoint_matrix_matches_closed_door_family():
    config = yaml.safe_load(
        Path("configs/checkpoint_complete_probe.yaml").read_text(encoding="utf-8")
    )
    assert tuple(config["rules"]) == CLOSED_DOOR_RULES == initially_closed_rule_names(2)
    assert config["source_methods"] == ["systematic_retained", "active_retained"]
    assert config["later_episodes"] == 10
    assert config["prefixes"] == [1, 2, 5, 10]
    assert [0, 1] in config["switch_permutations"]
    assert [1, 0] in config["switch_permutations"]


def test_complete_probe_reaches_two_toggle_target():
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x0_xor_x1"),))
    obs = env.reset()
    belief = _or_xor_two_toggle_belief(layout)
    task = conservative_plan(layout, obs.agent_pos, 0, belief, 10000)
    assert task.status == "ok"
    expected = select_active_probe(layout, obs.agent_pos, 0, belief, Random(1), 10000)
    assert expected.target == 3
    agent = make_agent(layout, "complete_reprobe_retained", seed=1, expansion_cap=10000)
    agent.belief = belief.clone()
    agent.on_episode_start(obs, episode_index=1)
    optional_toggles = 0
    while True:
        action = agent.select_action(obs)
        optional = agent.last_decision.optional_reprobe
        if optional and action is Action.TOGGLE:
            optional_toggles += 1
        obs, _reward, terminated, truncated, _info = env.step(action)
        agent.update(obs)
        if optional and optional_toggles and bits_to_int(obs.switch_bits) == 3:
            break
        if terminated or truncated:
            break
        if not optional and optional_toggles:
            break
    log = agent.extra_probe_log
    assert log["intended_target"] == 3
    assert log["target_reached"] is True
    assert 3 in log["configs_after_toggles"]
    assert log["configs_after_toggles"][0] != 3
    assert optional_toggles == 2
    assert log["toggles"] == 2
    assert log["early_stop_reason"] in {"target_reached", None}
    assert bits_to_int(obs.switch_bits) == 3


def test_first_toggle_reprobe_does_not_complete_two_toggle_target():
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x0_xor_x1"),))
    obs = env.reset()
    agent = make_agent(layout, "active_reprobe_retained", seed=1, expansion_cap=10000)
    agent.belief = _or_xor_two_toggle_belief(layout)
    agent.on_episode_start(obs, episode_index=1)
    optional_toggles = 0
    bits_after_extra = None
    while True:
        action = agent.select_action(obs)
        optional = agent.last_decision.optional_reprobe
        if optional and action is Action.TOGGLE:
            optional_toggles += 1
        obs, _reward, terminated, truncated, _info = env.step(action)
        agent.update(obs)
        if optional_toggles and not agent._current_plan_is_optional_reprobe:
            bits_after_extra = bits_to_int(obs.switch_bits)
            break
        if terminated or truncated:
            bits_after_extra = bits_to_int(obs.switch_bits)
            break
    assert optional_toggles == 1
    assert bits_after_extra != 3
    assert agent.extra_probe_log["intended_target"] == 3
    assert agent.extra_probe_log["target_reached"] is False
    assert agent.extra_probe_log["early_stop_reason"] == "first_toggle"


def test_checkpoint_forks_share_identical_public_belief():
    layout = probe_spur_layout()
    source_belief = _or_xor_two_toggle_belief(layout)
    exploit = make_checkpoint_fork(
        layout,
        "systematic",
        seed=2,
        expansion_cap=10000,
        optional_reprobe=False,
        complete_target_probe=False,
        belief=source_belief,
    )
    complete = make_checkpoint_fork(
        layout,
        "systematic",
        seed=2,
        expansion_cap=10000,
        optional_reprobe=True,
        complete_target_probe=True,
        belief=source_belief,
    )
    assert exploit.belief.snapshot() == complete.belief.snapshot() == source_belief.snapshot()
    assert exploit.belief is not source_belief
    assert complete.belief is not exploit.belief
    source_belief.update(3, (False,))
    assert 3 not in exploit.belief.evidence
    assert exploit.selector == complete.selector == "systematic"


def test_complete_reprobe_does_not_call_oracle(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("learner must not call oracle_plan")

    monkeypatch.setattr("experience_lab.planner.oracle_plan", boom)
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x0_xor_x1"),))
    obs = env.reset()
    agent = make_agent(layout, "complete_reprobe_retained", seed=1, expansion_cap=10000)
    agent.belief = _or_xor_two_toggle_belief(layout)
    agent.on_episode_start(obs, episode_index=1)
    agent.select_action(obs)


def test_belief_restore_snapshot_roundtrip():
    layout = probe_spur_layout()
    original = _or_xor_two_toggle_belief(layout)
    clone = Belief.prior(2, layout.door_ids)
    clone.restore_snapshot(original.snapshot())
    assert clone.snapshot() == original.snapshot()
    assert clone.names("door0") == original.names("door0")


def test_starting_conditions_split_expensive_systematic_and_cheap_active():
    assert classify_starting_condition("systematic_retained", 24, 7) == "expensive_systematic"
    assert classify_starting_condition("systematic_retained", 7, 7) == "cheap_systematic_control"
    assert classify_starting_condition("active_retained", 7, 7) == "cheap_active"
    assert classify_starting_condition("active_retained", 24, 7) == "expensive_active_control"


def test_labeled_probe_actions_are_distinct_from_additional_cost():
    later = [
        {
            "status": "completed",
            "success": True,
            "steps": 19,
            "extra_probe_actions": 12,
            "probe_steps": 12,
        }
    ]
    rows = later_prefix_summary(later, "completed", (1,), 256)
    assert rows[0]["capped_cost"] == 19
    assert rows[0]["labeled_probe_actions"] == 12
    exploit = [
        {
            "status": "completed",
            "success": True,
            "steps": 7,
            "extra_probe_actions": 0,
            "probe_steps": 0,
        }
    ]
    exploit_rows = later_prefix_summary(exploit, "completed", (1,), 256)
    additional = rows[0]["capped_cost"] - exploit_rows[0]["capped_cost"]
    assert additional == 12
    on_path = later_prefix_summary(
        [
            {
                "status": "completed",
                "success": True,
                "steps": 7,
                "extra_probe_actions": 7,
                "probe_steps": 7,
            }
        ],
        "completed",
        (1,),
        256,
    )
    additional_on_path = on_path[0]["capped_cost"] - exploit_rows[0]["capped_cost"]
    assert on_path[0]["labeled_probe_actions"] == 7
    assert additional_on_path == 0


def test_incomplete_later_prefix_is_not_a_low_cost():
    rows = later_prefix_summary(
        [{"status": "completed", "success": True, "steps": 8, "extra_probe_actions": 0, "probe_steps": 0}],
        "interrupted_time",
        (1, 2),
        256,
    )
    assert rows[0]["status"] == "incomplete"
    assert rows[0]["capped_cost"] is None
    assert rows[1]["all_success"] is False
