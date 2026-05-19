from src.data_reader import DataReader, DataReaderType

from io import TextIOWrapper, StringIO
import csv


class DataFileReader(DataReader):
    _filename: str = ""
    _file: TextIOWrapper

    EXPECTED_COLUMNS = ["timestamp", "sensor_id", "value", "priority"]

    def read_one(self) -> tuple[bool, str]:
        line: str = self._file.readline()  # includes the \n
        line = line.strip()
        if line == "":
            print("DataFileReader: EOF")
            return False, ""

        return True, line

    def set_data_file(self, filename: str):
        self._filename = filename

    def open(self) -> bool:
        try:
            self._file = open(self._filename, "r")

            header = self._file.readline()
            header = header.strip()
            if header == "":
                print("DataFileReader: provided file is empty")
                self._file.close()
                return False

            reader = csv.reader(StringIO(header))
            row = next(reader, None)
            if row is None:
                print("DataFileReader: this shouldn't happen")  # means that header is empty, checked before
                self._file.close()
                return False

            if len(row) != 4:
                print(f"DataFileReader: invalid csv chema, expected {DataFileReader.EXPECTED_COLUMNS}")

            for i in range(4):
                if row[i] != DataFileReader.EXPECTED_COLUMNS[i]:
                    print(f"DataFileReader: invalid csv schema, expected {DataFileReader.EXPECTED_COLUMNS}")
                    self._file.close()
                    return False

        except FileNotFoundError:
            print(f"DataFileReader: file '{self._filename}' not found")
            return False
        return True

    def close(self):
        self._file.close()
        pass

    def __str__(self) -> str:
        if self._filename is None or self._filename == "":
            return "DataFileReader (no file)"
        else:
            return f"DataFileReader ({self._filename})"

    @staticmethod
    def type() -> DataReaderType:
        return DataReaderType.FILE
