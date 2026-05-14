from abc import ABC, abstractmethod
from enum import Enum


class Operator(Enum):
    LESS = 0
    GREATER = 1

class Logic(Enum):
    AND = 0
    OR = 1

class Rule(ABC):
    INVALID_ID = 0
    _next_id = 1

    priority: int = 0
    id: int
    name: str

    # return True if rule is violated
    @abstractmethod
    def is_violated(self, readings: list[float | None]) -> bool:
        pass

    def __init__(self, priority: int, name: str) -> None:
        self.priority = priority
        self.name = name
        self.id = Rule._next_id
        Rule._next_id += 1

class SimpleRule(Rule):
    last_violated = False
    threshold: float
    operator: Operator

    def is_violated(self, readings: list[float | None]) -> bool:
        return False
    
    def __init__(self, priority: int, name: str, threshold: float, operator: Operator):
        super().__init__(priority, name)
        self.threshold = threshold
        self.operator = operator

class StepDifferenceRule(Rule):
    last_violated = False
    step: float
    operator: Operator
    
    def is_violated(self, readings: list[float | None]) -> bool:
        return False
    
    def __init__(self, priority: int, name: str, step: float, operator: Operator):
        super().__init__(priority, name)
        self.step = step
        self.operator = operator

class StatefulRule(Rule):
    consecutive_violations = 0
    threshold: float
    max_violations: int
    
    def is_violated(self, readings: list[float | None]) -> bool:
        return False
    
    def __init__(self, priority: int, name: str, threshold: float, max_violations: int):
        super().__init__(priority, name)
        self.threshold = threshold
        self.max_violations = max_violations

class LogicalCorrelationRule(Rule):
    logic: Logic
    op1: int
    op2: int

    def is_violated(self, readings: list[float]) -> bool:
        return False
    
    # logic operator and the two operands, the ids of the rules it depend on
    def __init__(self, priority: int, name: str, logic: Logic, op1: int, op2: int):
        super().__init__(priority, name)
        self.logic = logic
        self.op1 = op1
        self.op2 = op2
