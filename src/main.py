from astralog import AstraLog
from data_reader import DataReaderType
from data_file_reader import DataFileReader
from data_stream_reader import DataStreamReader

import argparse


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AstraLog Telemetry Collector")
    # parser.add_argument("--mode", choices=["count", "time"], required=True, help="Accumulation mode")
    # parser.add_argument("--limit", type=int, required=True, help="Messages count or Time interval in ms")
    # parser.add_argument("--seq-period", type=int, default=100, help="Sequence number period (default: 100)")
    args = parser.parse_args()

    data_reader_type: DataReaderType = DataReaderType.STREAM

    alog = AstraLog()
    if data_reader_type == DataReaderType.FILE:
        src = DataFileReader()
        src.set_data_file("csv_input/export_sat_alpha_small.csv")
        alog.set_data_source(src)
    elif data_reader_type == DataReaderType.STREAM:
        src = DataStreamReader()
        alog.set_data_source(src)

    alog.start()