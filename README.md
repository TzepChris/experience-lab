# Experience Lab

A CPU-only Python lab where a symbolic agent learns which Boolean switch-to-door rule is active by acting, observing, and planning. It does not train a neural network, call an LLM, or download datasets.

Central question (not answered by Milestone A): under a fixed interaction budget, does choosing informative experiments help more than systematic search? Milestone A only checks that learning, planning, and the information boundary work on one tiny map.

## Setup (Windows PowerShell)

```powershell
cd "C:\Users\chris\Rl project"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -U pip
.\.venv\Scripts\python.exe -m pip install -e .
```

Installed versions used for a run are recorded in `requirements.lock.txt` and in each run manifest.

## Commands

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m experience_lab.cli demo --config configs/smoke.yaml --seed 1
.\.venv\Scripts\python.exe -m experience_lab.cli benchmark --config configs/pilot.yaml --max-wall-seconds 120
.\.venv\Scripts\python.exe -m experience_lab.cli benchmark --config configs/probe_choice.yaml --max-wall-seconds 120
.\.venv\Scripts\python.exe -m experience_lab.cli report --input results/probe_choice
.\.venv\Scripts\python.exe -m experience_lab.cli benchmark --config configs/reprobe_closed_door.yaml --max-wall-seconds 120
.\.venv\Scripts\python.exe -m experience_lab.cli report --input results/reprobe_closed_door
.\.venv\Scripts\python.exe -m experience_lab.cli benchmark --config configs/checkpoint_complete_probe.yaml --max-wall-seconds 120
.\.venv\Scripts\python.exe -m experience_lab.cli report --input results/checkpoint_complete_probe
```

## Public loop

```text
public observation -> hypothesis filter -> conservative task plan
        |                                      |
        |                              if none: probe plan
        v                                      v
      action -----------------> environment -> new observation
```

The learner never receives hidden rules, seeds, oracle paths, or the environment object.

## Milestone A scope

Implemented: one 7x7 two-switch one-door world, exact hypothesis filtering, conservative BFS, control-area probes, active information-per-action selection, systematic baseline, oracle evaluator, tests, demo, and a 120-second-capped pilot.

A later diagnostic added a frozen spur/mirror pair, switch-ID permutation, and the random-informative baseline. A separate frozen comparison then tests optional re-probing after a conservative plan already exists. Transfer, changing rules, and a dashboard are still out of scope.

## Real demo (executed)

On the tiny AND world, seed 1, the active learner started with 5 remaining tables after seeing `00 -> closed`, probed the nearer switch, observed `10 -> closed`, reduced the set to `{x0_and_x1, x1}`, then followed a conservative plan that opened the door and reached the goal in 14 steps. Exact recovery of AND was not required for that success.

## Pilot (executed)

36/36 runs completed in 0.43s on local CPU (120s cap). All methods, including the oracle, used 14 steps on AND and 9 on XOR/`x0`. Active matched systematic. Retained memory did not reduce action cost on this map. Details: `docs/results.md`.

## Probe-choice diagnostic (executed)

Frozen matrix: 3 layouts × 3 rules × 2 ID permutations × 3 seeds × 7 methods = 378 runs, all completed in 4.90s. Selection changes cost when the cheap informative probe is not the first canonical config and is not on the oracle path. Active saved 12 actions vs systematic on spur XOR with swapped IDs, and lost 4 on spur AND with the same IDs. Details: `docs/results_probe_choice.md`. Do not read the pooled mean as a general win.

## Re-probe comparison (executed)

Frozen five-rule matrix: 3 layouts × 5 initially closed rules × 2 ID permutations × 3 seeds × 3 methods = 270 runs, all completed in 15.74s of a 120s cap. Episode 0 matched exploit-immediately. Optional later-episode probes never beat that baseline on cumulative cost: they were free on AND/`x1` (on-path) and wasted on `x0`/OR/XOR. The episode-1 premium was not recovered by episode 10. Success was 1.0 for both methods on every prefix. Details: `docs/results_reprobe.md`.

## Checkpoint complete-probe (executed)

180/180 pairs completed in 3.16s of a 120s cap. Forks started from real systematic and active episode-0 beliefs. Completing the selected target **recovered** from expensive systematic knowledge after ID swap (spur XOR later-10: A 190 vs B 88). From already-cheap active states the same completed probes **added** cost (spur XOR later-10: +30). AND/`x1` stayed equal. Success 1.0 on every prefix. Details: `docs/results_checkpoint_complete_probe.md`.
