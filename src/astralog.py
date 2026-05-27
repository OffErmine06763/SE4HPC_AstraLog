from src.data_reader import DataReader, DataReaderType
from src.utils import get_key, FrequencyMeter, TimestampData, SensorReading
from src.data_filter import validate_sensor_data_json, validate_sensor_data_csv
from src.batch_manager import BatchManager
from src.batch_analyzer import BatchAnalyzer
from src.config_reader import parse_sensors_config, parse_rules_config

import os
import io
import threading
import time
from queue import Queue, Empty


class AstraLog:
    _data_reader: DataReader | None
    _batch_manager: BatchManager
    _batch_analyzer: BatchAnalyzer
    _sensor_ids: dict[str, int]
    _sensor_names: list[str]

    _reading_freq: float
    _sensor_count: int

    _freq_meter: FrequencyMeter

    _analysis_thread: threading.Thread
    _stop_analysis_event: threading.Event

    # this is synchronized
    _batches_ready: Queue[str]

    ERASE_BATCHES = True
    BATCH_QUEUE_LOOP_TIMEOUT = 2

    def __init__(self):
        self._data_reader = None
        self._batch_analyzer = BatchAnalyzer()
        self._batch_manager = BatchManager()
        self._sensor_ids = dict()
        self._sensor_names = []

        self._reading_freq = 1.0
        self._sensor_count = 0

        self._freq_meter = FrequencyMeter()

        self._stop_analysis_event = threading.Event()
        self._batches_ready = Queue()

        self._freq_meter.on_hz = self.on_hz

    def analysis_loop(self):
        print("AstraLog - Analysis: starting")

        while True:
            if self._stop_analysis_event.is_set() and self._batches_ready.empty():
                break

            batch_filename: str
            try:
                batch_filename = self._batches_ready.get(timeout=self.BATCH_QUEUE_LOOP_TIMEOUT)
            except Empty:
                continue  # every 5 seconds check if this worker thread should quit

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
                print(
                    f"ERROR AstraLog - Analysis: batch file '{batch_filename}' not found"
                )
            except (
                PermissionError
            ):  # TODO: put "ERROR" or "WARNING" in the logs that need it
                print(
                    f"ERROR AstraLog - Analysis: no permission to read batch file '{batch_filename}'"
                )

            dt = time.perf_counter() - start
            print(
                f"AstraLog - Analysis: analyzing batch {batch_filename}... done in {dt:.3f}s"
            )

        print("AstraLog - Analysis: stopping")

    def prepare_before_start(self) -> bool:
        if self._data_reader is None:
            print(
                "AstraLog: specify a sensor data source using AstraLog.set_data_source"
            )
            return False
        if self._sensor_count == 0:
            print("AstraLog: provide sensors configuration using AstraLog.set_sensors")
            return False

        print("AstraLog: START")

        success = self._data_reader.open()
        if not success:
            print("AstraLog: failed to open connection to data source, aborting")
            return False

        self._freq_meter.init()
        self._batch_manager.init()

        return True

    def start(self):
        ok = self.prepare_before_start()
        if not ok:
            return
        
        data_reader = self._data_reader
        assert data_reader is not None  # narrows for mypy static analysis

        self._analysis_thread = threading.Thread(target=self.analysis_loop)
        self._analysis_thread.start()

        while True:
            # handle execution metrics and keyboard
            self._freq_meter.update()
            try:
                key = get_key()
                if key and key.lower() == "q":
                    self._stop_analysis_event.set()
                    break
            except io.UnsupportedOperation:
                print("\ngetting key failed\n")

            # retrieve 1 entry from the data stream
            valid, data_raw = data_reader.read_one()
            if not valid:  # EOF or connection issues
                break

            # validate the json or csv, returning a struct
            # TODO: i dont like the fact that we have to run this if at every iteration
            # tho i dont like the idea of moving this in the reader, i'd rather have the reader
            # to be a generic source of data, you know division of responsibilities
            data: SensorReading | None
            if data_reader.type() == DataReaderType.STREAM:
                data = validate_sensor_data_json(data_raw, self._sensor_ids)
            else:
                data = validate_sensor_data_csv(data_raw, self._sensor_ids)

            if data is None:  # data is invalid
                continue

            filename = self._batch_manager.add_to_batch(data, self._sensor_count)
            if filename != "":
                self._batches_ready.put(filename)

        data_reader.close()

        # flush what is left in the batch manager
        filename = self._batch_manager.get_flush_filename()
        self._batch_manager.flush(filename, full=True)
        self._batches_ready.put(filename)

        self._stop_analysis_event.set()
        self._analysis_thread.join()
        self._batch_analyzer.deinit()

        print("AstraLog: END")

    def set_data_source(self, data_reader: DataReader):
        self._data_reader = data_reader
        print(f"AstraLog: data source set to {data_reader.__str__()}")

    def set_rules(self, rules_filename) -> bool:
        if self._sensor_count == 0:
            print(
                "AstraLog: provide sensors configuration using AstraLog.set_sensors before specifying rules"
            )
            return False

        print("AstraLog: reading rules configuration file... ")

        ok, rules = parse_rules_config(rules_filename, self._sensor_ids)
        if not ok:
            return False

        print(f"AstraLog: found {len(rules)} rules")

        ok = self._batch_analyzer.load_rules(rules)
        if not ok:
            return False

        print("AstraLog: reading rules configuration file... done")
        return ok

    def set_sensors(self, sensors_filename: str) -> bool:
        print("AstraLog: reading sensor configuration file... ")

        count, freq = parse_sensors_config(
            sensors_filename, self._sensor_ids, self._sensor_names
        )
        if count == -1:
            return False

        self._sensor_count = count
        self._reading_freq = freq
        self._batch_analyzer.set_sensors(self._sensor_names)
        print(f"AstraLog: found {self._sensor_count} sensors at {self._reading_freq}Hz")

        print("AstraLog: reading sensor configuration file... done")
        return True

    def set_batch_mode(self, mode, param):
        self._batch_manager.set_mode(mode, param)
        if mode == BatchManager.MODE_SIZE and param < self._sensor_count:
            # if this happens the batch manager won't be able to put any data
            # in the batch files, cause they have to be rounded to a timestamp
            print("WARNING AstraLog: sensor count greater than batch size")
        if mode == BatchManager.MODE_TIME and 1 / param > self._reading_freq:
            # this shouldn't be a big deal, but we still generate some empty batches
            print(
                "WARNING AstraLog: batch frequency higher than sensor data generation frequency"
            )

    def set_batch_output_dir(self, path: str):
        if not os.path.exists(path):
            os.makedirs(path)
        self._batch_manager.output_dir = path

    def set_alarms_output_file(self, filename: str):
        self._batch_analyzer.set_alarms_output_file(filename)

    def set_valid_output_file(self, filename: str):
        self._batch_analyzer.set_valid_output_file(filename)

    def on_hz(self, hz):
        print(f"AstraLog: {hz:.2f} iterations/sec", end="")
        if hz < 0.9 * self._reading_freq * self._sensor_count:
            print(
                f" FALLING BEHIND (target = {self._reading_freq * self._sensor_count})",
                end="",
            )
        print()
