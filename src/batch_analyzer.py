from src.rule import Rule, IndependentRule, LogicalCorrelationRule

from io import TextIOWrapper
from time import sleep
from src.utils import TimestampData
from typing import cast
from queue import Queue
import threading
import multiprocessing
from concurrent.futures import ProcessPoolExecutor

def priority_to_str(p: int) -> str:

    if p == 0:
        return "LOW"
    if p == 1:
        return "MEDIUM"
    return "HIGH"


class RuleNode:
    # number of nodes this rule depends on (0, 1 or 2)
    num_pred: int

    # number of nodes this rule depends on that have been evaluated at this timestamp
    num_ready_pred: int

    # this LogicCorrelationRule id
    id: int

    # indexes and priorities of RuleNodes depending on this one (nodes are stored in three linear arrays)
    next: list[tuple[int, int]]

    def __init__(self, _id: int):
        self.id = _id
        self.num_pred = 0
        self.num_ready_pred = 0
        self.next = []

# define these to functions to pass to the processes to run the rules' evaluation in parallel

def eval_independent_worker(
    rule_id: int, rule: IndependentRule, readings: list[float | None]
) -> tuple[int, bool, IndependentRule]:

    result = rule.is_violated(readings)
    return rule_id, result, rule  # return mutated rule to preserve state

def eval_corr_worker(
    leaf_idx: int, rule_id: int, rule: LogicalCorrelationRule, op1: bool, op2: bool
) ->tuple[int, int, bool]:

    result = rule.is_violated(op1, op2)
    return leaf_idx, rule_id, result


