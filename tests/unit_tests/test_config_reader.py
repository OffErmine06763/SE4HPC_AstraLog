import pytest
import json
import yaml
from unittest.mock import patch
from src.config_reader import str_to_priority, str_to_operator, str_to_logic, parse_rules_config, parse_sensors_config
from src.rule import Rule, Operator, Logic, SimpleRule, StatefulRule, StepDifferenceRule, LogicalCorrelationRule


SENSOR_IDS = {
    "TEMP-01": 1,
    "PRES-01": 2,
    "VOLT-MAIN": 3
}


@pytest.fixture(autouse=True)
def reset_rule_ids():
    """Reset class-level IDs so tests are deterministic."""
    Rule._next_id = 0


# ------------------------------
# Helper functions (str to enum)
# ------------------------------

def test_str_to_priority():
    assert str_to_priority("LOW") == 0
    assert str_to_priority("MEDIUM") == 1
    assert str_to_priority("HIGH") == 2


def test_str_to_operator():
    assert str_to_operator("<") == Operator.LESS
    assert str_to_operator(">") == Operator.GREATER


def test_str_to_logic():
    assert str_to_logic("AND") == Logic.AND
    assert str_to_logic("OR") == Logic.OR


# --------------------
# Parse rules config
# --------------------

def test_parse_rules_simple_rule(tmp_path):
    data = [
        {
            "rule_id": "R1",
            "type": "simple",
            "sensor_id": "TEMP-01",
            "operator": ">",
            "value": 50.0,
            "priority": "MEDIUM"
        }
    ]

    file = tmp_path / "rules.json"
    file.write_text(json.dumps(data))

    ok, rules = parse_rules_config(str(file), SENSOR_IDS)

    assert ok == True
    assert len(rules) == 1
    assert isinstance(rules[0], SimpleRule)
    assert rules[0].name == "R1"
    assert rules[0].sensor_id == 1
    assert rules[0].operator == Operator.GREATER
    assert rules[0].threshold == 50.0
    assert rules[0].priority == 1


def test_parse_rules_step_difference_rule(tmp_path):
    data = [
        {
            "rule_id": "R2",
            "type": "step_difference",
            "sensor_id": "PRES-01",
            "operator": "<",
            "value": -2.0,
            "priority": "LOW"
        }
    ]

    file = tmp_path / "rules.json"
    file.write_text(json.dumps(data))

    ok, rules = parse_rules_config(str(file), SENSOR_IDS)

    assert ok == True
    assert len(rules) == 1
    assert isinstance(rules[0], StepDifferenceRule)
    assert rules[0].name == "R2"
    assert rules[0].sensor_id == 2
    assert rules[0].operator == Operator.LESS
    assert rules[0].step == -2.0
    assert rules[0].priority == 0


def test_parse_rules_stateful_rule(tmp_path):
    data = [
        {
            "rule_id": "R3",
            "type": "stateful",
            "sensor_id": "VOLT-MAIN",
            "operator": "<",
            "value": 20.0,
            "consecutive_measurements": 5,
            "priority": "HIGH"
        }
    ]

    file = tmp_path / "rules.json"
    file.write_text(json.dumps(data))

    ok, rules = parse_rules_config(str(file), SENSOR_IDS)

    assert ok == True
    assert len(rules) == 1
    assert isinstance(rules[0], StatefulRule)
    assert rules[0].name == "R3"
    assert rules[0].sensor_id == 3
    assert rules[0].operator == Operator.LESS
    assert rules[0].threshold == 20.0
    assert rules[0].max_violations == 5
    assert rules[0].priority == 2


