from enum import Enum
from abc import ABC, abstractmethod

class DataReaderType(Enum):
    FILE = 1
    STREAM = 2

class DataReader(ABC):
    @abstractmethod
    def read_one(self) -> tuple[bool, str]:
        pass

    # either open file or connection, maybe rename to "init"
    def open(self) -> bool:
        return True

    # either close file or connection
    def close(self):
        pass