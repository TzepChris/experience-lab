# Experience Lab: learning hidden rules through interaction

Implementation and experiment specification for Cursor

Status: proposed design, not an implemented or validated system. No performance results have been collected. Commands below are interfaces to implement, not commands known to work already.

## 1. Objective and boundaries

Build a small, reproducible Python project in which an agent discovers hidden switch-to-door mechanisms through its own actions, uses the learned mechanisms to reach goals, and reuses that knowledge in new layouts.

The central question is:

> Under a fixed interaction budget, does choosing informative experiments help an agent learn useful rules and solve new tasks more efficiently than systematic or random experimentation?

Connection to Ineffable Intelligence's stated mission: this studies a very small part of learning knowledge from experience. It does not implement a superlearner, motor learning, general intelligence, unlimited learning, or a new state-of-the-art RL algorithm.

Accurate description: **symbolic model learning, active experimentation, and model-based decision-making in a small reward-bearing environment**. A learned policy or neural network is not required. The experiment-selection heuristic is human-designed. Describe this accurately rather than marketing it as deep RL or a learned curiosity algorithm.

Constraints:

- Run experiments locally on CPU from the Cursor terminal.
- Cursor's coding model may help develop the project. No LLM is called by the experimental agent.
- No neural-network training, GPU dependency, paid API, external compute, dataset downloads, or hosted tracking service.
- No human demonstrations, solution trajectories, pretrained weights, or hardcoded hidden answers.
- The agent does learn: its stored hypotheses change after observations.
- First release emphasizes correct experiments and readable code. A dashboard, website, publication claim, or large benchmark is out of scope.

## 2. What is supplied and what is learned

Supplied by the developer:

- Grid navigation, collision rules, action semantics, symbolic observations, switch and door identities.
- A finite family of possible door rules.
- A planning algorithm and an experiment-selection rule.
- The goal, reward, episode budget, and reset behavior.

Learned only from interaction:

- Which allowed Boolean function controls each door in the current world.
- Which switch configurations reliably open useful routes.
- Whether the current evidence is sufficient to support a plan.

This is learning without human demonstrations, not learning without human inductive biases. The observation already identifies switches and doors; perception is not learned.

The rule family is deliberately small. An agent may identify it in a handful of informative observations. Report that honestly. Do not inflate the benchmark by repeating equivalent tasks or claim an open-ended discovery capability.

## 3. Environment: SwitchWorld

### 3.1 Minimal pilot

Start with one deterministic 7x7 or 9x9 map, two switches, one door, and one goal. Test several hidden functions, including AND and XOR. Do not start with a procedural map generator.

The first comparison is a learner with persistent hypotheses versus the same learner whose hypotheses are reset between episodes. The first purpose is to verify learning and information boundaries, not to prove superiority of an exploration method.

### 3.2 Version 1 world

- Small grids, normally 9x9 to 13x13.
- Two to four binary switches; one to three doors.
- Walls, walkable floor, switch tiles, door tiles, start, and goal.
- All switches sit in a control area reachable from the start with every door closed. This makes experiments feasible and keeps the first planner simple.
- Doors gate routes to goals. Include routes requiring more than one door, but accept only instances solvable under the actual rules.
- Keep starts in the control area for version 1. Goal locations must not disconnect the control area.
- Switch and door symbols are arbitrary identifiers. A switch named A must not implicitly control door A.
- World dynamics are deterministic. Observation noise and partial observability are later research extensions, not version 1 requirements.

Door rules for S switches:

```text
x_i
NOT x_i
x_i AND x_j
x_i OR x_j
x_i XOR x_j       (i < j)
```

Represent each rule as a Boolean truth table over all 2^S switch configurations. Deduplicate identical truth tables. No dynamic eval of formula strings. For S=4, this grammar has at most 26 distinct candidates per door, making exact hypothesis filtering cheap.

Each door has its own hidden rule. Different doors may share a rule. Constant functions and unbounded formulas are outside version 1. The agent knows the candidate family, but not the selected functions.

### 3.3 Actions, observations, and reward