def test_parse_rules_logical_correlation_rule(tmp_path):
    data = [
        {
            "rule_id": "R1",
            "type": "simple",
            "sensor_id": "TEMP-01",
            "operator": ">",
            "value": 50.0,
            "priority": "MEDIUM"
        },
        {
            "rule_id": "R2",
            "type": "step_difference",
            "sensor_id": "PRES-01",
            "operator": "<",
            "value": -2.0,
            "priority": "LOW"
        },
        {
            "rule_id": "R4",
            "type": "correlation",
            "logic": "AND",
            "conditions": ["R1", "R2"],
            "priority": "HIGH"
        }
    ]

    file = tmp_path / "rules.json"
    file.write_text(json.dumps(data))

    ok, rules = parse_rules_config(str(file), SENSOR_IDS)

    assert ok == True
    assert len(rules) == 3
    assert isinstance(rules[2], LogicalCorrelationRule)
    assert rules[2].name == "R4"
    assert rules[2].priority == 2
    assert rules[2].op1 == 0
    assert rules[2].op2 == 1


def test_parse_rules_file_not_found():
    ok, rules = parse_rules_config("does_not_exist.json", SENSOR_IDS)

    assert ok == False
    assert rules == []


def test_parse_rules_invalid_json(tmp_path):
    data = "{bad json"

    file = tmp_path / "rules.json"
    file.write_text(data)

    ok, rules = parse_rules_config(str(file), SENSOR_IDS)

    assert ok == False
    assert rules == []


def test_parse_rules_exception_missing_field(tmp_path):
    data = [
        {
            "rule_id": "R4",
            "conditions": ["R1", "R2"], 
            "priority": "HIGH"
        }
    ]

    file = tmp_path / "rules.json"
    file.write_text(json.dumps(data))

    ok, rules = parse_rules_config(str(file), SENSOR_IDS)

    assert ok == False
    assert rules == []



def test_parse_rules_exception_thrown():
    with patch("builtins.open", side_effect=PermissionError):
        ok, rules = parse_rules_config("rules.json", SENSOR_IDS)

    assert ok == False
    assert rules == []


# --------------------
# Parse sensors config
# --------------------

def test_parse_sensors_valid_list(tmp_path):
    data = { 
        "sensors": [
            {"id": "id1", "sampling_rate": "1Hz", "unit": "Celsius"},    
            {"id": "id2", "sampling_rate": "1Hz", "unit": "Celsius"}    
        ]
    }

    file = tmp_path / "sensors.yaml"
    file.write_text(yaml.dump(data))

    sensor_ids = {}
    sensor_names = []

    count, freq = parse_sensors_config(str(file), sensor_ids, sensor_names)

    assert count == 2
    assert freq == 1.0
    assert sensor_ids == { "id1": 0, "id2": 1 }
    assert sensor_names == [ "id1", "id2" ]


def test_parse_sensors_file_not_found():
    sensor_ids = {}
    sensor_names = []
    count, freq = parse_sensors_config("does_not_exist.yaml", sensor_ids, sensor_names)

    assert count == -1
    assert freq == 0.0
    assert sensor_ids == {}
    assert sensor_names == []


def test_parse_sensors_invalid_yaml(tmp_path):
    data = "{bad yaml"

    file = tmp_path / "sensors.yaml"
    file.write_text(data)

    sensor_ids = {}
    sensor_names = []
    count, freq = parse_sensors_config(str(file), sensor_ids, sensor_names)

    assert count == -1
    assert freq == 0.0
    assert sensor_ids == {}
    assert sensor_names == []


def test_parse_sensors_missing_fields(tmp_path):
    data = { 
        "sensors": [
            {"id": "id1", "unit": "Celsius"}
        ]
    }

    file = tmp_path / "sensors.yaml"
    file.write_text(yaml.dump(data))

    sensor_ids = {}
    sensor_names = []

    count, freq = parse_sensors_config(str(file), sensor_ids, sensor_names)

    assert count == -1
    assert freq == 0.0


def test_parse_sensors_exception_thrown():
    sensor_ids = {}
    sensor_names = []

    with patch("builtins.open", side_effect=PermissionError):
        count, freq = parse_sensors_config("sensors.yaml", sensor_ids, sensor_names)

    assert count == -1
    assert freq == 0.0
    assert sensor_ids == {}
    assert sensor_names == []
