from inspect import signature
from pathlib import Path

import yaml

from experience_lab.agents import make_agent, make_checkpoint_fork
from experience_lab.belief import Belief
from experience_lab.checkpoint_report import build_checkpoint_report
from experience_lab.env import SwitchWorld
from experience_lab.evaluation import run_episode
from experience_lab.layouts import SWAP_PERM, get_layout, probe_spur_layout, with_switch_permutation
from experience_lab.planner import (
    assumed_rule_plan,
    complete_hypothesis_assignments,
    conservative_plan,
    hypothesis_goal_plan_lengths,
    oracle_plan,
    ul_stopping_decision,
)
from experience_lab.rules import permute_rule_name, table_by_name
from experience_lab.types import bits_to_int


CLOSED_DOOR_RULES = ("x0", "x1", "x0_and_x1", "x0_or_x1", "x0_xor_x1")


def _run(env, agent, episode_index: int) -> dict:
    return run_episode(
        env,
        agent,
        run_id=f"test|{episode_index}",
        episode_index=episode_index,
        log_path=None,
        render=False,
        log_every_step=False,
        deadline=None,
    )


def _xor_remaining_belief(layout) -> Belief:
    belief = Belief.prior(2, layout.door_ids)
    belief.hypotheses["door0"] = {
        table_by_name(2, "x0"),
        table_by_name(2, "x0_or_x1"),
        table_by_name(2, "x0_xor_x1"),
    }
    belief.update(0, (False,))
    belief.update(1, (True,))
    return belief


def _or_xor_belief(layout) -> Belief:
    belief = Belief.prior(2, layout.door_ids)
    belief.hypotheses["door0"] = {
        table_by_name(2, "x0_or_x1"),
        table_by_name(2, "x0_xor_x1"),
    }
    belief.update(0, (False,))
    belief.update(2, (True,))
    return belief


def test_ul_config_preserves_frozen_checkpoint_matrix():
    old = yaml.safe_load(Path("configs/checkpoint_complete_probe.yaml").read_text(encoding="utf-8"))
    new = yaml.safe_load(Path("configs/checkpoint_ul_stopping.yaml").read_text(encoding="utf-8"))
    assert tuple(new["rules"]) == CLOSED_DOOR_RULES == tuple(old["rules"])
    assert new["layouts"] == old["layouts"]
    assert new["switch_permutations"] == old["switch_permutations"]
    assert new["seeds"] == old["seeds"]
    assert new["source_methods"] == old["source_methods"]
    assert new["later_episodes"] == old["later_episodes"] == 10
    assert new["prefixes"] == old["prefixes"] == [1, 2, 5, 10]
    assert new["include_ul_stopping"] is True
    assert "include_ul_stopping" not in old
    assert new["output"] != old["output"]


def test_ul_decision_probes_only_when_proven_shorter():
    shorter = ul_stopping_decision(
        19,
        "ok",
        {"decided_lengths": [19, 7], "any_undecided": False, "expansions": 4, "hypotheses": []},
    )
    assert shorter["decision"] == "optional_probe"
    assert shorter["U"] == 19
    assert shorter["L"] == 7
    assert shorter["proven_shorter"] is True
    assert shorter["certificate"] == "shorter_plan_witness"
    equal = ul_stopping_decision(
        7,
        "ok",
        {"decided_lengths": [7, 7, 19], "any_undecided": False, "expansions": 3, "hypotheses": []},
    )
    assert equal["decision"] == "exploit"
    assert equal["U"] == equal["L"] == 7
    assert equal["certificate"] == "certified_no_headroom"
    none = ul_stopping_decision(None, "no_plan", {"decided_lengths": [7], "any_undecided": False, "expansions": 0})
    assert none["decision"] == "required_explore"
    assert none["L_status"] == "not_applicable"


