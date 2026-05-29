import pytest
from io import StringIO
from src.batch_analyzer import priority_to_str, RuleNode, BatchAnalyzer
from src.rule import Rule, SimpleRule, LogicalCorrelationRule, Operator, Logic
from src.utils import TimestampData
from time import time

@pytest.fixture(autouse=True)
def reset_rule_ids():
    """Reset class-level IDs so tests are deterministic."""
    Rule._next_id = 0


# ------------------
# priority to string
# ------------------

def test_priority_to_str():
    assert priority_to_str(0) == "LOW"
    assert priority_to_str(1) == "MEDIUM"
    assert priority_to_str(2) == "HIGH"


# ---------
# Rule Node
# ---------

def test_rule_node_set():
    node = RuleNode(123)

    assert node.id == 123
    assert node.num_pred == 0
    assert node.num_ready_pred == 0
    assert node.next == []


# ---------------------
# BatchAnalyzer setters
# ---------------------

def test_batch_analyzer_set_and_deinit(tmp_path):
    file1 = tmp_path / "file1.txt"
    file1.write_text("txt1")

    file2 = tmp_path / "file2.txt"
    file2.write_text("txt2")

    analyzer = BatchAnalyzer()

    # __init__
    assert analyzer._sensor_id_to_name == []
    assert analyzer._rules == []
    assert analyzer._indep_rules_id == [[], [], []]
    assert analyzer._outcomes == []
    assert analyzer._corr_rules_graph == [[], [], []]
    assert analyzer._leaf_nodes_ind == [[], [], []]

    # Set
    analyzer.set_alarms_output_file(str(file1))
    analyzer.set_valid_output_file(str(file2))
    analyzer.set_sensors(["sensor1", "sensor2"])

    assert not analyzer._alarms_output_file.closed
    assert not analyzer._valid_output_file.closed
    assert analyzer._sensor_id_to_name == ["sensor1", "sensor2"]

    # Deinit
    analyzer.deinit()

    assert analyzer._alarms_output_file.closed
    assert analyzer._valid_output_file.closed


# -----------------------------
# BatchAnalyzer write functions
# -----------------------------

def test_write_alarms_file_closed(capsys):
    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer._alarms_output_file.close()

    rule = SimpleRule(0, "rule1", 0, 0.5, Operator.LESS)
    td = TimestampData("ts1", [0.3])

    analyzer.write_alarms(rule, td)

    captured_output = capsys.readouterr().out

    assert captured_output == \
        "WARNING BatchAnalyzer: did not provide an output file for alarm readings, use set_alarms_output_file\n"


def test_write_alarms_file_simple_rule():
    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer.set_sensors(["sensor1"])

    rule = SimpleRule(0, "rule1", 0, 0.5, Operator.LESS)
    td = TimestampData("ts1", [0.3])

    analyzer.write_alarms(rule, td)

    output = analyzer._alarms_output_file.getvalue()

    assert output == "ts1;rule1;LOW;sensor1;0.3\n"


def test_write_alarms_file_correlation_rule():
    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer.set_sensors(["sensor1", "sensor2"])

    rule1 = SimpleRule(0, "rule1", 0, 0.5, Operator.LESS)
    rule2 = SimpleRule(0, "rule2", 1, 0.4, Operator.LESS)
    rule3 = LogicalCorrelationRule(1, "rule3", Logic.AND, 0, 1)
    td = TimestampData("ts1", [0.3, 0.2])

    analyzer._rules = [rule1, rule2, rule3]
    analyzer.write_alarms(rule3, td)

    output = analyzer._alarms_output_file.getvalue()

    assert output == "ts1;rule3;MEDIUM;sensor1,sensor2;0.3,0.2\n"


def test_write_alarms_file_nested_correlation_rule():
    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer.set_sensors(["sensor1", "sensor2", "sensor3"])

    rule1 = SimpleRule(0, "rule1", 0, 0.5, Operator.LESS)
    rule2 = SimpleRule(0, "rule2", 1, 0.4, Operator.LESS)
    rule3 = SimpleRule(0, "rule3", 2, 0.1, Operator.GREATER)
    rule4 = LogicalCorrelationRule(1, "rule4", Logic.AND, 0, 1)
    rule5 = LogicalCorrelationRule(1, "rule5", Logic.AND, 2, 3)
    td = TimestampData("ts1", [0.3, 0.2, 0.15])

    analyzer._rules = [rule1, rule2, rule3, rule4, rule5]
    analyzer.write_alarms(rule5, td)

    output = analyzer._alarms_output_file.getvalue()

    assert output == "ts1;rule5;MEDIUM;sensor3,sensor1,sensor2;0.15,0.3,0.2\n"


