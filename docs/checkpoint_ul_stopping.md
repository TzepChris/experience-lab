# Frozen checkpoint U/L stopping matrix

Same frozen instance matrix as `docs/checkpoint_complete_probe.md` and
`configs/checkpoint_complete_probe.yaml`. Do not edit probe-choice,
closed-door re-probe, or the A-vs-B checkpoint configs.

## Pairing

Episode 0 is collected once from `systematic_retained` and `active_retained`.
Three learners copy that public belief:

- A `checkpoint_exploit`: execute a conservative goal plan when one exists.
- B `checkpoint_complete_reprobe`: at most one completed-target
  information-per-action probe per later episode, then exploit.
- C `checkpoint_ul_stopping`: hand-designed U vs L stopping rule, not a
  learned policy.

C uses only public geometry, the current observation, and the learner's
remaining complete rule hypotheses. It does not read the hidden rule,
evaluator oracle costs, checkpoint bucket labels, or which agent collected
episode 0.

C certificates (logging only; policy unchanged):

- `certified_no_headroom`: every remaining complete hypothesis search
  resolved and `min L_h == U`
- `shorter_plan_witness`: a resolved hypothesis has a path shorter than `U`
- `undecided`: unresolved searches prevent a no-headroom certificate

Exploiting after a compute cap is allowed. It is not logged as certified
optimality.

## Method C

`U` is the length of the existing conservative shortest goal plan.

For each surviving complete assignment `h` (one remaining table per door,
held fixed for the whole search), `L_h` is the shortest goal-plan length
assuming `h` is true from the current state. `L` is the minimum among
decided `L_h`. Predictions from incompatible hypotheses are not mixed.

At each later episode start:

- If `U == L`, exploit immediately.
- If `L < U`, allow one completed-target information-per-action probe,
  exactly as B does, then exploit.
- If no conservative plan exists, use the existing required-exploration
  behavior.

Planner-cap or time-limit exhaustion is **undecided**. It is not proof that
no shorter hypothetical route exists, so it does not authorize a probe.

Log `U`, `L`, the decision, actual extra-probe actions, and planning
overhead expansions.

## Reporting

Unchanged prefixes 1, 2, 5, 10. Lifetime = shared episode 0 + later prefix.
Report success, lifetime action costs, and wall time for A, B, and C.
C is not required to win.