Actions: NORTH, SOUTH, EAST, WEST, TOGGLE.

- TOGGLE flips the switch on the agent's current tile. Elsewhere it is a no-op.
- Switch tiles are walkable.
- A move into a wall, boundary, or currently closed door is a no-op.
- Door states are recomputed after a toggle.
- If a door closes under the agent, it may leave the tile; entering a closed door remains forbidden. Specify and test this edge case.
- Goal completion occurs when the agent reaches the goal tile.

Public observation:

```text
visible static grid and object identifiers
agent position and goal position
current switch bits
current open/closed bits for every door
```

The entire symbolic map and all door states are observable. This is an intentional simplification, not visual perception or hidden-state inference.

Reward: -0.01 per action, plus +1.0 on reaching the goal, including the final action cost. Invalid actions still consume a step. Default maximum 256 steps per episode. Termination means goal reached; truncation means budget exhausted.

On episode reset, switch bits return to zero. Rules remain unchanged unless the evaluator explicitly starts a new world or the later drift experiment changes them. All methods receive the initial door observation for free, and may use it to filter hypotheses.

### 3.4 Information boundary

The agent interface must accept only immutable public observations, actions, and rewards. Do not pass an environment object, generator seed, hidden rule index, internal state, oracle path, or privileged info dictionary into an agent.

The evaluator may separately inspect hidden rules for scoring and use an oracle solver to validate instances. Oracle outputs must not enter the learner's evidence or action-selection path.

Use separate RNG streams for generation, algorithm randomness, and evaluation. Never let an agent reconstruct rules from a public generation seed.

## 4. Learning and planning

### 4.1 Version-space learning

For every door d, initialize H_d to the full candidate family. Given observed switch vector x and door state y_d:

```text
H_d <- {h in H_d : h(x) == y_d}
```

Repeat after every observation, including reset. Store distinct observed switch configurations and their door outcomes. Duplicate observations must not count as new independent evidence or reduce uncertainty repeatedly.

Use a uniform prior over distinct candidate truth tables. Report this as a modeling assumption. Under deterministic filtering, the surviving candidates retain equal mass.

An empty hypothesis set in a stationary world is an error or out-of-family event. Record it and fail the run clearly; do not silently read the ground truth or invent a replacement rule. Drift recovery is a separate later feature.

The agent need not identify every rule before reaching a goal. Useful prediction and complete identification are different outcomes.

### 4.2 Conservative task planner

Use breadth-first search over states `(agent_position, switch_bits)` with a visited-state set.

- Known movement and toggle semantics are supplied by design.
- At a hypothetical switch configuration x, permit entering door d only when every surviving h in H_d predicts it is open.
- Compute future door predictions from the learned hypothesis sets, never from environment internals.
- With the true rule still in each hypothesis set, any complete plan obtained this way is safe in the deterministic stationary world.
- Replan after an informative observation, failed prediction, or episode reset.
- If a complete conservative route exists, execute it. Otherwise request an experiment.

The largest default search space is bounded by grid cells times 2^S. Record node expansions and impose an explicit configurable cap. Reaching that cap is an operational failure, not evidence that a world is unsolvable.

### 4.3 Selecting experiments

An experiment is a target switch configuration x plus a feasible action sequence to reach it. Enumerate at most 16 configurations for S<=4.

Find minimum-action probe routes within the control area, treating every door as blocked. All switches are reachable there, so probing never depends on an unverified door rule. Compute routes in augmented position-and-switch space. Any final position achieving the target configuration is acceptable.

For each target configuration and each door:

```text
p_d(x) = fraction of h in H_d for which h(x) == open
u_d(x) = binary_entropy(p_d(x))
U(x)   = sum_d u_d(x)
score(x) = U(x) / max(1, planned_action_cost(x))
```

Treat entropy at p=0 or p=1 as zero. This predicts information from observing the target configuration under the factored posterior. The ratio is a heuristic, not an optimal policy. It does not exactly account for observations collected along the route.

Choose a positive-score configuration, using seeded tie-breaking. Execute movement until the next toggle, incorporate its actual observation, then reconsider the task plan and probe target. Count information collected at intermediate configurations as real evidence.

