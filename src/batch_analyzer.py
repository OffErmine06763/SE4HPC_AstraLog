from src.rule import Rule, IndependentRule, LogicalCorrelationRule

from io import TextIOWrapper
from src.utils import TimestampData
from typing import cast
from queue import Queue


def priority_to_str(p: int) -> str:
    if p == 0:
        return "LOW"
    if p == 0:
        return "MEDIUM"
    return "HIGH"


class RuleNode:
    num_pred: int = 0        # number of nodes this rule depends on (0, 1 or 2)
    num_ready_pred: int = 0  # number of nodes this rule depends on that have been evaluated at this timestamp
    id: int                  # this LogicCorrelationRule id
    next: list[int] = []     # indexes of RuleNodes depending on this one (nodes are stored in a linear array)


class BatchAnalyzer:
    _valid_output_file: TextIOWrapper
    _alarms_output_file: TextIOWrapper

    _sensor_id_to_name: list[str] = []

    _rules           : list[Rule]     = []  # since rules have progressive ids, this can be indexed using rule.id
    _indep_rules_id  : list[int]      = []  # id of the rule type 1 2 and 3, equivalently those are their indexes in _rules
    _outcomes        : list[bool]     = []  # outcome of rule i (both index and id) at the current timestamp
    _corr_rules_graph: list[RuleNode] = []  # graph nodes corresponding to correlation rules
    _leaf_nodes_ind  : list[int]      = []  # indexes of graph nodes that do not depend on other correlation rules


    def analyze(self, td: TimestampData) -> bool:
        all_ok = True
        self._outcomes = [False] * len(self._rules)
        for node in self._corr_rules_graph:
            node.num_ready_pred = 0

        # first evaluate all rules that do not depend on anything else
        for rule_id in self._indep_rules_id:
            rule = cast(IndependentRule, self._rules[rule_id])
            self._outcomes[rule.id] = rule.is_violated(td.readings)
            if self._outcomes[rule.id]:
                all_ok = False
                self.write_alarms(rule, td)

        # keep a local copy of the current leaves, and a second list for the next iteration
        local_leafs: list[int] = self._leaf_nodes_ind.copy()
        local_leafs_next: list[int] = []
        # if the graph is well constructed, when there are no leaves we have evaluated all the rules
        while len(local_leafs) != 0:
            for i in local_leafs:
                node = self._corr_rules_graph[i]
                rule = cast(LogicalCorrelationRule, self._rules[node.id])
                
                self._outcomes[rule.id] = rule.is_violated(self._outcomes[rule.op1], self._outcomes[rule.op2])
                if self._outcomes[rule.id]:
                    all_ok = False
                    self.write_alarms(rule, td)

                # check if the nodes that depend on this rule are ready to be evaluated
                # note that the increment and compare of the counter should be done atomically when parallelizing
                for next in node.next:
                    next_node = self._corr_rules_graph[next]
                    next_node.num_ready_pred += 1
                    if next_node.num_ready_pred == next_node.num_pred:
                        local_leafs_next.append(next)

            # swap the buffers
            local_leafs = local_leafs_next
            local_leafs_next = []
        
        return all_ok


    def analyze_and_output(self, batch_data: list[TimestampData]):
        for td in batch_data:
            ok = self.analyze(td)
            if ok:
                self.write_valid_data(td)
    

    def load_rules(self, rules_filename: str, rules: list[Rule]) -> bool:
        self._rules = rules

        mapping: dict[int, int] = {} # mapping from rule id to _corr_rules_graph index

        for r in self._rules:
            if isinstance(r, IndependentRule):
                self._indep_rules_id.append(r.id)
            else:
                node = RuleNode()
                node.id = r.id
                self._corr_rules_graph.append(node)
                mapping[r.id] = len(self._corr_rules_graph) - 1

        # build the graph: i.e. set the number of predecessor nodes and the node indices of the successor nodes
        for i in range(len(self._corr_rules_graph)):
            n = self._corr_rules_graph[i]
            rule = cast(LogicalCorrelationRule, self._rules[n.id])
            
            if isinstance(self._rules[rule.op1], LogicalCorrelationRule):
                n.num_pred += 1
                self._corr_rules_graph[mapping[rule.op1]].next.append(i)
            if isinstance(self._rules[rule.op2], LogicalCorrelationRule):
                n.num_pred += 1
                self._corr_rules_graph[mapping[rule.op2]].next.append(i)

            # initial leaf nodes, to be used at the start of a new timestamp analysis
            if n.num_pred == 0:
                self._leaf_nodes_ind.append(i)
            

        # TODO: add validation of rules, i.e. well formed dependency graph (acyclic)
        return True

    def write_valid_data(self, td: TimestampData):
        if self._valid_output_file.closed:
            print("WARNING BatchAnalyzer: did not provide an output file for valid readings, use set_valid_output_file")
            return
        
        self._valid_output_file.write(f"{td.ts};NOMINAL;")
        for i in range(len(td.readings) - 1):
            data = td.readings[i]
            self._valid_output_file.write(f"{self._sensor_id_to_name[i]}:{data}|")
        end = len(td.readings) - 1
        self._valid_output_file.write(f"{self._sensor_id_to_name[end]}:{td.readings[end]}")
        self._valid_output_file.write("\n")
        
    def write_alarms(self, rule: Rule, td: TimestampData):
        if self._alarms_output_file.closed:
            print("WARNING BatchAnalyzer: did not provide an output file for valid readings, use set_valid_output_file")
            return
        
        self._alarms_output_file.write(f"{td.ts};{rule.name};{priority_to_str(rule.priority)};")
        if isinstance(rule, IndependentRule):
            self._alarms_output_file.write(f"{self._sensor_id_to_name[rule.sensor_id]};{td.readings[rule.sensor_id]}")
        elif isinstance(rule, LogicalCorrelationRule):
            to_print: Queue[Rule] = Queue()
            to_print.put(self._rules[rule.op1])
            to_print.put(self._rules[rule.op2])

            while not to_print.empty():
                r = to_print.get()
                if isinstance(r, IndependentRule):
                    self._alarms_output_file.write(f"{self._sensor_id_to_name[r.sensor_id]};{td.readings[r.sensor_id]}")
                elif isinstance(r, LogicalCorrelationRule):
                    to_print.put(self._rules[r.op1])
                    to_print.put(self._rules[r.op2])
        
        self._alarms_output_file.write("\n")
            


    def set_valid_output_file(self, filename: str):
        self._valid_output_file = open(filename, "w")
        # TODO: handle errors
    def set_alarms_output_file(self, filename: str):
        self._alarms_output_file = open(filename, "w")
        # TODO: handle errors
    def set_sensors(self, sensor_id_to_name: list[str]):
        self._sensor_id_to_name = sensor_id_to_name


    def deinit(self):
        if not self._alarms_output_file.closed:
            self._alarms_output_file.close()
        if not self._valid_output_file.closed:
            self._valid_output_file.close()
    