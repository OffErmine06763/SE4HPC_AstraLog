import sys
from collections.abc import Callable
import time


if sys.platform == "win32":
    import msvcrt

    def get_key():
        if msvcrt.kbhit():
            return msvcrt.getch().decode(errors="ignore")
        return None
else:
    import select
    import termios
    import tty

    class UnixKeyReader:
        def __enter__(self):
            self.fd = sys.stdin.fileno()
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setcbreak(self.fd)
            return self

        def __exit__(self, *args):
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)

    def get_key():
        dr, _, _ = select.select([sys.stdin], [], [], 0)
        if dr:
            return sys.stdin.read(1)
        return None

    unix_reader = UnixKeyReader()


class FrequencyMeter:
    count = 0
    start = time.perf_counter()
    on_hz: Callable[[float], None]

    def update(self):
        self.count += 1
        now = time.perf_counter()
        if now - self.start >= 5.0:
            hz = self.count / (now - self.start)

            self.on_hz(hz)

            self.start = now
            self.count = 0

    def init(self):
        self.start = time.perf_counter()


class TimestampData:
    ts: str = ""
    readings: list[float | None]


class SensorReading:
    ts: str
    id: int
    value: float
