from data_reader import DataReader
from io import TextIOWrapper

class DataFileReader(DataReader):
    _filename: str = ""
    _file: TextIOWrapper

    def read_one(self) -> tuple[bool, str]:
        line: str = self._file.readline() # includes the \n
        if line == "":
            print("DataFileReader: EOF")
            return False, ""
        return True, line.strip()


    def set_data_file(self, filename: str):
        self._filename = filename

    def open(self) -> bool: 
        try:
            self._file = open(self._filename, "r")
        except FileNotFoundError:
            print(f"DataFileReader: file '{self._filename}' not found")
            return False
        return True

    def close(self):
        self._file.close()
        pass

    def __str__(self) -> str:
        if self._filename is None:
           return "DataFileReader (no file)"
        else:
           return f"DataFileReader ({self._filename})"