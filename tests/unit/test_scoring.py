import numpy as np

from sgi_apex.forecasting import scoring


def test_crps_point_mass_is_absolute_error():
    assert np.isclose(scoring.crps(np.full(100, 10.0), 13.0), 3.0)


def test_crps_standard_normal_matches_closed_form():
    rng = np.random.default_rng(0)
    # Closed form at y=0 for N(0,1): 2*phi(0) - 1/sqrt(pi) = 0.2337
    assert abs(scoring.crps(rng.standard_normal(200_000), 0.0) - 0.2337) < 0.005


def test_brier_and_coverage():
    assert np.isclose(scoring.brier(0.7, True), 0.09)
    s = np.arange(101.0)
    assert scoring.covered(s, 50, 0.5) and not scoring.covered(s, 99, 0.9)
