# Frozen closed-door re-probe matrix

Frozen before A-vs-B rankings. This file is separate from
`docs/probe_choice_matrix.md`. Do not edit `configs/probe_choice.yaml`.

## Rules

Every listed rule is closed at switch configuration `00`, so the free initial
observation does not immediately identify a NOT-rule:

- `x0` and `x1` — both unary physical mechanisms
- `x0_and_x1`, `x0_or_x1`, `x0_xor_x1`

Switch permutations `[0,1]` and `[1,0]` rewrite the hidden rule so physics is
unchanged. `x0` with a swap is still the original `x0` mechanism, now labeled
`x1` in public bits.

## Layouts

Same three maps as the probe-choice diagnostic: `tiny_two_switch`,
`probe_spur`, `probe_spur_mirror`.

## Comparison

- A `active_retained`: if a conservative task plan exists, execute it.
- B `active_reprobe_retained`: on episode 0, identical to A. At the start of
  each later episode, if any informative probe remains, take at most one
  using the information-per-action selector, then reconsider the task plan.
- `oracle`: evaluator-only reference.

A probe is one selected target configuration. Execution uses the shared probe
planner and **ends at the first TOGGLE** (existing agent rule). That consumes
the optional re-probe for the episode even if the toggle is an intermediate
configuration on the way to the selected target. The agent then replans; it
does not spend another optional re-probe in that episode. Required probing
when no safe plan exists is unchanged.

Seeds `1, 2, 3` repeat instances. Prefix costs use episodes 1, 2, 5, and 10
from the same 10-episode runs.
