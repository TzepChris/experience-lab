# Checkpoint U/L stopping results

Measured 2026-09-18. Method **C** is a **hand-designed U vs L stopping
rule**, not a learned policy. The frozen matrix is unchanged from
`configs/checkpoint_complete_probe.yaml`. Previous A-vs-B logs in
`results/checkpoint_complete_probe/` and
`docs/results_checkpoint_complete_probe.md` were not edited.

A, B, and C fork from the same public episode-0 belief. C computes `U`
from the conservative goal plan and `L` as the minimum decided
hypothetical goal-plan length, one complete remaining rule assignment at
a time. It probes only when `L < U`. Search-cap exhaustion is logged as
undecided and does not authorize a probe.

## Runtime

- Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0
- Tests: 77 passed
- Batch: **180/180 pairs completed** in **4.92s** of a 120s cap
- Logs: `results/checkpoint_ul_stopping/` (`events.jsonl`, `summary.json`,
  `manifest.json`, `checkpoint_report.json`, `checkpoints.jsonl`)
- No interrupted, failed, or incomplete prefixes. Success rate 1.0 on
  every compared later episode for A, B, and C.

Each pair shares one episode-0 acquisition. Later prefixes are 1, 2, 5,
and 10 episodes after that checkpoint. Lifetime = episode 0 + later
prefix. On this re-run, A-vs-B later deltas match the preserved
checkpoint-complete-probe batch exactly.

## Starting conditions (pooled, k=10)

Later delta is extra actions versus A. Negative helps. C is not required
to win.

| start | pairs | B vs A | C vs A | C vs B | C labeled | C helps | C equal | C wastes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| expensive_systematic | 42 | −56.4 | −62.1 | −5.8 | 4.3 | 27 | 15 | 0 |
| cheap_active | 60 | +16.8 | 0 | −16.8 | 0.5 | 0 | 60 | 0 |
| cheap_systematic_control | 48 | +11.7 | +1.2 | −10.5 | 1.4 | 0 | 33 | 15 |
| expensive_active_control | 30 | 0 | 0 | 0 | 6.6 | 0 | 30 | 0 |

Lifetime at k=10 (episode 0 + later). Success 1.0.

| start | life A | life B | life C | later A | later B | later C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| expensive_systematic | 195.4 | 139.1 | 133.3 | 176.4 | 120.1 | 114.3 |
| cheap_active | 91.3 | 108.1 | 91.3 | 83.0 | 99.8 | 83.0 |
| cheap_systematic_control | 129.3 | 140.9 | 130.4 | 117.5 | 129.2 | 118.7 |
| expensive_active_control | 204.0 | 204.0 | 204.0 | 182.0 | 182.0 | 182.0 |

Mean later-episode wall (seconds) is small for all three: about
0.004–0.012s per 10-episode prefix. C's extra work shows up as planning
overhead expansions (about 800–1100 nodes per k=10 prefix), not as a
wall-time problem under the 120s cap. Batch wall was 4.92s versus 3.16s
for the earlier A-vs-B-only run.

## Expensive systematic

Same recovery pattern as B, with a further cut on OR/XOR because C skips
the later distinguisher after the useful first probe.

Mean later / lifetime cost at k=10. Success 1.0. `probe_spur_mirror`
matched `probe_spur`.

| layout | rule | ep0 | A | B | C | C vs A | labeled C | life A | life B | life C |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| probe_spur | x0 | 20 | 200 | 70 | 70 | −130 | 3 | 220 | 90 | 90 |
| probe_spur | OR | 19 | 190 | 87 | 70 | −120 | 3 | 209 | 106 | 89 |
| probe_spur | XOR | 19 | 190 | 88 | 70 | −120 | 3 | 209 | 107 | 89 |
| probe_spur | AND | 24 | 200 | 200 | 200 | 0 | 7 | 224 | 224 | 224 |
| probe_spur | x1 | 24 | 190 | 190 | 190 | 0 | 7 | 214 | 214 | 214 |
| tiny_two_switch | x0 | 14 | 140 | 90 | 90 | −50 | 3 | 154 | 104 | 104 |
| tiny_two_switch | OR | 13 | 130 | 95 | 90 | −40 | 3 | 143 | 108 | 103 |
| tiny_two_switch | XOR | 13 | 130 | 96 | 90 | −40 | 3 | 143 | 109 | 103 |
| tiny_two_switch | x1 | 14 | 130 | 130 | 130 | 0 | 5 | 144 | 144 | 144 |

AND and far-unary `x1` stay equal to A: `L` is not proven shorter than
the conservative both-on route, or the extra probe sits on that path.

## Cheap active: C matches A

Several hypotheses still remain, but `U == L` already, so C exploits.
B still pays for completed-target probes.

k=10 on `probe_spur` (mirror identical). Success 1.0.

| rule | ep0 | A | B | C | C vs A | labeled C |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| x0 | 7 | 70 | 83 | 70 | 0 | 0 |
| OR | 7 | 70 | 99 | 70 | 0 | 0 |
| XOR | 7 | 70 | 100 | 70 | 0 | 0 |
| AND (tiny only; 6 pairs) | 14 | 140 | 140 | 140 | 0 | 5 |

On XOR seed 1, C logged `U = L = 7`, decision `exploit`, extra-probe
actions 0.

## Cheap systematic control: C is not uniformly better

15 of 48 pairs waste a little versus A (+1 to +5 later actions at k=10).
Those are swapped-ID `x1` and AND **acquisition** cells (`ep0 == oracle`),
not the expensive-systematic identity AND/`x1` cells with episode-0 cost
24. Bucket labels are episode-0 cost versus oracle episode 0, not current
`U`. See `docs/checkpoint_certificate_and_bucket_audit.md` and
`results/checkpoint_ul_stopping/bucket_assignments.json`.

## XOR diagnostic (not a ranking)

Worked pair `probe_spur|x0_xor_x1|perm1,0|seed1`, systematic episode 0
cost 19 (oracle 7). Remaining `{x0, OR, XOR}`.

- A later episodes stay at 19. k=10 later cost 190.
- B later 0: target `2`, reached, 3 labeled actions, length 7. Remaining
  `{OR, XOR}`. Later 1: target `3` (OR-vs-XOR distinguisher), configs
  `[2, 3]`, length 25. Later 2+: length 7. k=10 later cost 88.
- C later 0: `U=19`, `L=7`, decision `optional_probe`, same useful
  target `2`, reached, 3 extra actions, length 7, planning overhead 179
  expansions. Remaining `{OR, XOR}`. Later 1: `U=L=7`, decision
  `exploit`, extra-probe actions 0, length 7. The OR-vs-XOR
  distinguisher is skipped. Later 2+ stay at 7. k=10 later cost 70.

This is the expected diagnostic: C does the first informative completed
target and then stops when every remaining complete hypothesis agrees
that the conservative plan is already shortest.

## What this does not show

C is a hand-designed stopping rule on top of the existing
information-per-action selector. It is not a learned policy, not a new
probe heuristic, and not a claim that U vs L is optimal. On this frozen
matrix C recovered the expensive systematic OR/XOR cases more cheaply
than B and matched A on already-cheap active states, but it also wasted
a small amount on some cheap-systematic AND/x1 checkpoints. Episode 0
cost is still sunk. No transfer, rule drift, or dashboard.
