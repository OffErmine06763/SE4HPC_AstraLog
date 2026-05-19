import pytest
from src.rule import \
    Rule, Operator, Logic, SimpleRule, StatefulRule, \
    StepDifferenceRule, LogicalCorrelationRule


@pytest.fixture(autouse=True)
def reset_rule_ids():
    """Reset class-level IDs so tests are deterministic."""
    Rule._next_id = 0


# --------------------
# Base class behaviour
# --------------------

def test_rule_ids_incrementing_correctly():
    rule1 = Rule(1, 'name1')
    rule2 = Rule(2, 'name2')

    assert rule1.id == 0
    assert rule2.id == 1


def test_rule_fields_set():
    rule = Rule(1, 'name1')

    assert rule.priority == 1
    assert rule.name == 'name1'


# ----------
# SimpleRule
# ----------

def test_simple_rule_set():
    rule = SimpleRule(100, 'name1', 1, 0.5, Operator.LESS)

    assert rule.priority == 100
    assert rule.name == 'name1'
    assert rule.sensor_id == 1
    assert rule.threshold == 0.5
    assert rule.operator == Operator.LESS


def test_simple_rule_empty_readings():
    rule = SimpleRule(100, 'name1', 1, 0.5, Operator.LESS)

    assert not rule.is_violated([None, None])


def test_simple_rule_violated_less():
    rule = SimpleRule(100, 'name1', 1, 0.5, Operator.LESS)

    assert rule.is_violated([0.4, 0.49])


def test_simple_rule_non_violated_less():
    rule = SimpleRule(100, 'name1', 1, 0.5, Operator.LESS)

    assert not rule.is_violated([0.4, 0.5])
    assert not rule.is_violated([0.4, 0.51])


def test_simple_rule_violated_greater():
    rule = SimpleRule(100, 'name1', 1, 0.5, Operator.GREATER)

    assert rule.is_violated([0.4, 0.51])


def test_simple_rule_non_violated_greater():
    rule = SimpleRule(100, 'name1', 1, 0.5, Operator.GREATER)

    assert not rule.is_violated([0.4, 0.5])
    assert not rule.is_violated([0.4, 0.49])


def test_simple_rule_violated_stays_the_same():
    rule = SimpleRule(100, 'name1', 1, 0.5, Operator.LESS)

    assert rule.is_violated([0.4, 0.4])
    assert rule.is_violated([0.4, None])


# ------------------
# StepDifferenceRule
# ------------------


def test_step_difference_rule_set():
    rule = StepDifferenceRule(100, 'name1', 0, 0.2, Operator.LESS)

    assert rule.priority == 100
    assert rule.name == 'name1'
    assert rule.sensor_id == 0
    assert rule.step == 0.2
    assert rule.operator == Operator.LESS


def test_step_difference_rule_violated_less():
    rule = StepDifferenceRule(100, 'name1', 0, 0.2, Operator.LESS)
    rule.is_violated([1.0])

    assert rule.is_violated([1.1])


def test_step_difference_rule_non_violated_less():
    rule = StepDifferenceRule(100, 'name1', 0, 0.2, Operator.LESS)
    rule.is_violated([1.0])

    assert not rule.is_violated([1.21])


def test_step_difference_rule_violated_greater():
    rule = StepDifferenceRule(100, 'name1', 0, 0.2, Operator.GREATER)
    rule.is_violated([1.0])

    assert rule.is_violated([1.21])


def test_step_difference_rule_non_violated_greater():
    rule = StepDifferenceRule(100, 'name1', 0, 0.2, Operator.GREATER)
    rule.is_violated([1.0])

    assert not rule.is_violated([1.19])


def test_step_difference_rule_reading_none_greater():
    rule = StepDifferenceRule(100, 'name1', 0, -0.1, Operator.GREATER)

    assert not rule.is_violated([None])
    assert not rule.is_violated([1.0])  # not ready
    assert rule.is_violated([None])


def test_step_difference_rule_reading_none_less():
    rule = StepDifferenceRule(100, 'name1', 0, 0.1, Operator.LESS)

    assert not rule.is_violated([None])
    assert not rule.is_violated([1.0])  # not ready
    assert rule.is_violated([None])

# ------------
# StatefulRule
# ------------


def test_stateful_rule_set():
    rule = StatefulRule(100, 'name1', 0, 0.5, 3, Operator.LESS)

    assert rule.priority == 100
    assert rule.name == 'name1'
    assert rule.sensor_id == 0
    assert rule.threshold == 0.5
    assert rule.max_violations == 3
    assert rule.operator == Operator.LESS


def test_stateful_rule_less():
    rule = StatefulRule(100, 'name1', 0, 0.5, 3, Operator.LESS)

    assert not rule.is_violated([0.5])
    assert not rule.is_violated([0.4])
    assert not rule.is_violated([0.5])
    assert not rule.is_violated([0.3])
    assert not rule.is_violated([0.2])
    assert rule.is_violated([0.1])
    assert rule.is_violated([0.1])
    assert not rule.is_violated([0.5])


def test_stateful_rule_greater():
    rule = StatefulRule(100, 'name1', 0, 0.5, 3, Operator.GREATER)

    assert not rule.is_violated([0.5])
    assert not rule.is_violated([0.6])
    assert not rule.is_violated([0.5])
    assert not rule.is_violated([0.6])
    assert not rule.is_violated([0.7])
    assert rule.is_violated([0.8])
    assert rule.is_violated([0.6])
    assert not rule.is_violated([0.5])


def test_stateful_rule_empty_readings():
    rule = StatefulRule(100, 'name1', 0, 0.5, 3, Operator.GREATER)

    assert not rule.is_violated([None])
    assert not rule.is_violated([None])
    assert not rule.is_violated([None])

    assert not rule.is_violated([0.8])
    assert not rule.is_violated([None])
    assert rule.is_violated([None])
    assert rule.is_violated([None])


# ----------------------
# LogicalCorrelationRule
# ----------------------

def test_logical_correlation_rule_set():
    rule = LogicalCorrelationRule(100, 'name1', Logic.AND, 1, 2)

    assert rule.priority == 100
    assert rule.name == 'name1'
    assert rule.logic == Logic.AND
    assert rule.op1 == 1
    assert rule.op2 == 2


def test_logical_correlation_rule_and():
    rule = LogicalCorrelationRule(100, 'name1', Logic.AND, 1, 2)

    assert not rule.is_violated(False, False)
    assert not rule.is_violated(False, True)
    assert not rule.is_violated(True, False)
    assert rule.is_violated(True, True)


def test_logical_correlation_rule_or():
    rule = LogicalCorrelationRule(100, 'name1', Logic.OR, 1, 2)

    assert not rule.is_violated(False, False)
    assert rule.is_violated(False, True)
    assert rule.is_violated(True, False)
    assert rule.is_violated(True, True)
