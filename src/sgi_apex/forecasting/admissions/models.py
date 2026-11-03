"""Admissions final-enrolment models. Each returns Monte Carlo samples.

Models are deterministic maps from standard-normal draws ``z`` to samples, so
the engine can correlate draws across programmes (shared group/campus shocks).
All models receive a leakage-safe snapshot (see ``pipeline.snapshot``) for a
single programme plus the campus-level snapshot for pooling. Samples are
floored at enrolments already confirmed and capped at sanctioned intake.

  seasonal_naive  last year's final, perturbed by historical YoY volatility
  pace_own        current enrolled / historical share-complete-by-this-week
  pace_pooled     pace_own with hierarchical shrinkage toward the campus curve
  bayes_blend     precision-weighted combination (log scale) of the seasonal
                  prior and the pooled pace likelihood
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

SIGMA_FLOOR = 0.04
POOLING_K = 3.0  # pseudo-years of campus evidence added to each programme


@dataclass
class Context:
    programme: pd.DataFrame  # one programme, snapshot rows
    campus: pd.DataFrame  # all programmes on the campus, snapshot rows
    year: int
    week: int
    intake: int


def _finals(df: pd.DataFrame, year: int) -> pd.DataFrame:
    hist = df[df.admission_year < year]
    last = hist.groupby(["programme_id", "admission_year"]).enrolled_cum.max().rename("final").reset_index()
    return last


def _current(ctx: Context) -> int:
    cur = ctx.programme[(ctx.programme.admission_year == ctx.year) & (ctx.programme.cycle_week <= ctx.week)]
    return int(cur.enrolled_cum.max()) if len(cur) else 0


def _bound(samples: np.ndarray, floor: int, cap: int) -> np.ndarray:
    return np.clip(np.round(samples), floor, cap)


def _share_complete(df: pd.DataFrame, year: int, week: int) -> pd.DataFrame:
    """log(enrolled_at_week / final) for every completed historical programme-year."""
    finals = _finals(df, year)
    at_w = df[(df.admission_year < year) & (df.cycle_week == week)][["programme_id", "admission_year", "enrolled_cum"]]
    m = at_w.merge(finals, on=["programme_id", "admission_year"])
    m = m[(m.final > 0) & (m.enrolled_cum > 0)]
    m["log_r"] = np.log(m.enrolled_cum / m.final)
    return m


def _naive_params(ctx: Context) -> tuple[float, float] | None:
    """(mu, sd) of log final enrolment under the seasonal-naive prior."""
    finals = _finals(ctx.programme, ctx.year).sort_values("admission_year")
    if finals.empty:
        return None
    yoy = np.diff(np.log(np.maximum(finals.final.to_numpy(), 1)))
    sigma = max(np.std(yoy, ddof=1) if len(yoy) > 1 else 0.15, SIGMA_FLOOR)
    return float(np.log(max(finals.final.iloc[-1], 1))), float(sigma)


def seasonal_naive(ctx: Context, z: np.ndarray) -> np.ndarray:
    floor = _current(ctx)
    params = _naive_params(ctx)
    if params is None:
        return np.full(len(z), float(floor))
    mu, sd = params
    return _bound(np.exp(mu + sd * z), floor, ctx.intake)


def _pace_params(ctx: Context, pooled: bool) -> tuple[float, float] | None:
    """(mu, sd) of log final enrolment implied by enrolment pace to date."""
    floor = _current(ctx)
    own = _share_complete(ctx.programme, ctx.year, ctx.week)
    if floor == 0 or own.empty:
        return None
    mu, n_own = own.log_r.mean(), len(own)
    sd = own.log_r.std(ddof=1) if n_own > 1 else 0.3
    if pooled:
        camp = _share_complete(ctx.campus, ctx.year, ctx.week)
        if len(camp) > n_own:
            w = n_own / (n_own + POOLING_K)
            mu = w * mu + (1 - w) * camp.log_r.mean()
            sd = np.sqrt(w * sd**2 + (1 - w) * camp.log_r.var(ddof=1))
    # Parameter uncertainty on mu plus year-to-year variation.
    sd_total = np.sqrt(max(sd, SIGMA_FLOOR) ** 2 * (1 + 1 / n_own))
    return float(np.log(floor) - mu), float(sd_total)


def _pace(ctx: Context, z: np.ndarray, pooled: bool) -> np.ndarray:
    params = _pace_params(ctx, pooled)
    if params is None:
        return seasonal_naive(ctx, z)
    mu, sd = params
    return _bound(np.exp(mu + sd * z), _current(ctx), ctx.intake)


def pace_own(ctx: Context, z: np.ndarray) -> np.ndarray:
    return _pace(ctx, z, pooled=False)


def pace_pooled(ctx: Context, z: np.ndarray) -> np.ndarray:
    return _pace(ctx, z, pooled=True)


def bayes_blend(ctx: Context, z: np.ndarray) -> np.ndarray:
    prior, like = _naive_params(ctx), _pace_params(ctx, pooled=True)
    if prior is None or like is None:
        return seasonal_naive(ctx, z)
    w0, w1 = 1 / prior[1] ** 2, 1 / like[1] ** 2
    mu = (w0 * prior[0] + w1 * like[0]) / (w0 + w1)
    sd = (w0 + w1) ** -0.5
    return _bound(np.exp(mu + sd * z), _current(ctx), ctx.intake)


# Ordered simplest first: ties within the simplicity margin go to the earlier model.
MODELS = {
    "seasonal_naive": seasonal_naive,
    "pace_own": pace_own,
    "pace_pooled": pace_pooled,
    "bayes_blend": bayes_blend,
}
