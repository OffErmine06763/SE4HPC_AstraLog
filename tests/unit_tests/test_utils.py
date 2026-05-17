import pytest
from unittest.mock import Mock, patch
from src.utils import FrequencyMeter, TimestampData, SensorReading


# TODO: tests for get key (now the logic is very platform-specific, so refactor is needed)


# --------------
# FrequencyMeter
# --------------

def test_frequency_meter_set():
    freq_meter = FrequencyMeter()

    assert freq_meter.count == 0


def test_frequency_meter_init():
    freq_meter = FrequencyMeter()
    with patch('src.utils.time.perf_counter', return_value=123.0):
        freq_meter.init()
    
    assert freq_meter.start == 123.0
        

def test_frequency_counter_incr():
    freq_meter = FrequencyMeter()
    with patch('src.utils.time.perf_counter', return_value=0.0):
        freq_meter.init()

    freq_meter.on_hz = Mock()

    with patch('src.utils.time.perf_counter', return_value=4.9):
        freq_meter.update()
    
    assert freq_meter.count == 1
    freq_meter.on_hz.assert_not_called()


def test_frequency_meter_counter_reset():
    freq_meter = FrequencyMeter()
    with patch('src.utils.time.perf_counter', return_value=0.0):
        freq_meter.init()

    freq_meter.on_hz = Mock()

    with patch('src.utils.time.perf_counter', return_value=4.9):
        freq_meter.update()
    with patch('src.utils.time.perf_counter', return_value=10.0):
        freq_meter.update()
    
    assert freq_meter.count == 0
    freq_meter.on_hz.assert_called_once_with(0.2)


# -------------
# TimestampData
# -------------

def test_timestamp_data_set():
    td = TimestampData('ts1', [0.4, None])

    assert td.ts == 'ts1'
    assert td.readings == [0.4, None]

# -------------
# SensorReading
# -------------

def test_sensor_reading_set():
    sr = SensorReading('ts1', 1, 0.4)

    assert sr.ts == 'ts1'
    assert sr.id == 1
    assert sr.value == 0.4
