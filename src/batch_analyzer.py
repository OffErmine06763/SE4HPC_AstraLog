from src.rule import Rule, IndependentRule, LogicalCorrelationRule

from io import TextIOWrapper
from src.utils import TimestampData
from typing import cast
from queue import Queue, Empty
from time import sleep
import threading
from concurrent.futures import ThreadPoolExecutor, wait

def priority_to_str(p: int) -> str:
    if p == 0:
        return "LOW"
    if p == 1:
        return "MEDIUM"
    return "HIGH"

class RuleNode:
    num_pred: int         # number of nodes this rule depends on (0, 1 or 2)
    num_ready_pred: int   # number of nodes this rule depends on that have been evaluated at this timestamp
    id: int               # this LogicCorrelationRule id
    next: list[tuple[int, int]]       # indexes and priorities of RuleNodes depending on this one (nodes are stored in three linear arrays)

    def __init__(self, _id: int):
        self.id = _id
        self.num_pred = 0
        self.num_ready_pred = 0
        self.next = []


class BatchAnalyzer:
    _valid_output_file: TextIOWrapper
    _alarms_output_file: TextIOWrapper

    _sensor_id_to_name: list[str]

    _rules: list[Rule]                 # since rules have progressive ids, this can be indexed using rule.id
    _indep_rules_id: list[list[int]]         # id of the rule type 1 2 and 3, equivalently those are their indexes in _rules, one list for each priority
    _outcomes: list[bool]              # outcome of rule i (both index and id) at the current timestamp
    _corr_rules_graph: list[list[RuleNode]]  # graph nodes corresponding to correlation rules, one list for each priority
    _leaf_nodes_ind: list[list[int]]         # indexes of graph nodes that do not depend on other correlation rules, one list for each priority
    
    _writing_thread: threading.Thread
    _stop_writing_event: threading.Event
    _valid_data_ready: Queue[int]
    _executor: ThreadPoolExecutor

    ALARM_QUEUE_TIMEOUT = 0.002
    
    def __init__(self, np = 1):
        self._sensor_id_to_name = []
        self._rules = []
        self._indep_rules_id = [[], [], []]
        self._outcomes = []
        self._corr_rules_graph = [[], [], []]
        self._leaf_nodes_ind = [[], [], []]
        
        self._stop_writing_event = threading.Event()
        self._alarms_ready = Queue()
        self._valid_data_ready = Queue()

        #managment of pool of np reusable threads
        self._executor = ThreadPoolExecutor(max_workers=np)

    def analyze(self, td: TimestampData) -> bool:
        all_ok = True
        outcomes = [False] * len(self._rules)
        ready_pred = {}
        lock = threading.Lock()
    
        # reset local pred counts
        for priority in range(3):
            for node in self._corr_rules_graph[priority]:
                ready_pred[node.id] = 0
        
        #define functions to submit to the threads
        def eval_independent(rule_id):
            nonlocal all_ok
            rule = cast(IndependentRule, self._rules[rule_id])
            result = rule.is_violated(td.readings)
            with lock:
                outcomes[rule.id] = result
                if result:
                    all_ok = False
                    self.write_alarms(rule, td)
    
        def eval_corr(leaf_idx, priority):
            #declare it non-local so that this function can change its state
            nonlocal all_ok
            node = self._corr_rules_graph[priority][leaf_idx]
            log_rule = cast(LogicalCorrelationRule, self._rules[node.id])
            op1 = outcomes[log_rule.op1]
            op2 = outcomes[log_rule.op2]
            result = log_rule.is_violated(op1, op2)
            outcomes[log_rule.id] = result
            if result:
                all_ok = False
                self.write_alarms(log_rule, td)
            next_ready = []
            for successor in node.next:
                s_idx, s_priority = successor
                next_node = self._corr_rules_graph[s_priority][s_idx]
                ready_pred[next_node.id] += 1
                if ready_pred[next_node.id] == next_node.num_pred:
                    next_ready.append((s_idx, s_priority))
            return next_ready
    
        # parallel independent rules per priority
        for priority in range(2, -1, -1):
            futures = [
                self._executor.submit(eval_independent, rule_id)
                for rule_id in self._indep_rules_id[priority]
            ]
            #barrier to wait for independant rules of this priority to finish
            wait(futures)
    
        # parallel correlation rules layer by layer
        local_leafs: list[list[int]] = [p.copy() for p in self._leaf_nodes_ind]
        local_leafs_next: list[list[int]] = [[], [], []]
    
        for priority in range(2, -1, -1):
            while local_leafs[priority]:
                #evaluate current priorities in the current layer, return following nodes
                futures = [
                    self._executor.submit(eval_corr, leaf_idx, priority)
                    for leaf_idx in local_leafs[priority]
                ]
                #synchronise
                wait(futures)
                #assigne the leafs for the next iteration
                for f in futures:
                    for s_idx, s_priority in f.result():
                        local_leafs_next[s_priority].append(s_idx)
                #swap buffers
                local_leafs[priority] = local_leafs_next[priority]
                local_leafs_next[priority] = []
                #keep leafs of the lower priorities
                for jj in range(priority):
                    local_leafs[jj] += local_leafs_next[jj]
                    local_leafs_next[jj] = []
    
        return all_ok
    
    def analyze_and_output(self, batch_data: list[TimestampData]):
        """
        * One threads starts, which loops and when ready, writes valid data (overlap with analysis)
        * Inside the analysis, np threads is spawned 
        * Each of this thread evaluates either one independant rule of given priority or one layer of correlated rules
        * The actual overlap happens when the alarms have to be written (thanks to GIL)
        """
        self._stop_writing_event.clear()
        self._writing_thread = threading.Thread(target = self.writing_loop, args = (batch_data, ))
        self._writing_thread.start()
        #loop over timestamps and its indeces so that we can pass them to the writes which already have batch_data
        for i, td in enumerate(batch_data):
            ok = self.analyze(td)
            if ok:
                self._valid_data_ready.put(i)
        self._stop_writing_event.set()
        self._writing_thread.join()


    def writing_loop(self, data):
        while True:
            try:
                index = self._valid_data_ready.get(timeout=self.ALARM_QUEUE_TIMEOUT)
                self.write_valid_data(data[index])
            except Empty:
                if self._stop_writing_event.is_set():
                    break
                else:
                    continue
    

    def load_rules(self, rules: list[Rule]) -> bool:
        self._rules = rules

        mapping: dict[int, tuple[int, int]] = {}  # mapping from rule id (and priorities) to _corr_rules_graph index

        for r in self._rules:
            if isinstance(r, IndependentRule):
                self._indep_rules_id[r.priority].append(r.id)
            else:
                node = RuleNode(r.id)
                self._corr_rules_graph[r.priority].append(node)
                mapping[r.id] = (len(self._corr_rules_graph[r.priority]) - 1, r.priority)

        # build the graph: i.e. set the number of predecessor nodes and the node indices of the successor nodes
        for priority in range(0, 3):
            for i in range(len(self._corr_rules_graph[priority])):
                n = self._corr_rules_graph[priority][i]
                rule = cast(LogicalCorrelationRule, self._rules[n.id])

                if isinstance(self._rules[rule.op1], LogicalCorrelationRule):
                    #each correlated rule can only depend on a rule of lower priority
                    if self._rules[rule.op1].priority < rule.priority:
                        raise RuntimeError("Correlation rule with id " + str(n.id) + " depends on a correlation rule with higher priority")
                    n.num_pred += 1
                    ind = mapping[rule.op1]
                    self._corr_rules_graph[ind[1]][ind[0]].next.append((i, rule.priority))
                if isinstance(self._rules[rule.op2], LogicalCorrelationRule):
                    if self._rules[rule.op2].priority < rule.priority:
                        raise RuntimeError("Correlation rule with id " + str(n.id) + " depends on a correlation rule with higher priority")
                    n.num_pred += 1
                    ind = mapping[rule.op2]
                    self._corr_rules_graph[ind[1]][ind[0]].next.append((i, rule.priority))

                # initial leaf nodes, to be used at the start of a new timestamp analysis
                if n.num_pred == 0:
                    self._leaf_nodes_ind[rule.priority].append(i)

        # TODO: add validation of rules, i.e. well formed dependency graph (acyclic)
        return True

    def write_valid_data(self, td: TimestampData):
        if self._valid_output_file.closed:
            print(
                "WARNING BatchAnalyzer: did not provide an output file for valid readings, use set_valid_output_file"
            )
            return

        self._valid_output_file.write(f"{td.ts};NOMINAL;")
        for i in range(len(td.readings) - 1):
            data = td.readings[i]
            self._valid_output_file.write(f"{self._sensor_id_to_name[i]}:{data}|")
        end = len(td.readings) - 1
        self._valid_output_file.write(
            f"{self._sensor_id_to_name[end]}:{td.readings[end]}"
        )
        self._valid_output_file.write("\n")

    def write_alarms(self, rule: Rule, td: TimestampData):
        if self._alarms_output_file.closed:
            print(
                "WARNING BatchAnalyzer: did not provide an output file for valid readings, use set_valid_output_file"
            )
            return

        self._alarms_output_file.write(
            f"{td.ts};{rule.name};{priority_to_str(rule.priority)};"
        )
        if isinstance(rule, IndependentRule):
            self._alarms_output_file.write(
                f"{self._sensor_id_to_name[rule.sensor_id]};{td.readings[rule.sensor_id]}"
            )
        elif isinstance(rule, LogicalCorrelationRule):
            to_print: Queue[Rule] = Queue()
            to_print.put(self._rules[rule.op1])
            to_print.put(self._rules[rule.op2])

            sensor_names_to_print: list[str | None] = []
            sensor_values_to_print: list[float | None] = []

            while not to_print.empty():
                r = to_print.get()
                if isinstance(r, IndependentRule):
                    sensor_names_to_print.append(self._sensor_id_to_name[r.sensor_id])
                    sensor_values_to_print.append(td.readings[r.sensor_id])
                elif isinstance(r, LogicalCorrelationRule):
                    to_print.put(self._rules[r.op1])
                    to_print.put(self._rules[r.op2])

            for name in sensor_names_to_print[:-1]:
                self._alarms_output_file.write(f"{name},")
            self._alarms_output_file.write(f"{sensor_names_to_print[-1]};")

            for value in sensor_values_to_print[:-1]:
                self._alarms_output_file.write(f"{value},")
            self._alarms_output_file.write(f"{sensor_values_to_print[-1]}")

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
        #shut down the executor before leaving
        self._executor.shutdown(wait=True)
