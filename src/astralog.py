from data_reader import DataReader, DataReaderType
from utils import get_key, FrequencyMeter, TimestampData
from data_filter import validate_sensor_data_json, validate_sensor_data_csv
from batch_manager import BatchManager
from sensor_reading import SensorReading
from batch_analyzer import BatchAnalyzer

import yaml
import os
import threading
import time
from queue import Queue

# fu GIL
class AstraLog:
    _data_reader: DataReader | None = None
    _batch_manager = BatchManager()
    _batch_analyzer = BatchAnalyzer()
    _sensor_ids: dict[str, int] = dict()

    _reading_freq: float = 1
    _sensor_count: int = 0

    _freq_meter = FrequencyMeter()

    _analysis_thread: threading.Thread
    _stop_analysis_event = threading.Event()
    # this is synchronized
    _batches_ready: Queue[str] = Queue()

    ERASE_BATCHES = True


    def analysis_loop(self):
        print("AstraLog - Analysis: starting")

        while not self._stop_analysis_event.is_set():
            batch_filename: str
            try:
                batch_filename = self._batches_ready.get(timeout=2)
            except:
                continue # every 5 seconds check if this worker thread should quit

            print(f"AstraLog - Analysis: analyzing batch {batch_filename}...")
            start = time.perf_counter()

            try:
                # MAYBE: the analysis could be done by reading one line at a time
                # in that case the BatchManager will take an open file and return
                # the next timestamp, rather than the full list, and BatchAnalyzer
                # will take one timestamp at a time
                batch_data: list[TimestampData] = []
                with open(batch_filename, "r", encoding="utf-8") as f:
                    batch_data = BatchManager.parse_batch_file(f.read())
                if AstraLog.ERASE_BATCHES:
                    os.remove(batch_filename)

                self._batch_analyzer.analyze_and_output(batch_data)

            except FileNotFoundError:
                print(f"ERROR AstraLog - Analysis: batch file '{batch_filename}' not found")
            except PermissionError: # TODO: put "ERROR" in the logs that need it
                print(f"ERROR AstraLog - Analysis: no permission to read batch file '{batch_filename}'")
            
            dt = time.perf_counter() - start
            print(f"AstraLog - Analysis: analyzing batch {batch_filename}... done in {dt:.3f}s")

        print("AstraLog - Analysis: stopping")



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
        self._analysis_thread = threading.Thread(target=self.analysis_loop)
        self._analysis_thread.start()

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

            filename = self._batch_manager.add_to_batch(data, self._sensor_count)
            if filename != "":
                self._batches_ready.put(filename)

        self._data_reader.close()
        self._stop_analysis_event.set()
        self._analysis_thread.join()
        self._batch_analyzer.deinit()

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
        if mode == BatchManager.MODE_SIZE and param < self._sensor_count:
            # if this happens the batch manager won't be able to put any data
            # in the batch files, cause they have to be rounded to a timestamp
            print("WARNING AstraLog: sensor count greater than batch size")

    def set_batch_output_dir(self, path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        self._batch_manager.output_dir = path
    def set_alarms_output_file(self, filename: str):
        self._batch_analyzer.set_alarms_output_file(filename)
    def set_valid_output_file(self, filename: str):
        self._batch_analyzer.set_valid_output_file(filename)

    def __init__(self):
        self._freq_meter.on_hz = self.on_hz


    def on_hz(self, hz):
        print(f"AstraLog: {hz:.2f} iterations/sec", end = "")
        if hz < 0.9 * self._reading_freq * self._sensor_count:
            print(f" FALLING BEHIND (target = {self._reading_freq * self._sensor_count})", end="")
        print()
