from sensor_reading import SensorReading

import time
import os


class BatchManager:
    # TODO: there is no specification of what the batch file should contain.
    # so unlike the example where they write everything, we could do sth like
    #   timestamp1
    #   reading1,reading2,reading3...
    #   timestamp2
    #   reading1,,reading3
    # NOTE: the sensor readings passed here are only the valid ones, so a
    # timestamp could have missing entries; in the file we have to support
    # missing values as well
    # NOTE: a batch could contain half a timestamp, so omit the last received
    # timestamp and put it in the next batch

    class Entry:
        ts: str = ""
        readings: list[float | None]

    _count = 0
    _ts_count = 0
    _cache: list[Entry] = []
    _current_ts: str = ""

    MODE_SIZE = 1
    MODE_TIME = 2

    _mode = MODE_SIZE
    # either batch size or time
    _mode_parameter: int = 100
    _last_flush_time = time.perf_counter()

    output_dir: str


    # TODO: this requires extensive testing, like we have to trigger the appends after the
    # initial warm-up, and also make sure the reuse of existing cache cells works correctly
    def add_to_batch(self, data: SensorReading, sensor_count: int) -> str:
        # TODO 
        # TODO: return filename of full batch
        # MAYBE: have a tmp file where you push complete timestamps, rename it when full
        # TODO: perform IO in a separate thread, even if we risk crossing GIL

        self._count += 1

        if data.ts != self._current_ts:
            if self._ts_count == len(self._cache):
                # add entry to cache for the new timestamp, initialized with None
                new_entry = BatchManager.Entry()
                new_entry.ts = data.ts
                new_entry.readings = [None] * sensor_count
                self._cache.append(new_entry)
            else:
                # reuse an old slot
                self._cache[self._ts_count].ts = data.ts
                self._cache[self._ts_count].readings = [None] * sensor_count
            self._ts_count += 1
            self._current_ts = data.ts

            # NOTE: we cannot preallocate the cache due to invalid readings, i.e. we might need more rows than max size / sensor count

        # insert the value to the sensor's slot in the last entry
        self._cache[-1].readings[data.id] = data.value
        
        flush = False
        if self._mode == BatchManager.MODE_SIZE:
            if self._count >= self._mode_parameter:
                flush = True
        elif self._mode == BatchManager.MODE_TIME:
            current_time = time.perf_counter() * 1000
            if current_time - self._last_flush_time >= self._mode_parameter:
                flush = True
        
        if flush:
            filename = os.path.join(self.output_dir, f"raw_data_{int(time.time())}.txt")
            self.flush(filename)
            return filename

        return ""
    
    # if `full = True` include in the output file the last timestamp
    def flush(self, filename: str, full = False):
        print("Batch!")

        for i in range(self._ts_count - (1 if not full else 0)):
            print(self._cache[i].ts)

        # move the last element at front
        self._cache[0] = self._cache[-1]
        self._count = sum(x is not None for x in self._cache[0].readings)
        self._ts_count = 1
    

    def init(self):
        self._last_flush_time = time.perf_counter()

    def set_mode(self, mode, param):
        self._mode = mode
        self._mode_parameter = param
