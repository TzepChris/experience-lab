"""Exact version-space filtering over the finite door-rule family."""

from __future__ import annotations

from dataclasses import dataclass, field

from experience_lab.rules import TruthTable, candidate_family, family_by_name, names_of
from experience_lab.types import Observation, bits_to_int


class EmptyHypothesisError(RuntimeError):
    """Filtering removed every candidate for a door. Stationary in-family data should not do this."""


@dataclass
class Belief:
    n_switches: int
    door_ids: tuple[str, ...]
    hypotheses: dict[str, set[TruthTable]]
    evidence: dict[int, tuple[bool, ...]] = field(default_factory=dict)

    @classmethod
    def prior(cls, n_switches: int, door_ids: tuple[str, ...]) -> Belief:
        family = set(candidate_family(n_switches))
        return cls(
            n_switches=n_switches,
            door_ids=door_ids,
            hypotheses={door_id: set(family) for door_id in door_ids},
            evidence={},
        )

    def reset_to_prior(self) -> None:
        family = set(candidate_family(self.n_switches))
        self.hypotheses = {door_id: set(family) for door_id in self.door_ids}
        self.evidence = {}

    def clone(self) -> Belief:
        return Belief(
            n_switches=self.n_switches,
            door_ids=self.door_ids,
            hypotheses={k: set(v) for k, v in self.hypotheses.items()},
            evidence=dict(self.evidence),
        )

    def restore_snapshot(self, snapshot: dict) -> None:
        """Restore hypotheses and evidence from a public snapshot. No hidden fields."""
        family = family_by_name(self.n_switches)
        restored: dict[str, set[TruthTable]] = {}
        for door_id in self.door_ids:
            names = snapshot["hypotheses"][door_id]
            restored[door_id] = {family[name] for name in names}
        self.hypotheses = restored
        self.evidence = {
            int(config): tuple(outcomes)
            for config, outcomes in snapshot.get("evidence", {}).items()
        }

    def hypothesis_count(self, door_id: str) -> int:
        return len(self.hypotheses[door_id])

    def total_hypothesis_count(self) -> int:
        return sum(len(tables) for tables in self.hypotheses.values())

    def names(self, door_id: str) -> tuple[str, ...]:
        return names_of(self.hypotheses[door_id])

    def snapshot(self) -> dict:
        return {
            "hypotheses": {door_id: list(self.names(door_id)) for door_id in self.door_ids},
            "evidence": {
                str(config): list(outcomes) for config, outcomes in sorted(self.evidence.items())
            },
            "hypothesis_count": {
                door_id: self.hypothesis_count(door_id) for door_id in self.door_ids
            },
        }

    def update_from_observation(self, observation: Observation) -> bool:
        """Filter with a public observation. Returns True if evidence was new."""
        if not isinstance(observation, Observation):
            raise TypeError("belief update requires a public Observation")
        config = bits_to_int(observation.switch_bits)
        return self.update(config, observation.door_open)

    def update(self, switch_config: int, door_open: tuple[bool, ...]) -> bool:
        if len(door_open) != len(self.door_ids):
            raise ValueError("door observation arity mismatch")
        if switch_config in self.evidence:
            if self.evidence[switch_config] != door_open:
                raise EmptyHypothesisError(
                    f"contradictory observation at config {switch_config}: "
                    f"{self.evidence[switch_config]} vs {door_open}"
                )
            return False

        self.evidence[switch_config] = door_open
        for door_i, door_id in enumerate(self.door_ids):
            y = door_open[door_i]
            remaining = {h for h in self.hypotheses[door_id] if h(switch_config) == y}
            if not remaining:
                raise EmptyHypothesisError(
                    f"empty hypothesis set for {door_id} after config {switch_config} -> {y}"
                )
            self.hypotheses[door_id] = remaining
        return True

    def conservatively_open(self, door_id: str, switch_config: int) -> bool:
        tables = self.hypotheses[door_id]
        if not tables:
            raise EmptyHypothesisError(f"empty hypothesis set for {door_id}")
        return all(h(switch_config) for h in tables)

    def open_fraction(self, door_id: str, switch_config: int) -> float:
        tables = self.hypotheses[door_id]
        if not tables:
            raise EmptyHypothesisError(f"empty hypothesis set for {door_id}")
        return sum(1 for h in tables if h(switch_config)) / len(tables)

    def identified_name(self, door_id: str) -> str | None:
        tables = self.hypotheses[door_id]
        if len(tables) != 1:
            return None
        return next(iter(tables)).name
