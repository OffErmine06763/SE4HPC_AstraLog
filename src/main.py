from src.astralog import AstraLog
from src.data_reader import DataReaderType
from src.data_file_reader import DataFileReader
from src.data_stream_reader import DataStreamReader
from src.batch_manager import BatchManager

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AstraLog Telemetry Collector")
    # TODO: bring back those command line args and add all the other parameters (sensor and rule filenames, output filename, batch output dir, stream or file mode (along with data file))
    # parser.add_argument("--mode", choices=["count", "time"], required=True, help="Accumulation mode")
    # parser.add_argument("--limit", type=int, required=True, help="Messages count or Time interval in ms")
    # parser.add_argument("--seq-period", type=int, default=100, help="Sequence number period (default: 100)")
    args = parser.parse_args()

    data_reader_type: DataReaderType = DataReaderType.FILE
    batch_mode, batch_param = BatchManager.MODE_SIZE, 8

    alog = AstraLog()

    if data_reader_type == DataReaderType.FILE:
        src = DataFileReader()
        src.set_data_file("res/readings_sigma.csv")
        alog.set_data_source(src)
    elif data_reader_type == DataReaderType.STREAM:
        src = DataStreamReader()
        alog.set_data_source(src)

    alog.set_sensors("res/sensors_sigma.yaml")
    alog.set_rules("res/rules_sigma.json")
    alog.set_batch_mode(batch_mode, batch_param)
    alog.set_batch_output_dir("out/readings")
    alog.set_valid_output_file("out/valid.txt")
    alog.set_alarms_output_file("out/alarms.txt")

    alog.start()