def test_search_cap_is_undecided_not_proof_no_shorter_route():
    capped = ul_stopping_decision(
        19,
        "ok",
        {
            "hypotheses": [{"hypothesis": ("x0_or_x1",), "status": "planner_cap", "length": None}],
            "expansions": 2,
            "any_undecided": True,
            "decided_lengths": [],
            "L": None,
        },
    )
    assert capped["decision"] == "exploit"
    assert capped["L_status"] == "undecided"
    assert capped["certificate"] == "undecided"
    assert capped["proven_shorter"] is False
    assert capped["L"] is None
    mixed = ul_stopping_decision(
        19,
        "ok",
        {
            "hypotheses": [
                {"hypothesis": ("x0_or_x1",), "status": "ok", "length": 7},
                {"hypothesis": ("x0",), "status": "planner_cap", "length": None},
            ],
            "expansions": 5,
            "any_undecided": True,
            "decided_lengths": [7],
        },
    )
    assert mixed["decision"] == "optional_probe"
    assert mixed["L"] == 7
    assert mixed["certificate"] == "shorter_plan_witness"
    assert mixed["note"] == "hand-designed U vs L stopping rule, not a learned policy"


def test_resolved_u_with_capped_other_search_is_not_certified_no_headroom():
    decision = ul_stopping_decision(
        19,
        "ok",
        {
            "hypotheses": [
                {"hypothesis": ("x0",), "status": "ok", "length": 19},
                {"hypothesis": ("x0_or_x1",), "status": "planner_cap", "length": None},
            ],
            "expansions": 8,
            "any_undecided": True,
            "decided_lengths": [19],
        },
    )
    assert decision["decision"] == "exploit"
    assert decision["L"] == 19
    assert decision["U"] == 19
    assert decision["certificate"] == "undecided"
    assert decision["certificate"] != "certified_no_headroom"
    assert decision["L_status"] == "undecided"
    assert decision["unresolved_search_count"] == 1


def test_hypothesis_plans_keep_one_complete_assignment():
    layout = with_switch_permutation(probe_spur_layout(), SWAP_PERM)
    belief = _xor_remaining_belief(layout)
    assignments = complete_hypothesis_assignments(belief)
    assert len(assignments) == 3
    for rules in assignments:
        assert len(rules) == 1
    report = hypothesis_goal_plan_lengths(layout, layout.start, 0, belief, 10000)
    by_name = {row["hypothesis"]: row["length"] for row in report["hypotheses"]}
    for rules in assignments:
        solo = assumed_rule_plan(layout, layout.start, 0, rules, 10000)
        assert solo.status == "ok"
        assert by_name[(rules[0].name,)] == len(solo.actions)
    conservative = conservative_plan(layout, layout.start, 0, belief, 10000)
    assert conservative.status == "ok"
    assert report["L"] == min(by_name.values())
    assert len(conservative.actions) > report["L"]


def test_assumed_rule_plan_matches_oracle_for_a_true_rule():
    layout = probe_spur_layout()
    rules = (table_by_name(2, "x0_xor_x1"),)
    assumed = assumed_rule_plan(layout, layout.start, 0, rules, 10000)
    privileged = oracle_plan(layout, layout.start, 0, rules, 10000)
    assert assumed.status == privileged.status == "ok"
    assert assumed.actions == privileged.actions


def test_ul_planner_api_does_not_take_hidden_or_oracle_inputs():
    assert list(signature(hypothesis_goal_plan_lengths).parameters) == [
        "layout",
        "agent_pos",
        "switch_bits",
        "belief",
        "expansion_cap",
        "deadline",
    ]
    assert list(signature(ul_stopping_decision).parameters) == ["U", "U_status", "hypothesis_report"]
    assert list(signature(assumed_rule_plan).parameters) == [
        "layout",
        "agent_pos",
        "switch_bits",
        "rules",
        "expansion_cap",
        "deadline",
    ]


def test_c_does_not_call_oracle_plan(monkeypatch):
    def boom(*_args, **_kwargs):
        raise AssertionError("learner must not call oracle_plan")

    monkeypatch.setattr("experience_lab.planner.oracle_plan", boom)
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x0_xor_x1"),))
    obs = env.reset()
    agent = make_checkpoint_fork(
        layout,
        "systematic",
        seed=1,
        expansion_cap=10000,
        optional_reprobe=True,
        complete_target_probe=True,
        belief=_xor_remaining_belief(layout),
        hypothesis_stopping=True,
    )
    agent.on_episode_start(obs, episode_index=1)
    agent.select_action(obs)
    assert agent.stopping_log["decision"] in {"optional_probe", "exploit", "required_explore"}


