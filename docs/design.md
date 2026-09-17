# Milestone A design notes

This is the implemented subset of `EXPERIENCE_LAB_PLAN.md`. The plan is a specification, not evidence that experiments already succeeded.

## World

One hand-built 7x7 map `tiny_two_switch`:

```text
#######
#S.0.1#
#.....#
###D###
#.....#
#....G#
#######
```

Switch identifiers are `sw0`/`sw1`. The door identifier is `door0`. Names do not encode control. The control area is the closed-door component of the start; both switches are in it and the goal is not.

## Ambiguities resolved (simplest options consistent with the plan)

1. Switch config integers use `sw_i` as bit `i` (`sw0` is the LSB). Canonical systematic order is `0, 1, 2, ..., 2^S-1`.
2. Active tie-breaking: uniform choice among maximum-score targets using `random.Random(seed)`.
3. The agent follows a committed plan until a toggle, plan exhaustion, or episode reset, then replans. Task plans are used whenever the conservative BFS finds a complete route.
4. `env.step` returns an empty `info` dict. Hidden rules stay on `SwitchWorld._hidden_rules` for the evaluator and tests.
5. The oracle is `evaluation.OracleController` plus `planner.oracle_plan`. Learning agents do not import or call it.
6. Evaluator predictive-accuracy tie-break, if used later: predict closed. Milestone A does not score offline accuracy in the pilot summary.
7. The door-closes-under-agent case cannot arise from public actions on this map (toggles require standing on a switch). Tests use a privileged `debug_set_state` helper.
8. Reset-memory restores the full prior at each episode start, then applies the free initial observation.
9. Pilot: 3 seeds, 3 fixed rules (`x0_and_x1`, `x0_xor_x1`, `x0`), 2 episodes, methods `active_retained`, `active_reset`, `systematic_retained`, `oracle`.
10. Matplotlib is installed as specified and unused in Milestone A.
11. No Gymnasium dependency. Reset/step follow a small Gymnasium-style contract: `(obs, reward, terminated, truncated, info)`.
12. Interrupted mid-episode runs are labeled `interrupted_time` and are not converted into ordinary episode timeouts.
13. Hypothesis names are the first canonical formula that produced each distinct truth table.
14. If conservative planning and probing both fail, the run is recorded as `inconsistency` rather than looping.
15. Probe-choice maps `probe_spur` and `probe_spur_mirror` are a frozen matched pair. Switch permutation `[1,0]` swaps public bit indices and rewrites the hidden rule so the physical mechanism is unchanged. Systematic order remains `0,1,2,...,2^S-1` over those public bits.
16. Random-informative samples uniformly among reachable configs with positive predicted information, then uses the shared probe planner.
17. Diagnostic instances are `(layout, requested_rule, permutation)`. Seeds repeat an instance for tie-breaking.
18. Random-informative sampling is uniform over the informative candidate set, not active-score tie-breaking. Intended targets are distinct from switch configs observed along the probe route.
19. Optional re-probe (`active_reprobe_retained`) may take at most one information-per-action probe at the start of later episodes even if a conservative task plan exists. The probe ends at the first `TOGGLE`; the agent then replans. Episode 0 matches exploit-immediately. The decision uses the public belief only.
20. Checkpoint complete-probe (`complete_reprobe_retained` / checkpoint forks) also uses at most one information-per-action extra probe per later episode, but executes the selected target configuration to completion. Intermediate observations update the belief. The first-TOGGLE end rule is not used. Episode 0 is a shared source-agent history; A and B copy that public belief after a physical reset.

## Modeling assumption

The posterior is uniform over remaining distinct truth tables. Filtering is exact and deterministic.

## Reward

`-0.01` per action, `+1.0` on the goal-reaching action, including that action's cost. Invalid actions consume a step. Default budget 256.
