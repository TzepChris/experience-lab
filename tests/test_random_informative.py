from random import Random

from experience_lab.agents import make_agent
from experience_lab.belief import Belief
from experience_lab.layouts import probe_spur_layout
from experience_lab.planner import (
    audit_random_informative_selection,
    informative_candidate_targets,
    select_active_probe,
    select_random_informative_probe,
    select_systematic_probe,
    simulate_probe_route_configs,
)
from experience_lab.rules import table_by_name


def _prior_after_off_closed():
    layout = probe_spur_layout()
    belief = Belief.prior(2, layout.door_ids)
    belief.update(0, (False,))
    return layout, belief


def test_random_informative_only_picks_positive_information():
    layout, belief = _prior_after_off_closed()
    chosen = select_random_informative_probe(
        layout, layout.start, 0, belief, Random(0), 10000
    )
    assert chosen.status == "ok"
    informative = [row["target"] for row in chosen.candidates if row["score"] is not None]
    assert chosen.target in informative
    assert 0 not in informative


def test_random_informative_uses_seeded_choice():
    layout = probe_spur_layout()
    belief = Belief.prior(2, layout.door_ids)
    belief.hypotheses["door0"] = {
        table_by_name(2, "x0_and_x1"),
        table_by_name(2, "x0_xor_x1"),
    }
    belief.update(0, (False,))
    targets = []
    for seed in range(30):
        chosen = select_random_informative_probe(
            layout, layout.start, 0, belief, Random(seed), 10000
        )
        targets.append(chosen.target)
    assert len(set(targets)) > 1


def test_systematic_ignores_rng_and_stays_canonical():
    layout, belief = _prior_after_off_closed()
    a = select_systematic_probe(layout, layout.start, 0, belief, 10000)
    b = select_systematic_probe(layout, layout.start, 0, belief, 10000)
    assert a.target == b.target == 1


def test_random_agent_constructs_from_method_name():
    layout = probe_spur_layout()
    agent = make_agent(layout, "random_informative_reset", seed=3, expansion_cap=10000)
    assert agent.selector == "random_informative"
    assert agent.reset_memory is True


def test_candidate_set_is_unobserved_informative_reachable():
    layout, belief = _prior_after_off_closed()
    chosen = select_random_informative_probe(
        layout, layout.start, 0, belief, Random(0), 10000
    )
    candidates = informative_candidate_targets(chosen.candidates)
    assert candidates == (1, 2, 3)
    observed = [row["target"] for row in chosen.candidates if row["observed"]]
    assert observed == [0]
    for row in chosen.candidates:
        if row["score"] is not None:
            assert not row["observed"]
            assert row["uncertainty"] > 0.0
            assert row["actions"] is not None


def test_random_informative_is_not_score_tie_breaking():
    layout, belief = _prior_after_off_closed()
    active_targets = [
        select_active_probe(layout, layout.start, 0, belief, Random(seed), 10000).target
        for seed in range(20)
    ]
    assert set(active_targets) == {1}
    random_targets = [
        select_random_informative_probe(
            layout, layout.start, 0, belief, Random(seed), 10000
        ).target
        for seed in range(20)
    ]
    assert set(random_targets) == {1, 2, 3}


def test_audit_100_seeds_records_intended_targets_not_route_configs():
    layout, belief = _prior_after_off_closed()
    audit = audit_random_informative_selection(layout, belief, n_seeds=100, expansion_cap=10000)
    assert audit["n_seeds"] == 100
    assert audit["candidate_set"] == [1, 2, 3]
    assert audit["sampling"] == "uniform_among_positive_information"
    assert audit["not_tie_breaking"] is True
    assert audit["scores_all_equal"] is False
    counts = {int(key): value for key, value in audit["counts"].items()}
    assert sum(counts.values()) == 100
    assert set(counts) == {1, 2, 3}
    for count in counts.values():
        assert count >= 15
    assert set(audit["intended_targets"]) == {1, 2, 3}

    both_on = [row for row in audit["draws"] if row["intended_target"] == 3]
    assert both_on
    for row in both_on:
        assert row["end_config"] == 3
        assert row["first_toggle_config"] != 3
        assert 3 not in row["incidental_toggle_configs"]
        assert row["incidental_toggle_configs"]
        route = simulate_probe_route_configs(
            layout,
            layout.start,
            0,
            select_random_informative_probe(
                layout, layout.start, 0, belief, Random(row["seed"]), 10000
            ).actions,
        )
        assert route["end_config"] == row["intended_target"]
        assert route["first_toggle_config"] == row["first_toggle_config"]