def test_write_valid_data_file_closed(capsys):
    analyzer = BatchAnalyzer()
    analyzer._valid_output_file = StringIO()
    analyzer._valid_output_file.close()

    td = TimestampData("ts1", [0.3])

    analyzer.write_valid_data(td)

    captured_output = capsys.readouterr().out
    assert captured_output == \
        "WARNING BatchAnalyzer: did not provide an output file for valid readings, use set_valid_output_file\n"


def test_write_valid_data_file_correct():
    analyzer = BatchAnalyzer()
    analyzer._valid_output_file = StringIO()

    td = TimestampData("ts1", [0.3, 0.4])

    analyzer.set_sensors(["sensor1", "sensor2"])
    analyzer.write_valid_data(td)

    output = analyzer._valid_output_file.getvalue()
    assert output == "ts1;NOMINAL;sensor1:0.3|sensor2:0.4\n"


# -----------------------------------------
# BatchAnalyzer creating graph and analysis
# -----------------------------------------

def test_batch_analyzer_load_rules1():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(2, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(2, "rule4", Logic.OR, 0, 2)
    ]

    analyzer = BatchAnalyzer()

    assert analyzer.load_rules(rules) is True

    assert analyzer._rules == rules

    # Verify the constructed graph
    assert analyzer._indep_rules_id == [[0], [1], []]
    assert analyzer._leaf_nodes_ind == [[], [], [0]]
    assert len(analyzer._corr_rules_graph[2]) == 2
    assert len(analyzer._corr_rules_graph[1]) == 0
    assert len(analyzer._corr_rules_graph[0]) == 0

    # Logical Correlation rule 0
    rule0 = analyzer._corr_rules_graph[2][0]
    assert rule0.id == 2
    assert rule0.num_pred == 0  # depends only on independent rules
    assert rule0.num_ready_pred == 0
    assert rule0.next == [(1, 2)]

    # Logical Correlation rule 1
    rule0 = analyzer._corr_rules_graph[2][1]
    assert rule0.id == 3
    assert rule0.num_pred == 1  # depends only on independent rules
    assert rule0.num_ready_pred == 0
    assert rule0.next == []


def test_batch_analyzer_load_rules2():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(2, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(2, "rule4", Logic.OR, 2, 0)
    ]

    analyzer = BatchAnalyzer()

    assert analyzer.load_rules(rules) is True

    assert analyzer._rules == rules

    # Verify the constructed graph
    assert analyzer._indep_rules_id == [[0], [1], []]
    assert analyzer._leaf_nodes_ind == [[], [], [0]]
    assert len(analyzer._corr_rules_graph[2]) == 2
    assert len(analyzer._corr_rules_graph[1]) == 0
    assert len(analyzer._corr_rules_graph[0]) == 0

    # Logical Correlation rule 0
    rule0 = analyzer._corr_rules_graph[2][0]
    assert rule0.id == 2
    assert rule0.num_pred == 0  # depends only on independent rules
    assert rule0.num_ready_pred == 0
    assert rule0.next == [(1, 2)]

    # Logical Correlation rule 1
    rule0 = analyzer._corr_rules_graph[2][1]
    assert rule0.id == 3
    assert rule0.num_pred == 1  # depends only on independent rules
    assert rule0.num_ready_pred == 0
    assert rule0.next == []


def test_analyze_all_ok():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(2, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(2, "rule4", Logic.OR, 0, 2)
    ]

    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer._valid_output_file = StringIO()
    analyzer.load_rules(rules)
    analyzer.set_sensors(["sensor1", "sensor2"])
    
    td = TimestampData("ts1", [0.6, 0.45])
    
    
    analyzer.analyze_and_output([td])
    assert analyzer._all_ok is True

    output = analyzer._alarms_output_file.getvalue()
    assert output == ""


