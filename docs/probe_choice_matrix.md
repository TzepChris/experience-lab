# Frozen probe-choice matrix

Frozen before method rankings were inspected. Do not edit layouts or the
schedule below in order to make active exploration look better.

## Factors

- Layouts: `tiny_two_switch` (control), `probe_spur`, `probe_spur_mirror`
- Rules (identity labeling): `x0_and_x1`, `x0_xor_x1`, `x0`
- Switch permutations: `[0, 1]` (identity) and `[1, 0]` (swap IDs)
- Seeds: `1, 2, 3` (algorithm RNG / tie-breaking only)
- Episodes: 2
- Methods: `active_retained`, `active_reset`, `systematic_retained`,
  `systematic_reset`, `random_informative_retained`,
  `random_informative_reset`, `oracle`

Permutation rewrites the hidden rule so the physical mechanism is unchanged.
Canonical systematic order still uses integer configs `0, 1, 2, 3` over the
public bit indices, so swapping IDs tests order sensitivity.

## Why these spur maps exist

On `tiny_two_switch`, the first systematic config is also a cheap on-path
probe, so selection cannot change cost. `probe_spur` puts one switch on the
door path and the other down a dead-end. Unnecessary probing of the spur can
add travel; probing the near switch first can also force a later round trip
when both switches are required.

`probe_spur_mirror` is a horizontal reflection with the same distances.

## Instance vs seed

A distinct problem/instance is `(layout, requested_rule, permutation)`.
Seeds repeat the same instance for tie-breaking. Do not treat 3 seeds as 3
independent worlds.
