from src.data_file_reader import DataFileReader
from src.data_reader import DataReaderType


def test_set_file_name():
    reader = DataFileReader()
    reader.set_data_file("filename.txt")
    assert reader._filename == "filename.txt"


def test_open_file_not_found():
    reader = DataFileReader()
    reader.set_data_file("does_not_exist.txt")
    assert reader.open() is False


def test_open_file_empty_file(tmp_path):
    file = tmp_path / "readings.csv"

    reader = DataFileReader()
    reader.set_data_file(str(file))
    assert reader.open() is False


def test_open_file_empty_header(tmp_path):
    file = tmp_path / "readings.csv"
    file.write_text("\n")

    reader = DataFileReader()
    reader.set_data_file(str(file))
    assert reader.open() is False


def test_open_file_header_too_short(tmp_path):
    file = tmp_path / "readings.csv"
    file.write_text("a,b,c")

    reader = DataFileReader()
    reader.set_data_file(str(file))
    assert reader.open() is False


def test_open_file_header_fields_wrong(tmp_path):
    file = tmp_path / "readings.csv"
    file.write_text("timestamp,sensor_id,value,AAA\n")

    reader = DataFileReader()
    reader.set_data_file(str(file))
    assert reader.open() is False


def test_open_file_success(tmp_path):
    file = tmp_path / "readings.csv"
    file.write_text("timestamp,sensor_id,value,priority\n")

    reader = DataFileReader()
    reader.set_data_file(str(file))
    assert reader.open() is True
    reader.close()


def test_read_one(tmp_path):
    data = "timestamp,sensor_id,value,priority\n"
    data += "1,TEMP-001,99,LOW\n"
    data += "1,TEMP-002,99,LOW\n"

    file = tmp_path / "readings.csv"
    file.write_text(data)

    reader = DataFileReader()
    reader.set_data_file(str(file))
    assert reader.open() is True

    ok1, line1 = reader.read_one()
    ok2, line2 = reader.read_one()
    ok3, line3 = reader.read_one()

    assert ok1
    assert line1 == "1,TEMP-001,99,LOW"
    assert ok2
    assert line2 == "1,TEMP-002,99,LOW"
    assert not ok3
    assert line3 == ""

    reader.close()


def test_reader_str_no_file():
    reader = DataFileReader()
    reader.set_data_file(None)
    assert str(reader) == "DataFileReader (no file)"


def test_reader_str_empty_filename():
    reader = DataFileReader()
    reader.set_data_file("")
    assert str(reader) == "DataFileReader (no file)"


def test_reader_str_with_file():
    reader = DataFileReader()
    reader.set_data_file("filename.txt")
    assert str(reader) == "DataFileReader (filename.txt)"


def test_data_file_reader_type():
    assert DataFileReader.type() == DataReaderType.FILE
