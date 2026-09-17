"""Model-learning agents. They accept only public observations."""

from __future__ import annotations

from dataclasses import dataclass, field
from random import Random
from typing import Literal

from experience_lab.belief import Belief, EmptyHypothesisError
from experience_lab.layouts import Layout
from experience_lab.planner import (
    PlanResult,
    conservative_plan,
    hypothesis_goal_plan_lengths,
    select_active_probe,
    select_random_informative_probe,
    select_systematic_probe,
    ul_stopping_decision,
)
from experience_lab.types import Action, Observation, bits_to_int


Selector = Literal["active", "systematic", "random_informative"]


class NoSafePlanError(RuntimeError):
    """Conservative planner and probe selector both failed to produce a plan."""


@dataclass
class Decision:
    action: Action
    plan_kind: str
    target: int | None
    score: float | None
    expansions: int
    hypotheses_before: dict
    plan_status: str
    optional_reprobe: bool = False


def empty_extra_probe_log() -> dict:
    return {
        "intended_target": None,
        "configs_after_toggles": [],
        "configs_visited": [],
        "target_reached": False,
        "hypothesis_count_before": None,
        "hypothesis_count_after": None,
        "hypotheses_before": None,
        "hypotheses_after": None,
        "information_gained": None,
        "early_stop_reason": None,
        "toggles": 0,
    }


def empty_stopping_log() -> dict:
    return {
        "U": None,
        "U_status": None,
        "L": None,
        "L_status": None,
        "certificate": None,
        "decision": None,
        "proven_shorter": False,
        "any_undecided": False,
        "unresolved_search_count": 0,
        "hypotheses": [],
        "planning_expansions": 0,
        "extra_probe_actions": 0,
        "note": "hand-designed U vs L stopping rule, not a learned policy",
    }


