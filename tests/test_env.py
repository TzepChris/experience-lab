from experience_lab.env import SwitchWorld, make_tiny_world
from experience_lab.layouts import tiny_two_switch_layout
from experience_lab.planner import oracle_plan
from experience_lab.rules import table_by_name
from experience_lab.types import GOAL_REWARD, STEP_COST, Action


def _exec(env: SwitchWorld, actions: list[Action]):
    obs = env.reset()
    total = 0.0
    terminated = truncated = False
    for action in actions:
        obs, reward, terminated, truncated, info = env.step(action)
        total += reward
        assert info == {}
        if terminated or truncated:
            break
    return obs, total, terminated, truncated


def test_layout_control_area_contains_switches_not_goal():
    layout = tiny_two_switch_layout()
    assert layout.start in layout.control_area
    assert layout.switch_positions[0] in layout.control_area
    assert layout.switch_positions[1] in layout.control_area
    assert layout.goal not in layout.control_area
    assert layout.door_positions[0] not in layout.control_area


def test_wall_and_closed_door_are_noops():
    env = make_tiny_world("x0_and_x1")
    obs = env.reset()
    assert obs.agent_pos == env.layout.start
    obs, reward, terminated, truncated, info = env.step(Action.NORTH)
    assert obs.agent_pos == env.layout.start
    assert reward == -STEP_COST
    assert not terminated and not truncated
    assert info == {}
    # door is closed at bits 00 for AND
    env.debug_set_state(agent_pos=(2, 3), switch_bits=0)
    obs, _, _, _, _ = env.step(Action.SOUTH)
    assert obs.agent_pos == (2, 3)
    assert obs.door_open == (False,)


def test_toggle_only_on_switch_tiles():
    env = make_tiny_world("x0")
    env.reset()
    obs, _, _, _, _ = env.step(Action.TOGGLE)
    assert obs.switch_bits == (False, False)
    env.debug_set_state(agent_pos=(1, 3), switch_bits=0)
    obs, _, _, _, _ = env.step(Action.TOGGLE)
    assert obs.switch_bits == (True, False)
    assert obs.door_open == (True,)


def test_reward_termination_and_truncation():
    env = make_tiny_world("x0", max_steps=3)
    env.reset()
    env.debug_set_state(agent_pos=env.layout.goal, switch_bits=1)
    # already at goal only terminates on the action that reaches it; reset-like
    # placement on the goal without a step is not a completion.
    env.debug_set_state(agent_pos=(5, 4), switch_bits=1)
    obs, reward, terminated, truncated, _ = env.step(Action.EAST)
    assert obs.agent_pos == env.layout.goal
    assert terminated is True
    assert truncated is False
    assert abs(reward - (-STEP_COST + GOAL_REWARD)) < 1e-12

    env = make_tiny_world("x0_and_x1", max_steps=2)
    env.reset()
    obs, _, terminated, truncated, _ = env.step(Action.EAST)
    assert not terminated and not truncated
    obs, _, terminated, truncated, _ = env.step(Action.EAST)
    assert not terminated and truncated
    assert obs.step_index == 2


def test_reset_clears_physical_state_not_rules():
    env = make_tiny_world("x0_xor_x1")
    env.reset()
    env.debug_set_state(agent_pos=(1, 3), switch_bits=1)
    env.reset()
    obs = env._observation()
    assert obs.agent_pos == env.layout.start
    assert obs.switch_bits == (False, False)
    assert env._hidden_rules[0].name == "x0_xor_x1"


def test_identical_seeds_and_actions_match():
    actions = [Action.EAST, Action.EAST, Action.TOGGLE, Action.WEST]
    env_a = make_tiny_world("x0_and_x1")
    env_b = make_tiny_world("x0_and_x1")
    out_a = _exec(env_a, actions)
    out_b = _exec(env_b, actions)
    assert out_a[0] == out_b[0]
    assert out_a[1] == out_b[1]


def test_agent_may_leave_closed_door_tile():
    env = make_tiny_world("x0")
    env.reset()
    env.debug_set_state(agent_pos=(3, 3), switch_bits=0)
    assert env._observation().door_open == (False,)
    obs, _, _, _, _ = env.step(Action.NORTH)
    assert obs.agent_pos == (2, 3)


def test_oracle_solves_and_xor_and_x0():
    layout = tiny_two_switch_layout()
    expected = {"x0_and_x1": 14, "x0_xor_x1": 9, "x0": 9}
    for name, length in expected.items():
        rule = table_by_name(2, name)
        plan = oracle_plan(layout, layout.start, 0, (rule,), 10000)
        assert plan.status == "ok"
        assert plan.actions is not None
        assert len(plan.actions) == length
        env = SwitchWorld(layout=layout, _hidden_rules=(rule,))
        obs, _, terminated, truncated = _exec(env, list(plan.actions))
        assert terminated and not truncated
        assert obs.agent_pos == layout.goal
