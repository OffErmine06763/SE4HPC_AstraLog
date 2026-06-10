from src.utils import TimestampData, SensorReading

import time
import os
from io import StringIO
import csv


class BatchManager:
    # NOTE: there is no specification of what the batch file should contain.
    # so unlike the example where everything is written, the system instead writes:
    #   timestamp1
    #   reading1,reading2,reading3...
    #   timestamp2
    #   reading1,,reading3
    # NOTE: only the first timestamp is useful, but keep all for clarity, maybe consider
    # adding a header with the csv of the sensor names
    # NOTE: the sensor readings passed here are only the valid ones, so a
    # timestamp could have missing entries; in the file we have to support
    # missing values as well
    # NOTE: a batch could contain half a timestamp, so we omit the last received
    # timestamp and put it in the next batch

    _count: int
    _ts_count: int
    _cache: list[TimestampData]
    _current_ts: str

    _sequence_number: int
    _sequence_period: int

    MODE_SIZE = 1
    MODE_TIME = 2

    _mode: int
    # either batch size or time
    _mode_parameter: int
    _last_flush_time: float

    output_dir: str

    def __init__(self):
        self._mode = self.MODE_SIZE
        self._mode_parameter = 100
        self._last_flush_time = time.perf_counter()

        self._sequence_number = 0
        self._sequence_period = 1000

        self._count = 0
        self._ts_count = 0
        self._cache = []
        self._current_ts = ""

    def get_flush_filename(self) -> str:
        seq_num = self._sequence_number % self._sequence_period
        self._sequence_number = (self._sequence_number + 1) % self._sequence_period
        return os.path.join(self.output_dir, f"raw_data_{int(time.time())}_{seq_num:04d}.txt")

    def add_to_batch(self, data: SensorReading, sensor_count: int) -> str:
        self._count += 1

        if data.ts != self._current_ts:
            # NOTE: we cannot preallocate the cache due to invalid readings, i.e. we might need
            # more rows than max size / sensor count
            # but we can reuse those allocated at previous batches.
            if self._ts_count == len(self._cache):
                # add entry to cache for the new timestamp, initialized with None
                readings: list[float | None] = [None] * sensor_count
                self._cache.append(TimestampData(data.ts, readings))
            else:
                # reuse an old slot
                self._cache[self._ts_count].ts = data.ts
                self._cache[self._ts_count].readings = [None] * sensor_count
            self._ts_count += 1
            self._current_ts = data.ts

        # insert the value to the sensor's slot in the last entry
        self._cache[self._ts_count - 1].readings[data.id] = data.value

        flush = False
        if self._mode == BatchManager.MODE_SIZE:
            # use > and not >= since the last timestamp is omitted
            # so at least if parameter = sensor count * n and all n
            # timestamps full of valid data, they are all put in the batch
            if self._count > self._mode_parameter:
                flush = True
        elif self._mode == BatchManager.MODE_TIME:
            current_time = time.perf_counter() * 1000
            if current_time - self._last_flush_time >= self._mode_parameter:
                flush = True

        if flush:
            filename = self.get_flush_filename()
            self.flush(filename)
            return filename

        return ""

    # if `full = True` include in the output file the last timestamp
    def flush(self, filename: str, full=False):
        print(f"BatchManager: saving batch to {filename}")
        try:
            with open(filename, "w") as f:
                for i in range(self._ts_count - (1 if not full else 0)):
                    f.write(self._cache[i].ts)
                    f.write("\n")
                    for r in self._cache[i].readings[:-1]:
                        if r is not None:
                            f.write(str(r))
                        f.write(",")
                    if self._cache[i].readings[-1] is not None:
                        f.write(str(self._cache[i].readings[-1]))
                    f.write("\n")
        except OSError as e:
            print(f"BatchManager: failed to save batch to {filename}: {e}")
            raise
        # move the last element at front
        if self._ts_count > 0:
            self._cache[0].ts = self._cache[self._ts_count - 1].ts
            self._cache[0].readings = self._cache[self._ts_count - 1].readings.copy()
            self._count = sum(x is not None for x in self._cache[0].readings)
            self._ts_count = 1
        self.reset_flush_timer()

    @staticmethod
    def parse_batch_file(content: str) -> list[TimestampData]:
        batch_data: list[TimestampData] = []

        def line_reader(s):
            for line in s.splitlines():
                yield line

        reader = line_reader(content)

        while True:
            ts = next(reader, None)
            if ts is None:
                break

            readings = next(reader, None)
            if readings is None:
                print(
                    "WARNING BatchManager: ill formatted batch file (timestamp with no data line)"
                )
                break

            csv_reader = csv.reader(StringIO(readings))
            readings_list = next(csv_reader, None)
            if readings_list is None:
                print("WARNING BatchManager: this shouldn't happen")
                break

            readings = [float(x) if x != "" else None for x in readings_list]
            batch_data.append(TimestampData(ts, readings))

        return batch_data

    def reset_flush_timer(self):
        self._last_flush_time = time.perf_counter() * 1000

    def init(self):
        self.reset_flush_timer()

    def set_mode(self, mode, param):
        self._mode = mode
        self._mode_parameter = param
