"""Programme-level admissions forecasts with coherent campus/group roll-ups.

Roll-ups sum programme samples draw-by-draw, so campus and group
distributions are reconciled with programme forecasts by construction
(bottom-up hierarchical reconciliation, PART XVII).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from sgi_apex import config
from sgi_apex.data import pipeline, quality
from sgi_apex.forecasting.admissions.models import MODELS, Context

QUANTILES = (0.05, 0.25, 0.5, 0.75, 0.95)


def shock_correlation(snap: pd.DataFrame, year: int) -> tuple[float, float]:
    """(group, same-campus) correlation of YoY log changes in final enrolment, from history only.

    Independent programme draws would make campus/group intervals far too
    narrow, because demand shocks are shared (a bad year is bad everywhere).
    """
    finals = (snap[snap.admission_year < year].groupby(["admission_year", "programme_id"]).enrolled_cum.max()
              .unstack())
    yoy = np.log(finals.clip(lower=1)).diff().dropna(how="all")
    if len(yoy) < 3:
        return 0.3, 0.4
    corr = yoy.corr().to_numpy()
    campus = snap.drop_duplicates("programme_id").set_index("programme_id").campus.reindex(yoy.columns).to_numpy()
    same = campus[:, None] == campus[None, :]
    off = ~np.eye(len(corr), dtype=bool)
    rho_g = float(np.nanmean(corr[off & ~same])) if (off & ~same).any() else 0.3
    rho_c = float(np.nanmean(corr[off & same]))
    rho_g = float(np.clip(rho_g, 0.0, 0.8))
    return rho_g, float(np.clip(max(rho_c, rho_g), rho_g, 0.9))


def programme_samples(silver: pd.DataFrame, programmes: pd.DataFrame, year: int, week: int,
                      model: str, n: int = config.N_SAMPLES, seed: int = config.SEED) -> dict[str, np.ndarray]:
    snap = pipeline.snapshot(silver, year, week)
    fn = MODELS[model]
    rho_g, rho_c = shock_correlation(snap, year)
    rng = np.random.default_rng([seed, year, week])
    z_group = rng.standard_normal(n)
    z_campus = {c: rng.standard_normal(n) for c in sorted(programmes.campus.unique())}
    out = {}
    for p in programmes.itertuples():
        z = (np.sqrt(rho_g) * z_group + np.sqrt(rho_c - rho_g) * z_campus[p.campus]
             + np.sqrt(1 - rho_c) * rng.standard_normal(n))
        ctx = Context(
            programme=snap[snap.programme_id == p.programme_id],
            campus=snap[snap.campus == p.campus],
            year=year, week=week, intake=int(p.sanctioned_intake),
        )
        out[p.programme_id] = fn(ctx, z)
    return out


def summarise(samples: np.ndarray, intake: int, target_fill: float) -> dict:
    q = np.quantile(samples, QUANTILES)
    target = target_fill * intake
    return {
        "expected": float(samples.mean()),
        "q05": float(q[0]), "q25": float(q[1]), "median": float(q[2]), "q75": float(q[3]), "q95": float(q[4]),
        "p_meet_target": float((samples >= target - 1e-9).mean()),
        "p_full": float((samples >= intake).mean()),
        "expected_shortfall_vs_target": float(np.maximum(target - samples, 0).mean()),
        "intake": intake, "target_fill": target_fill,
    }


def forecast(silver: pd.DataFrame, programmes: pd.DataFrame, year: int, week: int, model: str) -> dict:
    samples = programme_samples(silver, programmes, year, week, model)
    snap = pipeline.snapshot(silver, year, week)
    rows = []
    for p in programmes.itertuples():
        s = samples[p.programme_id]
        cur = snap[(snap.programme_id == p.programme_id) & (snap.admission_year == year)]
        dq = quality.score_programme(snap[snap.programme_id == p.programme_id], int(p.sanctioned_intake), year, week)
        hist = snap[(snap.programme_id == p.programme_id) & (snap.admission_year < year)]
        base_rate = hist.groupby("admission_year").enrolled_cum.max()
        rows.append({
            "programme_id": p.programme_id, "programme": p.programme, "institution": p.institution,
            "campus": p.campus, "intake_source": p.intake_source,
            "enrolled_to_date": int(cur.enrolled_cum.max()) if len(cur) else 0,
            "applications_to_date": int(cur.applications_cum.max()) if len(cur) else 0,
            "base_rate_fill": float((base_rate / p.sanctioned_intake).tail(3).mean()) if len(base_rate) else None,
            "data_quality": dq,
            **summarise(s, int(p.sanctioned_intake), float(p.target_fill)),
        })
    rollups = {}
    for level, keys in (("campus", programmes.campus.unique()), ("group", ["SGI"])):
        for k in keys:
            ids = programmes.programme_id if level == "group" else programmes[programmes.campus == k].programme_id
            sub = programmes[programmes.programme_id.isin(ids)]
            total = np.sum([samples[i] for i in ids], axis=0)
            intake = int(sub.sanctioned_intake.sum())
            target_fill = float((sub.sanctioned_intake * sub.target_fill).sum() / intake)
            rollups[f"{level}:{k}"] = summarise(total, intake, target_fill)
    return {"year": year, "week": week, "model": model, "programmes": rows, "rollups": rollups,
            "samples": samples}
