from data_reader import DataReader

import time


# fu GIL
class AstraLog:
    _data_reader: DataReader | None = None


    def start(self):
        if self._data_reader is None:
            print("Specify a sensor data source using AstraLog.set_data_source")
            return
        
        print("AstraLog: START")

        success = self._data_reader.open()
        if not success:
            print("AstraLog: failed to open connection to data source, aborting")
            return

        count = 0
        start = time.perf_counter()

        while True:
            self._data_reader.read_one()
            
            count += 1
            now = time.perf_counter()
            if now - start >= 5.0:
                hz = count / (now - start)
                print(f"AstraLog: {hz:.2f} iterations/sec")
                start = now
                count = 0

            # TODO: validate and add to batch
            # TODO: how to exit this loop? how do i detect keystrokes in python?

        self._data_reader.close()

        print("AstraLog: END")


    def set_data_source(self, data_reader: DataReader):
        self._data_reader = data_reader
        print(f"AstraLog: data source set to {data_reader.__str__()}")

    def __init__(self):
        pass