def test_c_cap_exhaustion_does_not_authorize_probe(monkeypatch):
    def capped(_layout, _pos, _bits, _belief, _cap, _deadline=None):
        return {
            "hypotheses": [{"hypothesis": ("x0_or_x1",), "status": "planner_cap", "length": None}],
            "expansions": 1,
            "any_undecided": True,
            "decided_lengths": [],
            "L": None,
        }

    monkeypatch.setattr("experience_lab.agents.hypothesis_goal_plan_lengths", capped)
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x0_xor_x1"),))
    obs = env.reset()
    belief = _or_xor_belief(layout)
    task = conservative_plan(layout, obs.agent_pos, bits_to_int(obs.switch_bits), belief, 10000)
    assert task.status == "ok"
    agent = make_checkpoint_fork(
        layout,
        "active",
        seed=1,
        expansion_cap=10000,
        optional_reprobe=True,
        complete_target_probe=True,
        belief=belief,
        hypothesis_stopping=True,
    )
    agent.on_episode_start(obs, episode_index=1)
    agent.select_action(obs)
    assert agent.stopping_log["decision"] == "exploit"
    assert agent.stopping_log["L_status"] == "undecided"
    assert agent.last_decision.optional_reprobe is False


def test_expensive_checkpoint_c_probes_when_l_lt_u():
    layout = with_switch_permutation(probe_spur_layout(), SWAP_PERM)
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, permute_rule_name("x0_xor_x1", 2, SWAP_PERM)),))
    obs = env.reset()
    belief = _xor_remaining_belief(layout)
    task = conservative_plan(layout, obs.agent_pos, 0, belief, 10000)
    report = hypothesis_goal_plan_lengths(layout, obs.agent_pos, 0, belief, 10000)
    assert task.status == "ok" and report["L"] is not None
    assert len(task.actions) > report["L"]
    agent = make_checkpoint_fork(
        layout,
        "systematic",
        seed=1,
        expansion_cap=10000,
        optional_reprobe=True,
        complete_target_probe=True,
        belief=belief,
        hypothesis_stopping=True,
    )
    agent.on_episode_start(obs, episode_index=1)
    agent.select_action(obs)
    assert agent.stopping_log["U"] == len(task.actions)
    assert agent.stopping_log["L"] == report["L"]
    assert agent.stopping_log["decision"] == "optional_probe"
    assert agent.last_decision.optional_reprobe is True
    assert agent.stopping_log["planning_expansions"] > 0


def test_cheap_multihypothesis_checkpoint_c_skips_probe():
    layout = probe_spur_layout()
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, "x0_xor_x1"),))
    obs = env.reset()
    belief = _or_xor_belief(layout)
    assert belief.hypothesis_count("door0") > 1
    task = conservative_plan(layout, obs.agent_pos, 0, belief, 10000)
    report = hypothesis_goal_plan_lengths(layout, obs.agent_pos, 0, belief, 10000)
    assert task.status == "ok"
    assert len(task.actions) == report["L"]
    agent = make_checkpoint_fork(
        layout,
        "active",
        seed=1,
        expansion_cap=10000,
        optional_reprobe=True,
        complete_target_probe=True,
        belief=belief,
        hypothesis_stopping=True,
    )
    record = _run(env, agent, 1)
    assert record["stopping_log"]["decision"] == "exploit"
    assert record["stopping_log"]["U"] == record["stopping_log"]["L"]
    assert record["extra_probe_actions"] == 0
    assert record["success"] is True


