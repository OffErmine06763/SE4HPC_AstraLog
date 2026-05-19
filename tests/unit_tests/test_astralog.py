import pytest
import os.path
from unittest.mock import Mock, patch
from src.astralog import AstraLog
from src.data_file_reader import DataFileReader
from src.batch_manager import BatchManager


# ----------------
# Astralog setters
# ----------------

def test_astralog_set_data_source():
    astralog = AstraLog()

    data_reader = DataFileReader()
    astralog.set_data_source(data_reader)
    assert astralog._data_reader == data_reader


def test_astralog_set_sensors_invalid_file():
    astralog = AstraLog()
    
    assert astralog.set_sensors("does_not_exist.json") == False
    assert astralog._sensor_count == 0


def test_astralog_set_batch_mode():
    astralog = AstraLog()
    astralog._batch_manager = Mock()

    astralog.set_batch_mode(BatchManager.MODE_SIZE, 10.0)
    astralog._batch_manager.set_mode.assert_called_with(BatchManager.MODE_SIZE, 10.0)

    astralog.set_batch_mode(BatchManager.MODE_SIZE, -1)
    astralog._batch_manager.set_mode.assert_called_with(BatchManager.MODE_SIZE, -1)

    astralog.set_batch_mode(BatchManager.MODE_TIME, 0.00001)
    astralog._batch_manager.set_mode.assert_called_with(BatchManager.MODE_TIME, 0.00001)


def test_astralog_set_paths(tmp_path):
    astralog = AstraLog()
    astralog._batch_analyzer = Mock()

    # set batch output dir
    output_dir = tmp_path / "out_dir"
    astralog.set_batch_output_dir(str(output_dir))
    assert astralog._batch_manager.output_dir == str(output_dir)
    assert os.path.isdir(output_dir)  # dir was created

    # set alarms output file
    file = tmp_path / "file.txt"
    astralog.set_alarms_output_file(str(file))
    astralog._batch_analyzer.set_alarms_output_file.assert_called_once_with(str(file))

    # set valid data output file
    astralog.set_valid_output_file(str(file))
    astralog._batch_analyzer.set_valid_output_file.assert_called_once_with(str(file))


def test_astralog_set_rules_no_sensors():
    astralog = AstraLog()
    assert astralog.set_rules("") == False


def test_astralog_set_rules_invalid_file():
    astralog = AstraLog()
    astralog._sensor_count = 1
    assert astralog.set_rules("does_not_exist.txt") == False


# -----------------------
# Astralog on hz function
# -----------------------

def test_astralog_on_hz(capsys):
    astralog = AstraLog()
    astralog._reading_freq = 1.0
    astralog._sensor_count = 1

    astralog.on_hz(0.5)

    captured_output = capsys.readouterr().out
    expected_output = "AstraLog: 0.50 iterations/sec FALLING BEHIND (target = 1.0)\n"
    assert expected_output == captured_output


# ------------------------------------
# Checking the failure of start method
# ------------------------------------

def test_astralog_start_fails_without_data_reader(capsys):
    alog = AstraLog()
    alog.start()

    output = capsys.readouterr().out
    assert "AstraLog: specify a sensor data source using AstraLog.set_data_source" \
        in output
    

def test_atralog_start_fails_without_sensors(capsys):
    alog = AstraLog()
    alog.set_data_source(Mock())

    alog.start()

    output = capsys.readouterr().out

    assert "AstraLog: provide sensors configuration using AstraLog.set_sensors" \
        in output