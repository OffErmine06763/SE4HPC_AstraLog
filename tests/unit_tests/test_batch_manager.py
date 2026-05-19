import os
from unittest.mock import patch
from src.batch_manager import BatchManager
from src.utils import SensorReading


# ------------------
# Parsing batch file
# ------------------

def test_parse_batch_file_invalid_format(capsys):
    data = "ts1\n"
    assert BatchManager.parse_batch_file(data) == []

    captured_output = capsys.readouterr().out
    assert captured_output == \
        "WARNING BatchManager: ill formatted batch file (timestamp with no data line)\n"


def test_parse_batch_file_correct():
    data = "ts1\n0.4,0.3,0.2\nts2\n0.1,,0.2"

    result = BatchManager.parse_batch_file(data)

    assert len(result) == 2
    assert result[0].ts == "ts1"
    assert result[0].readings == [0.4, 0.3, 0.2]
    assert result[1].ts == "ts2"
    assert result[1].readings == [0.1, None, 0.2]


# -----------------------------
# BatchManager init and setters
# -----------------------------

def test_batch_manager_init_and_set():
    with patch("src.batch_manager.time.perf_counter", return_value=0):
        manager = BatchManager()

    # __init__
    assert manager._mode == BatchManager.MODE_SIZE
    assert manager._mode_parameter == 100
    assert manager._last_flush_time == 0
    assert manager._sequence_number == 0
    assert manager._sequence_period == 1000
    assert manager._count == 0
    assert manager._ts_count == 0
    assert manager._cache == []
    assert manager._current_ts == ""

    # init
    with patch("src.batch_manager.time.perf_counter", return_value=1):
        manager.init()

    assert manager._last_flush_time == 1

    # set mode param
    manager.set_mode(BatchManager.MODE_TIME, 10)
    assert manager._mode == BatchManager.MODE_TIME
    assert manager._mode_parameter == 10


# ------------------------------------------
# Batch Manager add to batch and flush logic
# ------------------------------------------

def test_add_to_batch_creates_timestamp():
    manager = BatchManager()
    manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)

    assert manager._ts_count == 1
    assert manager._cache[0].ts == "ts1"
    assert manager._cache[0].readings == [0.4, None]


def test_add_to_batch_multiple_sensors_same_timestamp():
    manager = BatchManager()
    manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)
    manager.add_to_batch(SensorReading("ts1", 1, 0.3), 2)

    assert manager._ts_count == 1
    assert manager._cache[0].ts == "ts1"
    assert manager._cache[0].readings == [0.4, 0.3]


def test_add_to_batch_new_timestamp():
    manager = BatchManager()
    manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)
    manager.add_to_batch(SensorReading("ts2", 1, 0.3), 2)

    assert manager._ts_count == 2
    assert manager._cache[1].ts == "ts2"
    assert manager._cache[1].readings == [None, 0.3]


def test_flush_with_last(tmp_path):
    manager = BatchManager()
    manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)
    manager.add_to_batch(SensorReading("ts2", 1, 0.3), 2)

    file = tmp_path / "batch.txt"
    manager.flush(str(file), full=True)

    output = file.read_text()
    expected_output = "ts1\n0.4,\nts2\n,0.3\n"
    assert output == expected_output


def test_flush_without_last(tmp_path):
    manager = BatchManager()
    manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)
    manager.add_to_batch(SensorReading("ts2", 1, 0.3), 2)

    file = tmp_path / "batch.txt"
    manager.flush(str(file), full=False)

    output = file.read_text()
    expected_output = "ts1\n0.4,\n"
    assert output == expected_output


def test_flush_keeps_last_timestamp(tmp_path):
    manager = BatchManager()
    manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)
    manager.add_to_batch(SensorReading("ts2", 1, 0.3), 2)

    file = tmp_path / "batch.txt"
    manager.flush(str(file), full=False)

    assert manager._ts_count == 1
    assert manager._cache[0].ts == "ts2"
    assert manager._cache[0].readings == [None, 0.3]


def test_add_to_batch_reuses_cache_slot(tmp_path):
    manager = BatchManager()
    manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)
    manager.add_to_batch(SensorReading("ts2", 1, 0.3), 2)
    manager.add_to_batch(SensorReading("ts3", 0, 0.2), 2)

    file = tmp_path / "batch.txt"
    manager.flush(str(file), full=False)

    manager.add_to_batch(SensorReading("ts4", 0, 0.1), 2)

    assert manager._ts_count == 2
    assert manager._cache[1].ts == "ts4"
    assert manager._cache[1].readings == [0.1, None]


def test_add_to_batch_flushes_mode_size(tmp_path):
    manager = BatchManager()
    manager.set_mode(BatchManager.MODE_SIZE, 1)
    manager.output_dir = tmp_path / "out_dir"

    file = tmp_path / "out_dir" / "raw_data_0_0000.txt"
    os.mkdir(tmp_path / "out_dir")

    with patch("src.batch_manager.time.time", return_value=0.0):
        result1 = manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)
        result2 = manager.add_to_batch(SensorReading("ts2", 1, 0.2), 2)

    assert result1 == ""
    assert result2 == str(file)

    output = file.read_text()
    assert output == "ts1\n0.4,\n"


def test_add_to_batch_flushes_mode_time(tmp_path):
    manager = BatchManager()
    manager.set_mode(BatchManager.MODE_TIME, 100)
    manager.output_dir = tmp_path / "out_dir"

    file = tmp_path / "out_dir" / "raw_data_0_0000.txt"
    os.mkdir(tmp_path / "out_dir")

    with patch("src.batch_manager.time.perf_counter", return_value=0.0):
        manager.init()
        result1 = manager.add_to_batch(SensorReading("ts1", 0, 0.4), 2)

    with patch("src.batch_manager.time.time", return_value=0.0):
        with patch("src.batch_manager.time.perf_counter", return_value=0.5):
            result2 = manager.add_to_batch(SensorReading("ts2", 1, 0.2), 2)

    assert result1 == ""
    assert result2 == str(file)

    output = file.read_text()
    assert output == "ts1\n0.4,\n"