def test_xor_trace_c_does_useful_probe_then_skips_or_xor_distinguisher():
    layout = with_switch_permutation(get_layout("probe_spur"), SWAP_PERM)
    rule = permute_rule_name("x0_xor_x1", 2, SWAP_PERM)
    env = SwitchWorld(layout=layout, _hidden_rules=(table_by_name(2, rule),))
    source = make_agent(layout, "systematic_retained", seed=1, expansion_cap=10000)
    ep0 = _run(env, source, 0)
    assert ep0["success"] is True
    remaining = set(source.belief.names("door0"))
    assert remaining == {"x0", "x0_or_x1", "x0_xor_x1"}
    fork_c = make_checkpoint_fork(
        layout,
        "systematic",
        seed=1,
        expansion_cap=10000,
        optional_reprobe=True,
        complete_target_probe=True,
        belief=source.belief,
        hypothesis_stopping=True,
    )
    later0 = _run(env, fork_c, 1)
    assert later0["success"] is True
    stop0 = later0["stopping_log"]
    assert stop0["U"] > stop0["L"]
    assert stop0["decision"] == "optional_probe"
    assert later0["extra_probe_log"]["intended_target"] == 2
    assert later0["extra_probe_log"]["target_reached"] is True
    assert later0["extra_probe_actions"] > 0
    remaining_after = set(fork_c.belief.names("door0"))
    assert remaining_after == {"x0_or_x1", "x0_xor_x1"}
    later1 = _run(env, fork_c, 2)
    assert later1["success"] is True
    stop1 = later1["stopping_log"]
    assert stop1["U"] == stop1["L"]
    assert stop1["decision"] == "exploit"
    assert later1["extra_probe_actions"] == 0
    assert later1["extra_probe_log"]["intended_target"] is None
    assert set(fork_c.belief.names("door0")) == {"x0_or_x1", "x0_xor_x1"}


def test_c_fork_shares_public_belief_and_has_no_hidden_rule_handle():
    layout = probe_spur_layout()
    source = _xor_remaining_belief(layout)
    fork_c = make_checkpoint_fork(
        layout,
        "systematic",
        seed=2,
        expansion_cap=10000,
        optional_reprobe=True,
        complete_target_probe=True,
        belief=source,
        hypothesis_stopping=True,
    )
    assert fork_c.belief.snapshot() == source.snapshot()
    assert fork_c.belief is not source
    assert not hasattr(fork_c, "_hidden_rules")
    assert not hasattr(fork_c, "starting_condition")
    assert "starting_condition" not in signature(make_checkpoint_fork).parameters
    assert "acquisition_bucket" not in signature(make_checkpoint_fork).parameters
    assert fork_c.hypothesis_stopping is True


def test_checkpoint_report_includes_abc_lifetime_without_requiring_c_win():

    def _eps(steps: int, extra: int = 0, decision: str | None = None, u: int | None = None, l: int | None = None):
        rec = {
            "status": "completed",
            "success": True,
            "steps": steps,
            "extra_probe_actions": extra,
            "probe_steps": extra,
            "wall_seconds": 0.01,
        }
        if decision is not None:
            rec["stopping_log"] = {
                "U": u,
                "L": l,
                "decision": decision,
                "planning_expansions": 12,
            }
        return rec

    report = build_checkpoint_report(
        {
            "pairs": [
                {
                    "checkpoint_id": "toy",
                    "status": "completed",
                    "starting_condition": "expensive_systematic",
                    "episode0_cost": 19,
                    "forks": {
                        "checkpoint_exploit": {
                            "status": "completed",
                            "episodes": [_eps(19) for _ in range(10)],
                        },
                        "checkpoint_complete_reprobe": {
                            "status": "completed",
                            "episodes": [_eps(7, 3, None) for _ in range(10)],
                        },
                        "checkpoint_ul_stopping": {
                            "status": "completed",
                            "episodes": [
                                _eps(7, 3, "optional_probe", 19, 7),
                                *[_eps(7, 0, "exploit", 7, 7) for _ in range(9)],
                            ],
                        },
                    },
                }
            ]
        },
        256,
        (1, 10),
    )
    k10 = report["by_checkpoint"][0]["prefixes"]["10"]
    assert k10["lifetime_exploit"] == 19 + 190
    assert k10["lifetime_ul_stopping"] == 19 + 70
    assert k10["ul_verdict"] == "ul_helps"
    pooled = report["by_starting_condition"]["expensive_systematic"]["prefixes"][1]
    assert pooled["n_ul_helps"] == 1

