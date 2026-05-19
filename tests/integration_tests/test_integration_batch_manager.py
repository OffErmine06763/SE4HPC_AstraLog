import pytest
import os
import shutil
import time
from src.batch_manager import BatchManager
from src.utils import SensorReading, TimestampData


@pytest.fixture
def out_dir(tmp_path):
    out_dir = tmp_path / "out_dir"
    os.mkdir(out_dir)

    yield out_dir

    shutil.rmtree(out_dir)


def assert_batch_data_in_file(filename: str, expected_batch_data: list[TimestampData]):
    assert os.path.exists(filename)

    with open(filename, 'r') as f:
        actual_batch_data = BatchManager.parse_batch_file(f.read())

    assert len(actual_batch_data) == len(expected_batch_data)

    for i in range(len(actual_batch_data)):
        assert actual_batch_data[i].ts == expected_batch_data[i].ts
        assert actual_batch_data[i].readings == expected_batch_data[i].readings


def test_count_based_one_flush(out_dir):
    manager = BatchManager()
    manager.output_dir = str(out_dir)
    manager.set_mode(BatchManager.MODE_SIZE, 3)
    manager.init()

    assert "" == manager.add_to_batch(SensorReading("time1", 0, 0.5), 2)
    assert "" == manager.add_to_batch(SensorReading("time1", 1, 0.4), 2)
    assert "" == manager.add_to_batch(SensorReading("time2", 0, 0.2), 2)
    filename = manager.add_to_batch(SensorReading("time3", 0, 0.2), 2)  # triggers to flush the previous two

    assert_batch_data_in_file(filename, [
        TimestampData("time1", [0.5, 0.4]),
        TimestampData("time2", [0.2, None])
    ])


def test_time_based_one_flush(out_dir):
    manager = BatchManager()
    manager.output_dir = str(out_dir)
    manager.set_mode(BatchManager.MODE_TIME, 500)
    manager.init()

    assert "" == manager.add_to_batch(SensorReading("time1", 0, 0.5), 2)
    assert "" == manager.add_to_batch(SensorReading("time1", 1, 0.4), 2)
    assert "" == manager.add_to_batch(SensorReading("time2", 0, 0.2), 2)

    time.sleep(0.8)  # exceeds time limit

    filename = manager.add_to_batch(SensorReading("time3", 0, 0.2), 2)  # triggers to flush the previous two

    assert_batch_data_in_file(filename, [
        TimestampData("time1", [0.5, 0.4]),
        TimestampData("time2", [0.2, None])
    ])


def test_count_based_multiple_flushes(out_dir):
    manager = BatchManager()
    manager.output_dir = str(out_dir)
    manager.set_mode(BatchManager.MODE_SIZE, 2)
    manager.init()

    assert "" == manager.add_to_batch(SensorReading("time1", 0, 0.5), 2)
    assert "" == manager.add_to_batch(SensorReading("time1", 1, 0.2), 2)
    file1 = manager.add_to_batch(SensorReading("time2", 1, 0.4), 2)  # triggers flush
    assert "" == manager.add_to_batch(SensorReading("time2", 0, 0.1), 2)
    file2 = manager.add_to_batch(SensorReading("time3", 0, 0.2), 2)  # triggers flush
    assert "" == manager.add_to_batch(SensorReading("time4", 0, 0.04), 2)
    file3 = manager.add_to_batch(SensorReading("time4", 0, 0.2), 2)  # triggers flush

    assert_batch_data_in_file(file1, [TimestampData("time1", [0.5, 0.2])])
    assert_batch_data_in_file(file2, [TimestampData("time2", [0.1, 0.4])])
    assert_batch_data_in_file(file3, [TimestampData("time3", [0.2, None])])


def test_time_based_multiple_flushes(out_dir):
    manager = BatchManager()
    manager.output_dir = str(out_dir)
    manager.set_mode(BatchManager.MODE_TIME, 500)
    manager.init()


    assert "" == manager.add_to_batch(SensorReading("time1", 0, 0.5), 2)
    assert "" == manager.add_to_batch(SensorReading("time1", 1, 0.2), 2)
    time.sleep(0.8)  # exceeds time limit
    file1 = manager.add_to_batch(SensorReading("time2", 1, 0.4), 2)  # triggers flush
    assert "" == manager.add_to_batch(SensorReading("time2", 0, 0.1), 2)
    time.sleep(0.8)  # exceeds time limit
    file2 = manager.add_to_batch(SensorReading("time3", 0, 0.2), 2)  # triggers flush
    assert "" == manager.add_to_batch(SensorReading("time4", 0, 0.04), 2)
    time.sleep(0.8)  # exceeds time limit
    file3 = manager.add_to_batch(SensorReading("time4", 0, 0.2), 2)  # triggers flush

    assert_batch_data_in_file(file1, [TimestampData("time1", [0.5, 0.2])])
    assert_batch_data_in_file(file2, [TimestampData("time2", [0.1, 0.4])])
    assert_batch_data_in_file(file3, [TimestampData("time3", [0.2, None])])