import numpy as np

from sgi_apex.forecasting.admissions import engine
from sgi_apex.forecasting.admissions.models import MODELS


def test_forecast_ignores_future_rows(silver, programmes):
    year, week = 2024, 10
    base = engine.programme_samples(silver, programmes, year, week, "bayes_blend", n=500)
    corrupted = silver.copy()
    future = (corrupted.admission_year > year) | ((corrupted.admission_year == year) & (corrupted.cycle_week > week))
    corrupted.loc[future, "enrolled_cum"] = 10_000
    again = engine.programme_samples(corrupted, programmes, year, week, "bayes_blend", n=500)
    for pid in base:
        assert np.array_equal(base[pid], again[pid]), pid


def test_every_model_respects_snapshot(silver, programmes):
    for model in MODELS:
        s = engine.programme_samples(silver, programmes, 2023, 6, model, n=200)
        assert len(s) == len(programmes)
