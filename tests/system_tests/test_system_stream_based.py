import pytest
import json
import os
import threading
import time
import sys
import subprocess
import pathlib

import paho.mqtt.client as mqtt
from testcontainers.core.container import DockerContainer

from src.utils import SensorReading


DATA_DIR = os.path.join(pathlib.Path(__file__).parent, "data")


@pytest.fixture(autouse=True)
def set_environment_variables():
    os.environ["MQTT_BROKER_URL"] = "localhost"
    os.environ["MQTT_TOPIC"] = "test/topic"
    os.environ["MQTT_USER"] = "user"  # will not be used
    os.environ["MQTT_PASSWORD"] = "pass"  # will not be used
    os.environ["USE_TLS"] = "false"


@pytest.fixture
def output_dir(tmp_path):
    return tmp_path / "batches"


@pytest.fixture
def alarms_file(tmp_path):
    return tmp_path / "alarms.txt"


@pytest.fixture
def valid_file(tmp_path):
    return tmp_path / "valid.txt"


@pytest.fixture
def small_sensors_file():
    return os.path.join(DATA_DIR, "test_small", "sensors.yaml")


@pytest.fixture
def small_rules_file():
    return os.path.join(DATA_DIR, "test_small", "rules.json")


@pytest.fixture
def broker():
    # pre-test setup
    print('TEST STARTED')

    broker = DockerContainer("eclipse-mosquitto:2").with_exposed_ports(1883)
    broker.start()
    print('WITH DOCKER -- inside already')

    try:
        port = broker.get_exposed_port(1883)
        os.environ["MQTT_PORT"] = str(port)

        yield broker  # execute the test
    finally:
        # post-test cleanup
        broker.stop()


def assert_files_equal(file1, file2):
    assert os.path.exists(file1)
    assert os.path.exists(file2)

    with open(file1, "r") as f1:
        text1 = f1.read()
    with open(file2, "r") as f2:
        text2 = f2.read()

    assert text1 == text2


def publish_messages(port, sensor_readings: list[SensorReading]):
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv5,
    )

    client.connect("localhost", port)

    for reading in sensor_readings:
        payload = {
            "sensor_id": reading.id,
            "timestamp": reading.ts,
            "value": reading.value,
            "priority": "LOW"
        }
        client.publish("test/topic", json.dumps(payload))
        time.sleep(0.05)

    client.disconnect()


def publish_eos(port):
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        protocol=mqtt.MQTTv5,
    )

    client.connect("localhost", port)
    client.publish("test/topic", "EOS")
    client.disconnect()


def run_astralog(output_dir, valid_file, alarms_file, sensors_file, rules_file):
    print(f'VALID FILE: {str(valid_file)}')
    print(f'ALARMS FILE: {str(alarms_file)}')

    print('ASTRALOG PROCESS WITHIN THREAD STARTED')

    result = subprocess.run(
            [
                sys.executable, "-m", "src.main", "--reading-mode", "mqtt",
                "--batch-mode", "count", "--limit", "10",
                "--sensors-file", str(sensors_file),
                "--rules-file", str(rules_file),
                "--output-dir", str(output_dir),
                "--alarms-output-file", str(alarms_file),
                "--valid-output-file", str(valid_file)
            ],
            capture_output=True,
            timeout=60
        )

    print('ASTRALOG PROCESS WITHIN THREAD STOPPED')

    print(f'ASTRALOG OUTPUT:\n{result.stdout.decode("ascii")}')
    print(f'ASTRALOG STDERR:\n{result.stderr.decode("ascii")}')

    assert result.returncode == 0
    assert b"AstraLog: END" in result.stdout


def test_astralog_connection_to_mqtt(
    output_dir, alarms_file, valid_file, small_sensors_file, small_rules_file, broker
):
    port = broker.get_exposed_port(1883)

    t = threading.Thread(
        target=run_astralog,
        args=[output_dir, valid_file, alarms_file, small_sensors_file, small_rules_file]
    )
    t.start()

    print('THREAD STARTED FOR ASTRALOG')

    time.sleep(5)

    publish_messages(int(port), [SensorReading('time1', 'TEMP-001', 10.0),
                                 SensorReading('time2', 'TEMP-001', 60.0)])
    print('MESSAGES PUBLISHED')

    time.sleep(5)

    publish_eos(int(port))

    time.sleep(5)

    t.join(timeout=10)
    assert not t.is_alive()  # thread stopped already (due to EOS)

    print('ASTRALOG THREAD JOINED')

    assert valid_file.exists()
    assert alarms_file.exists()


def test_astralog_small_mqtt_stream(
    output_dir, alarms_file, valid_file, small_sensors_file, small_rules_file, broker
):
    port = broker.get_exposed_port(1883)

    t = threading.Thread(
        target=run_astralog,
        args=[output_dir, valid_file, alarms_file, small_sensors_file, small_rules_file]
    )
    t.start()

    print('THREAD STARTED FOR ASTRALOG')

    time.sleep(5)

    # MESSAGES SAME AS readings.csv of sigma case

    publish_messages(int(port), [SensorReading('1', 'TEMP-001', 99.)])
    time.sleep(5)
    publish_messages(int(port), [SensorReading('1', 'TEMP-002', 99.),
                                 SensorReading('2', 'TEMP-001', 99.),
                                 SensorReading('2', 'TEMP-002', 40.),
                                 SensorReading('3', 'TEMP-001', 30.)])
    time.sleep(5)
    publish_messages(int(port), [SensorReading('3', 'TEMP-002', 99.),
                                 SensorReading('4', 'TEMP-001', 30.),
                                 SensorReading('4', 'TEMP-002', 40.),
                                 SensorReading('5', 'TEMP-001', 99.),
                                 SensorReading('5', 'TEMP-002', 99.)])
    print('MESSAGES PUBLISHED')

    time.sleep(5)

    publish_eos(int(port))

    time.sleep(5)

    t.join(timeout=10)
    assert not t.is_alive()  # thread stopped already (due to EOS signal)

    print('ASTRALOG THREAD JOINED')

    expected_alarms_output = os.path.join(DATA_DIR, "test_small", "expected_alarm_output.txt")
    expected_valid_output = os.path.join(DATA_DIR, "test_small", "expected_valid_output.txt")

    assert_files_equal(expected_alarms_output, alarms_file)
    assert_files_equal(expected_valid_output, valid_file)


def test_astralog_disconnects_on_timeout(
    output_dir, alarms_file, valid_file, small_sensors_file, small_rules_file, broker
):
    port = broker.get_exposed_port(1883)

    t = threading.Thread(
        target=run_astralog,
        args=[output_dir, valid_file, alarms_file, small_sensors_file, small_rules_file]
    )
    t.start()

    print('THREAD STARTED FOR ASTRALOG')

    time.sleep(5)

    publish_messages(int(port), [SensorReading('time1', 'TEMP-001', 10.0),
                                 SensorReading('time2', 'TEMP-001', 60.0)])
    print('MESSAGES PUBLISHED')

    time.sleep(20)

    t.join(timeout=10)
    assert not t.is_alive()  # thread stopped already (due to timeout)

    print('ASTRALOG THREAD JOINED')

    assert valid_file.exists()
    assert alarms_file.exists()

    valid_file_content = valid_file.read_text()
    alarms_file_content = alarms_file.read_text()

    assert valid_file_content == "time2;NOMINAL;TEMP-001:60.0|TEMP-002:None\n"
    assert alarms_file_content == "time1;S1;HIGH;TEMP-001;10.0\n"
