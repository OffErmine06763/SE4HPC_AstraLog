import subprocess
import os
import pytest
import pathlib
import time


DATA_DIR = os.path.join(pathlib.Path(__file__).parent, "data")
LARGE_TEST_DIR = os.path.join(pathlib.Path(__file__).parent.parent.parent, "res")


def assert_files_equal(file1, file2):
    assert os.path.exists(file1)
    assert os.path.exists(file2)

    with open(file1, "r") as f1:
        text1 = f1.read()
    with open(file2, "r") as f2:
        text2 = f2.read()

    assert text1 == text2


def test_system_with_simple_files(tmp_path):
    expected_alarms_output = os.path.join(DATA_DIR, "test_small", "expected_alarm_output.txt")
    expected_valid_output = os.path.join(DATA_DIR, "test_small", "expected_valid_output.txt")

    readings_file = os.path.join(DATA_DIR, "test_small", "readings.csv")
    sensors_file = os.path.join(DATA_DIR, "test_small", "sensors.yaml")
    rules_file = os.path.join(DATA_DIR, "test_small", "rules.json")
    output_dir = tmp_path / "out_dir"
    valid_output_file = tmp_path / "valid_output.txt"
    alarms_output_file = tmp_path / "alarms_output.txt"

    result = subprocess.run(
        [
            "python3", "-m", "src.main", "--reading-mode", "file",
            "--batch-mode", "count", "--limit", "10",
            "--readings-file", str(readings_file),
            "--sensors-file", str(sensors_file),
            "--rules-file", str(rules_file),
            "--output-dir", str(output_dir),
            "--alarms-output-file", str(alarms_output_file),
            "--valid-output-file", str(valid_output_file)
        ],
        capture_output=True,
        timeout=10
    )

    assert result.returncode == 0
    assert b"AstraLog: END" in result.stdout

    assert_files_equal(expected_alarms_output, alarms_output_file)
    assert_files_equal(expected_valid_output, valid_output_file)


def run_with_timer_large_test(tmp_path, readings_filename, time_limit,
                              batch_mode_str, limit):
    readings_file = os.path.join(LARGE_TEST_DIR, readings_filename)
    sensors_file = os.path.join(LARGE_TEST_DIR, "sensors_alpha.yaml")
    rules_file = os.path.join(LARGE_TEST_DIR, "rules_alpha.json")
    output_dir = tmp_path / "out_dir"
    valid_output_file = tmp_path / "valid_output.txt"
    alarms_output_file = tmp_path / "alarms_output.txt"

    try:
        start_time = time.perf_counter()
        result = subprocess.run(
            [
                "python3", "-m", "src.main", "--reading-mode", "file",
                "--batch-mode", batch_mode_str, "--limit", str(limit),
                "--readings-file", str(readings_file),
                "--sensors-file", str(sensors_file),
                "--rules-file", str(rules_file),
                "--output-dir", str(output_dir),
                "--alarms-output-file", str(alarms_output_file),
                "--valid-output-file", str(valid_output_file)
            ],
            capture_output=True,
            timeout=time_limit
        )
        end_time = time.perf_counter()
    except TimeoutError:
        pytest.fail(f"AstraLog took longer than {time_limit}s for file {readings_filename}")

    print(f"AstraLog finished in {end_time-start_time}s for {readings_filename}")
    assert result.returncode == 0
    assert b"AstraLog: END" in result.stdout


def test_system_with_readings_alpha_small(tmp_path):
    run_with_timer_large_test(tmp_path, "readings_alpha_small.csv", time_limit=10,
                              batch_mode_str="count", limit=100)


def test_system_with_readings_alpha_medium(tmp_path):
    run_with_timer_large_test(tmp_path, "readings_alpha_medium.csv", time_limit=10,
                              batch_mode_str="count", limit=100)


def test_system_with_readings_alpha_large_count_mode(tmp_path):
    run_with_timer_large_test(tmp_path, "readings_alpha_large.csv", time_limit=20,
                              batch_mode_str="count", limit=100)


def test_system_with_readings_alpha_large_infinite_batch(tmp_path):
    run_with_timer_large_test(tmp_path, "readings_alpha_large.csv", time_limit=20,
                              batch_mode_str="count", limit=1000000000)


def test_system_with_readings_alpha_large_time_mode(tmp_path):
    run_with_timer_large_test(tmp_path, "readings_alpha_large.csv", time_limit=30,
                              batch_mode_str="time", limit=10)
