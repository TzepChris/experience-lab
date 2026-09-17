"""Finite Boolean door-rule family represented as truth tables.

No formula strings are evaluated. Equivalent tables are stored once.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable


@dataclass(frozen=True, order=True)
class TruthTable:
    n_switches: int
    bits: tuple[bool, ...]
    name: str

    def __call__(self, switch_config: int) -> bool:
        return self.bits[switch_config]

    def predicts_open(self, switch_config: int) -> bool:
        return self.bits[switch_config]


def _table_from_fn(
    n_switches: int,
    name: str,
    fn: Callable[[int], bool],
) -> TruthTable:
    n_rows = 1 << n_switches
    bits = tuple(bool(fn(x)) for x in range(n_rows))
    return TruthTable(n_switches=n_switches, bits=bits, name=name)


def candidate_family(n_switches: int) -> tuple[TruthTable, ...]:
    """Distinct truth tables for x_i, NOT x_i, and pairwise AND/OR/XOR."""
    if n_switches < 1:
        raise ValueError("n_switches must be >= 1")
    tables: dict[tuple[bool, ...], TruthTable] = {}

    def add(name: str, fn: Callable[[int], bool]) -> None:
        table = _table_from_fn(n_switches, name, fn)
        tables.setdefault(table.bits, table)

    for i in range(n_switches):
        add(f"x{i}", lambda x, i=i: bool((x >> i) & 1))
        add(f"not_x{i}", lambda x, i=i: not bool((x >> i) & 1))

    for i in range(n_switches):
        for j in range(i + 1, n_switches):
            add(
                f"x{i}_and_x{j}",
                lambda x, i=i, j=j: bool((x >> i) & 1) and bool((x >> j) & 1),
            )
            add(
                f"x{i}_or_x{j}",
                lambda x, i=i, j=j: bool((x >> i) & 1) or bool((x >> j) & 1),
            )
            add(
                f"x{i}_xor_x{j}",
                lambda x, i=i, j=j: bool((x >> i) & 1) ^ bool((x >> j) & 1),
            )

    return tuple(tables.values())


def family_by_name(n_switches: int) -> dict[str, TruthTable]:
    return {table.name: table for table in candidate_family(n_switches)}


def table_by_name(n_switches: int, name: str) -> TruthTable:
    family = family_by_name(n_switches)
    if name not in family:
        known = ", ".join(sorted(family))
        raise KeyError(f"unknown rule {name!r}; known: {known}")
    return family[name]


def names_of(tables: Iterable[TruthTable]) -> tuple[str, ...]:
    return tuple(sorted(table.name for table in tables))


def permute_rule(table: TruthTable, perm: tuple[int, ...]) -> TruthTable:
    """Rewrite a rule so the physical mechanism is unchanged after switch relabeling.

    If new_positions[i] = old_positions[perm[i]], then new bit i is old bit perm[i].
    """
    n = table.n_switches
    if tuple(sorted(perm)) != tuple(range(n)):
        raise ValueError(f"permutation must be a rearrangement of 0..{n - 1}, got {perm}")
    inverse = [0] * n
    for new_i, old_i in enumerate(perm):
        inverse[old_i] = new_i
    bits = []
    for new_x in range(1 << n):
        old_x = 0
        for old_i, new_i in enumerate(inverse):
            if (new_x >> new_i) & 1:
                old_x |= 1 << old_i
        bits.append(table(old_x))
    bits_t = tuple(bits)
    for candidate in candidate_family(n):
        if candidate.bits == bits_t:
            return candidate
    raise ValueError("permuted rule left the candidate family")


def permute_rule_name(name: str, n_switches: int, perm: tuple[int, ...]) -> str:
    return permute_rule(table_by_name(n_switches, name), perm).name


def initially_closed_rule_names(n_switches: int = 2) -> tuple[str, ...]:
    """Candidate names whose truth table is closed at the all-off configuration."""
    return tuple(table.name for table in candidate_family(n_switches) if not table(0))
