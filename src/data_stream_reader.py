from data_reader import DataReader

import paho.mqtt.client as mqtt
import ssl
import uuid
import time
import os
from queue import Queue
import threading

def on_message(self, userdata, msg):
    queue = userdata['queue']
    queue.put(msg.payload.decode('utf-8'))
    # self._message_payload = msg.payload.decode('utf-8')
    # self._message_event.set()  # unblock waiting code

# This class should just handle the connection to the stream and listen for one sensor reading at a time
# The loop to keep listening is in AstraLog
class DataStreamReader(DataReader):
    # --- MISSION CONFIGURATION ---
    BROKER_URL = "fb2fb70e5df845aaa8ac44ead8e3c5e1.s1.eu.hivemq.cloud"
    PORT = 8883
    TOPIC = "esa/astralog/telemetry"
    USER = "students"
    PASSWORD = "Listeningstuff26"
    OUTPUT_DIR = "collector_output"

    _client_id: str = ""
    _client: mqtt.Client
    _connected: bool = False

    # _message_event = threading.Event()
    # _message_payload: str = ""
    _message_queue = Queue()

    def __init__(self):
        self._client_id = f"Station_{uuid.uuid4().hex[:6]}"


    def read_one(self):
        try:
            payload = self._message_queue.get(timeout=5)
            # print(payload)
        except:
            # TODO: handle timeout
            pass
        
        # self._message_event.wait(timeout=10) # blocks until message arrives

        # if not self._message_event.is_set():
        #    pass
          
        # print(self._message_payload)

        # TODO: handle connection issues / end of stream
        pass


    def open(self) -> bool:
        # init client
        try: # if you use vscode don't mind the error here v, it's stupid
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._client_id, protocol=mqtt.MQTTv5, userdata={'queue': self._message_queue})
        except:
            self._client = mqtt.Client(client_id=self._client_id, protocol=mqtt.MQTTv5, userdata={'queue': self._message_queue})

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
        pass

    def __str__(self) -> str:
        return f"DataStreamReader (connected = {self._connected})"