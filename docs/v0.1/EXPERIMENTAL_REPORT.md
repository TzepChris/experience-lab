# Experience Lab v0.1 experimental report

This is a controlled study of a **hand-designed** U vs L stopping rule on frozen SwitchWorld checkpoints. It is not a novelty claim and not a claim that method C is generally superior.

Generated numbers: [`tables.md`](tables.md), [`holdout_stats.json`](holdout_stats.json), [`xor_trace.json`](xor_trace.json), [`versions.json`](versions.json), [`figures/`](figures/). Rebuild with `python -m experience_lab.cli artifact`. A/B/C were not modified to produce this package.

## Question

After a shared public episode-0 belief, under a fixed later-episode budget, how do three checkpoint policies compare on action cost and success:

- **A**: exploit whenever a conservative goal plan exists.
- **B**: take at most one completed-target information-per-action probe, then exploit.
- **C**: take that same completed-target probe only when a decided hypothetical plan is shorter than the conservative plan.

The sampling unit on the holdout is a geometry map. Rankings were not used to change C.

## Supplied knowledge

These are built into the lab, not recovered from interaction:

- Public geometry, actions, per-action cost, and episode budget 256.
- The candidate two-switch Boolean rule family and exact version-space filtering.
- Conservative BFS over remaining tables, and the shared probe planner.
- Active selection by predicted information per action; systematic order `0 .. 2^S-1`.
- Physics-preserving switch-ID permutation with rule rewrite.
- B/C probe procedure: finish the selected target configuration; update beliefs on the way.
- C's U vs L rule, complete-hypothesis searches, and certificate labels.
- Frozen development layouts and the 20 holdout maps (generator version 1, solvability-only acceptance).
- Evaluator-only oracle plans, hidden rules, and acquisition-bucket labels.

## Learned knowledge

From public observations, actions, and rewards only:

- Which candidate tables remain after `(switch config, door)` evidence.
- Whether a conservative goal plan exists from the current state.
- For C: `U`, decided `L`, and the probe-or-exploit decision implied by those quantities.

The learner does not receive the hidden rule, generator seed, environment object, oracle path, or bucket label. Bucket labels compare episode-0 cost to oracle episode 0; they are not current exploit-plan `U` and are not inputs to A/B/C.

## Method definitions

All three forks copy the same public `Belief` after episode 0.

| method | later-episode policy |
| --- | --- |
| A `checkpoint_exploit` | If a conservative plan exists, follow it. No optional probe. |
| B `checkpoint_complete_reprobe` | At most one completed-target information-per-action probe, then exploit. |
| C `checkpoint_ul_stopping` | Hand-designed gate: probe like B only if `L < U`; otherwise exploit. Search-cap exhaustion is `undecided` and does not authorize a probe. |

`U` is the length of the current conservative goal plan. For each remaining complete assignment `h` (one table per door, held fixed for the search), `L_h` is the shortest goal-plan length assuming `h`. `L` is the minimum among decided `L_h`. Incompatible hypotheses are not mixed.

C certificates (logging only; policy unchanged):

- `certified_no_headroom`: every remaining complete search resolved and `min L_h == U`.
- `shorter_plan_witness`: a resolved hypothesis has a path shorter than `U`.
- `undecided`: unresolved searches prevent a no-headroom certificate.

Exploiting after a compute cap is allowed. It is not logged as certified optimality.

## Development versus holdout protocol

**Development / regression matrix** (`configs/checkpoint_ul_stopping.yaml`): layouts `tiny_two_switch`, `probe_spur`, `probe_spur_mirror`; five initially closed rules; both ID permutations; seeds 1–3; acquisition `systematic_retained` and `active_retained`. Used to design and test C, including the XOR diagnostic below. This matrix is not the confirmatory sample.

**Geometry holdout** (`configs/checkpoint_geometry_holdout.yaml`, maps in `configs/geometry_holdout_maps.yaml`): 20 generator seeds, two switches, one door, five rules, both permutations, both acquisition methods. Maps were accepted by oracle solvability only, before A/B/C rankings. Agent RNG seed is 1 and is not a sampling unit.

Inside each map the 20 cells stay paired: 5 rules × 2 permutations × 2 acquisition methods. Later prefixes are 1, 2, 5, 10. Primary cost is k=10 later actions. Lifetime = shared episode 0 + later prefix. Incomplete prefixes are not converted into low costs.

Holdout methods and maps were frozen at git `77852692cf7ababb11dc8a33793fcb8eee93da34` (`dirty: false`) before inspecting rankings. C was not tuned after that inspection.

