from utils import SensorReading

import json
from io import StringIO
import csv


def validate_sensor_data_json(
    data_json: str, sensor_ids: dict[str, int]
) -> tuple[bool, SensorReading]:
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
    except json.JSONDecodeError:
        return False, SensorReading()


# Tho unspecified, the csv lines appear to be missing fields, contain CORRUPT, SYSTEM_HALT_ERR or ERR
# i think that a blacklist is still the most convenient choice in this case
def validate_sensor_data_csv(
    data_csv: str, sensor_ids: dict[str, int]
) -> tuple[bool, SensorReading]:
    reader = csv.reader(StringIO(data_csv))
    row = next(reader, None)
    if row is None:
        print(
            "this shouldn't happen"
        )  # means that row is empty, but DataFileReader should signal EOF and AstraLog should quit
        return False, SensorReading()

    for i in range(4):
        if (
            len(row[i]) == 0
            or row[i] == "CORRUPT"
            or row[i] == "ERR"
            or row[i] == "SYSTEM_HALT_ERR"
        ):
            return False, SensorReading()

    reading = SensorReading()
    reading.ts = row[0]
    reading.id = sensor_ids[row[1]]
    reading.value = float(row[2])
    # reading priority is useless
    # reading.priority = row[3]

    return True, reading
