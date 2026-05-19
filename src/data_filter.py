from src.utils import SensorReading

import json
from io import StringIO
import csv


# returns None if data is invalid, otherwise returns SensorReading object
def validate_sensor_data_json(data_json: str, sensor_ids: dict[str, int]) -> SensorReading | None:
    try:
        parsed = json.loads(data_json)

        if not isinstance(parsed, dict):
            return None

        if "timestamp" not in parsed or not isinstance(parsed["timestamp"], str):
            return None
        if "sensor_id" not in parsed or not isinstance(parsed["sensor_id"], str):
            return None
        if "value" not in parsed or not isinstance(parsed["value"], float):
            return None
        if "priority" not in parsed or not isinstance(parsed["priority"], str):
            return None

        ts = parsed["timestamp"]
        id = sensor_ids[parsed["sensor_id"]]
        value = parsed["value"]
        # reading priority is useless
        # reading.priority = priority

        return SensorReading(ts, id, value)
    except json.JSONDecodeError:
        return None


# Tho unspecified, the csv lines appear to be missing fields, contain CORRUPT, SYSTEM_HALT_ERR or ERR
# i think that a blacklist is still the most convenient choice in this case
# returns None if invalid data, otherwise SensorReading object
def validate_sensor_data_csv(data_csv: str, sensor_ids: dict[str, int]) -> SensorReading | None:
    reader = csv.reader(StringIO(data_csv))
    row = next(reader, None)
    if row is None:
        # means that row is empty, but DataFileReader should signal EOF and AstraLog should quit
        print("this shouldn't happen")
        return None

    for i in range(4):
        if len(row[i]) == 0 or row[i] == "CORRUPT" or row[i] == "ERR" or row[i] == "SYSTEM_HALT_ERR":
            return None

    ts = row[0]
    id = sensor_ids[row[1]]
    value = float(row[2])
    # reading priority is useless
    # reading.priority = row[3]

    return SensorReading(ts, id, value)