@dataclass
class ModelBasedAgent:
    layout: Layout
    selector: Selector
    reset_memory: bool
    rng: Random
    expansion_cap: int
    optional_reprobe: bool = False
    complete_target_probe: bool = False
    checkpoint_mode: bool = False
    hypothesis_stopping: bool = False
    belief: Belief = field(init=False)
    _plan: tuple[Action, ...] = field(default_factory=tuple)
    _plan_index: int = 0
    _plan_kind: str = "none"
    _target: int | None = None
    _score: float | None = None
    _replan: bool = True
    _optional_reprobe_pending: bool = False
    _used_optional_reprobe: bool = False
    _current_plan_is_optional_reprobe: bool = False
    _ul_pending: bool = False
    last_expansions: int = 0
    last_decision: Decision | None = None
    extra_probe_actions: int = 0
    extra_probe_target: int | None = None
    extra_probe_log: dict = field(default_factory=empty_extra_probe_log)
    stopping_log: dict = field(default_factory=empty_stopping_log)

    def __post_init__(self) -> None:
        if self.selector not in ("active", "systematic", "random_informative"):
            raise ValueError(f"unknown selector {self.selector!r}")
        self.belief = Belief.prior(self.layout.n_switches, self.layout.door_ids)

    def snapshot(self) -> dict:
        return self.belief.snapshot()

    def on_episode_start(
        self,
        observation: Observation,
        deadline: float | None = None,
        episode_index: int = 0,
    ) -> None:
        del deadline
        if self.reset_memory:
            self.belief.reset_to_prior()
        self._plan = ()
        self._plan_index = 0
        self._plan_kind = "none"
        self._target = None
        self._score = None
        self._replan = True
        self._used_optional_reprobe = False
        self._current_plan_is_optional_reprobe = False
        self.extra_probe_actions = 0
        self.extra_probe_target = None
        self.extra_probe_log = empty_extra_probe_log()
        self.stopping_log = empty_stopping_log()
        self._ul_pending = False
        if self.hypothesis_stopping:
            # U vs L is decided on the first plan of the episode, from the
            # reset public state. Cap exhaustion cannot authorize a probe.
            self._optional_reprobe_pending = False
            self._ul_pending = True
        elif self.checkpoint_mode:
            self._optional_reprobe_pending = bool(self.optional_reprobe)
        else:
            self._optional_reprobe_pending = bool(
                self.optional_reprobe and episode_index >= 1
            )
        self.update(observation)

    def _holding_complete_probe(self) -> bool:
        return bool(
            self.complete_target_probe
            and self._current_plan_is_optional_reprobe
            and self._plan_index < len(self._plan)
        )

    def _finalize_extra_probe(self, observation: Observation) -> None:
        bits = bits_to_int(observation.switch_bits)
        reached = (
            self.extra_probe_target is not None and bits == self.extra_probe_target
        )
        self.extra_probe_log["target_reached"] = bool(reached)
        if self.extra_probe_log.get("early_stop_reason") is None:
            if reached:
                self.extra_probe_log["early_stop_reason"] = "target_reached"
            elif self._used_optional_reprobe:
                self.extra_probe_log["early_stop_reason"] = "plan_exhausted_without_target"
        after = self.belief.total_hypothesis_count()
        self.extra_probe_log["hypothesis_count_after"] = after
        self.extra_probe_log["hypotheses_after"] = self.belief.snapshot()["hypotheses"]
        before = self.extra_probe_log.get("hypothesis_count_before")
        if before is not None:
            self.extra_probe_log["information_gained"] = before - after

    def update(self, observation: Observation) -> bool:
        if not isinstance(observation, Observation):
            raise TypeError("agent.update accepts only Observation")
        changed = self.belief.update_from_observation(observation)
        if self._current_plan_is_optional_reprobe or (
            self._used_optional_reprobe
            and self.extra_probe_log.get("early_stop_reason") is None
        ):
            bits = bits_to_int(observation.switch_bits)
            visited = self.extra_probe_log["configs_visited"]
            if not visited or visited[-1] != bits:
                visited.append(bits)
            if self.last_decision is not None and self.last_decision.action is Action.TOGGLE:
                self.extra_probe_log["configs_after_toggles"].append(bits)
                self.extra_probe_log["toggles"] += 1
            if self.extra_probe_target is not None and bits == self.extra_probe_target:
                self.extra_probe_log["target_reached"] = True
        if changed and not self._holding_complete_probe():
            self._replan = True
        return changed

    def _select_probe(self, observation: Observation, bits: int, deadline: float | None) -> PlanResult:
        if self.selector == "active":
            return select_active_probe(
                self.layout,
                observation.agent_pos,
                bits,
                self.belief,
                self.rng,
                self.expansion_cap,
                deadline,
            )
        if self.selector == "random_informative":
            return select_random_informative_probe(
                self.layout,
                observation.agent_pos,
                bits,
                self.belief,
                self.rng,
                self.expansion_cap,
                deadline,
            )
        return select_systematic_probe(
            self.layout,
            observation.agent_pos,
            bits,
            self.belief,
            self.expansion_cap,
            deadline,
        )

    def _probe_result(self, probe: PlanResult, optional: bool) -> PlanResult:
        self.last_expansions += probe.expansions
        if probe.status == "ok" and probe.actions is not None:
            if probe.actions == ():
                return PlanResult(actions=None, expansions=probe.expansions, status="no_plan")
            if optional:
                self._used_optional_reprobe = True
                self._current_plan_is_optional_reprobe = True
            else:
                self._current_plan_is_optional_reprobe = False
            return PlanResult(
                actions=probe.actions,
                expansions=probe.expansions,
                status="probe",
                target=probe.target,
                score=probe.score,
                candidates=probe.candidates,
            )
        return probe

    def _make_plan(self, observation: Observation, deadline: float | None) -> PlanResult:
        if (
            self._used_optional_reprobe
            and not self._optional_reprobe_pending
            and self.extra_probe_log.get("hypothesis_count_after") is None
            and not self._holding_complete_probe()
        ):
            self._finalize_extra_probe(observation)
        bits = bits_to_int(observation.switch_bits)
        task = conservative_plan(
            self.layout,
            observation.agent_pos,
            bits,
            self.belief,
            self.expansion_cap,
            deadline,
        )
        self.last_expansions += task.expansions
        task_ok = task.status == "ok" and task.actions is not None

        if self.hypothesis_stopping and self._ul_pending:
            self._ul_pending = False
            U = len(task.actions) if task_ok else None
            if U is None:
                hypothesis_report: dict = {
                    "hypotheses": [],
                    "expansions": 0,
                    "any_undecided": False,
                    "decided_lengths": [],
                    "L": None,
                }
            else:
                hypothesis_report = hypothesis_goal_plan_lengths(
                    self.layout,
                    observation.agent_pos,
                    bits,
                    self.belief,
                    self.expansion_cap,
                    deadline,
                )
                self.last_expansions += int(hypothesis_report.get("expansions") or 0)
            self.stopping_log = ul_stopping_decision(U, task.status, hypothesis_report)
            self._optional_reprobe_pending = (
                self.stopping_log.get("decision") == "optional_probe"
            )

        if self._optional_reprobe_pending:
            # At most one extra probe, chosen by information-per-action, not
            # hidden rules. Permit is consumed even if no informative target exists.
            self._optional_reprobe_pending = False
            extra = select_active_probe(
                self.layout,
                observation.agent_pos,
                bits,
                self.belief,
                self.rng,
                self.expansion_cap,
                deadline,
            )
            optional = self._probe_result(extra, optional=True)
            if optional.status == "probe" and optional.actions is not None:
                self.extra_probe_target = optional.target
                self.extra_probe_log["intended_target"] = optional.target
                self.extra_probe_log["hypothesis_count_before"] = (
                    self.belief.total_hypothesis_count()
                )
                self.extra_probe_log["hypotheses_before"] = self.belief.snapshot()[
                    "hypotheses"
                ]
                return optional
            self.extra_probe_log["early_stop_reason"] = "no_informative_probe"
            self.extra_probe_log["hypothesis_count_before"] = (
                self.belief.total_hypothesis_count()
            )
            self.extra_probe_log["hypothesis_count_after"] = (
                self.belief.total_hypothesis_count()
            )
            self.extra_probe_log["information_gained"] = 0
            self.extra_probe_log["hypotheses_before"] = self.belief.snapshot()[
                "hypotheses"
            ]
            self.extra_probe_log["hypotheses_after"] = self.belief.snapshot()[
                "hypotheses"
            ]

        if task_ok:
            self._current_plan_is_optional_reprobe = False
            return PlanResult(
                actions=task.actions,
                expansions=task.expansions,
                status="task",
                target=None,
                score=None,
            )

        probe = self._probe_result(self._select_probe(observation, bits, deadline), optional=False)
        if probe.status == "probe" and probe.actions is not None:
            return probe
        if probe.status == "no_informative_probe" and task.status == "no_plan":
            return PlanResult(
                actions=None,
                expansions=task.expansions + probe.expansions,
                status="inconsistency",
                candidates=probe.candidates,
            )
        return PlanResult(
            actions=None,
            expansions=task.expansions + probe.expansions,
            status=task.status if task.status != "no_plan" else probe.status,
            candidates=probe.candidates,
        )

    def select_action(
        self,
        observation: Observation,
        deadline: float | None = None,
    ) -> Action:
        if not isinstance(observation, Observation):
            raise TypeError("agent.select_action accepts only Observation")
        hypotheses_before = self.belief.snapshot()
        if self._replan or self._plan_index >= len(self._plan):
            result = self._make_plan(observation, deadline)
            if result.actions is None:
                raise NoSafePlanError(
                    f"no conservative task plan or probe (status={result.status})"
                )
            self._plan = result.actions
            self._plan_index = 0
            self._plan_kind = result.status
            self._target = result.target
            self._score = result.score
            self._replan = False
            if not self._plan:
                raise NoSafePlanError("empty plan while not at goal")

        action = self._plan[self._plan_index]
        self._plan_index += 1
        was_optional = self._current_plan_is_optional_reprobe
        if was_optional:
            self.extra_probe_actions += 1
        if was_optional and self.complete_target_probe:
            if self._plan_index >= len(self._plan):
                self._replan = True
        elif action is Action.TOGGLE:
            self._replan = True
            if was_optional:
                # Frozen first-TOGGLE end for active_reprobe_retained.
                self._current_plan_is_optional_reprobe = False
                self._plan = ()
                self._plan_index = 0
                if self.extra_probe_log.get("early_stop_reason") is None:
                    self.extra_probe_log["early_stop_reason"] = "first_toggle"
        self.last_decision = Decision(
            action=action,
            plan_kind=self._plan_kind,
            target=self._target,
            score=self._score,
            expansions=self.last_expansions,
            hypotheses_before=hypotheses_before,
            plan_status=self._plan_kind,
            optional_reprobe=was_optional,
        )
        return action


