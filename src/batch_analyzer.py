from rule import Rule, IndependentRule, LogicalCorrelationRule

from io import TextIOWrapper
from utils import TimestampData
from typing import cast

class BatchAnalyzer:
    _valid_output_file: TextIOWrapper
    _alarms_output_file: TextIOWrapper

    _rules: list[Rule] = []
    _indep_rules: list[int] = []
    _outcomes: list[bool] = []

    def analyze(self, td: TimestampData) -> bool:
        all_ok = True
        self._outcomes = [False] * len(self._rules)

        for rule_id in self._indep_rules:
            rule = cast(IndependentRule, self._rules[rule_id])
            self._outcomes[rule.id] = rule.is_violated(td.readings)
            if self._outcomes[rule.id]:
                all_ok = False
                self.write_alarms(rule, td)
        return all_ok

    def analyze_and_output(self, batch_data: list[TimestampData]):
        for td in batch_data:
            ok = self.analyze(td)

            if ok:
                self.write_valid_data(td)
    

    def load_rules(self, rules_filename: str):
        # TODO: error handling
        # TODO: Here populate the _rules list, which will be indexed using rule.id,
        #       then store the ids of IndependentRules in _indep_rules
        #       then build the graph of LogicCorrelationRules, it can be stored in a list since the number of nodes
        #       is fixed and known in advance. A node can be sth like
        class Node:
            num_pred: int        # number of nodes this rule depends on (0, 1 or 2)
            num_ready_pred: int  # number of nodes this rule depends on that have been evaluated at this timestamp
            # prev: list[int] # ids of the rules that this one depends on (len is 0, 1 or 2)
            # prev_ready: list[bool] # whether the prev rule has been evaluated at this timestamp
            id: int # this LogicCorrelationRule id
            next: list[int] # ids of rules depending on this one
        #       keep an initial list of the leaf nodes (i.e. len(prev) == 0 == num_pred)
        #       when evaluating a node, check all the next, atomically updating their num_ready_pred,
        #       if it reaches num_pred we can add the new node to the list of evaluable
        #       (keep two lists and ping back and forth).
        #       note that the prev rules ids can be retrieved using _rules[node.id].op1 and .op2

        pass

    def write_valid_data(self, td: TimestampData):
        print(f"VALID {td.ts}")
    def write_alarms(self, rule: Rule, td: TimestampData):
        print(f"ALARM {td.ts} {rule.id}")


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
    