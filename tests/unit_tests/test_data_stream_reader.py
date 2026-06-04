import pytest
from queue import Queue
from unittest.mock import Mock, patch
from src.data_reader import DataReaderType
from src.data_stream_reader import DataStreamReader, on_message


@pytest.fixture
def reader():
    return DataStreamReader('url', 'port', 'topic', 'user', 'password')


# -------------------
# on_message callback
# -------------------

def test_on_message():
    msg = Mock()
    msg.payload = b"msg1"

    queue = Queue()
    user_data = {"queue": queue}

    on_message(None, user_data, msg)

    assert queue.get() == "msg1"


# ----------------
# DataStreamReader
# ----------------

def test_data_stream_reader_init(reader):
    assert reader._client_id.startswith("Station_")
    assert len(reader._client_id) == len("Station_") + 6


def test_data_stream_reader_open_success(reader):
    client = Mock()
    client.connect.return_value = 0

    with patch("src.data_stream_reader.mqtt.Client", return_value=client):
        result = reader.open()

    assert result is True
    assert reader._connected

    # Verify calls to MQTT client
    client.username_pw_set.assert_called_once()
    client.tls_set_context.assert_called_once()
    client.connect.assert_called_once_with(reader.broker_url, reader.port)
    client.subscribe.assert_called_once_with(reader.topic)
    client.loop_start.assert_called_once()


def test_data_stream_reader_open_failure(reader):
    client = Mock()
    client.connect.return_value = 1  # failure to connect

    with patch("src.data_stream_reader.mqtt.Client", return_value=client):
        result = reader.open()

    assert result is False
    assert not reader._connected

    # Verify calls to MQTT client
    client.subscribe.assert_not_called()
    client.loop_start.assert_not_called()


def test_data_stream_reader_open_version2_not_supported(reader):
    client = Mock()
    client.connect.return_value = 0

    with patch("src.data_stream_reader.mqtt.Client", side_effect=[
        Exception("Version2 not supported"),
        client
    ]) as client_class:
        result = reader.open()

        assert client_class.call_count == 2

    assert result is True
    assert reader._connected

    # Verify calls to MQTT client
    client.username_pw_set.assert_called_once()
    client.tls_set_context.assert_called_once()
    client.connect.assert_called_once_with(reader.broker_url, reader.port)
    client.subscribe.assert_called_once_with(reader.topic)
    client.loop_start.assert_called_once()


def test_data_stream_reader_close(reader):
    client = Mock()
    client.connect.return_value = 0

    with patch("src.data_stream_reader.mqtt.Client", return_value=client):
        reader.open()

    reader.close()

    assert not reader._connected

    # Verify calls to MQTT client
    client.loop_stop.assert_called_once()
    client.disconnect.assert_called_once()


def test_data_stream_reader_str(reader):
    reader._connected = False
    assert str(reader) == "DataStreamReader (connected = False)"

    reader._connected = True
    assert str(reader) == "DataStreamReader (connected = True)"


def test_data_stream_reader_type():
    assert DataStreamReader.type() == DataReaderType.STREAM


def test_data_stream_reader_read_one_success(reader):
    reader._message_queue = Queue()
    reader._message_queue.put("payload1")

    ok, payload = reader.read_one()

    assert ok
    assert payload == "payload1"


def test_data_stream_reader_read_one_empty_queue(reader):
    reader._message_queue = Queue()

    ok, payload = reader.read_one()

    assert not ok
    assert payload == ""
