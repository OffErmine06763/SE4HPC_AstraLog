from abc import ABC, abstractmethod
from enum import Enum


class Operator(Enum):
    LESS = 0
    GREATER = 1

class Logic(Enum):
    AND = 0
    OR = 1


# Base rule class, used to store common fields
# NOTE: rules define the violation of the conditions that determine the nominal state of the system,
#       i.e. when the rule condition evaluates to True an alarm should be raised.
#       notice the problem of calling them "violated", since we are actually checking if they are satisfied,
#       but alas i'm sticking to the words used in the assignment
class Rule(ABC):
    INVALID_ID = -1
    _next_id = 0

    priority: int = 0
    id: int
    name: str

    def __init__(self, priority: int, name: str) -> None:
        self.priority = priority
        self.name = name
        self.id = Rule._next_id
        Rule._next_id += 1


# This is the parent class for Simple, Stateful and Step rules
# that have to define the abstract method is_violated(readings_list)
# since they can just access whatever reading they need
class IndependentRule(Rule):
    operator: Operator
    sensor_id: int

    @abstractmethod
    def is_violated(self, readings: list[float | None]) -> bool:
        pass

    def __init__(self, priority: int, name: str, sensor_id: int, operator: Operator) -> None:
        super().__init__(priority, name)
        self.operator = operator
        self.sensor_id = sensor_id


class SimpleRule(IndependentRule):
    last_violated = False
    threshold: float


    def is_violated(self, readings: list[float | None]) -> bool:
        reading = readings[self.sensor_id]
        if reading is None:
            # assume the value remained the same
            return self.last_violated
        
        if self.operator == Operator.LESS:
            self.last_violated = reading < self.threshold
        else:
            self.last_violated = reading > self.threshold
            
        return self.last_violated
    
    def __init__(self, priority: int, name: str, sensor_id: int, threshold: float, operator: Operator):
        super().__init__(priority, name, sensor_id, operator)
        self.threshold = threshold



class StepDifferenceRule(IndependentRule):
    step: float
    operator: Operator
    sensor_id: int
    last_reading: float
    ready: bool = False


    def is_violated(self, readings: list[float | None]) -> bool:
        reading = readings[self.sensor_id]
        if reading is None:
            if not self.ready:
                # we dont have a previous reading to compare against
                return False
            
            # assume the value remained the same, so a delta of 0, which might violate the rule
            if self.operator == Operator.LESS:
                return 0 < self.step
            else:
                return 0 > self.step
        else:
            if not self.ready:
                self.last_reading = reading
                self.ready = True
                return False

            delta = reading - self.last_reading
            self.last_reading = reading
            if self.operator == Operator.LESS:
                return delta < self.step
            else:
                return  delta > self.step
    
    def __init__(self, priority: int, name: str, sensor_id: int, step: float, operator: Operator):
        super().__init__(priority, name, sensor_id, operator)
        self.step = step



class StatefulRule(IndependentRule):
    consecutive_violations = 0
    threshold: float
    max_violations: int
    sensor_id: int
    operator: Operator


    def is_violated(self, readings: list[float | None]) -> bool:
        reading = readings[self.sensor_id]
        if reading is None:
            # assume the value remained the same
            if self.consecutive_violations > 0: # this is equivalent to last_violated
                self.consecutive_violations += 1
        else:
            violated = False
            if self.operator == Operator.LESS:
                violated = reading < self.threshold
            else:
                violated = reading > self.threshold
            
            if violated: self.consecutive_violations += 1
            else:        self.consecutive_violations = 0
            
        return self.consecutive_violations >= self.threshold
    
    def __init__(self, priority: int, name: str, sensor_id: int, threshold: float, max_violations: int, operator: Operator):
        super().__init__(priority, name, sensor_id, operator)
        self.threshold = threshold
        self.max_violations = max_violations



# Logical rules will have sth like is_violated(operand_1_outcome, operand_2_outcome)
# which will be called based on the dependency graph
class LogicalCorrelationRule(Rule):
    logic: Logic
    op1: int
    op2: int

    def is_violated(self, operand_1_result: bool, operand_2_result) -> bool:
        if self.logic == Logic.AND:
            return operand_1_result and operand_2_result
        return operand_1_result or operand_2_result
    
    # logic operator and the two operands, the ids of the rules it depend on
    def __init__(self, priority: int, name: str, logic: Logic, op1: int, op2: int):
        super().__init__(priority, name)
        self.logic = logic
        self.op1 = op1
        self.op2 = op2
