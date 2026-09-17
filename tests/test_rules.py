from experience_lab.rules import (
    candidate_family,
    initially_closed_rule_names,
    permute_rule_name,
    table_by_name,
)


def test_s2_family_has_seven_distinct_tables():
    family = candidate_family(2)
    assert len(family) == 7
    assert len({table.bits for table in family}) == 7


def test_named_tables_match_boolean_definitions():
    x0 = table_by_name(2, "x0")
    x1 = table_by_name(2, "x1")
    not_x0 = table_by_name(2, "not_x0")
    and_t = table_by_name(2, "x0_and_x1")
    or_t = table_by_name(2, "x0_or_x1")
    xor_t = table_by_name(2, "x0_xor_x1")
    for cfg in range(4):
        b0 = bool(cfg & 1)
        b1 = bool(cfg & 2)
        assert x0(cfg) is b0
        assert x1(cfg) is b1
        assert not_x0(cfg) is (not b0)
        assert and_t(cfg) is (b0 and b1)
        assert or_t(cfg) is (b0 or b1)
        assert xor_t(cfg) is (b0 ^ b1)


def test_family_includes_stationary_pilot_rules():
    names = {table.name for table in candidate_family(2)}
    for name in ("x0", "x0_and_x1", "x0_xor_x1"):
        assert name in names


def test_equivalent_formulas_would_deduplicate_if_added():
    family = candidate_family(2)
    bits = {table.bits for table in family}
    assert len(bits) == len(family)


def test_swap_permutation_rewrites_x0_to_x1():
    assert permute_rule_name("x0", 2, (1, 0)) == "x1"
    assert permute_rule_name("x1", 2, (1, 0)) == "x0"
    assert permute_rule_name("x0_and_x1", 2, (1, 0)) == "x0_and_x1"
    assert permute_rule_name("x0_xor_x1", 2, (1, 0)) == "x0_xor_x1"
    assert permute_rule_name("x0_or_x1", 2, (1, 0)) == "x0_or_x1"


def test_initially_closed_names_exclude_not_rules():
    assert initially_closed_rule_names(2) == (
        "x0",
        "x1",
        "x0_and_x1",
        "x0_or_x1",
        "x0_xor_x1",
    )
