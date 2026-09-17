# Frozen checkpoint complete-probe matrix

Frozen before A-vs-B checkpoint rankings. Separate from
`docs/probe_choice_matrix.md` and `docs/reprobe_matrix.md`.
Do not edit `configs/probe_choice.yaml` or `configs/reprobe_closed_door.yaml`.

## Why this comparison exists

The closed-door re-probe comparison forked from **active** episode-0 states.
On this matrix those states were already cheap after episode 0. It did not
test recovery from the **systematic** agent's expensive known solution.

This experiment collects real episode-0 histories from both `systematic_retained`
and `active_retained`, then forks two copies of that public belief.

## Rules and layouts

Same five initially closed rules (`x0`, `x1`, AND, OR, XOR) and the same three
layouts. Switch permutations `[0,1]` and `[1,0]` rewrite the hidden rule so
physics is unchanged.

## Pairing

1. Run episode 0 with the source agent. Save hypotheses and evidence.
2. Physical reset. Create two identical learners from that checkpoint:
   - A `checkpoint_exploit`: if a conservative plan exists, execute it.
   - B `checkpoint_complete_reprobe`: at most one information-per-action
     extra probe per later episode, then exploit.
3. B uses the existing selector. No new heuristic. Hidden rules and oracle
   costs are not learner inputs.
4. B **completes the selected target configuration**. Intermediate
   observations still update the belief. The probe does not stop at the
   first TOGGLE. Log intended target, configs visited, target reached,
   information gained, and early-stop reason.

Required probing when no safe plan exists still uses the source selector
(active or systematic). Extra probes still use information-per-action.

## Reporting

- Include every checkpoint, including already-cheap controls.
- Report expensive-systematic and cheap-active starts separately.
- Pair A and B inside each identical checkpoint.
- Cumulative later-episode actions at prefixes 1, 2, 5, 10.
- Shared episode-0 acquisition cost is reported separately and in lifetime
  totals (episode 0 + later prefix).
- Distinguish labeled extra-probe actions from additional actions versus A.

Seeds `1, 2, 3` repeat instances. Wall cap 120 seconds.
