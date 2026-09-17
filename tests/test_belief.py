import pytest

from experience_lab.belief import Belief, EmptyHypothesisError
from experience_lab.rules import table_by_name


def _belief() -> Belief:
    return Belief.prior(2, ("door0",))


def test_filtering_keeps_true_and_rule():
    true = table_by_name(2, "x0_and_x1")
    belief = _belief()
    for cfg in range(4):
        belief.update(cfg, (true(cfg),))
    assert belief.identified_name("door0") == "x0_and_x1"
    assert belief.hypothesis_count("door0") == 1


def test_duplicate_observation_is_not_new_evidence():
    belief = _belief()
    first = belief.update(0, (False,))
    count = belief.hypothesis_count("door0")
    second = belief.update(0, (False,))
    assert first is True
    assert second is False
    assert len(belief.evidence) == 1
    assert belief.hypothesis_count("door0") == count


def test_repeated_observation_does_not_shrink_again():
    belief = _belief()
    belief.update(0, (False,))
    names = belief.names("door0")
    belief.update(0, (False,))
    assert belief.names("door0") == names
    assert "not_x0" not in names
    assert "x0_and_x1" in names


def test_empty_hypothesis_is_an_error():
    belief = _belief()
    belief.update(0, (False,))
    belief.update(1, (False,))
    with pytest.raises(EmptyHypothesisError):
        belief.update(3, (False,))


def test_contradictory_duplicate_is_an_error():
    belief = _belief()
    belief.update(0, (False,))
    with pytest.raises(EmptyHypothesisError):
        belief.update(0, (True,))
