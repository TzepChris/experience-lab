# Closed-door re-probe comparison

Measured 2026-09-17. The matrix in `docs/reprobe_matrix.md` and
`configs/reprobe_closed_door.yaml` was frozen before these rankings were
inspected. `configs/probe_choice.yaml` was not edited.

## Runtime

- Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0
- Tests: 55 passed (`pytest -q`)
- Batch: **270/270 completed** in **15.74s** of a 120s cap
- Logs: `results/reprobe_closed_door/` (`events.jsonl`, `summary.json`,
  `manifest.json`, `reprobe_report.json`, `random_informative_audit.json`)
- No interrupted, failed, or incomplete prefixes

A is `active_retained` (exploit when a conservative plan exists). B is
`active_reprobe_retained` (episode 0 matches A; later episodes may take at
most one information-per-action probe, ending at the first TOGGLE). Prefix
costs are cumulative actions over the same 10-episode runs. Every extra
exploration action is included. All cells below have success rate 1.0, so
failures cannot look like savings.

Each physical cell pools 2 switch-ID permutations × 3 seeds = 6 runs.
Permutation preserves physics; identity and swap matched on every cell.

## Random-informative audit (fixed belief)

On `probe_spur`, start `00`, after observing closed: candidate set `{1,2,3}`.
Config `0` is observed (score `null`) and is not a candidate. Predicted
information-per-action scores are **not** equal (`1`: 0.324, `2`: 0.139,
`3`: 0.060), so uniform sampling here is not active-score tie-breaking.

100 independent seeds, intended targets: `1` 36, `2` 35, `3` 29.

Intended target is the sampled end config. Route observations are separate.
Seed 5 selected target `3` (`11`); the first toggle observed config `1`,
which is an incidental route observation, not the selected target.

## Prefix costs by layout and physical rule

Mean cumulative capped cost. Extra = mean extra-probe actions in the prefix.

### `tiny_two_switch`

| rule | k | A | B | oracle | B−A | extra | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| x0 | 1 | 9 | 9 | 9 | 0 | 0 | equal |
| x0 | 2 | 18 | 23 | 18 | +5 | 5 | wastes |
| x0 | 5 | 45 | 50 | 45 | +5 | 5 | wastes |
| x0 | 10 | 90 | 95 | 90 | +5 | 5 | wastes |
| x1 | 1 | 14 | 14 | 13 | 0 | 0 | equal |
| x1 | 2 | 27 | 27 | 26 | 0 | 5 | equal |
| x1 | 5 | 66 | 66 | 65 | 0 | 5 | equal |
| x1 | 10 | 131 | 131 | 130 | 0 | 5 | equal |
| AND | 1 | 14 | 14 | 14 | 0 | 0 | equal |
| AND | 2 | 28 | 28 | 28 | 0 | 5 | equal |
| AND | 5 | 70 | 70 | 70 | 0 | 5 | equal |
| AND | 10 | 140 | 140 | 140 | 0 | 5 | equal |
| OR | 1 | 9 | 9 | 9 | 0 | 0 | equal |
| OR | 2 | 18 | 22 | 18 | +4 | 5 | wastes |
| OR | 5 | 45 | 49 | 45 | +4 | 14 | wastes |
| OR | 10 | 90 | 94 | 90 | +4 | 29 | wastes |
| XOR | 1 | 9 | 9 | 9 | 0 | 0 | equal |
| XOR | 2 | 18 | 22 | 18 | +4 | 5 | wastes |
| XOR | 5 | 45 | 49 | 45 | +4 | 14 | wastes |
| XOR | 10 | 90 | 94 | 90 | +4 | 29 | wastes |

### `probe_spur` (mirror identical)

| rule | k | A | B | oracle | B−A | extra | verdict |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| x0 | 1 | 7 | 7 | 7 | 0 | 0 | equal |
| x0 | 2 | 14 | 27 | 14 | +13 | 7 | wastes |
| x0 | 5 | 35 | 48 | 35 | +13 | 7 | wastes |
| x0 | 10 | 70 | 83 | 70 | +13 | 7 | wastes |
| x1 | 1 | 24 | 24 | 19 | 0 | 0 | equal |
| x1 | 2 | 43 | 43 | 38 | 0 | 7 | equal |
| x1 | 5 | 100 | 100 | 95 | 0 | 7 | equal |
| x1 | 10 | 195 | 195 | 190 | 0 | 7 | equal |
| AND | 1 | 24 | 24 | 20 | 0 | 0 | equal |
| AND | 2 | 44 | 44 | 40 | 0 | 7 | equal |
| AND | 5 | 104 | 104 | 100 | 0 | 7 | equal |
| AND | 10 | 204 | 204 | 200 | 0 | 7 | equal |
| OR | 1 | 7 | 7 | 7 | 0 | 0 | equal |
| OR | 2 | 14 | 26 | 14 | +12 | 7 | wastes |
| OR | 5 | 35 | 47 | 35 | +12 | 16 | wastes |
| OR | 10 | 70 | 82 | 70 | +12 | 31 | wastes |
| XOR | 1 | 7 | 7 | 7 | 0 | 0 | equal |
| XOR | 2 | 14 | 26 | 14 | +12 | 7 | wastes |
| XOR | 5 | 35 | 47 | 35 | +12 | 16 | wastes |
| XOR | 10 | 70 | 82 | 70 | +12 | 31 | wastes |

`probe_spur_mirror` matched `probe_spur` on every rule and prefix.

Instance count at k=10: 0 helps, 36 equal, 54 wastes (90 paired instances).

## Where re-probing helps, wastes, or recovers

Episode 0 is identical, as specified.

**Equal (AND, far unary `x1`).** B does take an extra probe on episode 1
(`extra` 5 on the tiny map, 7 on the spur). Net episode cost does not change.
Those extra actions sit on a later-episode route that A already uses. A’s
episode 1 on `x1` is already oracle-length (tiny 13, spur 19); B does not
beat it. The expensive first episode is already sunk for both.

**Wastes, one extra probe (`x0`).** After the cheap first probe, a conservative
plan already exists. B’s extra probe of the remaining distinguisher identifies
the unary rule, then later episodes match A. The episode-1 premium stays
through k=10: +5 tiny, +13 spur. Extra-probe counts stop after episode 1
(`extra` 5 or 7 at k=2 and k=10). The cost is not recovered, because A’s
later episodes were already oracle-length.

**Wastes, repeated extra probes (OR, XOR).** A exploits the cheap opening and
never needs another probe. Remaining tables still disagree on unobserved
configs, so B keeps taking the optional probe on later episodes (`extra`
grows to 29 tiny / 31 spur by k=10). Net premium is unchanged after episode 1
(+4 tiny, +12 spur): later extra-probe steps partly replace walking A would
have done anyway, but they never cancel the first detour. Cost is not
recovered.

Re-probing never produced a lower cumulative cost on this frozen matrix. It
also never reduced success: both methods succeeded on every episode.
Pooled per-episode means (A 11.73, B 12.31) hide the rule split above and
are not a general ranking.
