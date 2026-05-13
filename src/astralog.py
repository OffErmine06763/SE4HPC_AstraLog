from data_reader import DataReader, DataReaderType
from utils import get_key, FrequencyMeter
from data_filter import validate_sensor_data_json, validate_sensor_data_csv
from batch_manager import BatchManager
from sensor_reading import SensorReading

import yaml
import os

# fu GIL
class AstraLog:
    _data_reader: DataReader | None = None
    _batch_manager = BatchManager()
    _sensor_ids: dict[str, int] = dict()

    _reading_freq: float = 1
    _sensor_count: int = 0

    _freq_meter = FrequencyMeter()

    def start(self):
        if self._data_reader is None:
            print("AstraLog: specify a sensor data source using AstraLog.set_data_source")
            return
        if self._sensor_count == 0:
            print("AstraLog: provide sensors configuration using AstraLog.set_sensors")
            return
        
        print("AstraLog: START")

        success = self._data_reader.open()
        if not success:
            print("AstraLog: failed to open connection to data source, aborting")
            return

        self._freq_meter.init()
        self._batch_manager.init()

        while True:
            # handle execution metrics and keyboard
            self._freq_meter.update()
            key = get_key()
            if key and key.lower() == "q":
                break

            # retrieve 1 entry from the data stream
            valid, data_raw = self._data_reader.read_one()
            if not valid: # EOF or connection issues
                break

            # validate the json or csv, returning a struct
            # TODO: i dont like the fact that we have to run this if at every iteration
            # tho i dont like the idea of moving this in the reader, i'd rather have the reader
            # to be a generic source of data, you know division of responsibilities
            data: SensorReading
            if self._data_reader.type() == DataReaderType.STREAM:
                valid, data = validate_sensor_data_json(data_raw, self._sensor_ids)
            else:
                valid, data = validate_sensor_data_csv(data_raw, self._sensor_ids)

            if not valid:
                continue

            # print(data_json)

            self._batch_manager.add_to_batch(data, self._sensor_count)

        self._data_reader.close()

        print("AstraLog: END")


    def set_data_source(self, data_reader: DataReader):
        self._data_reader = data_reader
        print(f"AstraLog: data source set to {data_reader.__str__()}")

    def set_sensors(self, sensors_filename: str) -> bool:
        print("AstraLog: reading sensor configuration file... ")
        
        try:
            with open(sensors_filename, "r") as f:
                sensors_yaml = yaml.safe_load(f)

                counter = 0
                for sensor in sensors_yaml["sensors"]:
                    self._sensor_ids[sensor["id"]] = counter
                    counter += 1
                self._sensor_count = counter
                rate_str: str = sensors_yaml["sensors"][0]["sampling_rate"]
                self._reading_freq = float(rate_str[:-2]) # Hz

                print(f"AstraLog: found {self._sensor_count} sensors at {self._reading_freq}Hz")

        except FileNotFoundError:
            print(f"AstraLog: sensor file '{sensors_filename}' not found")
            return False
        except PermissionError:
            print(f"AstraLog: no permission to read sensor file '{sensors_filename}'")
            return False
        except yaml.YAMLError as e:
            print(f"AstraLog: invalid YAML in sensor file '{sensors_filename}':", e, sep="\n")
            return False
        except Exception as e:
            print(f"AstraLog: unexpected error reading sensor file '{sensors_filename}':", e, sep="\n")
            return False
        
        print("AstraLog: reading sensor configuration file... done")
        return True

    def set_batch_mode(self, mode, param):
        self._batch_manager.set_mode(mode, param)

    def set_batch_output_dir(self, path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        self._batch_manager.output_dir = path

    def __init__(self):
        self._freq_meter.on_hz = self.on_hz


    def on_hz(self, hz):
        print(f"AstraLog: {hz:.2f} iterations/sec", end = "")
        if hz < 0.9 * self._reading_freq * self._sensor_count:
            print(f" FALLING BEHIND (target = {self._reading_freq * self._sensor_count})", end="")
        print()
