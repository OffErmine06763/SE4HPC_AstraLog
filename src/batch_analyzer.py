from rule import Rule

from io import TextIOWrapper
from utils import TimestampData


class BatchAnalyzer:
    _valid_output_file: TextIOWrapper
    _alarms_output_file: TextIOWrapper

    _rules: list[Rule] = []

    def analyze(self, td: TimestampData) -> bool:
        all_ok = True
        for rule in self._rules:
            if rule.is_violated(td.readings):
                all_ok = False
                self.write_alarms(rule, td)
        return all_ok

    def analyze_and_output(self, batch_data: list[TimestampData]):
        for td in batch_data:
            ok = self.analyze(td)

            if ok:
                self.write_valid_data(td)
    
    def write_valid_data(self, td: TimestampData):
        print(f"VALID {td.ts}")
    def write_alarms(self, rule: Rule, td: TimestampData):
        print(f"ALARM {td.ts}")


    def set_valid_output_file(self, filename: str):
        self._valid_output_file = open(filename, "w")
        # TODO: handle errors
    def set_alarms_output_file(self, filename: str):
        self._alarms_output_file = open(filename, "w")
        # TODO: handle errors


    def deinit(self):
        if not self._alarms_output_file.closed:
            self._alarms_output_file.close()
        if not self._valid_output_file.closed:
            self._valid_output_file.close()
    