def test_analyze_rules_triggered():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(2, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(2, "rule4", Logic.OR, 0, 2)
    ]

    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer.load_rules(rules)
    analyzer.set_sensors(["sensor1", "sensor2"])

    td = TimestampData("ts1", [0.4, 0.45])
    
    analyzer.analyze_and_output([td])
    assert analyzer._all_ok is False

    output = analyzer._alarms_output_file.getvalue()
    expected_output = "ts1;rule1;LOW;sensor1;0.4\n"
    expected_output += "ts1;rule4;HIGH;sensor1,sensor1,sensor2;0.4,0.4,0.45\n"
    assert output == expected_output


def test_analyze_and_output():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(2, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(2, "rule4", Logic.OR, 0, 2)
    ]

    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer._valid_output_file = StringIO()
    analyzer.load_rules(rules)
    analyzer.set_sensors(["sensor1", "sensor2"])

    td1 = TimestampData("ts1", [0.6, 0.45])
    td2 = TimestampData("ts2", [0.4, 0.45])
    td3 = TimestampData("ts3", [0.2, 0.3])
    td4 = TimestampData("ts4", [0.7, 0.55])

    analyzer.analyze_and_output([td1, td2, td3, td4])

    # Alarms data output
    alarms_output = analyzer._alarms_output_file.getvalue()
    alarms_expected = "ts2;rule1;LOW;sensor1;0.4\n"
    alarms_expected += "ts2;rule4;HIGH;sensor1,sensor1,sensor2;0.4,0.4,0.45\n"
    alarms_expected += "ts3;rule2;MEDIUM;sensor2;0.3\n"
    alarms_expected += "ts3;rule1;LOW;sensor1;0.2\n"
    alarms_expected += "ts3;rule3;HIGH;sensor1,sensor2;0.2,0.3\n"
    alarms_expected += "ts3;rule4;HIGH;sensor1,sensor1,sensor2;0.2,0.2,0.3\n"
    assert alarms_output == alarms_expected

    # Valid data output
    valid_output = analyzer._valid_output_file.getvalue()
    valid_expected = "ts1;NOMINAL;sensor1:0.6|sensor2:0.45\n"
    valid_expected += "ts4;NOMINAL;sensor1:0.7|sensor2:0.55\n"
    assert valid_output == valid_expected


def test_analyze_and_output_with_priorities():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(2, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(1, "rule4", Logic.OR, 0, 2)
    ]

    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer._valid_output_file = StringIO()
    analyzer.load_rules(rules)
    analyzer.set_sensors(["sensor1", "sensor2"])

    td1 = TimestampData("ts1", [0.6, 0.45])
    td2 = TimestampData("ts2", [0.4, 0.45])
    td3 = TimestampData("ts3", [0.2, 0.3])
    td4 = TimestampData("ts4", [0.7, 0.55])

    analyzer.analyze_and_output([td1, td2, td3, td4])

    # Alarms data output
    alarms_output = analyzer._alarms_output_file.getvalue()
    alarms_expected = "ts2;rule1;LOW;sensor1;0.4\n"
    alarms_expected += "ts2;rule4;MEDIUM;sensor1,sensor1,sensor2;0.4,0.4,0.45\n"
    alarms_expected += "ts3;rule2;MEDIUM;sensor2;0.3\n"
    alarms_expected += "ts3;rule1;LOW;sensor1;0.2\n"
    alarms_expected += "ts3;rule3;HIGH;sensor1,sensor2;0.2,0.3\n"
    alarms_expected += "ts3;rule4;MEDIUM;sensor1,sensor1,sensor2;0.2,0.2,0.3\n"
    assert alarms_output == alarms_expected

    # Valid data output
    valid_output = analyzer._valid_output_file.getvalue()
    valid_expected = "ts1;NOMINAL;sensor1:0.6|sensor2:0.45\n"
    valid_expected += "ts4;NOMINAL;sensor1:0.7|sensor2:0.55\n"
    assert valid_output == valid_expected


