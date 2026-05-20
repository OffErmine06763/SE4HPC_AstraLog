import pytest
import os.path
import pathlib
import time
import threading
import shutil
from src.astralog import AstraLog
from src.data_file_reader import DataFileReader
from src.batch_manager import BatchManager
from src.rule import Rule


DATA_DIR = os.path.join(pathlib.Path(__file__).parent, "data")
SENSORS_FILE = os.path.join(DATA_DIR, "sensors.yaml")
RULES_FILE = os.path.join(DATA_DIR, "rules.json")
READINGS_FILE = os.path.join(DATA_DIR, "readings.csv")
BATCH_FILE = os.path.join(DATA_DIR, "batch.txt")

EXPECTED_ALARM_FILE = os.path.join(DATA_DIR, "expected_alarm_output.txt")
EXPECTED_VALID_FILE = os.path.join(DATA_DIR, "expected_valid_output.txt")


def assert_files_equal(file1, file2):
    assert os.path.exists(file1)
    assert os.path.exists(file2)

    with open(file1, "r") as f1:
        text1 = f1.read()
    with open(file2, "r") as f2:
        text2 = f2.read()

    assert text1 == text2


@pytest.fixture(autouse=True)
def reset_rule_ids():
    """Reset class-level IDs so tests are deterministic."""
    Rule._next_id = 0


@pytest.fixture
def out_dir(tmp_path):
    return tmp_path / "out_dir"


@pytest.fixture
def valid_output_file(tmp_path):
    return tmp_path / "valid_output.txt"


@pytest.fixture
def alarms_output_file(tmp_path):
    return tmp_path / "alarms_output.txt"


@pytest.fixture
def astralog(out_dir, valid_output_file, alarms_output_file):
    alog = AstraLog()

    AstraLog.ERASE_BATCHES = True
    AstraLog.BATCH_QUEUE_LOOP_TIMEOUT = 0.2

    reader = DataFileReader()
    reader.set_data_file(READINGS_FILE)
    alog.set_data_source(reader)

    alog.set_sensors(SENSORS_FILE)
    alog.set_rules(RULES_FILE)
    alog.set_batch_mode(BatchManager.MODE_SIZE, 0)  # to flush everything

    alog.set_alarms_output_file(str(alarms_output_file))
    alog.set_valid_output_file(str(valid_output_file))
    alog.set_batch_output_dir(str(out_dir))

    yield alog

    # back to the default values
    AstraLog.ERASE_BATCHES = True
    AstraLog.BATCH_QUEUE_LOOP_TIMEOUT = 2.0


# ---------------------
# Testing analysis loop
# ---------------------

def test_analysis_loop_waits_for_batch(astralog, tmp_path, valid_output_file, alarms_output_file):
    analysis_thread = threading.Thread(target=astralog.analysis_loop)
    analysis_thread.start()

    batch_file = tmp_path / "batch-tmp.txt"
    shutil.copy(BATCH_FILE, batch_file)
    assert os.path.exists(batch_file)

    time.sleep(0.5)  # Loop will have to busy wait

    astralog._batches_ready.put(batch_file)

    astralog._stop_analysis_event.set()
    analysis_thread.join(timeout=15.0)

    astralog._batch_analyzer.deinit()

    assert not analysis_thread.is_alive()  # thread stopped (not because of timeout)
    assert not os.path.exists(batch_file)  # astralog deleted batch file

    assert_files_equal(EXPECTED_ALARM_FILE, alarms_output_file)
    assert_files_equal(EXPECTED_VALID_FILE, valid_output_file)


def test_analysis_loop_stops_on_event(astralog, tmp_path, valid_output_file, alarms_output_file):
    analysis_thread = threading.Thread(target=astralog.analysis_loop)
    analysis_thread.start()

    time.sleep(0.5)  # Loop will have to busy wait

    astralog._stop_analysis_event.set()
    analysis_thread.join(timeout=15.0)

    astralog._batch_analyzer.deinit()

    assert not analysis_thread.is_alive()  # thread stopped (not because of timeout)


def test_analysis_loop_does_not_delete_batch(astralog, tmp_path, valid_output_file, alarms_output_file):
    AstraLog.ERASE_BATCHES = False

    analysis_thread = threading.Thread(target=astralog.analysis_loop)
    analysis_thread.start()

    batch_file = tmp_path / "batch-tmp.txt"
    shutil.copy(BATCH_FILE, batch_file)
    assert os.path.exists(batch_file)

    astralog._batches_ready.put(batch_file)

    astralog._stop_analysis_event.set()
    analysis_thread.join(timeout=15.0)

    astralog._batch_analyzer.deinit()

    assert not analysis_thread.is_alive()  # thread stopped (not because of timeout)
    assert os.path.exists(batch_file)      # astralog did not delete the batch file

    assert_files_equal(EXPECTED_ALARM_FILE, alarms_output_file)
    assert_files_equal(EXPECTED_VALID_FILE, valid_output_file)


def test_analysis_loop_warns_on_invalid_file(capsys, astralog, tmp_path, valid_output_file, alarms_output_file):
    analysis_thread = threading.Thread(target=astralog.analysis_loop)
    analysis_thread.start()

    batch_file = tmp_path / "does_not_exist.txt"
    astralog._batches_ready.put(batch_file)

    astralog._stop_analysis_event.set()
    analysis_thread.join(timeout=15.0)

    astralog._batch_analyzer.deinit()

    assert not analysis_thread.is_alive()  # thread stopped (not because of timeout)

    sysout = capsys.readouterr().out
    assert f"ERROR AstraLog - Analysis: batch file '{batch_file}' not found" \
        in sysout


# ---------------------
# AstraLog start method
# ---------------------

def test_astralog_start(astralog, valid_output_file, alarms_output_file):
    astralog.start()

    assert_files_equal(EXPECTED_ALARM_FILE, alarms_output_file)
    assert_files_equal(EXPECTED_VALID_FILE, valid_output_file)


def test_astralog_finishes_non_flushed(astralog, valid_output_file, alarms_output_file):
    astralog.set_batch_mode(BatchManager.MODE_SIZE, 1000)  # will never flush when adding new batches
    astralog.start()

    assert_files_equal(EXPECTED_ALARM_FILE, alarms_output_file)
    assert_files_equal(EXPECTED_VALID_FILE, valid_output_file)
