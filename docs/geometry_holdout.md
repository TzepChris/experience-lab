# Frozen 20-map geometry holdout

Frozen 2026-09-18 **before** A/B/C rankings on these maps. Generation
rules and seeds are in `src/experience_lab/geometry.py` and
`configs/geometry_holdout_maps.yaml`. The development matrix
`tiny_two_switch` / `probe_spur` / `probe_spur_mirror` remains regression
data and is not replaced.

## Sampling

Each geometry seed `{1..20}` is one independent sampling unit
(`holdout_01` ... `holdout_20`). Inside a map, the paired conditions are:

- five initially closed rules
- ID permutations `[0,1]` and `[1,0]`
- acquisition `systematic_retained` and `active_retained`

Agent RNG is fixed at seed 1. It is not a sampling unit.

## Generation

A control room, optional spur, one door, and a goal shaft. Draws vary
control width/height, spur length, goal-shaft length, switch placement,
and horizontal mirror. Two switches, one door. Switches and start stay in
the closed-door control area; the goal does not.

A draw is accepted only if the oracle reaches the goal under every
initially closed two-switch rule. Failed draws are skipped inside the
same `Random(seed)` stream. Method costs are not an acceptance input.

## Protocol

Same paired public-checkpoint protocol as A/B/C: one episode-0
acquisition, then forks

- A `checkpoint_exploit`
- B `checkpoint_complete_reprobe`
- C `checkpoint_ul_stopping` (hand-designed U vs L stopping rule)

C certificates: `certified_no_headroom`, `shorter_plan_witness`,
`undecided`. Cap exhaustion may still exploit; it is not certified
optimality. Bucket labels stay evaluator-only.

Do not tune C after inspecting holdout rankings.
