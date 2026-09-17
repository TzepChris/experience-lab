# Probe-choice diagnostic results

Measured 2026-09-17. The matrix in `docs/probe_choice_matrix.md` and
`configs/probe_choice.yaml` was frozen before these rankings were inspected.
Maps were not edited afterward.

## Runtime

- Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0
- Tests: `40 passed in 0.15s`
- Batch: **378/378 completed** in **4.90s** of a 120s cap
- Logs: `results/probe_choice/events.jsonl`, `summary.json`, `manifest.json`, `report.json`
- No interrupted or failed runs. Equal and negative results are kept.

Seeds `1, 2, 3` are tie-breaking repeats of the same instance, not independent
worlds. An instance is `(layout, requested_rule, permutation)`. Permutation
preserves physics and changes public bit indices.

## When selection does not change cost

On `tiny_two_switch` with identity labels, every learner matched the oracle:
AND 14, XOR 9, `x0` 9. That replicates the Milestone A pilot.

On both spur maps with identity labels, `sw0` is the near on-path switch.
Active, systematic, and random all took that first probe for XOR and `x0`
(excess 0). AND paid a 2-action mean excess for retained learners (episode 0
cost 24, episode 1 cost 20) versus 4 for reset (both episodes 24).

`probe_spur` and `probe_spur_mirror` matched on every identity and swap cell.
The mirror did not introduce a left/right artifact.

## When selection does change cost

Canonical systematic order always tries config `1` (`sw0` only) first. After
the swap permutation, `sw0` is the far spur. Active still prefers the cheaper
equal-information probe (config `2`, near switch).

Mean excess over oracle, retained memory, 3 seeds × 2 episodes:

| instance | active | systematic | random-informative |
| --- | ---: | ---: | ---: |
| spur/mirror XOR + swap | 0 | 12 | 12 |
| spur/mirror `x0` + swap | 0 | 13 | 13 |
| spur/mirror AND + swap | 2 | 0 | 0 |
| tiny XOR + swap | 0 | 4 | 4 |
| tiny `x0` + swap | 0 | 5 | 5 |

Active is cheaper when the cheap probe opens the door (XOR, unary near-switch).
Systematic is cheaper on AND + swap, because visiting the far switch first is
the oracle AND route; active's cheap near probe forces a later round trip.

## Real traces

**Active gain** (`probe_spur|x0_xor_x1|perm1,0`, seed 1, episode 0):
active first probed config 2 (near, 3 actions, door opened) then walked to the
goal, **7** actions:
`EAST, EAST, TOGGLE, EAST, EAST, SOUTH, SOUTH`.
Systematic first probed config 1 (far spur, 7 actions, door also opened for XOR)
and walked back, **19** actions. Excess +12 is exactly that detour.

**Active loss** (`probe_spur|x0_and_x1|perm1,0`, seed 1, episode 0):
same first probes (active 2, systematic 1). AND stays closed after one switch.
Active then had to travel to the spur and back: **24** actions. Systematic
toggled the spur first, then the near switch beside the door: **20** actions,
matching the oracle. The cheap probe cost 4 extra actions.

**Retained memory** (`probe_spur|x0_and_x1|perm0,1`, seed 1, episode 1):
reset re-probed config 1 and repeated the 24-action round trip. Retained skipped
probing and executed the oracle AND order (spur then near): **20** actions.

On XOR + swap, retained systematic still costs 19 on episode 2: evidence says
the far-only config opens the door, so the task planner keeps using that valid
but expensive opening. Reset random can re-sample a near probe and do better.
Memory helps when it encodes a cheaper sufficient configuration, not merely
because it is retained.

## Pooled means (not independent worlds)

These average 18 instances × 3 seeds × 2 episodes. Use the instance table, not
this line, as the scientific unit.

| method | mean steps | mean excess vs oracle |
| --- | ---: | ---: |
| oracle | 11.11 | 0 |
| active_retained | 11.56 | 0.44 |
| active_reset | 12.00 | 0.89 |
| random_informative_reset | 13.89 | 2.78 |
| random_informative_retained | 14.61 | 3.50 |
| systematic_retained | 14.61 | 3.50 |
| systematic_reset | 14.83 | 3.72 |

Active's pooled edge is concentrated on swapped unary/XOR instances. It is not
a uniform win, and AND + swap is a real loss.

## Conclusion

Experiment selection changes action cost when equally informative probes have
very different travel, and when the first probe is or is not on a shortest
satisfying path. Canonical order is sensitive to switch IDs. The original
control map hid that because the first canonical probe was already cheap and
on-path. Active must not be declared better in general from this matrix.
