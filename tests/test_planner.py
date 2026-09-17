from random import Random

from experience_lab.agents import make_agent
from experience_lab.belief import Belief
from experience_lab.env import make_tiny_world
from experience_lab.layouts import tiny_two_switch_layout
from experience_lab.planner import (
    conservative_plan,
    oracle_plan,
    probe_plan,
    select_active_probe,
    select_systematic_probe,
)
from experience_lab.rules import table_by_name
from experience_lab.types import Action, bits_to_int


def test_conservative_and_plan_succeeds_when_singleton():
    layout = tiny_two_switch_layout()
    belief = Belief.prior(2, layout.door_ids)
    belief.hypotheses["door0"] = {table_by_name(2, "x0_and_x1")}
    plan = conservative_plan(layout, layout.start, 0, belief, 10000)
    assert plan.status == "ok"
    assert plan.actions is not None
    env = make_tiny_world("x0_and_x1")
    obs = env.reset()
    for action in plan.actions:
        obs, _, terminated, truncated, _ = env.step(action)
    assert terminated and not truncated
    assert obs.agent_pos == layout.goal
    assert len(plan.actions) == 14


def test_probe_does_not_use_doors():
    layout = tiny_two_switch_layout()
    plan = probe_plan(layout, layout.start, 0, target_bits=1, expansion_cap=10000)
    assert plan.status == "ok"
    assert plan.actions is not None
    assert Action.TOGGLE in plan.actions
    env = make_tiny_world("x0_and_x1")
    obs = env.reset()
    for action in plan.actions:
        before = obs.agent_pos
        obs, _, _, _, _ = env.step(action)
        if action is not Action.TOGGLE:
            assert obs.agent_pos != layout.door_positions[0]
        assert obs.agent_pos != before or action is Action.TOGGLE
    assert bits_to_int(obs.switch_bits) == 1


def test_active_prefers_informative_cheaper_probe():
    layout = tiny_two_switch_layout()
    belief = Belief.prior(2, layout.door_ids)
    and_t = table_by_name(2, "x0_and_x1")
    xor_t = table_by_name(2, "x0_xor_x1")
    belief.hypotheses["door0"] = {and_t, xor_t}
    belief.update(0, (False,))
    chosen = select_active_probe(
        layout, layout.start, 0, belief, Random(0), 10000
    )
    assert chosen.status == "ok"
    assert chosen.target == 1
    sys_chosen = select_systematic_probe(layout, layout.start, 0, belief, 10000)
    assert sys_chosen.target == 1


def test_equal_information_prefers_shorter_travel():
    layout = tiny_two_switch_layout()
    belief = Belief.prior(2, layout.door_ids)
    belief.hypotheses["door0"] = {
        table_by_name(2, "x0"),
        table_by_name(2, "x1"),
        table_by_name(2, "x0_and_x1"),
    }
    belief.update(0, (False,))
    active = select_active_probe(
        layout, layout.start, 0, belief, Random(1), 10000
    )
    systematic = select_systematic_probe(layout, layout.start, 0, belief, 10000)
    assert active.target == 1
    assert systematic.target == 1
    costs = {
        row["target"]: row["cost"]
        for row in active.candidates
        if row["score"] is not None
    }
    assert costs[1] < costs[2]


def test_oracle_not_used_by_learning_agent(monkeypatch):
    layout = tiny_two_switch_layout()
    called = {"n": 0}

    def boom(*_args, **_kwargs):
        called["n"] += 1
        raise AssertionError("learner must not call oracle_plan")

    monkeypatch.setattr("experience_lab.planner.oracle_plan", boom)
    env = make_tiny_world("x0")
    obs = env.reset()
    agent = make_agent(layout, "active_retained", seed=1, expansion_cap=10000)
    agent.on_episode_start(obs)
    action = agent.select_action(obs)
    assert action in Action
    assert called["n"] == 0


def test_known_oracle_shortest_paths():
    layout = tiny_two_switch_layout()
    plan = oracle_plan(
        layout, layout.start, 0, (table_by_name(2, "x0_and_x1"),), 10000
    )
    assert plan.actions is not None
    assert len(plan.actions) == 14
