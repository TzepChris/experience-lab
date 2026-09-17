from inspect import signature

from experience_lab.agents import ModelBasedAgent, make_agent
from experience_lab.belief import Belief
from experience_lab.env import make_tiny_world
from experience_lab.layouts import tiny_two_switch_layout
from experience_lab.serialization import observation_to_dict
from experience_lab.types import PUBLIC_OBSERVATION_FIELDS, Action, Observation


def test_observation_fields_are_exactly_the_public_set():
    expected = {
        "width",
        "height",
        "static_grid",
        "switch_ids",
        "door_ids",
        "switch_positions",
        "door_positions",
        "agent_pos",
        "goal_pos",
        "switch_bits",
        "door_open",
        "step_index",
    }
    assert set(PUBLIC_OBSERVATION_FIELDS) == expected
    env = make_tiny_world("x0_and_x1")
    obs = env.reset()
    dumped = observation_to_dict(obs)
    assert "hidden" not in dumped
    assert "rule" not in dumped
    assert "seed" not in dumped
    assert not hasattr(obs, "_hidden_rules")
    assert not hasattr(obs, "hidden_rules")


def test_step_info_is_empty():
    env = make_tiny_world("x0")
    env.reset()
    _, _, _, _, info = env.step(Action.EAST)
    assert info == {}


def test_agent_api_does_not_accept_environment_or_rules():
    sig = signature(ModelBasedAgent.select_action)
    assert list(sig.parameters) == ["self", "observation", "deadline"]
    update_sig = signature(ModelBasedAgent.update)
    assert list(update_sig.parameters) == ["self", "observation"]
    layout = tiny_two_switch_layout()
    agent = make_agent(layout, "active_retained", seed=1, expansion_cap=10000)
    assert not hasattr(agent, "_hidden_rules")
    assert not hasattr(agent, "rules")
    assert "hidden" not in signature(ModelBasedAgent.__init__).parameters
    assert "oracle" not in signature(ModelBasedAgent.__init__).parameters
    assert "starting_condition" not in signature(ModelBasedAgent.__init__).parameters


def test_same_public_history_same_belief_and_action():
    layout = tiny_two_switch_layout()
    env_and = make_tiny_world("x0_and_x1")
    env_xor = make_tiny_world("x0_xor_x1")
    obs_and = env_and.reset()
    obs_xor = env_xor.reset()
    assert obs_and.switch_bits == obs_xor.switch_bits
    assert obs_and.door_open == obs_xor.door_open
    agent_and = make_agent(layout, "active_retained", seed=7, expansion_cap=10000)
    agent_xor = make_agent(layout, "active_retained", seed=7, expansion_cap=10000)
    agent_and.on_episode_start(obs_and)
    agent_xor.on_episode_start(obs_xor)
    assert agent_and.snapshot()["hypotheses"] == agent_xor.snapshot()["hypotheses"]
    a1 = agent_and.select_action(obs_and)
    a2 = agent_xor.select_action(obs_xor)
    assert a1 == a2


def test_belief_from_observation_does_not_use_env():
    env = make_tiny_world("x0_and_x1")
    obs = env.reset()
    belief = Belief.prior(2, obs.door_ids)
    belief.update_from_observation(obs)
    assert "x0_and_x1" in belief.names("door0")
    assert env._hidden_rules[0].name == "x0_and_x1"
    assert obs.door_open == (False,)
    assert isinstance(obs, Observation)
