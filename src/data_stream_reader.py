from src.data_reader import DataReader, DataReaderType

import paho.mqtt.client as mqtt
import ssl
import uuid
from queue import Queue, Empty


def on_message(self, userdata, msg):
    queue = userdata["queue"]
    queue.put(msg.payload.decode("utf-8"))


# This class should just handle the connection to the stream and listen for one sensor reading at a time
# The loop to keep listening is in AstraLog
class DataStreamReader(DataReader):
    _client_id: str = ""
    _client: mqtt.Client
    _connected: bool = False

    # _message_event = threading.Event()
    # _message_payload: str = ""
    _message_queue: Queue[str] = Queue()

    def __init__(self,
                 broker_url,
                 port,
                 topic,
                 user,
                 password,
                 use_tls=True,
                 timeout=20
                 ):
        self._client_id = f"Station_{uuid.uuid4().hex[:6]}"
        self.broker_url = broker_url
        self.port = port
        self.topic = topic
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.timeout = timeout

        print(f'DataStreamReader created, will connect to: broker_url={broker_url}')
        print(f'   port={self.port}, topic={self.topic}, user={self.user}, password={self.password}')
        print(f'   use_tls={self.use_tls}, timeout={self.timeout}')

    def read_one(self) -> tuple[bool, str]:
        try:
            payload = self._message_queue.get(timeout=self.timeout)

            if payload == 'EOS':  # meant for testing to mark the end of stream
                return False, ''

            return True, payload
        except Empty:
            print(f"DataStreamReader: timed out waiting for message after {self.timeout}s")
        return False, ''

    def open(self) -> bool:
        # init client
        try:  # if you use vscode don't mind the error here
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

        self._client.username_pw_set(self.user, self.password)

        if self.use_tls:
            self._client.tls_set_context(ssl.create_default_context())

        self._client.on_message = on_message

        # init connection
        rc = self._client.connect(self.broker_url, self.port)
        if rc == 0:
            print(f"DataStreamReader: connected to {self.broker_url}")
            self._client.subscribe(self.topic)
        else:
            print(f"DataStreamReader: connection error {rc}")
            return False

        # listen for events
        self._client.loop_start()

        self._connected = True
        return True

    def close(self):
        self._connected = False
        self._client.loop_stop()  # stop listening for events
        try:
            self._client.disconnect()
            print("DataStreamReader: disconnected cleanly")
        except Exception as e:
            print(f"DataStreamReader: error during disconnect: {e}")

    def __str__(self) -> str:
        return f"DataStreamReader (connected = {self._connected})"

    @staticmethod
    def type() -> DataReaderType:
        return DataReaderType.STREAM
