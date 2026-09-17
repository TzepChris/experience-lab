# Certificate and bucket audit (development matrix)

Evaluator-only audit of the existing `results/checkpoint_ul_stopping/`
batch. Method C's **policy is unchanged**. Logging now names certificates
explicitly so a compute-cap exploit cannot be read as certified
optimality.

## Planner caps in the existing batch

C later-episode decisions: **1800**. Hypothesis searches logged: **3708**.
All searches had status `ok`. **Planner-cap decisions: 0**. Time-limit
decisions: 0.

Retrospective certificates from those logs (policy already matched this):

- `shorter_plan_witness`: 99 (optional probe)
- `certified_no_headroom`: 1701 (exploit, every remaining assignment
  resolved and `L == U`)
- `undecided`: 0

No existing decision exploited because of a compute cap. The certificate
field is still required: a resolved hypothesis of cost `U` plus a capped
search must not be logged as `certified_no_headroom`. That case is
tested and remains `undecided` while still exploiting.

## Acquisition buckets versus exploit-plan cost U

`starting_condition` / `acquisition_bucket` compares **episode-0
acquisition cost** to the **oracle episode-0 cost**. It is not the
current conservative exploit-plan length `U`. Bucket labels are not
passed into learner decisions.

Explicit instance-to-bucket rows:
`results/checkpoint_ul_stopping/bucket_assignments.json`.

The development-matrix report described C's cheap-systematic losses as
swapped AND/`x1`. That permutation split is real. Those cells are **not**
the expensive-systematic AND/`x1` cells from the earlier table.

On `probe_spur`, systematic AND/`x1`:

| perm | rule | ep0 | oracle ep0 | bucket | first U |
| --- | --- | ---: | ---: | --- | ---: |
| `[0,1]` identity | x1 | 24 | 19 | expensive_systematic | 20 |
| `[1,0]` swap | x1 | 19 | 19 | cheap_systematic_control | 19 |
| `[0,1]` identity | AND | 24 | 20 | expensive_systematic | 20 |
| `[1,0]` swap | AND | 20 | 20 | cheap_systematic_control | 20 |

Expensive-systematic AND/`x1` is identity labels, where episode 0 paid
more than oracle. Cheap-systematic AND/`x1` is the swap, where episode 0
already matched oracle. C's small losses are in the **cheap-acquisition**
rows: `U` still equals oracle, but a remaining false hypothesis had
`L < U`, so C took a `shorter_plan_witness` probe that did not repay.

`tiny_two_switch` x1 is the same split: identity `ep0=14 > oracle=13`
(expensive_systematic); swap `ep0=oracle=13` (cheap_systematic_control).

XOR/OR expensive-systematic cells remain the swapped-ID copies. Bucket
membership is per instance, not a blanket "swap = expensive" rule.

## Frozen methods

A, B, and C stay the development-matrix methods. C adds certificate
names only. Old maps remain regression data. The 20-map holdout is a
separate frozen test.