def make_agent(
    layout: Layout,
    method: str,
    seed: int,
    expansion_cap: int,
) -> ModelBasedAgent:
    reset_memory = method.endswith("_reset")
    optional_reprobe = False
    complete_target_probe = False
    if method.startswith("complete_reprobe"):
        selector: Selector = "active"
        optional_reprobe = True
        complete_target_probe = True
    elif method.startswith("active_reprobe"):
        selector = "active"
        optional_reprobe = True
    elif method.startswith("active"):
        selector = "active"
    elif method.startswith("systematic"):
        selector = "systematic"
    elif method.startswith("random_informative"):
        selector = "random_informative"
    else:
        raise ValueError(f"unknown learning method {method!r}")
    return ModelBasedAgent(
        layout=layout,
        selector=selector,
        reset_memory=reset_memory,
        rng=Random(seed),
        expansion_cap=expansion_cap,
        optional_reprobe=optional_reprobe,
        complete_target_probe=complete_target_probe,
    )


def make_checkpoint_fork(
    layout: Layout,
    selector: Selector,
    seed: int,
    expansion_cap: int,
    *,
    optional_reprobe: bool,
    complete_target_probe: bool,
    belief: Belief,
    hypothesis_stopping: bool = False,
) -> ModelBasedAgent:
    """Identical public belief copy. Extra-probe decisions still use Belief only."""
    agent = ModelBasedAgent(
        layout=layout,
        selector=selector,
        reset_memory=False,
        rng=Random(seed),
        expansion_cap=expansion_cap,
        optional_reprobe=optional_reprobe,
        complete_target_probe=complete_target_probe,
        checkpoint_mode=True,
        hypothesis_stopping=hypothesis_stopping,
    )
    agent.belief = belief.clone()
    return agent


# Re-export for tests that check the learner error type.
__all__ = [
    "Decision",
    "ModelBasedAgent",
    "NoSafePlanError",
    "EmptyHypothesisError",
    "make_agent",
    "make_checkpoint_fork",
    "empty_extra_probe_log",
    "empty_stopping_log",
]
