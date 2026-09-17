# Geometry holdout A/B/C results

Measured 2026-09-18 **after** freeze commit `7785269`. Maps, generation
rules, and A/B/C (including C certificates) were not changed after these
rankings. C remains a hand-designed U vs L stopping rule, not a learned
policy. The old three-map matrix is still development/regression data.

Geometry seeds 1–20 are the sampling units. Inside each map, five rules,
two ID permutations, and two acquisition methods are paired conditions
(20 cells per map). Agent RNG seed is 1.

## Runtime

- Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0
- Tests: 82 passed before the batch
- Batch: **400/400 pairs completed** in **13.61s** of a 120s cap
- Incomplete pairs: 0. Success rate 1.0 for A, B, and C on every k=10
  later prefix
- Logs: `results/checkpoint_geometry_holdout/`
- Frozen maps: `configs/geometry_holdout_maps.yaml`

## Certificates and planner caps

C later decisions: 4000 (400 pairs × 10 later episodes).

| certificate | count |
| --- | ---: |
| certified_no_headroom | 3780 |
| shorter_plan_witness | 220 |
| undecided | 0 |

Unresolved hypothesis searches (planner cap or time limit): **0**.
Exploiting because of a compute cap did not occur. Caps would have been
logged as `undecided`, not as certified optimality.

Mean C planning overhead at k=10: 1394 expansions per pair.

## Sampling-unit ranking (20 maps)

Each map's statistic is the mean k=10 later action cost across its 20
paired cells. Negative delta means fewer actions than the comparator.

| | vs A | vs B |
| --- | ---: | ---: |
| C wins | 20 | 20 |
| ties | 0 | 0 |
| losses | 0 | 0 |
| incomplete | 0 | 0 |

Mean of map means, k=10 later cost: A **132.53**, B **129.68**, C **126.30**.
Mean lifetime (episode 0 + later 10): A 146.22, B 143.37, C 139.99.

This map-level win is an average over mixed acquisition cells. It does
not mean C helped on every paired condition.

## Per-map k=10 later means

20 paired cells per map. Success 1.0. Undecided 0.

| map | A | B | C | C−A | C−B | overhead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| holdout_01 | 123.5 | 122.8 | 118.4 | −5.2 | −4.5 | 1297 |
| holdout_02 | 110.5 | 108.6 | 106.3 | −4.2 | −2.3 | 774 |
| holdout_03 | 150.5 | 143.7 | 142.0 | −8.6 | −1.8 | 1107 |
| holdout_04 | 140.5 | 138.6 | 132.8 | −7.8 | −5.9 | 1078 |
| holdout_05 | 113.5 | 113.4 | 112.3 | −1.2 | −1.1 | 2366 |
| holdout_06 | 166.5 | 161.6 | 154.1 | −12.5 | −7.6 | 1051 |
| holdout_07 | 110.5 | 109.2 | 106.6 | −3.9 | −2.6 | 890 |
| holdout_08 | 113.5 | 113.4 | 112.3 | −1.2 | −1.1 | 1632 |
| holdout_09 | 180.5 | 173.7 | 172.0 | −8.6 | −1.8 | 2139 |
| holdout_10 | 180.5 | 176.8 | 168.2 | −12.4 | −8.7 | 1189 |
| holdout_11 | 140.5 | 134.3 | 132.6 | −8.0 | −1.8 | 1803 |
| holdout_12 | 113.5 | 113.4 | 112.3 | −1.2 | −1.1 | 1965 |
| holdout_13 | 114.5 | 112.2 | 108.1 | −6.5 | −4.2 | 1484 |
| holdout_14 | 97.0 | 93.4 | 90.5 | −6.5 | −2.9 | 1005 |
| holdout_15 | 134.5 | 132.2 | 128.1 | −6.5 | −4.2 | 881 |
| holdout_16 | 119.0 | 118.0 | 116.0 | −3.0 | −2.0 | 1941 |
| holdout_17 | 174.5 | 169.0 | 164.3 | −10.2 | −4.7 | 2000 |
| holdout_18 | 123.5 | 123.4 | 122.3 | −1.2 | −1.1 | 1299 |
| holdout_19 | 113.0 | 107.8 | 104.7 | −8.3 | −3.1 | 949 |
| holdout_20 | 130.5 | 128.0 | 122.5 | −8.1 | −5.6 | 1030 |

## Paired cells (not the sampling unit)

400 complete pairs. C vs A at k=10: **91 helps, 246 ties, 63 wastes**.

By acquisition method (200 pairs each):

| acquisition | C vs A mean later | helps | ties | wastes |
| --- | ---: | ---: | ---: | ---: |
| systematic_retained | −7.44 | 44 | 129 | 27 |
| active_retained | −5.02 | 47 | 117 | 36 |

Acquisition buckets (episode-0 cost vs oracle episode 0, not U):

| bucket | pairs | B vs A | C vs A | C helps | C equal | C wastes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| expensive_systematic | 79 | −18.1 | −20.0 | 44 | 35 | 0 |
| expensive_active_control | 58 | −18.7 | −19.8 | 47 | 11 | 0 |
| cheap_systematic_control | 121 | +4.6 | +0.8 | 0 | 94 | 27 |
| cheap_active | 142 | +5.8 | +1.0 | 0 | 106 | 36 |

C still wastes on already-cheap acquisitions and recovers on expensive
ones. Map-level means mix those cells, so every map can show a C win
while 63 paired cells still lose.

## What this does not show

No new algorithm. C was not tuned after this batch. Zero undecided
certificates on these maps does not prove caps cannot happen; the
development-matrix audit also had zero caps. Bucket labels remain
evaluator-only.
