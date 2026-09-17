"""SwitchWorld environment with a Gymnasium-style reset/step contract.

Hidden rules stay on the environment object. step() returns an empty info dict
so privileged data cannot leak through the public API.
"""

from __future__ import annotations

from dataclasses import dataclass

from experience_lab.layouts import Layout, tiny_two_switch_layout
from experience_lab.rules import TruthTable, table_by_name
from experience_lab.types import (
    DEFAULT_MAX_STEPS,
    GOAL_REWARD,
    MOVE_DELTAS,
    STEP_COST,
    Action,
    Observation,
    bits_to_int,
    int_to_bits,
)


@dataclass
class SwitchWorld:
    layout: Layout
    _hidden_rules: tuple[TruthTable, ...]
    max_steps: int = DEFAULT_MAX_STEPS
    _agent_pos: tuple[int, int] = (0, 0)
    _switch_bits: int = 0
    _step_index: int = 0
    _terminated: bool = False
    _truncated: bool = False

    def __post_init__(self) -> None:
        if len(self._hidden_rules) != self.layout.n_doors:
            raise ValueError("one hidden rule is required per door")
        for rule in self._hidden_rules:
            if rule.n_switches != self.layout.n_switches:
                raise ValueError("rule arity does not match switch count")

    @property
    def n_switches(self) -> int:
        return self.layout.n_switches

    def _door_open_bits(self, switch_bits: int | None = None) -> tuple[bool, ...]:
        bits = self._switch_bits if switch_bits is None else switch_bits
        return tuple(rule(bits) for rule in self._hidden_rules)

    def _observation(self) -> Observation:
        return Observation(
            width=self.layout.width,
            height=self.layout.height,
            static_grid=self.layout.static_grid,
            switch_ids=self.layout.switch_ids,
            door_ids=self.layout.door_ids,
            switch_positions=self.layout.switch_positions,
            door_positions=self.layout.door_positions,
            agent_pos=self._agent_pos,
            goal_pos=self.layout.goal,
            switch_bits=int_to_bits(self._switch_bits, self.layout.n_switches),
            door_open=self._door_open_bits(),
            step_index=self._step_index,
        )

    def reset(self, seed: int | None = None) -> Observation:
        del seed  # deterministic world; accepted for API compatibility
        self._agent_pos = self.layout.start
        self._switch_bits = 0
        self._step_index = 0
        self._terminated = False
        self._truncated = False
        return self._observation()

    def _can_enter(self, pos: tuple[int, int], door_open: tuple[bool, ...]) -> bool:
        if self.layout.is_wall(pos):
            return False
        door_i = self.layout.door_index_at(pos)
        if door_i is not None and not door_open[door_i]:
            return False
        return True

    def step(self, action: Action) -> tuple[Observation, float, bool, bool, dict]:
        if self._terminated or self._truncated:
            raise RuntimeError("step called after episode end; reset first")

        reward = -STEP_COST
        pos = self._agent_pos
        bits = self._switch_bits
        door_open = self._door_open_bits(bits)

        if action is Action.TOGGLE:
            switch_i = self.layout.switch_index_at(pos)
            if switch_i is not None:
                bits ^= 1 << switch_i
        else:
            delta = MOVE_DELTAS[action]
            nxt = (pos[0] + delta[0], pos[1] + delta[1])
            if self._can_enter(nxt, door_open):
                pos = nxt

        self._agent_pos = pos
        self._switch_bits = bits
        self._step_index += 1

        terminated = pos == self.layout.goal
        truncated = (not terminated) and self._step_index >= self.max_steps
        if terminated:
            reward += GOAL_REWARD
        self._terminated = terminated
        self._truncated = truncated
        return self._observation(), reward, terminated, truncated, {}

    def debug_set_state(
        self,
        agent_pos: tuple[int, int] | None = None,
        switch_bits: int | None = None,
    ) -> Observation:
        """Privileged test helper. Never used by learner code."""
        if agent_pos is not None:
            self._agent_pos = agent_pos
        if switch_bits is not None:
            self._switch_bits = switch_bits
        return self._observation()


def make_tiny_world(
    rule_name: str,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> SwitchWorld:
    layout = tiny_two_switch_layout()
    rule = table_by_name(layout.n_switches, rule_name)
    return SwitchWorld(layout=layout, _hidden_rules=(rule,), max_steps=max_steps)


def hidden_rule_names(env: SwitchWorld) -> tuple[str, ...]:
    """Evaluator/test accessor. Do not call from learner decision code."""
    return tuple(rule.name for rule in env._hidden_rules)
