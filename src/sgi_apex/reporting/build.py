"""Milestone 1 closed loop, end to end.

historical admissions -> clean (silver) -> backtest & champion -> frozen live
forecast -> seat-fill alerts -> action options -> decision register ->
actual outcome -> forecast + decision evaluation -> chairman brief + site data.
"""

from __future__ import annotations

import json
import math
import re
import shutil
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from sgi_apex import config
from sgi_apex.data import pipeline
from sgi_apex.decisions import options as opt
from sgi_apex.decisions import register
from sgi_apex.entities import registry
from sgi_apex.forecasting import lockbox, scoring
from sgi_apex.forecasting.admissions import backtest, engine
from sgi_apex.metrics import alerts

TARGET = "admissions_final_enrolment"


def cycle_date(year: int, week: int) -> date:
    m, d = config.CYCLE_START_MONTH_DAY
    return date(year, m, d) + timedelta(weeks=week)


def _round(obj):
    if isinstance(obj, float):
        return None if math.isnan(obj) else round(obj, 4)  # NaN -> null keeps the JSON strict
    if isinstance(obj, dict):
        return {k: _round(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_round(v) for v in obj]
    return obj


def run_backtests(silver, programmes, validation_years=config.VALIDATION_YEARS, lockbox_years=config.LOCKBOX_YEARS,
                  horizon_week=config.LIVE_AS_OF_WEEK):
    config.BACKTESTS.mkdir(parents=True, exist_ok=True)
    val = backtest.run(silver, programmes, validation_years)
    champion, selection = backtest.select_champion(val, horizon_week=horizon_week)
    lock = backtest.run(silver, programmes, lockbox_years)
    val.to_parquet(config.BACKTESTS / "admissions_validation.parquet", index=False)
    lock.to_parquet(config.BACKTESTS / "admissions_lockbox.parquet", index=False)
    return val, lock, champion, selection


def live_forecast(silver, programmes, model, year=config.LIVE_YEAR, week=config.LIVE_AS_OF_WEEK):
    fc = engine.forecast(silver, programmes, year, week, model)
    payload = _round({"programmes": fc["programmes"], "rollups": fc["rollups"]})
    snap_hash = lockbox.data_snapshot_hash(pipeline.snapshot(silver, year, week))
    lockbox.freeze(TARGET, year, week, model, payload, snap_hash)
    return fc


def build_actions(fc, programmes, as_of: date):
    t = alerts.thresholds()
    levels = programmes.set_index("programme_id").level
    items = []
    weeks_left = config.CYCLE_WEEKS - fc["week"]
    for row in fc["programmes"]:
        status = alerts.classify(row, t)
        row["status"] = status
        if status not in ("RED", "AMBER"):
            continue
        evald = opt.evaluate(fc["samples"][row["programme_id"]], row["enrolled_to_date"], row["intake"],
                             row["target_fill"], levels[row["programme_id"]], weeks_left)
        row["actions"] = evald
        rec = next(o for o in evald["options"] if o["id"] == evald["recommended"])
        owner = "Head of Admissions" if status == "AMBER" else "Director General"
        decision = {
            "decision_id": f"ADM-{fc['year']}-{row['programme_id']}",
            "date": as_of.isoformat(),
            "problem": f"{row['programme']} ({row['campus']}) seat-fill risk: P(meet {row['target_fill']:.0%} target) = {row['p_meet_target']:.0%}",
            "options": [o["id"] for o in evald["options"]],
            "forecast": {k: row[k] for k in ("expected", "q05", "q95", "p_meet_target", "intake")},
            "assumptions": evald["basis"],
            "recommended_action": rec["id"],
            "decision_owner": owner,
            "expected_value": rec["expected_net_value_inr"],
            "risk": status,
            "confidence": evald["robustness"],
            "deadline": (as_of + timedelta(days=7)).isoformat(),
        }
        register.propose(decision)
        items.append(row)
    return items


def evaluate_loop(silver, year, week, programmes):
    """Score the frozen forecast against the realised outcome (never against a re-run)."""
    frozen = lockbox.load(TARGET, year, week)
    actual = silver[silver.admission_year == year].groupby("programme_id").enrolled_cum.max()
    if silver[silver.admission_year == year].cycle_week.max() < config.CYCLE_WEEKS:
        return {"status": "OPEN", "message": "cycle not complete; outcome pending"}
    lockbox.record_outcome(TARGET, year, week, {k: int(v) for k, v in actual.items()})
    rows = []
    for p in frozen["forecast"]["programmes"]:
        y = int(actual[p["programme_id"]])
        hit = y >= p["target_fill"] * p["intake"] - 1e-9
        rows.append({
            "programme_id": p["programme_id"], "programme": p["programme"], "campus": p["campus"],
            "forecast_median": p["median"], "q05": p["q05"], "q95": p["q95"], "q25": p["q25"], "q75": p["q75"],
            "actual": y, "intake": p["intake"], "p_meet_target": p["p_meet_target"], "hit_target": bool(hit),
            "in_50": p["q25"] <= y <= p["q75"], "in_90": p["q05"] <= y <= p["q95"],
            "brier": scoring.brier(p["p_meet_target"], hit),
            "abs_err": abs(p["median"] - y),
        })
    df = pd.DataFrame(rows)
    group_actual = int(actual.sum())
    g = frozen["forecast"]["rollups"]["group:SGI"]
    return {
        "status": "CLOSED", "frozen_at": frozen["frozen_at"], "model": frozen["model"],
        "content_hash": frozen["content_hash"][:16], "data_snapshot_hash": frozen["data_snapshot_hash"][:16],
        "programmes": rows,
        "coverage50": float(df.in_50.mean()), "coverage90": float(df.in_90.mean()),
        "brier": float(df.brier.mean()), "mae_seats": float(df.abs_err.mean()),
        "group": {"actual": group_actual, "median": g["median"], "q05": g["q05"], "q95": g["q95"],
                  "in_90": g["q05"] <= group_actual <= g["q95"]},
    }


def health_score(fc) -> float:
    """Admissions-only partial health: intake-weighted P(meet target), 0-100."""
    rows = fc["programmes"]
    w = np.array([r["intake"] for r in rows])
    p = np.array([r["p_meet_target"] for r in rows])
    return float(100 * (w * p).sum() / w.sum())


MIN_PRIOR_YEARS = 2  # closed cycles a backtest year needs behind it


def plan_real_run(silver, programmes, as_of_week=None) -> dict:
    """Live year/week and backtest years from the data itself, not from the demo constants."""
    year = int(silver.admission_year.max())
    cur = silver[silver.admission_year == year]
    observed = cur[~cur.imputed] if "imputed" in cur else cur
    week = int(observed.cycle_week.max()) if as_of_week is None else as_of_week
    if not 0 <= week <= config.CYCLE_WEEKS:
        raise SystemExit(f"as-of week {week} outside 0..{config.CYCLE_WEEKS}")
    closed = sorted(int(y) for y in silver.admission_year.unique() if y < year)
    usable = closed[MIN_PRIOR_YEARS:]
    if len(usable) < 2:
        raise SystemExit(f"need ≥{MIN_PRIOR_YEARS + 2} closed cycles before {year} to backtest; have {len(closed)} "
                         f"({closed}). Load more history.")
    live_ids = set(silver[silver.admission_year == year].programme_id)
    hist_ids = set(silver[silver.admission_year < year].programme_id)
    keep = programmes.programme_id.isin(live_ids & hist_ids)
    return {"year": year, "week": week, "lockbox_years": (usable[-1],), "validation_years": tuple(usable[:-1][-5:]),
            "programmes": programmes[keep].reset_index(drop=True),
            "excluded": sorted(set(programmes.programme_id) - set(programmes[keep].programme_id))}


def _check_private(out: Path) -> Path:
    out = Path(out).resolve()
    inside_repo = out == config.ROOT or config.ROOT in out.parents
    if inside_repo and config.DATA not in (out, *out.parents):
        raise SystemExit(f"refusing to write real-data outputs to {out}: inside the public repo. "
                         "Use a folder outside it, or under data/ (git-ignored).")
    return out


def _copy_site_shell(out: Path, real: bool) -> None:
    """Page + assets for an out-of-repo build. The data comes from the run, never from the public demo."""
    (out / "site").mkdir(parents=True, exist_ok=True)
    shutil.copytree(config.ROOT / "site" / "assets", out / "site" / "assets", dirs_exist_ok=True)
    html = (config.ROOT / "site" / "index.html").read_text()
    if real:
        html = re.sub(r'<div class="demo-banner".*?</div>', '<div class="demo-banner" role="note"><strong>Real SGI data '
                      '— confidential.</strong> Internal use only. Do not publish or forward.</div>', html, flags=re.DOTALL)
        html = html.replace("(synthetic demo data)", "(confidential internal build)")
    (out / "site" / "index.html").write_text(html)


def run(real: bool = False, out: Path | None = None, as_of_week: int | None = None) -> dict:
    """Synthetic demo (default) or a real run on the ingested silver table into a private folder."""
    reg = registry.load_registry()
    programmes = registry.load_programmes()
    problems = registry.reconcile(reg, programmes)
    if problems:
        raise SystemExit("entity reconciliation failed — group reporting blocked:\n" + "\n".join(problems))

    excluded = []
    if real:
        if out is None:
            raise SystemExit("a real-data run needs --out <private folder>")
        if not pipeline.SILVER_ADMISSIONS.exists():
            raise SystemExit("no silver table: run `sgi ingest --file <export>` first")
        silver = pd.read_parquet(pipeline.SILVER_ADMISSIONS)
        if silver.source.str.startswith("synthetic").any():
            raise SystemExit("silver table holds synthetic rows; ingest the real export first")
        out = _check_private(out)
        config.set_output_root(out)
        config.DATA_MODE = "REAL"
        plan = plan_real_run(silver, programmes, as_of_week)
        programmes, excluded = plan["programmes"], plan["excluded"]
        year, week = plan["year"], plan["week"]
        validation_years, lockbox_years = plan["validation_years"], plan["lockbox_years"]
        _copy_site_shell(out, real=True)
    else:
        if out is not None:
            config.set_output_root(out)
            _copy_site_shell(Path(out).resolve(), real=False)
        registry.write_master(reg)
        silver = pipeline.to_silver(pipeline.ingest())
        year, week = config.LIVE_YEAR, config.LIVE_AS_OF_WEEK
        validation_years, lockbox_years = config.VALIDATION_YEARS, config.LOCKBOX_YEARS
    val, lock, champion, selection = run_backtests(silver, programmes, validation_years, lockbox_years, week)
    as_of = cycle_date(year, week)

    fc = live_forecast(silver, programmes, champion, year, week)
    prev = engine.forecast(silver, programmes, year, max(week - 1, 0), champion)
    prev_map = {r["programme_id"]: r["p_meet_target"] for r in prev["programmes"]}
    for r in fc["programmes"]:
        r["p_change_wow"] = r["p_meet_target"] - prev_map[r["programme_id"]]
    items = build_actions(fc, programmes, as_of)
    loop = evaluate_loop(silver, year, week, programmes)

    curves = {}
    for pid, g in silver.groupby("programme_id"):
        curves[pid] = {int(y): gg.sort_values("cycle_week").enrolled_cum.tolist()
                       for y, gg in g.groupby("admission_year") if y >= year - 3}

    vs = backtest.summary(val)
    ls = backtest.summary(lock)
    champ_rows = val[(val.model == champion) & (val.programme_id != backtest.GROUP)]
    reliability = scoring.reliability(champ_rows.p_target.to_numpy(), champ_rows.hit_target.to_numpy().astype(float))
    status_counts = pd.Series([r["status"] for r in fc["programmes"]]).value_counts().to_dict()
    decisions = list(register.current().values())

    site = _round({
        "meta": {"data_mode": config.DATA_MODE, "as_of": as_of.isoformat(), "year": year, "week": week,
                 "cycle_weeks": config.CYCLE_WEEKS, "champion": champion, "generated": date.today().isoformat(),
                 "admissions_health": health_score(fc),
                 "admissions_health_prev": health_score(prev), "status_counts": status_counts,
                 "excluded_programmes": excluded},
        "group": fc["rollups"],
        "programmes": fc["programmes"],
        "attention": [r["programme_id"] for r in sorted(items, key=lambda r: r["p_meet_target"])],
        "curves": curves,
        "backtest": {"selection": selection, "validation": vs.to_dict("records"), "lockbox": ls.to_dict("records"),
                     "validation_group": backtest.summary(val, group=True).drop(columns=["brier", "log_loss"]).to_dict("records"),
                     "reliability": reliability, "validation_years": list(validation_years),
                     "lockbox_years": list(lockbox_years)},
        "loop": loop,
        "decisions": decisions,
        "entities": reg.to_dict("records"),
        "programme_registry": programmes.to_dict("records"),
    })
    (config.SITE / "data").mkdir(parents=True, exist_ok=True)
    (config.SITE / "data" / "apex.json").write_text(json.dumps(site, default=str, allow_nan=False))
    config.GOLD.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(fc["programmes"]).drop(columns=["data_quality", "actions"], errors="ignore").to_parquet(
        config.GOLD / f"admissions_forecast_{year}_w{week:02d}.parquet", index=False)
    return site
