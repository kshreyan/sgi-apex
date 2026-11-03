"""Synthetic admissions history for the demo replay.

No real SGI admissions data is in this repository. This generator produces
plausible weekly funnel snapshots so the full loop (ingest -> forecast ->
alert -> decision -> outcome -> evaluation) can be exercised end to end.
Every row carries ``source = "synthetic"`` and must be replaced by real
ERP/admissions exports before any number is used for a decision.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sgi_apex import config


def _logistic(w: np.ndarray, mid: float, scale: float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-(w - mid) / scale))


def generate(programmes: pd.DataFrame, seed: int = config.SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    years = np.arange(config.FIRST_YEAR, config.LIVE_YEAR + 1)
    weeks = np.arange(config.CYCLE_WEEKS + 1)
    group_shock = dict(zip(years, rng.normal(0, 0.05, len(years))))
    campus_shock = {
        (c, y): rng.normal(0, 0.04) for c in programmes.campus.unique() for y in years
    }

    rows = []
    for _, p in programmes.iterrows():
        intake = int(p.sanctioned_intake)
        level = rng.uniform(0.85, 1.25)
        trend = rng.uniform(-0.03, 0.05)
        mid = rng.uniform(9, 15)
        conv = rng.uniform(0.35, 0.60)
        for y in years:
            t = y - config.FIRST_YEAR
            shock = group_shock[y] + campus_shock[(p.campus, y)] + rng.normal(0, 0.07)
            # Scripted demo scenario: engineering demand softens in the live year.
            if p.programme_id.startswith("BET-BTECH") and y == config.LIVE_YEAR:
                shock -= 0.30
            demand = intake * level * np.exp(trend * t + shock)
            final = int(min(intake, rng.poisson(max(demand, 1))))
            m = mid + rng.normal(0, 1.5)
            curve = _logistic(weeks, m, 2.6)
            curve = (curve - curve[0]) / (curve[-1] - curve[0])
            enrolled = np.maximum.accumulate(np.round(final * curve)).astype(int)
            yconv = np.clip(conv + rng.normal(0, 0.04), 0.2, 0.8)
            applications = np.maximum.accumulate(np.round(enrolled / yconv + weeks * 0.3)).astype(int)
            enquiries = np.round(applications * rng.uniform(2.6, 3.4)).astype(int)
            for w in weeks:
                rows.append({
                    "programme_id": p.programme_id,
                    "admission_year": int(y),
                    "cycle_week": int(w),
                    "enquiries_cum": int(enquiries[w]),
                    "applications_cum": int(applications[w]),
                    "enrolled_cum": int(enrolled[w]),
                    "source": "synthetic",
                })
    return pd.DataFrame(rows)
