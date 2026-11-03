from sgi_apex.metrics import alerts


def row(p, shortfall, intake=60, hold=False):
    return {"p_meet_target": p, "expected_shortfall_vs_target": shortfall, "intake": intake,
            "data_quality": {"hold": hold}}


def test_classification():
    assert alerts.classify(row(0.2, 10)) == "RED"
    assert alerts.classify(row(0.6, 10)) == "AMBER"
    assert alerts.classify(row(0.9, 1)) == "GREEN"


def test_immaterial_shortfall_does_not_alert():
    assert alerts.classify(row(0.1, 1.0)) == "GREEN"


def test_bad_data_holds_instead_of_alerting():
    assert alerts.classify(row(0.1, 20, hold=True)) == "DQ-HOLD"
