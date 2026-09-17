# Closed-door re-probe comparison

Measured 2026-09-17. The matrix in `docs/reprobe_matrix.md` and
`configs/reprobe_closed_door.yaml` was frozen before A-vs-B rankings were
inspected. `configs/probe_choice.yaml` was not edited.

## Runtime

- Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0
- Tests: `55 passed in 2.70s`
- Batch: **270/270 completed** in **15.13s** of a 120s cap
- Logs: `results/reprobe_closed_door/` (`events.jsonl`, `summary.json`,
  `manifest.json`, `reprobe_report.json`, `random_informative_audit.json`)
- No interrupted, failed, or incomplete prefixes. Every compared episode
  reached the goal, so extra cost is extra actions, not hidden failures.

Methods: A `active_retained` (exploit when a conservative plan exists),
B `active_reprobe_retained` (at most one later-episode information-per-action
probe, ending at the first `TOGGLE`), plus evaluator-only `oracle`.

Seeds `1, 2, 3` repeat instances. An instance is
`(layout, requested_rule, permutation)`. Tables below pool the two
permutations of the same physical rule.

## Random-informative audit (fixed belief)

Belief: `probe_spur` start, config `0` already observed closed. Candidate
set is the three unobserved reachable configs with positive predicted
information: `{1, 2, 3}`.

100 independent seeds (`Random(0)` … `Random(99)`):

| intended target | draws | travel cost | U | U/cost |
| ---: | ---: | ---: | ---: | ---: |
| 1 (near) | 36 | 3 | 0.971 | 0.324 |
| 2 (far) | 35 | 7 | 0.971 | 0.139 |
| 3 (both) | 29 | 12 | 0.722 | 0.060 |

Sampling is uniform among positive-information configs, not active-score
tie-breaking. The three scores are different; active would pick target `1`
only. All 29 draws whose intended target is `3` also visit an incidental
toggle config `1` or `2` on the route. Those route observations are not the
selected target.

## Prefix cost (success = 1.0 on every cell)

Episode 0 is identical for A and B. Deltas appear at prefix 2. No cell with
a positive extra at k=2 recovers it by k=5 or k=10.

### `probe_spur` (mirror matches on every cell)

Mean capped cost over 6 runs (2 permutations × 3 seeds). Success rate 1.0.

| physical rule | k | A exploit | B re-probe | delta | extra probe actions | oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| x0 | 1 | 7 | 7 | 0 | 0 | 7 |
| x0 | 2 | 14 | 27 | +13 | 7 | 14 |
| x0 | 5 | 35 | 48 | +13 | 7 | 35 |
| x0 | 10 | 70 | 83 | +13 | 7 | 70 |
| x1 | 1 | 24 | 24 | 0 | 0 | 19 |
| x1 | 2 | 43 | 43 | 0 | 7 | 38 |
| x1 | 5 | 100 | 100 | 0 | 7 | 95 |
| x1 | 10 | 195 | 195 | 0 | 7 | 190 |
| AND | 1 | 24 | 24 | 0 | 0 | 20 |
| AND | 2 | 44 | 44 | 0 | 7 | 40 |
| AND | 5 | 104 | 104 | 0 | 7 | 100 |
| AND | 10 | 204 | 204 | 0 | 7 | 200 |
| OR | 1 | 7 | 7 | 0 | 0 | 7 |
| OR | 2 | 14 | 26 | +12 | 7 | 14 |
| OR | 5 | 35 | 47 | +12 | 16 | 35 |
| OR | 10 | 70 | 82 | +12 | 31 | 70 |
| XOR | 1 | 7 | 7 | 0 | 0 | 7 |
| XOR | 2 | 14 | 26 | +12 | 7 | 14 |
| XOR | 5 | 35 | 47 | +12 | 16 | 35 |
| XOR | 10 | 70 | 82 | +12 | 31 | 70 |

`probe_spur_mirror` is the same table.

### `tiny_two_switch`

| physical rule | k | A exploit | B re-probe | delta | extra probe actions | oracle |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| x0 | 1 | 9 | 9 | 0 | 0 | 9 |
| x0 | 2 | 18 | 23 | +5 | 5 | 18 |
| x0 | 10 | 90 | 95 | +5 | 5 | 90 |
| x1 | 1 | 14 | 14 | 0 | 0 | 13 |
| x1 | 2 | 27 | 27 | 0 | 5 | 26 |
| x1 | 10 | 131 | 131 | 0 | 5 | 130 |
| AND | 1 | 14 | 14 | 0 | 0 | 14 |
| AND | 2 | 28 | 28 | 0 | 5 | 28 |
| AND | 10 | 140 | 140 | 0 | 5 | 140 |
| OR | 1 | 9 | 9 | 0 | 0 | 9 |
| OR | 2 | 18 | 22 | +4 | 5 | 18 |
| OR | 10 | 90 | 94 | +4 | 29 | 90 |
| XOR | 1 | 9 | 9 | 0 | 0 | 9 |
| XOR | 2 | 18 | 22 | +4 | 5 | 18 |
| XOR | 10 | 90 | 94 | +4 | 29 | 90 |

## Where re-probing helps, wastes, or is recovered

**No cost win.** B never undercuts A on this matrix. Identification can
improve while episode length stays the same.

**On-path / cost-neutral (`x1`, AND):** after episode 0 both agents have a
conservative both-on plan and two remaining hypotheses. B's extra probe
target is config `2` (one `TOGGLE`). That toggle is already on A's task
path, so episode 1 stays 19 (`x1`) or 20 (AND) on the spur. Later episodes
match. The extra 7 probe actions are not recovered because they were never
an added detour.

**Off-path waste (`x0`, OR, XOR):** episode 0 already found a cheap
sufficient opening (near switch, 7 actions on the spur, 9 on tiny). A's
stopping rule then repeats that cheap task. B still takes the remaining
informative probe. On `probe_spur|x0_xor_x1|perm0,1` seed 1:

- A episode 1: 7 task actions, 3 hypotheses remain
- B episode 1: 7 extra probe actions to far config `2`, then a 12-action
  return, **19** total, 2 hypotheses remain
- Prefix-2 delta **+12**; prefix-10 delta still **+12**

Later B episodes on XOR/OR keep selecting intended target `3`, but the
probe **ends at the first TOGGLE**, which is an already-observed
intermediate. The agent then exploits the cheap door. Those later
"extra" actions sit on the task path (episode length 7 again). They do
not identify XOR versus OR, and they do not repay the episode-1 detour.

`x0` wastes +13 on the spur (+5 on tiny) once, then has no remaining
informative probe. Also never repaid.

## What this does not show

A is already the information-per-action agent. The expensive conservative
plan from the probe-choice diagnostic was systematic-on-XOR-after-swap,
not active. Optional re-probing from a *cheap* sufficient plan only buys
a distinguisher. On these maps that distinguisher is either on the
existing route (no savings) or off it (a detour that later episodes do
not amortize). The first-`TOGGLE` end rule also blocks completing a
two-toggle distinguisher.

Pooled means (900 episodes each): oracle 11.60, A 11.73, B 12.31. Use the
layout-by-rule table, not this line.
