from src.data_reader import DataReader, DataReaderType

import paho.mqtt.client as mqtt
import ssl
import uuid
from queue import Queue
import os
from dotenv import load_dotenv

load_dotenv()

def on_message(self, userdata, msg):
    queue = userdata["queue"]
    queue.put(msg.payload.decode("utf-8"))
    # self._message_payload = msg.payload.decode('utf-8')
    # self._message_event.set()  # unblock waiting code


# This class should just handle the connection to the stream and listen for one sensor reading at a time
# The loop to keep listening is in AstraLog
class DataStreamReader(DataReader):
    # --- MISSION CONFIGURATION ---
    broker_url = os.getenv("MQTT_BROKER_URL")
    port = int(os.getenv("MQTT_PORT", 8883))
    topic = os.getenv("MQTT_TOPIC")
    user = os.getenv("MQTT_USER")
    password = os.getenv("MQTT_PASSWORD")

    if broker_url is None:
        raise ValueError("DataStreamReader: missing MQTT_BROKER_URL environment variable")
    
    if topic is None:
        raise ValueError("DataStreamReader: missing MQTT_TOPIC environment variable")

    if user is None:
        raise ValueError("DataStreamReader: missing MQTT_USER environment variable")

    if password is None:
        raise ValueError("DataStreamReader: missing MQTT_PASSWORD environment variable")

    BROKER_URL: str = broker_url
    PORT: int = port
    TOPIC: str = topic
    USER: str = user
    PASSWORD: str = password

    _client_id: str = ""
    _client: mqtt.Client
    _connected: bool = False

    # _message_event = threading.Event()
    # _message_payload: str = ""
    _message_queue: Queue[str] = Queue()

    def __init__(self):
        self._client_id = f"Station_{uuid.uuid4().hex[:6]}"

    def read_one(self) -> tuple[bool, str]:
        try:
            payload = self._message_queue.get(timeout=5)
            return True, payload
        except Exception:
            # TODO: handle timeout
            pass

        # TODO: handle connection issues / end of stream
        return False, ""

    def open(self) -> bool:
        # init client
        try:  # if you use vscode don't mind the error here v, it's stupid
            self._client = mqtt.Client(
                mqtt.CallbackAPIVersion.VERSION2,
                client_id=self._client_id,
                protocol=mqtt.MQTTv5,
                userdata={"queue": self._message_queue},
            )
        except Exception:
            self._client = mqtt.Client(
                client_id=self._client_id,
                protocol=mqtt.MQTTv5,
                userdata={"queue": self._message_queue},
            )

        self._client.username_pw_set(DataStreamReader.USER, DataStreamReader.PASSWORD)
        self._client.tls_set_context(ssl.create_default_context())
        self._client.on_message = on_message

        # init connection
        rc = self._client.connect(DataStreamReader.BROKER_URL, DataStreamReader.PORT)
        if rc == 0:
            print(f"DataStreamReader: connected to {DataStreamReader.BROKER_URL}")
            self._client.subscribe(DataStreamReader.TOPIC)
        else:
            print(f"DataStreamReader: connection error {rc}")
            return False

        # listen for events
        self._client.loop_start()

        self._connected = True
        return True

    def close(self):
        # TODO: verify correct disposal of connection

        self._connected = False
        self._client.loop_stop()  # stop listening for events
        self._client.disconnect()

    def __str__(self) -> str:
        return f"DataStreamReader (connected = {self._connected})"

    @staticmethod
    def type() -> DataReaderType:
        return DataReaderType.STREAM
