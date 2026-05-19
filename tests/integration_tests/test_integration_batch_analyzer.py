import pytest
from src.rule import Rule, SimpleRule, LogicalCorrelationRule, Operator, Logic
from src.batch_analyzer import BatchAnalyzer
from src.utils import TimestampData


@pytest.fixture(autouse=True)
def reset_rule_ids():
    """Reset class-level IDs so tests are deterministic."""
    Rule._next_id = 0


def complex_rules():
    return [
        SimpleRule(1, "simple1", 0, 0.5, Operator.GREATER),
        SimpleRule(0, "simple2", 1, 0.5, Operator.LESS),
        LogicalCorrelationRule(2, "and1", Logic.AND, 0, 1),
        SimpleRule(2, "simple3", 2, 0.5, Operator.GREATER),
        SimpleRule(0, "simple4", 3, 0.5, Operator.LESS),
        LogicalCorrelationRule(0, "and2", Logic.AND, 3, 4),
        LogicalCorrelationRule(2, "or", Logic.OR, 2, 5)
    ]


def timestamp_data():
    return [
        TimestampData("time1", [None, None, None, None]),
        TimestampData("time2", [0.6, 0.4, 0.6, 0.4]),
        TimestampData("time3", [None, None, None, None]),
        TimestampData("time4", [0.4, 0.6, 0.4, 0.6]),
        TimestampData("time5", [0.6, 0.4, 0.4, 0.6])
    ]


def test_analyzing_batched_data(tmp_path):
    valid_output_file = tmp_path / "valid_output.txt"
    alarms_output_file = tmp_path / "alarm_output.txt"

    analyzer = BatchAnalyzer()
    analyzer.set_sensors(["sensor1", "sensor2", "sensor3", "sensor4"])
    analyzer.set_valid_output_file(str(valid_output_file))
    analyzer.set_alarms_output_file(str(alarms_output_file))
    analyzer.load_rules(complex_rules())
    analyzer.analyze_and_output(timestamp_data())
    analyzer.deinit()

    expected_valid_output = "time1;NOMINAL;sensor1:None|sensor2:None|sensor3:None|sensor4:None\n"
    expected_valid_output += "time4;NOMINAL;sensor1:0.4|sensor2:0.6|sensor3:0.4|sensor4:0.6\n"

    expected_alarms_output = """time2;simple1;MEDIUM;sensor1;0.6
time2;simple2;LOW;sensor2;0.4
time2;simple3;HIGH;sensor3;0.6
time2;simple4;LOW;sensor4;0.4
time2;and1;HIGH;sensor1,sensor2;0.6,0.4
time2;and2;LOW;sensor3,sensor4;0.6,0.4
time2;or;HIGH;sensor1,sensor2,sensor3,sensor4;0.6,0.4,0.6,0.4
time3;simple1;MEDIUM;sensor1;None
time3;simple2;LOW;sensor2;None
time3;simple3;HIGH;sensor3;None
time3;simple4;LOW;sensor4;None
time3;and1;HIGH;sensor1,sensor2;None,None
time3;and2;LOW;sensor3,sensor4;None,None
time3;or;HIGH;sensor1,sensor2,sensor3,sensor4;None,None,None,None
time5;simple1;MEDIUM;sensor1;0.6
time5;simple2;LOW;sensor2;0.4
time5;and1;HIGH;sensor1,sensor2;0.6,0.4
time5;or;HIGH;sensor1,sensor2,sensor3,sensor4;0.6,0.4,0.4,0.6
"""

    actual_valid_output = valid_output_file.read_text()
    actual_alarm_output = alarms_output_file.read_text()

    assert expected_valid_output == actual_valid_output
    assert expected_alarms_output == actual_alarm_output
