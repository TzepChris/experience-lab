# Milestone A results

Measured locally on 2026-09-17. These numbers come from executed commands, not estimates.

## Runtime

- Hardware: Windows 10.0.26200, AMD64 Family 25 Model 33, Python 3.11.0
- Installed: numpy 2.4.6, matplotlib 3.11.2, PyYAML 6.0.3, pytest 9.1.1 (see `requirements.lock.txt`)
- Tests: `28 passed in 0.05s`
- Demo: completed in 0.1190s (`results/demo/`)
- Pilot: completed 36/36 scheduled runs in 0.4257s of a 120s cap (`results/pilot/`). No interrupted or failed runs.

## Demo (AND rule, seed 1, active retained)

Public start: switches `00`, door closed. Prior size 7; the free initial observation left 5 tables (`x0`, `x1`, AND, OR, XOR).

1. Probe target config 1 (toggle nearer switch). After TOGGLE, door stayed closed. Hypotheses became `{x0_and_x1, x1}`.
2. Conservative task plan: toggle the second switch. Door opened. Remaining tables still agree that `11` opens the door.
3. Walk through the door to the goal in 14 actions, return 0.86.
4. Exact truth-table recovery was **false** in this one-episode demo. The learner solved the task without uniquely naming AND vs `x1`.

Trace: `results/demo/events.jsonl`.

## Pilot table

Same tiny map; rules AND / XOR / `x0`; seeds 1, 2, 3; 2 episodes; max 256 steps. All learning methods used the shared filter and planners.

| method | completed runs | success rate | mean steps (all succeeded) | mean |H| | interactions | planner expansions | belief changed |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| active_retained | 9/9 | 1.0 | 10.667 | 2.5 | 192 | 1875 | 9/9 |
| active_reset | 9/9 | 1.0 | 10.667 | 2.667 | 192 | 2214 | 9/9 |
| systematic_retained | 9/9 | 1.0 | 10.667 | 2.5 | 192 | 1875 | 9/9 |
| oracle | 9/9 | 1.0 | 10.667 | n/a | 192 | 4938 | 0/9 |

Per-rule successful lengths matched the oracle: AND 14, XOR 9, `x0` 9, on every seed and both episodes.

## What this does and does not show

- Hypotheses changed from real observations, and those hypotheses supported goal plans. Gate for Milestone A: passed.
- Active and systematic produced identical action sequences here: the cheapest informative probe is also first in canonical order `0,1,2,3`, and it lies on an optimal AND/XOR/`x0` route.
- Retained vs reset did **not** change action cost. The first probe is already on the shortest task path, so re-learning is free in steps. Retained AND runs did uniquely recover `x0_and_x1` on episode 2 (episode-2 path visits the remaining distinguishing config); reset AND runs ended episode 2 still with `{x0_and_x1, x1}`.
- This is not evidence that active experimentation beats systematic search.

## Logs

- `results/demo/events.jsonl`, `results/demo/summary.json`, `results/demo/manifest.json`
- `results/pilot/events.jsonl`, `results/pilot/summary.json`, `results/pilot/manifest.json`