If all reachable configurations have zero disagreement, all surviving functions are behaviorally equivalent over the rule domain. If the goal planner still fails in an oracle-solvable world, expose the inconsistency instead of looping forever.

Do not add bandits, MCTS, neural curiosity, embeddings, or a symbolic theorem prover to version 1.

## 5. Baselines and fair comparisons

All model-learning agents must share the same candidate family, evidence filter, exploitation planner, public observations, and action costs. Change only experiment selection.

Core methods:

1. **Active-cost:** maximize predicted information per action, as above.
2. **Random-informative:** select uniformly among reachable configurations with positive predicted information, then use the common probe planner.
3. **Systematic:** enumerate switch configurations in a fixed canonical order, skipping previously observed or zero-disagreement configurations, then use the common probe planner. Fix and disclose the order before evaluation.

Diagnostic comparators:

- **Primitive-random:** random primitive actions. A sanity-check floor, not the main evidence for usefulness.
- **Oracle:** full-rule shortest-path solver. Privileged reference for task difficulty and action efficiency; never a fair learning competitor.

Optional ablation after the core benchmark: **Active-no-cost**, maximizing U(x) without dividing by travel cost. This tests whether travel-aware experimentation helps beyond uncertainty reduction.

Do not weaken the systematic baseline, remove its exploitation planner, or give the active method extra observations to force a win. Similar performance is a valid result in this small world.

## 6. Experiments, in order

### E0: correctness and compute pilot

One hand-built map, a small set of known test rule assignments, three paired seeds. Run the learner, reset-memory comparator, and oracle.

Verify actual changes in hypotheses, correct predicted routes, and zero privileged access. Measure wall time, memory where available, actions/second, and planner expansions. Record the measured hardware/runtime; do not guess compute duration.

Recommended first execution allowance: stop the pilot after at most 120 seconds of experiment time, preserving partial results and labeling incomplete runs. This is a safety cap, not a promised runtime.

### E1: stationary learning

Generate accepted world instances from fixed layout templates. Within one world, preserve rules and hypotheses across episodes, but reset physical state. Use a pre-generated goal/start schedule shared by methods. Track first-episode and subsequent-episode performance separately.

Compare the three core methods over the same instances. Keep the world difficulty distribution fixed. Include an unchanging-world control before interpreting any later change experiment.

Primary measure: action cost to solve goals within budget. Secondary: success, probes, uncertainty, and predictive accuracy. Never require exhaustive rule identification merely to inflate learning duration.

### E2: transfer to new layouts

For each world seed:

1. Allocate an identical pretraining interaction budget to each method on designated training layouts.
2. Retain its learned rule hypotheses and evidence.
3. Rebuild geometry using held-out layouts, keeping switch/door identities and hidden rules fixed.
4. Discard cached paths, coordinates, and layout-specific plans.
5. Compare retained memory against a fresh full-prior copy of the SAME method on the new layouts.

The main test permits online learning and counts every test action. Name it **online transfer**, not zero-shot performance. Report pretraining interactions separately and total lifetime interactions including pretraining. A trained agent's test advantage is not free.

Optional later test: freeze the rule model and evaluate task execution without updates. Label this zero-update evaluation and do not merge its results with online transfer.

This tests reuse of stable mechanisms under new geometry. It does not test generalization to unseen rule operators or a larger number of switches.

### E3: rule changes, only after E1/E2 work

Change one hidden door function between episodes, without notifying agents which rule changed or when. The evaluator privately records the change. Admit only post-change instances that remain solvable. Normal observations, including changed initial door states, are allowed.

A minimal repair agent detects contradiction when filtering would empty H_d. For that door only, discard obsolete evidence and rebuild the hypothesis set from the full prior using the new contradictory observation. Preserve unaffected door hypotheses and discard stale plans. This assumes abrupt, deterministic, in-family changes.

Do not keep filtering a new rule through old incompatible evidence. Do not reveal a world-version identifier to the agent. Changes invisible to the visited observations cannot be detected immediately.

