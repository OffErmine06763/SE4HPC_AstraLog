import pytest
from src.utils import SensorReading
from src.data_filter import validate_sensor_data_csv, validate_sensor_data_json


SENSOR_IDS = {
    'sensor1': 1,
    'sensor2': 2
}


# ----
# JSON
# ----

def test_validate_json_valid():
    data = """
    {
        "timestamp": "ts1",
        "sensor_id": "sensor1",
        "value": 0.5,
        "priority": "HIGH"
    }
    """

    result = validate_sensor_data_json(data, SENSOR_IDS)

    assert isinstance(result, SensorReading)
    assert result.ts == "ts1"
    assert result.id == 1
    assert result.value == 0.5


def test_validate_json_no_timestamp():
    data = """
    {
        "sensor_id": "sensor1",
        "value": 0.5,
        "priority": "HIGH"
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None


def test_validate_json_timestamp_not_string():
    data = """
    {
        "timestamp": 123
        "sensor_id": "sensor1",
        "value": 0.5,
        "priority": "HIGH"
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None



def test_validate_json_no_sensor():
    data = """
    {
        "timestamp": "ts1",
        "value": 0.5,
        "priority": "HIGH"
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None


def test_validate_json_sensor_not_string():
    data = """
    {
        "timestamp": "ts1",
        "sensor_id": 123,
        "value": 0.5,
        "priority": "HIGH"
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None


def test_validate_json_no_value():
    data = """
    {
        "timestamp": "ts1",
        "sensor_id": "sensor1",
        "priority": "HIGH"
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None 


def test_validate_json_value_not_float():
    data = """
    {
        "timestamp": "ts1",
        "sensor_id": "sensor1",
        "value": "0.5",
        "priority": "HIGH"
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None


def test_validate_json_no_priority():
    data = """
    {
        "timestamp": "ts1",
        "sensor_id": "sensor1",
        "value": 0.5
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None 


def test_validate_json_priority_not_string():
    data = """
    {
        "timestamp": "ts1",
        "sensor_id": "sensor1",
        "value": 0.5,
        "priority": 123
    }
    """

    assert validate_sensor_data_json(data, SENSOR_IDS) is None


def test_validate_json_invalid_json():
    data = "{bad json"
    assert validate_sensor_data_json(data, SENSOR_IDS) is None


def test_validate_json_not_dict():
    data = "[1, 2, 3]"
    assert validate_sensor_data_json(data, SENSOR_IDS) is None


# ---
# CSV
# ---

def test_validate_csv_correct():
    data = "ts1,sensor1,0.25,HIGH"

    result = validate_sensor_data_csv(data, SENSOR_IDS)

    assert isinstance(result, SensorReading)
    assert result.ts == "ts1"
    assert result.id == 1
    assert result.value == 0.25


def test_validate_csv_empty():
    data = ""
    assert validate_sensor_data_csv(data, SENSOR_IDS) is None


def test_validate_csv_missing_field():
    data = "ts1,,0.25,HIGH"
    assert validate_sensor_data_csv(data, SENSOR_IDS) is None


def test_validate_csv_corrupt():
    data = "ts1,CORRUPT,0.25,HIGH"
    assert validate_sensor_data_csv(data, SENSOR_IDS) is None


def test_validate_csv_err():
    data = "ts1,sensor1,ERR,HIGH"
    assert validate_sensor_data_csv(data, SENSOR_IDS) is None


def test_validate_csv_system_halt_error():
    data = "ts1,sensor1,0.25,SYSTEM_HALT_ERR"
    assert validate_sensor_data_csv(data, SENSOR_IDS) is None
