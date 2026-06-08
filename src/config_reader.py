from src.rule import Rule, StatefulRule, StepDifferenceRule, LogicalCorrelationRule, SimpleRule, Logic, Operator

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


def parse_simple_step_diff_rule(
    rule_json, sensor_ids: dict[str, int]
) -> Rule | None:
    priority = str_to_priority(rule_json["priority"])
    name = rule_json["rule_id"]

    for field in ["sensor_id", "value", "operator"]:
        if field not in rule_json:
            print(f"parse_rules_config: missing field '{field}' in {rule_json['type']} rule '{name}'")
            return None
        if field == "value" and not isinstance(rule_json[field], (int, float)):
            print(f"parse_rules_config: field '{field}' in {rule_json['type']} rule '{name}' must be a number")
            return None
    if rule_json["type"] == "simple":
        return SimpleRule(
            priority,
            name,
            sensor_ids[rule_json["sensor_id"]],
            rule_json["value"],
            str_to_operator(rule_json["operator"]),
        )
    else:
        return StepDifferenceRule(
                priority,
                name,
                sensor_ids[rule_json["sensor_id"]],
                rule_json["value"],
                str_to_operator(rule_json["operator"]),
            )


def parse_stateful_rule(
    rule_json, sensor_ids: dict[str, int]
) -> Rule | None:
    priority = str_to_priority(rule_json["priority"])
    name = rule_json["rule_id"]
    for field in ["sensor_id", "value", "consecutive_measurements", "operator"]:
        if field not in rule_json:
            print(f"parse_rules_config: missing field '{field}' in stateful rule '{name}'")
            return None
        if field in ("value", "consecutive_measurements") and not isinstance(rule_json[field], (int, float)):
            print(f"parse_rules_config: field '{field}' in stateful rule '{name}' must be a number")
            return None
    rule = StatefulRule(
        priority,
        name,
        sensor_ids[rule_json["sensor_id"]],
        rule_json["value"],
        rule_json["consecutive_measurements"],
        str_to_operator(rule_json["operator"]),
    )
    return rule


def parse_logical_rule(
    rule_json, sensor_ids: dict[str, int], mapping
) -> Rule | None:
    priority = str_to_priority(rule_json["priority"])
    name = rule_json["rule_id"]
    for field in ["conditions", "logic"]:
        if field not in rule_json:
            print(f"parse_rules_config: missing field '{field}' in correlation rule '{name}'")
            return None
    if not isinstance(rule_json["conditions"], list) or len(rule_json["conditions"]) < 2:
        print(f"parse_rules_config: 'conditions' in correlation rule '{name}'"
              "must be a list of at least 2 elements")
        return None
    for cond in rule_json["conditions"][:2]:
        if cond not in mapping:
            print(f"parse_rules_config: condition '{cond}' in correlation rule '{name}'"
                  "references an unknown rule")
            return None
    rule = LogicalCorrelationRule(
        priority,
        name,
        str_to_logic(rule_json["logic"]),
        mapping[rule_json["conditions"][0]],
        mapping[rule_json["conditions"][1]],
    )
    return rule


def parse_rules_config(
    rules_filename: str, sensor_ids: dict[str, int]
) -> tuple[bool, list[Rule]]:
    try:
        with open(rules_filename, "r", encoding="utf-8") as f:
            data = json.load(f)
            rules: list[Rule] = []
            mapping: dict[str, int] = {}  # from rule.name to rule.id
            for rule_json in data:
                if rule_json["type"] == "simple" or rule_json["type"] == "step_difference":
                    rule = parse_simple_step_diff_rule(rule_json, sensor_ids)
                elif rule_json["type"] == "stateful":
                    rule = parse_stateful_rule(rule_json, sensor_ids)
                else:
                    rule = parse_logical_rule(rule_json, sensor_ids, mapping)
                if rule is None:
                    return False, []
                mapping[rule.name] = rule.id
                rules.append(rule)
            return True, rules

    except FileNotFoundError:
        print(f"ERROR ConfigReader: rules file '{rules_filename}' not found")
        return False, []
    except PermissionError:
        print(
            f"ERROR ConfigReader: no permission to read rules file '{rules_filename}'"
        )
        return False, []
    except json.JSONDecodeError as e:
        print(
            f"ERROR ConfigReader: invalid JSON in rules file '{rules_filename}':",
            e,
            sep="\n",
        )
        return False, []
    except Exception as e:
        print(
            f"ERROR ConfigReader: unexpected error reading rules file '{rules_filename}':",
            e,
            sep="\n",
        )
        return False, []


def parse_sensors_config(
    sensors_filename: str, out_sensor_ids: dict[str, int], out_sensor_names: list[str]
) -> tuple[int, float]:
    try:
        with open(sensors_filename, "r") as f:
            sensors_yaml = yaml.safe_load(f)

            counter = 0
            for sensor in sensors_yaml["sensors"]:
                out_sensor_ids[sensor["id"]] = counter
                out_sensor_names.append(sensor["id"])
                counter += 1
            rate_str: str = sensors_yaml["sensors"][0]["sampling_rate"]
            freq = float(rate_str[:-2])  # Hz

            return counter, freq

    except FileNotFoundError:
        print(f"ERROR ConfigReader: sensor file '{sensors_filename}' not found")
        return -1, 0
    except PermissionError:
        print(
            f"ERROR ConfigReader: no permission to read sensor file '{sensors_filename}'"
        )
        return -1, 0
    except yaml.YAMLError as e:
        print(
            f"ERROR ConfigReader: invalid YAML in sensor file '{sensors_filename}':",
            e,
            sep="\n",
        )
        return -1, 0
    except Exception as e:
        print(
            f"ERROR ConfigReader: unexpected error reading sensor file '{sensors_filename}':",
            e,
            sep="\n",
        )
        return -1, 0