## Measured results

### Reconciliation (holdout)

From `results/checkpoint_geometry_holdout/summary.json`:

- 400 scheduled pairs, 400 parsed cells, 400 complete, 0 incomplete.
- 20 maps, 20 cells each.
- Success A/B/C = 1.0 on every k=10 later prefix.
- Mean of map means equals the grand cell mean (balanced 20 cells/map).
- Paired-cell C vs A outcomes sum to 400.

Batch status `completed` in 13.61s of a 120s cap. Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0.

### Map-level later cost and paired bootstrap

Maps are treated as i.i.d. draws from this generator. The bootstrap draws 10,000 resamples of the 20 maps with replacement (seed `20260918`) and keeps all 20 paired conditions inside each resampled map. Percentile 95% intervals describe uncertainty **within this map generator**, not over other map families, switch counts, or rule families.

| estimand | point | 95% CI |
| --- | ---: | --- |
| mean of map means, later A | 132.53 | 122.05 to 143.65 |
| mean of map means, later B | 129.68 | 119.75 to 140.08 |
| mean of map means, later C | 126.30 | 116.87 to 136.36 |
| mean of map means, lifetime A | 146.22 | 134.67 to 158.49 |
| mean of map means, lifetime B | 143.37 | 132.41 to 154.93 |
| mean of map means, lifetime C | 139.99 | 129.51 to 151.20 |
| C−A map-mean later delta | −6.23 | −7.71 to −4.69 |
| C−B map-mean later delta | −3.38 | −4.34 to −2.49 |
| map win rate C vs A | 1.00 | 1.00 to 1.00 |
| map win rate C vs B | 1.00 | 1.00 to 1.00 |

Map-level wins: C vs A 20–0–0; C vs B 20–0–0. Per-map means are in [`tables.md`](tables.md) and [`figures/fig1_map_later_cost.png`](figures/fig1_map_later_cost.png). Every map's mean C−A is negative ([`figures/fig2_map_delta_c_minus_a.png`](figures/fig2_map_delta_c_minus_a.png)). That map-level win mixes recovery and waste inside the map.

### Paired cells (descriptive; not the sampling unit)

C vs A at k=10: **91 helps, 246 equal, 63 wastes** ([`figures/fig3_paired_cell_outcomes.png`](figures/fig3_paired_cell_outcomes.png)). C vs B: 220 helps, 180 equal, 0 wastes.

| acquisition | n | C−A mean later | helps | equal | wastes |
| --- | ---: | ---: | ---: | ---: | ---: |
| systematic_retained | 200 | −7.44 | 44 | 129 | 27 |
| active_retained | 200 | −5.02 | 47 | 117 | 36 |

Acquisition buckets (episode-0 cost vs oracle episode 0):

| bucket | n | B−A | C−A | C helps | C equal | C wastes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| expensive_systematic | 79 | −18.13 | −20.00 | 44 | 35 | 0 |
| expensive_active_control | 58 | −18.72 | −19.83 | 47 | 11 | 0 |
| cheap_systematic_control | 121 | +4.61 | +0.76 | 0 | 94 | 27 |
| cheap_active | 142 | +5.77 | +1.03 | 0 | 106 | 36 |

C recovers on expensive starts and still wastes on already-cheap acquisitions. A map can therefore show a C win while some of its cells lose.

### Costs

- Holdout wall time: 13.61s / 120s cap; development U/L batch: 4.92s / 120s.
- Mean C planning overhead on the holdout: 1394 expansions per pair at k=10.
- C later decisions: 4000. Certificates: 3780 `certified_no_headroom`, 220 `shorter_plan_witness`, 0 `undecided`. Unresolved hypothesis searches: 0.
- Action cost is the reported objective. Planning expansions are an extra compute cost, not subtracted from action totals.

### Negative results

- C is not better on every paired cell: 63 k=10 wastes vs A, all on cheap-acquisition buckets.
- On cheap active cells, C's mean later cost is **higher** than A by 1.03 actions; B is worse still (+5.77).
- On cheap systematic-control cells, C is also slightly worse than A (+0.76).
- Map-level 20–0–0 therefore does not imply a uniform cell-level win.
- Zero `undecided` certificates on these maps does not prove planner caps cannot occur; the development audit also had zero caps.
- Earlier first-TOGGLE re-probe (not C) never beat exploit-immediately on cumulative cost on its frozen matrix.
- Milestone A and the tiny-map pilot did not show an active vs systematic action-cost difference.

