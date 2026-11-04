"""Rolling-origin backtest. Champion is chosen on VALIDATION years only;
LOCKBOX years are scored once for the record and never used for selection."""

from __future__ import annotations

import numpy as np
import pandas as pd

from sgi_apex import config
from sgi_apex.forecasting import scoring
from sgi_apex.forecasting.admissions import engine
from sgi_apex.forecasting.admissions.models import MODELS

GROUP = "__GROUP__"


def _final_actuals(silver: pd.DataFrame, year: int) -> pd.Series:
    return silver[silver.admission_year == year].groupby("programme_id").enrolled_cum.max()


def run(silver: pd.DataFrame, programmes: pd.DataFrame, years, weeks=config.BACKTEST_WEEKS,
        n: int = 1500) -> pd.DataFrame:
    rows = []
    intake = programmes.set_index("programme_id").sanctioned_intake
    target = programmes.set_index("programme_id").target_fill * intake
    for year in years:
        actual = _final_actuals(silver, year)
        for week in weeks:
            for model in MODELS:
                samples = engine.programme_samples(silver, programmes, year, week, model, n=n)
                samples = {pid: s for pid, s in samples.items() if pid in actual.index}  # programme not run that year
                for pid, s in samples.items():
                    y = float(actual[pid])
                    p = float((s >= target[pid] - 1e-9).mean())
                    hit = y >= target[pid] - 1e-9
                    rows.append({
                        "year": year, "week": week, "model": model, "programme_id": pid,
                        "actual": y, "median": float(np.median(s)),
                        "crps_norm": scoring.crps(s, y) / intake[pid],
                        "abs_err_norm": abs(float(np.median(s)) - y) / intake[pid],
                        "cover50": scoring.covered(s, y, 0.5), "cover90": scoring.covered(s, y, 0.9),
                        "p_target": p, "hit_target": hit,
                        "brier": scoring.brier(p, hit), "log_loss": scoring.log_loss(p, hit),
                    })
                # Group roll-up: checks that summed programme draws stay calibrated.
                total = np.sum(list(samples.values()), axis=0)
                y = float(actual.sum())
                rows.append({"year": year, "week": week, "model": model, "programme_id": GROUP,
                             "actual": y, "median": float(np.median(total)),
                             "crps_norm": scoring.crps(total, y) / intake.sum(),
                             "abs_err_norm": abs(float(np.median(total)) - y) / intake.sum(),
                             "cover50": scoring.covered(total, y, 0.5), "cover90": scoring.covered(total, y, 0.9)})
    return pd.DataFrame(rows)


def summary(bt: pd.DataFrame, group: bool = False) -> pd.DataFrame:
    bt = bt[bt.programme_id == GROUP] if group else bt[bt.programme_id != GROUP]
    return (bt.groupby(["model", "week"])
              .agg(crps=("crps_norm", "mean"), mae=("abs_err_norm", "mean"), cover50=("cover50", "mean"),
                   cover90=("cover90", "mean"), brier=("brier", "mean"), log_loss=("log_loss", "mean"),
                   n=("crps_norm", "size"))
              .reset_index())


def select_champion(validation: pd.DataFrame, horizon_week: int | None = None,
                    simplicity_margin: float = 0.02) -> tuple[str, dict]:
    """Lowest mean CRPS wins, but a simpler model is kept if within ``simplicity_margin`` (PART LXXXV).

    With ``horizon_week`` the champion is chosen on the backtest week nearest
    the live as-of week: the best model at week 2 is not the best at week 18.
    """
    order = list(MODELS)  # listed simplest first
    validation = validation[validation.programme_id != GROUP]
    if horizon_week is not None:
        weeks = validation.week.unique()
        nearest = weeks[abs(weeks - horizon_week).argmin()]
        validation = validation[validation.week == nearest]
    score = validation.groupby("model").crps_norm.mean().reindex(order)
    best = score.min()
    for m in order:
        if score[m] <= best * (1 + simplicity_margin):
            champion = m
            break
    ranked = score.sort_values()
    roles = {champion: "CHAMPION"}
    letters = iter("ABC")
    for m in ranked.index:
        if m not in roles:
            roles[m] = f"CHALLENGER {next(letters)}"
    return champion, {"crps_by_model": score.round(5).to_dict(), "roles": roles,
                      "horizon_week": None if horizon_week is None else int(nearest)}
