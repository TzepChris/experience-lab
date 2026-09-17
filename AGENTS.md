# Experience Lab — project instructions

These rules apply to work in this repository. They complement, and do not replace, the experiment specification in `EXPERIENCE_LAB_PLAN.md`.

## Role split

- The coding assistant may edit code, tests, configs, and docs.
- The experimental learner is a separate deterministic/symbolic Python program. It may update hypotheses only from its own actions and public observations.
- Do not call an LLM, neural network, or external API from the experimental agent or from experiment loops.

## Execution

- Run experiments locally on CPU only. No GPU, paid compute, cloud jobs, or dataset downloads.
- Ordinary package installation into the project virtual environment and reading public documentation are allowed.
- Do not install system-wide software, start cloud services, publish the repository, or upload artifacts unless a user explicitly asks.
- Default to one local process. Enforce configured wall-time, episode, action, and planner-expansion caps inside long loops, not only between runs.
- Cap experimental execution as configured (pilot default 120 seconds). Save partial results and label incomplete runs. Do not launch large sweeps.

## Information boundary

- Learners receive only immutable public `Observation` objects, actions, and rewards.
- Do not pass an environment object, generator seed, hidden rule, internal state, oracle path, or privileged info dictionary into learner decision code.
- Hidden rules, oracle plans, and seeds may be used by tests and the evaluator only.
- Do not write privileged fields into logs that are later fed back into learner decisions.
- Do not expose hidden rules, seeds, environment internals, or oracle answers to the learner to make a run succeed.

## Reproducibility and honesty

- Use the project virtual environment (`.venv`) and `pyproject.toml`. Record actually installed versions in run manifests and `requirements.lock.txt`.
- Do not fabricate traces, charts, timings, or outcomes. Label unexecuted commands and incomplete runs accurately.
- Do not weaken a baseline or change evaluation to manufacture a win.
- Preserve existing work and conventions. Milestone A is a tiny fixed world; later milestones add transfer, changing rules, and broader benchmarks.
- If a pilot fails, diagnose and fix correctness before expanding scope.