def test_analyze_and_output_with_independat_correlations():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(2, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(1, "rule4", Logic.OR, 0, 2),
        LogicalCorrelationRule(1, "rule5", Logic.AND, 0, 1)
    ]

    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer._valid_output_file = StringIO()
    analyzer.load_rules(rules)
    analyzer.set_sensors(["sensor1", "sensor2"])

    td1 = TimestampData("ts1", [0.6, 0.45])
    td2 = TimestampData("ts2", [0.4, 0.45])
    td3 = TimestampData("ts3", [0.2, 0.3])
    td4 = TimestampData("ts4", [0.7, 0.55])

    analyzer.analyze_and_output([td1, td2, td3, td4])

    # Alarms data output
    alarms_output = analyzer._alarms_output_file.getvalue()
    alarms_expected = "ts2;rule1;LOW;sensor1;0.4\n"
    alarms_expected += "ts2;rule4;MEDIUM;sensor1,sensor1,sensor2;0.4,0.4,0.45\n"
    alarms_expected += "ts3;rule2;MEDIUM;sensor2;0.3\n"
    alarms_expected += "ts3;rule1;LOW;sensor1;0.2\n"
    alarms_expected += "ts3;rule3;HIGH;sensor1,sensor2;0.2,0.3\n"
    alarms_expected += "ts3;rule5;MEDIUM;sensor1,sensor2;0.2,0.3\n"
    alarms_expected += "ts3;rule4;MEDIUM;sensor1,sensor1,sensor2;0.2,0.2,0.3\n"
    assert alarms_output == alarms_expected

    # Valid data output
    valid_output = analyzer._valid_output_file.getvalue()
    valid_expected = "ts1;NOMINAL;sensor1:0.6|sensor2:0.45\n"
    valid_expected += "ts4;NOMINAL;sensor1:0.7|sensor2:0.55\n"
    assert valid_output == valid_expected


def test_bad_rules():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(1, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(1, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(2, "rule4", Logic.OR, 0, 2)
    ]

    analyzer = BatchAnalyzer()
    analyzer._alarms_output_file = StringIO()
    analyzer._valid_output_file = StringIO()
    with pytest.raises(RuntimeError):
        analyzer.load_rules(rules)

def test_analyze_parallel():
    rules = [
        SimpleRule(0, "rule1", 0, 0.5, Operator.LESS),
        SimpleRule(0, "rule2", 1, 0.4, Operator.LESS),
        LogicalCorrelationRule(1, "rule3", Logic.AND, 0, 1),
        LogicalCorrelationRule(0, "rule4", Logic.OR, 0, 2),
    ]
    #create many correlated and independant rules which can be run in parallel
    N_max = 1000
    for i in range(5, N_max):
        rule_num = "rule" + str(i)
        and_num = "and" + str(i - 5)
        rules.append(SimpleRule(0, rule_num, 1, 0.6, Operator.LESS))
        rules.append(SimpleRule(1, rule_num, 1, 0.6, Operator.LESS))
        rules.append(LogicalCorrelationRule(1, and_num, Logic.OR, 0, 2))
        rules.append(LogicalCorrelationRule(0, and_num, Logic.OR, 0, 2))

    analyzer = BatchAnalyzer(4)
    analyzer._alarms_output_file = StringIO()
    analyzer.load_rules(rules)
    analyzer.set_sensors(["sensor1", "sensor2"])

    td = TimestampData("ts1", [0.4, 0.45])
    analyzer.analyze_and_output([td])
    assert analyzer._all_ok is False

    output = analyzer._alarms_output_file.getvalue()
    
    
    expected_output = ""
    
    #simple medium -> simple low -> correlated medium -> correlated low

    for i in range(5, N_max):
        rule_num = "rule" + str(i)
        expected_output += "ts1;" + rule_num +";MEDIUM;sensor2;0.45\n"
    
    expected_output += "ts1;rule1;LOW;sensor1;0.4\n"
    for i in range(5, N_max):
        rule_num = "rule" + str(i)
        expected_output += "ts1;" + rule_num +";LOW;sensor2;0.45\n"
    

    for i in range(5, N_max):
        and_num = "and" + str(i - 5)
        expected_output += "ts1;" + and_num +";MEDIUM;sensor1,sensor1,sensor2;0.4,0.4,0.45\n"
    
    expected_output += "ts1;rule4;LOW;sensor1,sensor1,sensor2;0.4,0.4,0.45\n"
    
    for i in range(5, N_max):
        and_num = "and" + str(i - 5)
        expected_output += "ts1;" + and_num +";LOW;sensor1,sensor1,sensor2;0.4,0.4,0.45\n"

    assert output == expected_output