Compare targeted repair with resetting all learned door hypotheses upon the SAME observable contradiction. This isolates the value of preserving unaffected knowledge. Use independent evidence records so old contradictions do not repeatedly trigger resets.

Measure recovery actions, new-rule prediction accuracy, false alarms in stationary controls, and detection delay from both the hidden change and the first observation that conflicts with the current hypotheses.

Do not start E3 automatically before the version 1 acceptance gates pass and a measured execution budget is available.

## 7. Metrics and statistics

One independent experimental seed defines a world/rule assignment and its task schedule. Methods use paired world instances. Episodes within the same world are dependent; do not count them as independent seeds.

Required metrics:

- Success rate within the episode limit.
- Capped action cost: actual steps on success, full episode budget on ordinary timeout. Report successful-only steps separately to avoid hiding failures.
- Return using the documented reward definition.
- Actions and toggles before the first goal.
- Hypothesis count and total log2 hypothesis count over time.
- Offline predictive accuracy on every switch configuration, computed by the evaluator only. With ambiguous beliefs, use posterior majority prediction and fix tie-breaking in advance.
- Exact rule recovery by truth-table equivalence, not formula text.
- Wall time, planner expansions, and measured compute overhead.
- For transfer: paired fresh-minus-retained action cost and success difference, plus pretraining cost.

Distinguish ordinary task timeout, process time limit, planner cap, invalid generation, and software exceptions. Infrastructure failures are not silently turned into ordinary RL losses or dropped from the report.

Suggested scope after profiling:

- Pilot: 3 seeds on a tiny instance set.
- Development: 10 independent worlds, fixed debug configuration.
- Initial report: 20 independent held-out worlds, if feasible.
- Expand toward 50 worlds only when the runtime and value justify it.

These are provisional counts, not promises. A run is an entire scheduled sequence for one method and world, not an individual action, episode, or checkpoint.

Use paired comparisons and show individual-world outcomes plus aggregate estimates. If intervals are computed, bootstrap whole independent worlds, retaining their internal episode sequences. State that small samples give imprecise intervals.

Freeze parameters, layout families, seed lists, and scoring rules before final evaluation. Keep development seeds disjoint from test seeds. Do not retune after inspecting test results and then report the same test as untouched.

Do not impose a pass criterion such as 'active must beat baseline by 20%'. Acceptance concerns correctness and reproducibility, not a desired scientific outcome.

## 8. Implementation structure

Use Python 3.11+ with a normal virtual environment. Prefer the existing repository's package manager if there is one. Otherwise use `venv`, `pip`, and `pyproject.toml`.

Minimal dependencies: NumPy, Matplotlib, PyYAML, pytest. The environment can use small dataclasses and a Gymnasium-style reset/step contract without depending on Gymnasium initially. If Gymnasium is added, implement and check its actual API correctly; do not add it solely for branding.

Record the dependency versions actually installed and tested in a reproducible lock or requirements file. Do not invent a tested compatibility matrix.

```text
experience-lab/
  README.md
  AGENTS.md
  pyproject.toml
  configs/
    smoke.yaml
    pilot.yaml
    stationary.yaml
    transfer.yaml
  src/experience_lab/
    types.py
    env.py
    rules.py
    layouts.py
    belief.py
    planner.py
    agents.py
    evaluation.py
    metrics.py
    serialization.py
    cli.py
  tests/
    test_rules.py
    test_env.py
    test_information_boundary.py
    test_belief.py
    test_planner.py
    test_transfer.py
    test_resume.py
  docs/
    design.md
    experiment_protocol.md
    related_work.md
    results.md
  results/                 # ignored except explicitly selected small artifacts
```

Avoid frameworks and abstraction layers that the pilot does not need. Keep the first implementation inspectable by one reader. Do not build a web app or require Docker.

## 9. Planned command-line interface

Implement these commands or document equivalent names clearly:

```bash
python -m pytest -q
python -m experience_lab.cli demo --config configs/smoke.yaml --seed 1
python -m experience_lab.cli benchmark --config configs/pilot.yaml --max-wall-seconds 120
python -m experience_lab.cli benchmark --config configs/stationary.yaml --output results/stationary
python -m experience_lab.cli benchmark --config configs/transfer.yaml --output results/transfer
python -m experience_lab.cli report --input results/stationary --output results/report
```

Provide Windows PowerShell setup commands in README; do not assume Bash activation. ANSI terminal rendering and saved PNG frames are sufficient for the first demo. Rendering must not expose hidden rules in the agent's observation path.

## 10. Tests that matter

1. Truth tables match Boolean definitions; equivalent functions are deduplicated.
2. Every candidate family includes the rules used by its stationary generators.
3. Collision, toggle, closed-door, reward, termination, truncation, and reset semantics are correct.
4. Identical seeds and action sequences produce identical observations and rewards.
5. All switches are reachable in the closed-door control area; accepted worlds are oracle-solvable within an appropriate validated limit.
6. A learner cannot access hidden rules or seeds through observations, info, constructor arguments, or logs fed back into decisions.
7. Two different hidden worlds producing the same public action-observation history produce the same belief state and, for the same agent RNG, the same next action.
8. Filtering preserves the true hypothesis under noiseless stationary data; repeated observations do not create additional evidence.
9. Known rule fixtures produce known shortest paths. A conservative predicted plan succeeds when executed against a compatible hidden world.
10. Active scoring prefers informative probes on a constructed fixture; a second fixture verifies the travel-cost trade-off. These are unit checks, not benchmark results.
11. Transfer retains rules but discards stale geometry. Starting a genuinely independent world resets all learned beliefs.
12. Saving/resuming preserves RNG state, beliefs, schedule position, and result identities without duplicate records.
13. For E3, contradictory evidence repairs only the specified scope and stationary data causes no false contradiction.

An oracle solver can be used for generation and tests. Its privileged access must remain separate from agent code.

## 11. Runtime limits and reproducibility

- Default to one local process until the pilot identifies a reason for concurrency.
- Enforce max wall time, environment actions, planner expansions, and episode count independently.
- Check time limits inside long planner/runner loops, not just between full runs.
- Save small JSON/JSONL records incrementally and atomically checkpoint completed work.
- Save model beliefs, relevant evidence, RNG state, config, schedule position, and run identifiers. Include environment state if resuming mid-episode; otherwise mark the interrupted episode and restart it reproducibly without counting partial results twice.
- Manifest: UTC time, git commit and dirty status, dependency versions, config hash, seed hierarchy, hardware summary, budgets, method, and completion status.
- Record failed and interrupted runs; never overwrite them with successful-looking summaries.
- Keep output paths explicit. Never upload or publish without a user request.
- Resume under the same configuration only; refuse incompatible config hashes unless creating a new run.
- Prefer a batch script executing experiments directly. Avoid an LLM reasoning turn for each agent action or training step.

The project has no external training/API cost by design. Cursor subscription/usage consumption still depends on the user's plan. Do not promise that coding-agent usage is unlimited or free.

## 12. Milestones and gates

### Milestone A — an honest working pilot

Implement minimal environment, candidate rules, belief filtering, conservative planner, active probe selection, oracle tests, and a terminal trace. Include a simple systematic comparator.

Deliver: tests, one reproducible real trace, timing, and a short explanation of exactly what was learned.

Gate: at least one controlled example demonstrates useful belief change and use of that belief to reach a goal. No runtime claims without measurement. Stop and diagnose if the learner cannot solve fixtures that the oracle can solve.

### Milestone B — a fair stationary benchmark

Add validated template generation, random-informative baseline, manifests, resumable batches, and plots. Run the small development suite.

Gate: methods receive identical public information and comparable task schedules; output counts reconcile with the manifest; repeats reproduce trajectories excluding timing fields.

### Milestone C — knowledge reuse

Implement held-out layout transfer with retained versus reset knowledge. Produce a report containing both pretraining cost and test cost.

Gate: transfer works mechanically, and the report distinguishes benefit, no benefit, and uncertainty. A negative result does not fail the project.

