"""Data-quality scoring. A forecast is never issued silently on bad data."""

from __future__ import annotations

import pandas as pd

from sgi_apex import config

DQ_HOLD_THRESHOLD = 0.80


def score_programme(snap: pd.DataFrame, intake: int, year: int, week: int) -> dict:
    """Score one programme's snapshot as of (year, week). Each check is 0..1."""
    cur = snap[snap.admission_year == year].sort_values("cycle_week")
    expected_weeks = week + 1
    completeness = min(1.0, cur.cycle_week.nunique() / expected_weeks) if expected_weeks else 1.0
    freshness = 1.0 if (not cur.empty and cur.cycle_week.max() >= week) else 0.0
    monotone = all((cur[c].diff().dropna() >= 0).all() for c in ("enquiries_cum", "applications_cum", "enrolled_cum"))
    within_cap = bool((cur.enrolled_cum <= intake).all())
    funnel = bool((cur.enrolled_cum <= cur.applications_cum).all())
    validity = (monotone + within_cap + funnel) / 3
    uniqueness = 0.0 if snap.duplicated(["admission_year", "cycle_week"]).any() else 1.0
    history_years = snap[snap.admission_year < year].admission_year.nunique()
    consistency = min(1.0, history_years / 5)
    checks = {
        "completeness": completeness,
        "freshness": freshness,
        "validity": validity,
        "uniqueness": uniqueness,
        "consistency": consistency,
    }
    score = sum(checks.values()) / len(checks)
    return {**checks, "score": round(score, 3), "hold": score < DQ_HOLD_THRESHOLD, "lineage": snap.source.iloc[0] if len(snap) else "none"}


def lineage_label() -> str:
    return config.DATA_MODE