class BatchAnalyzer:
    _valid_output_file: TextIOWrapper
    _alarms_output_file: TextIOWrapper
    _sensor_id_to_name: list[str]
    # since rules have progressive ids, this can be indexed using rule.id
    _rules: list[Rule]

    # id of the rule type 1 2 and 3, equivalently those are their indexes in _rules, one list for each priority
    _indep_rules_id: list[list[int]]

    # outcome of rule i (both index and id) at the current timestamp
    _outcomes: list[bool]

    # graph nodes corresponding to correlation rules, one list for each priority
    _corr_rules_graph: list[list[RuleNode]]

    # indexes of graph nodes that do not depend on other correlation rules, one list for each priority
    _leaf_nodes_ind: list[list[int]]

    _writing_thread: threading.Thread

    _stop_writing_event: threading.Event

    # queue of valid data ready to be written by the writing loop
    _valid_data_ready: Queue[int]

    # counter for the timestamp number in the analysis
    _counter: int

    # queue of alamrs ready to be written by the writing loop
    _alarm_data_ready: Queue[tuple[int, int]]

    _executor: ProcessPoolExecutor

    # for testing moved into the object
    _all_ok: bool

    # how long the writing loop sleeps if both queues are empty and _stop_writing_event is not set
    ALARM_QUEUE_TIMEOUT = 0.0002

    def __init__(self, np: int = 1):
        # np -> number of processes to evaluate rules
        self._sensor_id_to_name = []
        self._rules = []
        self._outcomes = []
        self._indep_rules_id = [[], [], []]
        self._corr_rules_graph = [[], [], []]
        self._leaf_nodes_ind = [[], [], []]

        self._stop_writing_event = threading.Event()
        self._valid_data_ready = Queue()
        self._alarm_data_ready = Queue()
        self._counter = 0
        self._all_ok = True
        # start the pool of processes here, less overhead
        ctx = multiprocessing.get_context('spawn')
        self._executor = ProcessPoolExecutor(max_workers=np, mp_context=ctx)

    def analyze(self, td: TimestampData) -> bool:
        self._all_ok = True
        self._outcomes = [False] * len(self._rules)
        ready_pred = {}
    
        # reset local pred counts
        for priority in range(3):
            for node in self._corr_rules_graph[priority]:
                ready_pred[node.id] = 0

        for priority in range(2, -1, -1):
            # this submits the rule evaluation to the processes
            # inside the array, there are the results of the evaluation (what the eval_independent_worker returns)
            futures = [
                self._executor.submit(
                    eval_independent_worker,
                    rule_id,
                    cast(IndependentRule, self._rules[rule_id]),
                    td.readings,
                )
                for rule_id in self._indep_rules_id[priority]
            ]
            for f in futures:
                # for each evaluation, retrieve results
                rule_id, result, updated_rule = f.result()
                # since the processes get their own copy of everything, rules need to be update in case they change state
                self._rules[rule_id] = updated_rule
                self._outcomes[rule_id] = result
                if result:
                    self._all_ok = False
                    # put the alarms to the alarm queue for the writing loop
                    self._alarm_data_ready.put((rule_id, self._counter))

        local_leafs: list[list[int]] = [p.copy() for p in self._leaf_nodes_ind]
        local_leafs_next: list[list[int]] = [[], [], []]
        for priority in range(2, -1, -1):
            while local_leafs[priority]:
                futures_logical = []
                for leaf_idx in local_leafs[priority]:
                    node = self._corr_rules_graph[priority][leaf_idx]
                    log_rule = cast(LogicalCorrelationRule, self._rules[node.id])
                    futures_logical.append(self._executor.submit(
                        eval_corr_worker,
                        leaf_idx,
                        node.id,
                        log_rule,
                        self._outcomes[log_rule.op1],
                        self._outcomes[log_rule.op2]
                    ))

                # since the processes apparently cannot change state of the object, post-process everything on the main thread
                for f_l in futures_logical:
                    leaf_idx, rule_id, result = f_l.result()
                    self._outcomes[rule_id] = result
                    if result:
                        self._all_ok = False
                        self._alarm_data_ready.put((rule_id, self._counter))
                    node = self._corr_rules_graph[priority][leaf_idx]
                    for succesor in node.next:
                        next_node = self._corr_rules_graph[succesor[1]][succesor[0]]
                        ready_pred[next_node.id] += 1
                        if ready_pred[next_node.id] == next_node.num_pred:
                            local_leafs_next[succesor[1]].append(succesor[0])

                local_leafs[priority] = local_leafs_next[priority]
                local_leafs_next[priority] = []
                # keep the leafs of the lower priorities which were untouched
                for jj in range(priority):
                    local_leafs[jj] += local_leafs_next[jj]
                    local_leafs_next[jj] = []

        return self._all_ok

    def analyze_and_output(self, batch_data: list[TimestampData]):
        # set counter, because the writing loop needs to know the index of the timestamp it's supposed to write
        self._counter = 0
        # unset the event from previous runs
        self._stop_writing_event.clear()
        # start the writing loop
        self._writing_thread = threading.Thread(target=self.writing_loop, args=(batch_data,))
        self._writing_thread.start()
        for td in batch_data:
            ok = self.analyze(td)
            if ok:
                self._valid_data_ready.put(self._counter)
            self._counter += 1
        self._stop_writing_event.set()
        self._writing_thread.join()

    def writing_loop(self, data: list[TimestampData]):
        # input data->TimeStamps
        # checks if both queues are empty, only then checks the event
        # with two queues, this solution seems better than the one with try...except blocks
        while True:
            if not self._valid_data_ready.empty():
                index = self._valid_data_ready.get()
                self.write_valid_data(data[index])
            elif not self._alarm_data_ready.empty():
                rule, index = self._alarm_data_ready.get()
                self.write_alarms(self._rules[rule], data[index])
            else:
                if self._stop_writing_event.is_set():
                    break
                sleep(self.ALARM_QUEUE_TIMEOUT)

    def load_rules(self, rules: list[Rule]) -> bool:
        self._rules = rules
        mapping: dict[int, tuple[int, int]] = {}

        for r in self._rules:
            if isinstance(r, IndependentRule):
                self._indep_rules_id[r.priority].append(r.id)
            else:
                node = RuleNode(r.id)
                self._corr_rules_graph[r.priority].append(node)
                mapping[r.id] = (len(self._corr_rules_graph[r.priority]) - 1, r.priority)

        for priority in range(3):
            for i in range(len(self._corr_rules_graph[priority])):
                n = self._corr_rules_graph[priority][i]
                rule = cast(LogicalCorrelationRule, self._rules[n.id])
                for op in [rule.op1, rule.op2]:
                    if isinstance(self._rules[op], LogicalCorrelationRule):
                        if self._rules[op].priority < rule.priority:
                            raise RuntimeError(f"Correlation rule {n.id} depends on a higher priority rule")
                        n.num_pred += 1
                        ind = mapping[op]
                        self._corr_rules_graph[ind[1]][ind[0]].next.append((i, rule.priority))
                # initial leaf nodes, to be used at the start of a new timestamp analysis
                if n.num_pred == 0:
                    self._leaf_nodes_ind[rule.priority].append(i)

        # TODO: add validation of rules, i.e. well formed dependency graph (acyclic)
        return True

    def write_valid_data(self, td: TimestampData):
        # this function now performs a single atomic write
        # this is better for the IO parallelization
        # first assemble the whole string, then write
        if self._valid_output_file is None or self._valid_output_file.closed:
            print("WARNING BatchAnalyzer: did not provide an output file for valid readings, use set_valid_output_file")
            return
        readings = "|".join(
            f"{self._sensor_id_to_name[i]}:{td.readings[i]}"
            for i in range(len(td.readings))
        )
        self._valid_output_file.write(f"{td.ts};NOMINAL;{readings}\n")

    def write_alarms(self, rule: Rule, td: TimestampData):
        # same in this function as above
        if self._alarms_output_file is None or self._alarms_output_file.closed:
            print("WARNING BatchAnalyzer: did not provide an output file for alarm readings, use set_alarms_output_file")
            return
        towrite = f"{td.ts};{rule.name};{priority_to_str(rule.priority)};"
        if isinstance(rule, IndependentRule):
            towrite += f"{self._sensor_id_to_name[rule.sensor_id]};{td.readings[rule.sensor_id]}"
        elif isinstance(rule, LogicalCorrelationRule):
            to_print: Queue[Rule] = Queue()
            to_print.put(self._rules[rule.op1])
            to_print.put(self._rules[rule.op2])
            sensor_names: list[str] = []
            sensor_values: list[float | None] = []
            while not to_print.empty():
                r = to_print.get()
                if isinstance(r, IndependentRule):
                    sensor_names.append(self._sensor_id_to_name[r.sensor_id])
                    sensor_values.append(td.readings[r.sensor_id])
                elif isinstance(r, LogicalCorrelationRule):
                    to_print.put(self._rules[r.op1])
                    to_print.put(self._rules[r.op2])
            if sensor_names:
                towrite += ",".join(sensor_names) + ";"
                towrite += ",".join(map(str, sensor_values))
        towrite += "\n"
        self._alarms_output_file.write(towrite)

    def set_valid_output_file(self, filename: str):
        try:
            self._valid_output_file = open(filename, "w")
        except OSError as e:
            raise RuntimeError(f"Failed to open valid data output file '{filename}': {e}") from e

    def set_alarms_output_file(self, filename: str):
        try:
            self._alarms_output_file = open(filename, "w")
        except OSError as e:
            raise RuntimeError(f"Failed to open alarms output file '{filename}': {e}") from e

    def set_sensors(self, sensor_id_to_name: list[str]):
        self._sensor_id_to_name = sensor_id_to_name

    def deinit(self):
        if self._alarms_output_file and not self._alarms_output_file.closed:
            self._alarms_output_file.close()
        if self._valid_output_file and not self._valid_output_file.closed:
            self._valid_output_file.close()
        self._executor.shutdown(wait=True)
