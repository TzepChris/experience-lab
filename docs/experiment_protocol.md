# Experiment protocol

## E0 pilot

- Layout: `tiny_two_switch`
- Hidden rules: `x0_and_x1`, `x0_xor_x1`, `x0`
- Seeds: 1, 2, 3 (agent RNG; the world is deterministic)
- Episodes per run: 2 (physical reset; rules persist)
- Methods: `active_retained`, `active_reset`, `systematic_retained`, `oracle`
- Wall-time cap: 120 seconds of experiment execution
- Planner expansion cap: 10,000 nodes per search

## Probe-choice diagnostic

Frozen in `configs/probe_choice.yaml` and `docs/probe_choice_matrix.md` before rankings were inspected.

- Layouts: `tiny_two_switch` (control), `probe_spur`, `probe_spur_mirror`
- Same three rules, with switch permutations `[0,1]` and `[1,0]` that rewrite the hidden rule so physics is unchanged
- Seeds 1, 2, 3 are tie-breaking repeats, not independent worlds
- Methods add `systematic_reset` and `random_informative_{retained,reset}`
- Rewards, episode budget (256), planner cap, and 120s wall cap unchanged

A distinct instance is `(layout, requested_rule, permutation)`. Report excess actions over the oracle on that instance. Do not pool seeds as extra environments.

## Closed-door re-probe comparison

Frozen in `configs/reprobe_closed_door.yaml` and `docs/reprobe_matrix.md`.
Do not edit `configs/probe_choice.yaml`.

- Same three layouts; rules `x0`, `x1`, AND, OR, XOR (every family member closed at `00`)
- Both unary mechanisms; permutations preserve physics
- Methods: `active_retained` (A: exploit when a safe plan exists),
  `active_reprobe_retained` (B: at most one later-episode informative probe),
  `oracle`
- 10 episodes; prefix costs at 1, 2, 5, 10; success reported with cost
- Random-informative 100-seed audit on a fixed belief, written separately

A probe ends at the first `TOGGLE`. Extra exploration actions count toward
prefix cost. Incomplete prefixes are not converted into low costs.

## Checkpoint complete-probe comparison

Frozen in `configs/checkpoint_complete_probe.yaml` and
`docs/checkpoint_complete_probe.md`. Do not edit the probe-choice or
closed-door re-probe configs.

- Same five initially closed rules and three layouts
- Episode 0 collected from `systematic_retained` and `active_retained`
- A exploit vs B complete-target extra probe, forked from that public belief
- B finishes the selected target configuration; beliefs update after every
  intermediate observation
- Later-episode prefixes 1, 2, 5, 10 plus shared episode-0 cost and lifetime
  totals
- Labeled probe actions are reported separately from additional cost versus A
- Expensive-systematic and cheap-active starts are reported separately
- Wall-time cap: 120 seconds

## Checkpoint U/L stopping comparison

Frozen in `configs/checkpoint_ul_stopping.yaml` and
`docs/checkpoint_ul_stopping.md`. Same matrix as the A-vs-B checkpoint
experiment. Do not edit the earlier frozen configs.

- A, B, and C fork from the same public episode-0 belief
- C is a hand-designed U vs L stopping rule, not a learned policy
- Probe only when a decided hypothetical plan is shorter than the
  conservative plan; search-cap exhaustion is undecided
- Prefixes 1, 2, 5, 10; success, lifetime action costs, and wall time
- C is not required to win
- Wall-time cap: 120 seconds

## Geometry holdout (20 maps)

Frozen in `configs/checkpoint_geometry_holdout.yaml`,
`configs/geometry_holdout_maps.yaml`, and `docs/geometry_holdout.md`
before method rankings. Generation rules live in
`src/experience_lab/geometry.py`. Do not edit earlier frozen configs.

- 20 geometry seeds are the independent sampling units
- Two switches, one door, five initially closed rules, both ID permutations
- Maps accepted by oracle solvability only, not by method cost
- Same A/B/C paired public-checkpoint protocol; agent RNG seed 1
- C certificates distinguish certified_no_headroom, shorter_plan_witness,
  and undecided. Compute-cap exploits are not certified optimality
- Acquisition buckets are episode-0 cost versus oracle episode 0, not U
- Do not tune C after inspecting holdout rankings
- Wall-time cap: 120 seconds

Methods that learn share the candidate family, filter, conservative planner, probe planner, observations, and action costs. Only experiment selection and memory reset differ. The oracle is a privileged reference, not a learning competitor.

## Recording

Each batch writes:

- `manifest.json` — UTC time, git status if available, dependency versions, hardware, config, completion status
- `events.jsonl` — public observations, hypotheses before/after, actions, rewards, plan kind
- `summary.json` — per-run status, steps, returns, hypothesis counts, expansions, wall time

True rule names appear in evaluator run headers only. They are not fields on `Observation` and are not passed into `ModelBasedAgent`.

## Failure labels

- `completed` — finished the scheduled episodes
- `interrupted_time` — hit the wall-time cap
- `planner_cap` / `time_limit` — planner stopped by its own cap
- `empty_hypothesis` — filtering emptied a door's version space
- `inconsistency` — no conservative task plan and no informative probe
- `exception` — software error

Infrastructure failures are not rewritten as ordinary RL timeouts.
