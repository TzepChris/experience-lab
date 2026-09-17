# Checkpoint complete-probe results

Measured 2026-09-18. The matrix in `docs/checkpoint_complete_probe.md` and
`configs/checkpoint_complete_probe.yaml` was frozen before these rankings
were inspected. Existing probe-choice and closed-door re-probe results were
not edited.

The previous re-probe comparison started from **active** episode-0 states
that were already cheap. This batch starts from real episode-0 histories of
both systematic and active agents, then forks A (exploit) and B (complete
the selected target, then exploit) from that public belief.

## Runtime

- Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0
- Tests: 64 passed
- Batch: **180/180 pairs completed** in **3.16s** of a 120s cap
- Logs: `results/checkpoint_complete_probe/` (`events.jsonl`, `summary.json`,
  `manifest.json`, `checkpoint_report.json`, `checkpoints.jsonl`)
- No interrupted, failed, or incomplete prefixes. Success rate 1.0 on every
  compared later episode, so extra cost is extra actions, not hidden failures.

Each pair shares one episode-0 acquisition. Later prefixes are 1, 2, 5, and
10 episodes after that checkpoint. Lifetime = episode 0 + later prefix.
Labeled probe actions are steps marked as B's extra probe. Additional
actions versus A are B's extra later-episode cost, including any longer
task path after the probe.

## Starting conditions (pooled)

| start | pairs | k=10 later delta | labeled probe | additional vs A | helps | equal | wastes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| expensive_systematic | 42 | −56.4 | 8.6 | −56.4 | 27 | 15 | 0 |
| cheap_active | 60 | +16.8 | 12.2 | +16.8 | 0 | 6 | 54 |
| cheap_systematic_control | 48 | +11.7 | 8.8 | +11.7 | 0 | 6 | 42 |
| expensive_active_control | 30 | 0 | 6.6 | 0 | 0 | 30 | 0 |

`probe_spur_mirror` matched `probe_spur` on every cell. Expensive systematic
cells are the swapped-ID copies (canonical first probe is the far switch).
Identity systematic is the cheap-systematic control.

## Expensive systematic: completed probes can recover

After swap, systematic's episode 0 probes public config `1` (far). That
observation often leaves a conservative plan that repeats the expensive
opening. A copies that plan forever. B is allowed one complete-target
information-per-action probe per later episode.

Mean later / lifetime cost at k=10. Success 1.0.

| layout | rule | ep0 | A later | B later | delta | labeled | lifetime A | lifetime B |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| probe_spur | x0 | 20 | 200 | 70 | −130 | 3 | 220 | 90 |
| probe_spur | OR | 19 | 190 | 87 | −103 | 15 | 209 | 106 |
| probe_spur | XOR | 19 | 190 | 88 | −102 | 15 | 209 | 107 |
| probe_spur | AND | 24 | 200 | 200 | 0 | 7 | 224 | 224 |
| probe_spur | x1 | 24 | 190 | 190 | 0 | 7 | 214 | 214 |
| tiny_two_switch | x0 | 14 | 140 | 90 | −50 | 3 | 154 | 104 |
| tiny_two_switch | OR | 13 | 130 | 95 | −35 | 9 | 143 | 108 |
| tiny_two_switch | XOR | 13 | 130 | 96 | −34 | 9 | 143 | 109 |
| tiny_two_switch | x1 | 14 | 130 | 130 | 0 | 5 | 144 | 144 |

Mirror matches the spur table. Tiny AND is not in this bucket: identity and
swap episode-0 costs already match the oracle (14), so those checkpoints are
cheap-active / cheap-systematic controls.

**Worked pair:** `probe_spur|x0_xor_x1|perm1,0|seed1`, systematic episode 0
cost 19 (oracle 7). Remaining `{x0, OR, XOR}`. A later episodes stay at 19.

- B later 0: intended target `2`, reached, 1 toggle, configs `[2]`, 3 labeled
  actions, episode length 7. Remaining `{OR, XOR}`.
- B later 1: intended target `3`, reached after configs `[2, 3]`, 2 toggles,
  12 labeled actions, episode length 25. Remaining `{XOR}`.
- B later 2+: `no_informative_probe`, episode length 7.

k=10: A 190, B 88, additional −102. Labeled probes were 15; the savings are
larger than the labeled count because later exploits became cheap. The
episode-0 cost of 19 is not refunded, but it is recovered in lifetime totals
(209 vs 107).

AND and far-unary `x1` stay equal: the remaining conservative plan is already
the both-on route. B's extra probe is on that path (labeled 7, additional 0).

## Cheap active: completed probes add cost

These are the states the previous comparison already tested, now with
**completed** targets instead of first-TOGGLE. Negative result preserved,
and completing the target makes OR/XOR waste more, not less.

k=10 on `probe_spur` (mirror identical). Success 1.0.

| rule | ep0 | A later | B later | delta | labeled | additional |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| x0 | 7 | 70 | 83 | +13 | 7 | +13 |
| OR | 7 | 70 | 99 | +29 | 19 | +29 |
| XOR | 7 | 70 | 100 | +30 | 19 | +30 |
| AND (tiny only; 6 pairs) | 14 | 140 | 140 | 0 | 5 | 0 |

On XOR, additional (30) exceeds labeled (19): the extra probe finishes
target `3`, then the task path back from that config is longer than A's
cheap 7-step exploit. The previous first-TOGGLE run left a +12 XOR/OR
premium that never grew. Completing the two-toggle distinguisher spends
that probe for real and does not repay it.

`x0` wastes once (+13 spur, +5 tiny); later episodes have no remaining
informative target.

## Other controls

**Cheap systematic (identity labels):** same waste pattern as cheap active,
smaller because only the identity permutation is in this bucket.

**Expensive active (AND on spur/mirror, `x1` everywhere):** episode 0 already
paid more than oracle, but A later is already as short as B. Labeled extra
probes sit on A's task path. Additional 0.

## Labeled probe vs additional cost

- Expensive systematic XOR swap: labeled 15, additional −102 (probes buy a
  cheaper later policy).
- Cheap active XOR: labeled 19, additional +30 (probes plus a longer return).
- Expensive systematic AND: labeled 7, additional 0 (on-path).

Do not treat labeled probe steps as the cost of re-probing.

## What this does not show

No new selection heuristic. Extra probes still use information-per-action.
The win is only recovery from systematic's expensive sufficient plan after
ID swap. From an already-cheap active plan, completing remaining experiments
still adds cost. Episode 0 of an expensive systematic run remains sunk; the
saving is on later episodes.
