from src.astralog import AstraLog
from src.data_reader import DataReaderType
from src.data_file_reader import DataFileReader
from src.data_stream_reader import DataStreamReader
from src.batch_manager import BatchManager
from src.data_reader import DataReader

import argparse
import os
from dotenv import load_dotenv


load_dotenv()


# Example command (from root dir):
# python3 -m src.main --reading-mode file --batch-mode count --limit 10
if __name__ == "__main__": # noqa
    parser = argparse.ArgumentParser(description="AstraLog Telemetry Collector")

    parser.add_argument("--reading-mode", choices=["file", "mqtt"], required=True,
                        help="Type of data provider")
    parser.add_argument("--batch-mode", choices=["count", "time"], required=True,
                        help="Accumulation mode")
    parser.add_argument("--limit", type=int, required=True,
                        help="Messages count or Time interval in ms")

    # TODO uncomment the seq-period flag
    # parser.add_argument("--seq-period", type=int, default=100, help="Sequence number period (default: 100)")

    parser.add_argument("--readings-file", type=str, default="res/readings_sigma.csv",
                        help="In case of mode=count, the filename of the readings. (default=res/readings_sigma.csv)")
    parser.add_argument("--sensors-file", type=str, default="res/sensors_sigma.yaml",
                        help="File with sensor information (default=res/sensors_sigma.yaml)")
    parser.add_argument("--rules-file", type=str, default="res/rules_sigma.json",
                        help="File with rules information (default=res/rules_sigma.json)")

    parser.add_argument("--output-dir", type=str, default="out/readings",
                        help="Output dir for batch files (default=out/readings)")
    parser.add_argument("--valid-output-file", type=str, default="out/valid.txt",
                        help="File for valid readings (default=out/valid.txt)")
    parser.add_argument("--alarms-output-file", type=str, default="out/alarms.txt",
                        help="File for alarms (default=out/alarms.txt)")

    parser.add_argument("--duration", type=int, default=None,
                        help="Time (s) program runs before stopping (default: run indefinitely)")

    args = parser.parse_args()

    data_reader_type = DataReaderType.FILE if args.reading_mode == "file" else DataReaderType.STREAM
    batch_mode = BatchManager.MODE_SIZE if args.batch_mode == "count" else BatchManager.MODE_TIME
    batch_param = args.limit

    alog = AstraLog()

    src: DataReader

    if data_reader_type == DataReaderType.FILE:
        src = DataFileReader()
        src.set_data_file(args.readings_file)
        alog.set_data_source(src)
    elif data_reader_type == DataReaderType.STREAM:
        # --- MISSION CONFIGURATION ---
        broker_url = os.getenv("MQTT_BROKER_URL")
        port = int(os.getenv("MQTT_PORT", 8883))
        topic = os.getenv("MQTT_TOPIC")
        user = os.getenv("MQTT_USER")
        password = os.getenv("MQTT_PASSWORD")
        use_tls_env = os.getenv("USE_TLS")

        if use_tls_env is None:
            use_tls = True
        else:
            use_tls = bool(use_tls_env == 'True' or use_tls_env == 'true')

        if broker_url is None:
            raise ValueError("DataStreamReader: missing BROKER_URL environment variable")

        if port is None:
            raise ValueError("DataStreamReader: missing PORT environment variable")

        if topic is None:
            raise ValueError("DataStreamReader: missing TOPIC environment variable")

        if user is None:
            raise ValueError("DataStreamReader: missing USER environment variable")

        if password is None:
            raise ValueError("DataStreamReader: missing PASSWORD environment variable")

        src = DataStreamReader(
            broker_url=broker_url, port=port, topic=topic, user=user, password=password,
            use_tls=use_tls
        )
        alog.set_data_source(src)

    flag = alog.set_sensors(args.sensors_file)
    flag &= alog.set_rules(args.rules_file)
    alog.set_batch_mode(batch_mode, batch_param)
    alog.set_batch_output_dir(args.output_dir)
    alog.set_valid_output_file(args.valid_output_file)
    alog.set_alarms_output_file(args.alarms_output_file)
    alog.set_duration(args.duration)
    
    try:
        if flag:
            alog.start()
        else:
            print("AstraLog: Configuration failed, exiting")
    except KeyboardInterrupt:
        print("AstraLog: KeyboardInterrupt received, stopping")
    except Exception as e:
        print(f"AstraLog: unexpected error: {e}")
    finally:
        alog.shutdown()
