import pytest
from hypothesis import given
from hypothesis import strategies as st
from src.rule import Rule, SimpleRule, StepDifferenceRule, StatefulRule, Operator, Logic

readings_value = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e9, max_value=1e9)
threshold_value = st.floats(allow_nan=False, allow_infinity=False, min_value=-1e6, max_value=1e6)
max_violations_value = st.integers(min_value=2, max_value=10)
priority_st = st.integers(min_value=1, max_value=3)
name_st = st.text(min_size=1, max_size=20)
operator_st = st.sampled_from(list(Operator))
logic_st = st.sampled_from(list(Logic))
repeat_none_times_value = st.integers(min_value=1, max_value=5)


@pytest.fixture(autouse=True)
def reset_rule_ids():
    Rule._next_id = 0


# ----------
# SimpleRule
# ----------

class TestPrioritySimpleRule:

    @given(threshold_value, readings_value, operator_st)
    def test_operator_matches_python_operator(self, threshold, reading, operator):
        rule = SimpleRule(1, "rule1", 0, threshold, operator)
        result = rule.is_violated([reading])

        if operator == Operator.LESS:
            assert result == (reading < threshold)
        else:
            assert result == (reading > threshold)

    @given(threshold_value, readings_value, operator_st, repeat_none_times_value)
    def test_none_reading_returs_last_known(self, threshold, reading, operator, repeat_none_times):
        rule = SimpleRule(1, "rule1", 0, threshold, operator)
        result1 = rule.is_violated([reading])

        for _ in range(repeat_none_times):
            result2 = rule.is_violated([None])
            assert result1 == result2

    @given(threshold_value, operator_st, repeat_none_times_value)
    def test_none_readings_default_to_none(self, threshold, operator, repeat_none_times):
        rule = SimpleRule(1, "rule1", 0, threshold, operator)

        for _ in range(repeat_none_times):
            assert not rule.is_violated([None])

    @given(threshold_value, operator_st)
    def test_equal_to_threshold_gives_false(self, threshold, operator):
        rule = SimpleRule(1, "rule1", 0, threshold, operator)
        assert not rule.is_violated([threshold])


# ------------------
# StepDifferenceRule
# ------------------

class TestPriorityStepDifferenceRule:

    @given(threshold_value, readings_value, operator_st)
    def test_first_reading_never_violated(self, step, reading, operator):
        rule = StepDifferenceRule(1, "rule1", 0, step, operator)
        assert not rule.is_violated([reading])

    @given(threshold_value, operator_st, repeat_none_times_value)
    def test_none_readings_default_to_none(self, step, operator, repeat_none_times):
        rule = StepDifferenceRule(1, "rule1", 0, step, operator)

        for _ in range(repeat_none_times):
            assert not rule.is_violated([None])

    @given(
        readings_value,
        st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_violate_operator_greater(self, reading, delta):
        step = delta / 2  # step is strictly less than delta
        rule = StepDifferenceRule(1, "rule1", 0, step, Operator.GREATER)
        rule.is_violated([reading])
        assert rule.is_violated([reading + delta])

    @given(
        readings_value,
        st.floats(min_value=0.01, max_value=1e6, allow_nan=False, allow_infinity=False),
    )
    def test_violate_operator_less(self, reading, delta):
        step = delta / 2  # step is strictly less than delta
        rule = StepDifferenceRule(1, "rule1", 0, step, Operator.LESS)
        rule.is_violated([reading])
        assert rule.is_violated([reading - delta])


# ------------
# StatefulRule
# ------------


class TestPriorityStatefulRule:

    @given(threshold_value, max_violations_value, operator_st)
    def test_never_violated_before_max_violations_reached(self, threshold, max_violations, operator):
        # Ensure reading actually violates the simple threshold condition
        if operator == Operator.LESS:
            reading = threshold - 1.0
        else:
            reading = threshold + 1.0

        rule = StatefulRule(1, "rule1", 0, threshold, max_violations, operator)
        for _ in range(max_violations - 1):
            assert not rule.is_violated([reading])

    @given(threshold_value, max_violations_value, operator_st)
    def test_violated_when_max_violations_reached(self, threshold, max_violations, operator):
        # Ensure reading actually violates the simple threshold condition
        if operator == Operator.LESS:
            reading = threshold - 1.0
        else:
            reading = threshold + 1.0

        rule = StatefulRule(1, "rule1", 0, threshold, max_violations, operator)
        for _ in range(max_violations - 1):
            rule.is_violated([reading])

        assert rule.is_violated([reading])

    @given(threshold_value, max_violations_value, operator_st, repeat_none_times_value)
    def test_none_keeps_the_violation(self, threshold, max_violations, operator, repeat_none_times):
        # Ensure reading actually violates the simple threshold condition
        if operator == Operator.LESS:
            reading = threshold - 1.0
        else:
            reading = threshold + 1.0

        rule = StatefulRule(1, "rule1", 0, threshold, max_violations, operator)
        for _ in range(max_violations):
            rule.is_violated([reading])

        for _ in range(repeat_none_times):
            assert rule.is_violated([reading])
