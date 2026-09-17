# Experience Lab v0.1

A local CPU-only symbolic SwitchWorld study of a **hand-designed** later-episode stopping rule. The learner does not train a neural network, call an LLM, or download datasets.

This package is a controlled comparison of three frozen checkpoint policies (A, B, C) on a development matrix and a 20-map geometry holdout. It is **not** a claim that C is novel or generally superior.

Full write-up: [`docs/v0.1/EXPERIMENTAL_REPORT.md`](docs/v0.1/EXPERIMENTAL_REPORT.md). Generated tables and figures: [`docs/v0.1/`](docs/v0.1/).

## Question

After a shared public episode-0 checkpoint, does a U vs L gate (method C) reduce later action cost relative to always exploiting (A) and always completing one information-per-action probe (B)?

## Setup

Python 3.11+. Clone the repository, then install into a local virtualenv from the repo root:

```bash
git clone https://github.com/TzepChris/experience-lab.git
cd experience-lab
python -m venv .venv
```

Use the venv interpreter (not system Python) to install:

```bash
# Windows
.venv\Scripts\python -m pip install -U pip
.venv\Scripts\python -m pip install -e .

# macOS / Linux
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e .
```

Installed versions used for the measured batches are in `requirements.lock.txt` and each run `manifest.json`. Package version: `0.1.0`.

## Reproduction

Commands below assume the venv interpreter is on your `PATH` after activation, or replace `python` with `.venv\Scripts\python` (Windows) or `.venv/bin/python` (macOS / Linux).

Rebuild tables, bootstrap intervals, and figures from **saved** summaries. This does not rerun A/B/C and must not be used to retune them.

```bash
python -m pytest -q
python -m experience_lab.cli artifact --holdout results/checkpoint_geometry_holdout --development results/checkpoint_ul_stopping --output docs/v0.1
```

Optional: regenerate the raw batches under the 120-second cap (do not change A/B/C afterward, and do not tune against the holdout).

```bash
python -m experience_lab.cli benchmark --config configs/checkpoint_ul_stopping.yaml --max-wall-seconds 120
python -m experience_lab.cli benchmark --config configs/checkpoint_geometry_holdout.yaml --max-wall-seconds 120
```

Holdout maps, methods, and certificates were frozen at git `77852692cf7ababb11dc8a33793fcb8eee93da34` before rankings. The development batch predates `git init` (`commit: null` in its manifest).

## Measured holdout (k=10 later actions)

20 maps × 20 paired cells = 400/400 complete pairs in 13.61s. Success 1.0 for A, B, and C.

Mean of map means: A 132.53, B 129.68, C 126.30. Paired bootstrap 95% CI for C−A: −7.71 to −4.69. Map-level C vs A is 20–0–0; paired cells are 91 helps / 246 ties / 63 wastes.

## Public loop

```text
public observation -> hypothesis filter -> conservative task plan
        |                                      |
        |                              if none: probe plan
        v                                      v
      action -----------------> environment -> new observation
```

The learner never receives hidden rules, seeds, oracle paths, bucket labels, or the environment object.

## What this is not

No transfer study, changing-rule study, dashboard, or remote publication. Earlier diagnostics (probe choice, first-TOGGLE re-probe, A vs B complete-target) remain development history in `docs/`.

## License

MIT. See [`LICENSE`](LICENSE).
