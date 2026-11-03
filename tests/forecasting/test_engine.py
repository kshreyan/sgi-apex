import numpy as np

from sgi_apex.decisions import options
from sgi_apex.forecasting.admissions import engine


def test_samples_bounded_by_enrolled_and_intake(silver, programmes):
    fc = engine.forecast(silver, programmes, 2025, 10, "bayes_blend")
    for row in fc["programmes"]:
        s = fc["samples"][row["programme_id"]]
        assert s.min() >= row["enrolled_to_date"]
        assert s.max() <= row["intake"]
        assert row["q05"] <= row["q25"] <= row["median"] <= row["q75"] <= row["q95"]


def test_hierarchy_is_coherent(silver, programmes):
    fc = engine.forecast(silver, programmes, 2025, 10, "bayes_blend")
    total = sum(fc["samples"][p] for p in programmes.programme_id)
    assert np.isclose(fc["rollups"]["group:SGI"]["expected"], total.mean())
    campus_sum = sum(fc["rollups"][f"campus:{c}"]["expected"] for c in programmes.campus.unique())
    assert np.isclose(campus_sum, fc["rollups"]["group:SGI"]["expected"])


def test_correlation_widens_group_interval(silver, programmes):
    rho_g, rho_c = engine.shock_correlation(silver[silver.admission_year < 2025], 2025)
    assert 0 <= rho_g <= rho_c < 1


def test_do_nothing_adds_nothing():
    s = np.full(1000, 40.0)
    out = options.evaluate(s, enrolled=20, intake=60, target_fill=0.9, level="UG", weeks_left=16)
    dn = next(o for o in out["options"] if o["id"] == "do_nothing")
    assert dn["added_enrolments_mean"] == 0 and out["robustness"] in {"ROBUST", "MODERATE", "FRAGILE"}
