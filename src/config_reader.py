from rule import Rule, StatefulRule, StepDifferenceRule, IndependentRule, LogicalCorrelationRule, SimpleRule, Logic, Operator

import yaml
import json

def str_to_priority(s: str) -> int:
    if s == "LOW":
        return 0
    if s == "MEDIUM":
        return 1
    return 2
def str_to_operator(s: str) -> Operator:
    if s == "<":
        return Operator.LESS
    return Operator.GREATER
def str_to_logic(s: str) -> Logic:
    if s == "AND":
        return Logic.AND
    return Logic.OR

def parse_rules_config(rules_filename: str, sensor_ids: dict[str, int]) -> tuple[bool, list[Rule]]:
    try:
        with open(rules_filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            rules: list[Rule] = []
            mapping: dict[str, int] = {} # from rule.name to rule.id

            for rule_json in data:
                # TODO: add checks for existence of fields and correct datatype
                priority = str_to_priority(rule_json["priority"])
                name = rule_json["rule_id"]

                rule: Rule
                if rule_json["type"] == "simple":
                    rule = SimpleRule(
                            priority, name, sensor_ids[rule_json["sensor_id"]],
                            rule_json["value"], str_to_operator(rule_json["operator"])
                        )
                elif rule_json["type"] == "step_difference":
                    rule = StepDifferenceRule(
                            priority, name, sensor_ids[rule_json["sensor_id"]],
                            rule_json["value"], str_to_operator(rule_json["operator"])
                        )
                elif rule_json["type"] == "stateful":
                    rule = StatefulRule(
                            priority, name, sensor_ids[rule_json["sensor_id"]],
                            rule_json["value"], rule_json["consecutive_measurements"], str_to_operator(rule_json["operator"])
                        )
                else:
                    # TODO: check that rule_json["conditions"] are present in the mapping, if not return False
                    rule = LogicalCorrelationRule(
                            priority, name,
                            str_to_logic(rule_json["logic"]), mapping[rule_json["conditions"][0]], mapping[rule_json["conditions"][1]]
                        )

                mapping[rule.name] = rule.id
                rules.append(rule)
        
            return True, rules
    
    except FileNotFoundError:
        print(f"ERROR ConfigReader: rules file '{rules_filename}' not found")
        return False, []
    except PermissionError:
        print(f"ERROR ConfigReader: no permission to read rules file '{rules_filename}'")
        return False, []
    except json.JSONDecodeError as e:
        print(f"ERROR ConfigReader: invalid JSON in rules file '{rules_filename}':", e, sep="\n")
        return False, []
    except Exception as e:
        print(f"ERROR ConfigReader: unexpected error reading rules file '{rules_filename}':", e, sep="\n")
        return False, []


def parse_sensors_config(sensors_filename: str, out_sensor_ids: dict[str, int]) -> tuple[int, float]:
    try:
        with open(sensors_filename, "r") as f:
            sensors_yaml = yaml.safe_load(f)

            counter = 0
            for sensor in sensors_yaml["sensors"]:
                out_sensor_ids[sensor["id"]] = counter
                counter += 1
            rate_str: str = sensors_yaml["sensors"][0]["sampling_rate"]
            freq = float(rate_str[:-2]) # Hz

            return counter, freq

    except FileNotFoundError:
        print(f"ERROR ConfigReader: sensor file '{sensors_filename}' not found")
        return -1, 0
    except PermissionError:
        print(f"ERROR ConfigReader: no permission to read sensor file '{sensors_filename}'")
        return -1, 0
    except yaml.YAMLError as e:
        print(f"ERROR ConfigReader: invalid YAML in sensor file '{sensors_filename}':", e, sep="\n")
        return -1, 0
    except Exception as e:
        print(f"ERROR ConfigReader: unexpected error reading sensor file '{sensors_filename}':", e, sep="\n")
        return -1, 0