## XOR trace: why C skips the unnecessary probe

Real development checkpoint `probe_spur|x0_xor_x1|perm1,0|seed1|systematic_retained` (source: `results/checkpoint_ul_stopping/summary.json`). Full extract: [`xor_trace.json`](xor_trace.json).

Episode 0 cost 19 (oracle 7). Remaining hypotheses `{x0, x0_or_x1, x0_xor_x1}`. Starting condition `expensive_systematic`.

| later | A | B | C |
| ---: | --- | --- | --- |
| 0 | 19, no probe | 7 actions, completed target 2, remaining `{OR, XOR}` | `U=19`, `L=7`, `shorter_plan_witness`, same target 2, 7 actions |
| 1 | 19, no probe | 25 actions, target 3 (OR-vs-XOR distinguisher) | `U=7`, `L=7`, `certified_no_headroom`, **exploit, 0 extra-probe actions** |
| 2 | 19 | 7, no probe | 7, exploit |

k=10 later cost: A 190, B 88, C 70.

After the first completed target, every remaining complete hypothesis agrees that the conservative plan is already shortest. C therefore skips the OR-vs-XOR distinguisher that B still runs. This is the designed behavior of the hand-written gate, not a learned policy.

## Code and config versions

| item | value |
| --- | --- |
| package | `experience-lab` 0.1.0 |
| Python | 3.11.0 |
| numpy | 2.4.6 |
| matplotlib | 3.11.2 |
| pytest | 9.1.1 |
| PyYAML | 6.0.3 |
| lockfile | `requirements.lock.txt` |
| holdout freeze commit | `77852692cf7ababb11dc8a33793fcb8eee93da34`, dirty false |
| development manifest git | `commit: null` (batch run before `git init`) |
| holdout config | `configs/checkpoint_geometry_holdout.yaml` |
| development config | `configs/checkpoint_ul_stopping.yaml` |
| frozen maps | `configs/geometry_holdout_maps.yaml`, generator version 1 |
| bootstrap | 10,000 map resamples, seed 20260918 |

## Reproduction commands

Windows PowerShell, project virtual environment, CPU only.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m experience_lab.cli artifact --holdout results/checkpoint_geometry_holdout --development results/checkpoint_ul_stopping --output docs/v0.1
```

The artifact command rebuilds tables and figures from saved summaries. It does not rerun learners.

To regenerate the raw batches (120s cap). Do not edit A/B/C or tune against the holdout after inspecting rankings.

```powershell
.\.venv\Scripts\python.exe -m experience_lab.cli benchmark --config configs/checkpoint_ul_stopping.yaml --max-wall-seconds 120
.\.venv\Scripts\python.exe -m experience_lab.cli benchmark --config configs/checkpoint_geometry_holdout.yaml --max-wall-seconds 120
```

Raw `results/` logs are local working files. This `docs/v0.1/` folder holds the derived artifact.

## Limitations

- Two switches, one door, five initially closed Boolean rules, deterministic physics.
- Twenty maps from one generator; intervals are not a statement about other generators.
- C's probe, when taken, is the existing information-per-action completed-target probe, not a new selector.
- C is a hand-designed rule with a complete-hypothesis planner, not a learned policy.
- Success was 1.0 here; the comparison is about action cost, not sparse failures.
- Episode 0 cost is shared and sunk; later-prefix savings do not undo a costly acquisition.
- Planner expansion caps were not stressed on these maps.
- No transfer, nonstationary rules, larger switch counts, or human-subject claims.

## Future research questions

Listed only. None of these is implemented in v0.1.

1. Can a stopping rule be induced from public traces instead of written by hand?
2. How does the same U vs L gate behave with more than two switches or more than one door?
3. What should the agent do when hypothetical searches actually hit the planner cap?
4. Does a different probe selector change the value of this stopping rule?
5. Can acquisition be improved so expensive systematic checkpoints are rarer?
6. How sensitive are map-level rankings to a different geometry generator or to three-switch maps?
7. How should the agent respond if the hidden rule can change between episodes?
8. Does any of A/B/C transfer across map families without retuning?
9. When exact version-space filtering is infeasible, what approximation preserves the U vs L certificate meaning?
10. On larger maps, when do planning expansions dominate the action-cost savings?

## Contribution

v0.1 is a reproducible, CPU-only record of a **controlled study of a hand-designed stopping rule** under an information boundary. It reports paired development diagnostics and a frozen geometry holdout with map-level bootstrap intervals. It does not claim a new general exploration algorithm.