### Milestone D — final evidence and optional change adaptation

Freeze configs and run the measured, affordable final suite. Add E3 only after the core artifact is stable. Add extra methods only to answer a specific remaining question.

Do not run an unbounded experiment sweep. Do not spend time on presentation polish before the evidence pipeline works.

## 13. Failure cases worth reporting

- Systematic enumeration matches or beats active exploration: the hypothesis space may be too small for selection overhead to pay off.
- Information-focused probes learn irrelevant doors: the heuristic optimizes information, not exact goal value. A later goal-relevance ablation may be justified, but do not quietly change the final protocol.
- Task solving succeeds before full identification: this is expected and should not be called incomplete learning failure.
- Transfer benefit vanishes once pretraining cost is included: report the number of future tasks needed to amortize it, if measurable.
- Different formulas produce the same truth table: they are the same behavior for this experiment, not distinct scientific discoveries.
- Changing rules remain consistent with existing evidence: no agent can detect an unobserved difference immediately.
- Environment rejection biases the world distribution toward easy cases: publish rejection counts and reasons, and bound generation attempts.
- CPU time is dominated by planning rather than interaction: profile the planner before adding more runs or methods.

## 14. GitHub deliverable and claims

README should contain:

1. One paragraph stating the question and limitations.
2. A short real demo showing an uncertain prediction, a chosen experiment, the observed outcome, and an updated plan.
3. Copy-paste setup and pilot commands.
4. Diagram of public observations -> hypotheses -> planning/experiment choice -> action -> observation.
5. A results table with methods, independent worlds, success, action costs, uncertainty, and compute.
6. Links to configs, selected raw logs, and reproduction commands.
7. Failure cases, prior assumptions, and a related-work section.
8. A brief AI-assistance disclosure describing coding assistance and human verification.

Suggested description, to use only once supported by completed experiments:

> A CPU-only experimental platform for learning hidden switch-door rules through interaction. It compares active, random, and systematic experimentation and measures reuse of learned mechanisms across new layouts.

Never claim: 'no human knowledge', 'discovered general intelligence', 'first comparison', 'state of the art', 'solved continual learning', or a benchmark win unsupported by retained results.

The credible contribution is an inspectable experimental system and a well-supported answer to a narrow question. Originality is not established by this specification.

## 15. Reading and attribution

These are background and related work, not claims that this exact project reproduces their results:

- Sutton and Barto, Reinforcement Learning: An Introduction, chapter on planning and learning: https://www.incompleteideas.net/book/bookdraft2018mar21.pdf — background for learning a model and using it to plan. This project is not a Dyna-Q replication.
- Gymnasium environment contract: https://gymnasium.farama.org/api/env/ — reference if implementing a Gymnasium adapter; distinguish termination from truncation and seed resets correctly.
- Gymnasium custom environments: https://gymnasium.farama.org/introduction/create_custom_env/ — implementation reference, not a required dependency.
- Elahi et al., Adaptive Online Experimental Design for Causal Discovery: https://proceedings.mlr.press/v235/elahi24a.html — related research on adaptive interventions; different assumptions and objectives.
- Kosoy et al., Learning Causal Overhypotheses through Exploration in Children and Computational Models: https://proceedings.mlr.press/v177/kosoy22a.html — related exploration and structured causal-learning work.
- One Life to Learn: Inferring Symbolic World Models for Stochastic Environments from Unguided Exploration: https://proceedings.iclr.cc/paper_files/paper/2026/hash/a24d08f2eecc6c96f4a0ad37a74ddeca-Abstract-Conference.html — relevant broader symbolic-world-model work; our finite deterministic setting is much smaller.

Before claiming a research gap, read the nearest relevant work and update related_work.md. Before reusing code, inspect its license, preserve attribution, and distinguish reused components from original implementation.

## 16. First instruction to the Cursor agent

Start with Milestone A only, following the companion CURSOR_START_PROMPT.md. Complete useful code and run the bounded pilot. Then provide measured results and a recommendation for the next affordable experiment. Do not implement every later extension at once.
