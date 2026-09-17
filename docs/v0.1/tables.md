# v0.1 generated tables

Generated from saved `summary.json` files. Do not edit by hand.
A/B/C were not modified to produce these numbers.

## Reconciliation

Scheduled pairs 400; parsed cells 400;
expected 400. Completed status 400;
complete cells 400; incomplete 0.
Maps 20; 20 cells per map: True.
Success A/B/C all 1.0: True.
Mean of map means equals grand cell mean: True.
Paired-cell C vs A counts sum to n: True.

## Holdout map-level means and paired bootstrap

Sampling unit: geometry map. Bootstrap: 10,000 resamples of 20 maps with
replacement; all 20 paired conditions stay inside the resampled map.
Seed `20260918`. Maps are treated as i.i.d. draws from this generator. All 20 paired conditions stay with the map. The interval is uncertainty within the generator, not over other map families, switch counts, or rule families.

| estimand | point | 95% CI |
| --- | ---: | --- |
| mean of map means, later A | 132.53 | 122.05 to 143.65 |
| mean of map means, later B | 129.68 | 119.75 to 140.08 |
| mean of map means, later C | 126.30 | 116.87 to 136.36 |
| mean of map means, lifetime A | 146.22 | 134.67 to 158.49 |
| mean of map means, lifetime B | 143.37 | 132.41 to 154.93 |
| mean of map means, lifetime C | 139.99 | 129.51 to 151.20 |
| C−A map-mean later delta | -6.23 | -7.71 to -4.69 |
| C−B map-mean later delta | -3.38 | -4.34 to -2.49 |
| map win rate C vs A | 1.00 | 1.00 to 1.00 |
| map win rate C vs B | 1.00 | 1.00 to 1.00 |

## Map-level wins, ties, losses

C vs A: helps=20, equal=0, wastes=0.
C vs B: helps=20, equal=0, wastes=0.

## Per-map later means

| map | A | B | C | C−A | C−B | overhead |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| holdout_01 | 123.50 | 122.80 | 118.35 | -5.15 | -4.45 | 1297 |
| holdout_02 | 110.50 | 108.60 | 106.30 | -4.20 | -2.30 | 774 |
| holdout_03 | 150.50 | 143.70 | 141.95 | -8.55 | -1.75 | 1107 |
| holdout_04 | 140.50 | 138.60 | 132.75 | -7.75 | -5.85 | 1078 |
| holdout_05 | 113.50 | 113.40 | 112.30 | -1.20 | -1.10 | 2366 |
| holdout_06 | 166.50 | 161.60 | 154.05 | -12.45 | -7.55 | 1051 |
| holdout_07 | 110.50 | 109.20 | 106.60 | -3.90 | -2.60 | 890 |
| holdout_08 | 113.50 | 113.40 | 112.30 | -1.20 | -1.10 | 1632 |
| holdout_09 | 180.50 | 173.70 | 171.95 | -8.55 | -1.75 | 2139 |
| holdout_10 | 180.50 | 176.80 | 168.15 | -12.35 | -8.65 | 1189 |
| holdout_11 | 140.50 | 134.30 | 132.55 | -7.95 | -1.75 | 1803 |
| holdout_12 | 113.50 | 113.40 | 112.30 | -1.20 | -1.10 | 1965 |
| holdout_13 | 114.50 | 112.20 | 108.05 | -6.45 | -4.15 | 1484 |
| holdout_14 | 97.00 | 93.40 | 90.50 | -6.50 | -2.90 | 1005 |
| holdout_15 | 134.50 | 132.20 | 128.05 | -6.45 | -4.15 | 881 |
| holdout_16 | 119.00 | 118.00 | 116.00 | -3.00 | -2.00 | 1941 |
| holdout_17 | 174.50 | 169.00 | 164.30 | -10.20 | -4.70 | 2000 |
| holdout_18 | 123.50 | 123.40 | 122.30 | -1.20 | -1.10 | 1299 |
| holdout_19 | 113.00 | 107.80 | 104.70 | -8.30 | -3.10 | 949 |
| holdout_20 | 130.50 | 128.00 | 122.45 | -8.05 | -5.55 | 1030 |

## Paired-cell C vs A (descriptive; not the sampling unit)

n=400 complete, 0 incomplete. helps=91, equal=246, wastes=63.
C vs B: helps=220, equal=180, wastes=0.
Cell-mean later: A 132.53, B 129.68, C 126.30.
Cell-mean lifetime: A 146.22, B 143.37, C 139.99.

| acquisition | n | C−A mean later | helps | equal | wastes |
| --- | ---: | ---: | ---: | ---: | ---: |
| active_retained | 200 | -5.02 | 47 | 117 | 36 |
| systematic_retained | 200 | -7.44 | 44 | 129 | 27 |

| acquisition bucket | n | B−A | C−A | helps | equal | wastes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| cheap_active | 142 | 5.77 | 1.03 | 0 | 106 | 36 |
| cheap_systematic_control | 121 | 4.61 | 0.76 | 0 | 94 | 27 |
| expensive_active_control | 58 | -18.72 | -19.83 | 47 | 11 | 0 |
| expensive_systematic | 79 | -18.13 | -20.00 | 44 | 35 | 0 |

## C certificates (later k=10 decisions)

certified_no_headroom=3780, shorter_plan_witness=220, undecided=0.
Unresolved hypothesis searches: 0.
Mean C planning expansions per pair: 1394.

## XOR development trace

Checkpoint `probe_spur|x0_xor_x1|perm1,0|seed1|systematic_retained`. Starting condition `expensive_systematic`.
Episode 0 cost 19 (oracle 7).
k=10 later cost A 190, B 88, C 70.

After episode 0 cost 19 (oracle 7), remaining hypotheses were ['x0', 'x0_or_x1', 'x0_xor_x1']. C later-0 had U=19 and L=7 (shorter_plan_witness), so it ran the completed-target probe to config 2 and finished in 7 actions. Remaining hypotheses became ['x0_or_x1', 'x0_xor_x1']. C later-1 had U=7 and L=7 (certified_no_headroom), so it exploited with 0 extra-probe actions. B later-1 still probed target 3 (OR-vs-XOR distinguisher) and used 25 actions.

| later | A steps | B steps / target | C steps / U / L / decision / target |
| ---: | ---: | --- | --- |
| 0 | 19 | 7 / 2 | 7 / 19 / 7 / optional_probe / 2 |
| 1 | 19 | 25 / 3 | 7 / 7 / 7 / exploit / None |
| 2 | 19 | 7 / None | 7 / 7 / 7 / exploit / None |
