from sensor_reading import SensorReading

import json

def validate_sensor_data(data_json: str, sensor_ids: dict[str, int]) -> tuple[bool, SensorReading]:
    try:
        parsed = json.loads(data_json)
        reading = SensorReading()

        if not isinstance(parsed, dict):
            return False, SensorReading()

        if "timestamp" not in parsed or not isinstance(parsed["timestamp"], str):
            return False, SensorReading()
        if "sensor_id" not in parsed or not isinstance(parsed["sensor_id"], str):
            return False, SensorReading()
        if "value" not in parsed or not isinstance(parsed["value"], float):
            return False, SensorReading()
        if "priority" not in parsed or not isinstance(parsed["priority"], str):
            return False, SensorReading()

        reading.ts = parsed["timestamp"]
        reading.id = sensor_ids[parsed["sensor_id"]]
        reading.value = parsed["value"]
        # reading priority is useless
        # reading.priority = priority

        return True, reading
    except json.JSONDecodeError as e:
        return False, SensorReading()