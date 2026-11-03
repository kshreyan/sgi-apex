"""Real admissions-export adapter: file -> canonical weekly funnel + validation report.

Accepts the admissions office's CSV/Excel export in either shape:
  * weekly:  programme, admission_year, cycle_week, cumulative counts
  * dated:   programme, as_of_date, cumulative counts (week derived from 1 April)

Nothing is silently fixed. Every rule that changes or rejects data adds an Issue;
ERROR issues block ingestion, WARN issues pass through and show in the report
and in the per-forecast data-quality score.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from sgi_apex import config

COUNTS = ["enquiries_cum", "applications_cum", "enrolled_cum"]
CANONICAL = ["programme_id", "admission_year", "cycle_week", *COUNTS]
MAPPING_FILE = config.CONFIGS / "data" / "admissions_export.json"
MIN_HISTORY_YEARS = 5


@dataclass
class Issue:
    severity: str  # ERROR | WARN | INFO
    check: str
    detail: str
    rows: int = 0
    programme_id: str = ""
    admission_year: int | None = None


class IngestError(ValueError):
    def __init__(self, issues: list[Issue]):
        self.issues = issues
        errors = [i for i in issues if i.severity == "ERROR"]
        super().__init__(f"{len(errors)} blocking issue(s): " + "; ".join(f"{i.check}: {i.detail}" for i in errors[:5]))


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9.]", "", str(s).lower())


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_file(path: Path) -> pd.DataFrame:
    path = Path(path)
    if path.suffix.lower() in (".xlsx", ".xls"):
        try:
            return pd.read_excel(path, dtype=str)
        except ImportError as e:
            raise SystemExit("Excel export needs openpyxl: pip install -e '.[excel]' (or save as CSV)") from e
    return pd.read_csv(path, dtype=str, skipinitialspace=True)


def load_mapping() -> dict:
    return json.loads(MAPPING_FILE.read_text())


def _rename(raw: pd.DataFrame, mapping: dict) -> pd.DataFrame:
    lookup = {_key(alias): canon for canon, aliases in mapping["columns"].items() for alias in aliases}
    renamed = {c: lookup[_key(c)] for c in raw.columns if _key(c) in lookup}
    return raw.rename(columns=renamed)[list(dict.fromkeys(renamed.values()))]


def _programme_lookup(programmes: pd.DataFrame, mapping: dict) -> dict[str, str]:
    lut: dict[str, str] = {}
    for p in programmes.itertuples():
        lut[_key(p.programme_id)] = p.programme_id
        lut[f"{_key(p.programme)}|{_key(p.campus)}"] = p.programme_id
    names = programmes.groupby(programmes.programme.map(_key)).programme_id.agg(list)
    lut.update({name: ids[0] for name, ids in names.items() if len(ids) == 1})  # unambiguous name only
    for alias, pid in mapping.get("programme_aliases", {}).items():
        if not alias.startswith("_"):
            name, _, campus = alias.partition("|")
            lut[f"{_key(name)}|{_key(campus)}" if campus else _key(name)] = pid
    return lut


def _resolve_programmes(df: pd.DataFrame, programmes: pd.DataFrame, mapping: dict, issues: list[Issue]):
    lut = _programme_lookup(programmes, mapping)
    if "programme_id" in df:
        raw = df.programme_id.fillna("")
        resolved = raw.map(lambda v: lut.get(_key(v)))
    elif "programme" in df:
        raw = df.programme.fillna("") + ("|" + df.campus.fillna("") if "campus" in df else "")
        def find(v):
            name, _, campus = v.partition("|")
            return lut.get(f"{_key(name)}|{_key(campus)}") or lut.get(_key(name))
        resolved = raw.map(find)
    else:
        issues.append(Issue("ERROR", "schema", "no programme_id or programme column"))
        return df
    bad = resolved.isna()
    for value, n in raw[bad].value_counts().items():
        issues.append(Issue("ERROR", "unknown_programme",
                            f"'{value}' matches nothing in programmes.csv or programme_aliases", int(n)))
    df = df.assign(programme_id=resolved)
    return df[~bad]


def _to_int(df: pd.DataFrame, cols: list[str], issues: list[Issue]) -> pd.DataFrame:
    for c in cols:
        num = pd.to_numeric(df[c].astype(str).str.replace(",", "").str.strip(), errors="coerce")
        bad = num.isna() | (num < 0) | (num != np.floor(num))
        if bad.any():
            issues.append(Issue("ERROR", "bad_number", f"{c}: {int(bad.sum())} blank, negative or fractional value(s), "
                                f"e.g. {df.loc[bad, c].iloc[0]!r}", int(bad.sum())))
        df = df.assign(**{c: num})
    return df


def _derive_weeks(df: pd.DataFrame, issues: list[Issue]) -> pd.DataFrame:
    """as_of_date -> (admission_year, cycle_week); latest snapshot in a week wins."""
    d = pd.to_datetime(df.as_of_date, errors="coerce", dayfirst=True)
    if d.isna().any():
        issues.append(Issue("ERROR", "bad_date", f"{int(d.isna().sum())} unparseable as_of_date value(s)",
                            int(d.isna().sum())))
    df = df.assign(_date=d)[d.notna()]
    if "admission_year" not in df:
        df = df.assign(admission_year=df._date.dt.year)
    m, dd = config.CYCLE_START_MONTH_DAY
    start = pd.to_datetime({"year": df.admission_year.astype(int), "month": m, "day": dd})
    week = ((df._date - start).dt.days // 7).clip(0, config.CYCLE_WEEKS)
    df = df.assign(cycle_week=week).sort_values("_date")
    return df.drop_duplicates(["programme_id", "admission_year", "cycle_week"], keep="last").drop(columns="_date")


def _conform(df: pd.DataFrame, live_year: int, issues: list[Issue]) -> pd.DataFrame:
    """Complete the weekly grid. Gaps carry the last cumulative value forward (never backward)."""
    out = []
    for (pid, year), g in df.groupby(["programme_id", "admission_year"]):
        g = g.set_index("cycle_week").sort_index()
        last = config.CYCLE_WEEKS if year < live_year else int(g.index.max())
        grid = g.reindex(range(last + 1))
        imputed = grid[COUNTS[0]].isna()
        grid[COUNTS] = grid[COUNTS].ffill().fillna(0)
        if g.index.min() > 0:
            issues.append(Issue("WARN", "leading_gap", f"no data before week {g.index.min()}; earlier weeks set to 0",
                                int(g.index.min()), pid, int(year)))
        n_mid = int(imputed.sum()) - int(g.index.min())
        if n_mid > 0:
            issues.append(Issue("WARN", "gap_filled", f"{n_mid} missing week(s) carried forward from the prior week",
                                n_mid, pid, int(year)))
        out.append(grid.assign(programme_id=pid, admission_year=int(year), imputed=imputed.to_numpy())
                   .rename_axis("cycle_week").reset_index())
    res = pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=[*CANONICAL, "imputed"])
    return res.astype({c: int for c in ["admission_year", "cycle_week", *COUNTS]})


def _check_values(df: pd.DataFrame, programmes: pd.DataFrame, live_year: int, issues: list[Issue]) -> None:
    intake = programmes.set_index("programme_id").sanctioned_intake
    for (pid, year), g in df.groupby(["programme_id", "admission_year"]):
        g = g.sort_values("cycle_week")
        for c in COUNTS:
            drops = int((g[c].diff() < 0).sum())
            if drops:
                issues.append(Issue("WARN", "non_monotone", f"{c} falls in {drops} week(s) (withdrawal or "
                                    "re-keying?); lowers data-quality score", drops, pid, int(year)))
        n = int((g.enrolled_cum > g.applications_cum).sum())
        if n:
            issues.append(Issue("WARN", "funnel_inverted", "enrolled exceeds applications", n, pid, int(year)))
        peak = int(g.enrolled_cum.max())
        if peak > intake[pid]:
            issues.append(Issue("WARN", "over_intake", f"enrolled {peak} > sanctioned intake {intake[pid]} — "
                                "check intake config or regulator compliance", 1, pid, int(year)))
        if year < live_year and g.cycle_week.max() < config.CYCLE_WEEKS:
            issues.append(Issue("WARN", "incomplete_cycle", f"closed cycle ends at week {g.cycle_week.max()}; "
                                "final enrolment assumed = last value", 1, pid, int(year)))
    hist = df[df.admission_year < live_year].groupby("programme_id").admission_year.nunique()
    for pid in programmes.programme_id:
        n = int(hist.get(pid, 0))
        if pid not in set(df.programme_id):
            issues.append(Issue("INFO", "programme_absent", "not in export", 0, pid))
        elif n < MIN_HISTORY_YEARS:
            issues.append(Issue("WARN", "short_history", f"{n} closed cycle(s); backtest needs {MIN_HISTORY_YEARS}",
                                n, pid))


def parse(raw: pd.DataFrame, programmes: pd.DataFrame, live_year: int = config.LIVE_YEAR,
          mapping: dict | None = None) -> tuple[pd.DataFrame, list[Issue]]:
    """Raw export -> canonical complete weekly grid. Raises IngestError on any ERROR."""
    mapping = mapping or load_mapping()
    issues: list[Issue] = []
    df = _rename(raw, mapping)
    missing = [c for c in COUNTS if c not in df]
    if "cycle_week" not in df and "as_of_date" not in df:
        missing.append("cycle_week or as_of_date")
    if "cycle_week" in df and "admission_year" not in df:
        missing.append("admission_year")
    if missing:
        raise IngestError([Issue("ERROR", "schema", f"missing column(s): {', '.join(missing)}")])

    df = _resolve_programmes(df, programmes, mapping, issues)
    df = _to_int(df, COUNTS, issues)
    if "cycle_week" in df:
        df = _to_int(df, ["admission_year", "cycle_week"], issues)
        out = (df.cycle_week < 0) | (df.cycle_week > config.CYCLE_WEEKS)
        if out.any():
            issues.append(Issue("ERROR", "week_range", f"cycle_week outside 0..{config.CYCLE_WEEKS}", int(out.sum())))
    else:
        if "admission_year" in df:
            df = _to_int(df, ["admission_year"], issues)
        df = _derive_weeks(df, issues)
    if any(i.severity == "ERROR" for i in issues):
        raise IngestError(issues)

    key = ["programme_id", "admission_year", "cycle_week"]
    df = df[CANONICAL]
    exact = df.duplicated()
    if exact.any():
        issues.append(Issue("WARN", "duplicate_rows", "identical rows dropped", int(exact.sum())))
    df = df[~exact]
    clash = df[df.duplicated(key, keep=False)]
    for (pid, year, week), _ in clash.groupby(key):
        issues.append(Issue("ERROR", "conflicting_duplicate", f"week {week} reported with different counts",
                            2, pid, int(year)))
    if clash.size:
        raise IngestError(issues)

    df = df.astype({c: int for c in CANONICAL[1:]})
    _check_values(df, programmes, live_year, issues)
    return _conform(df, live_year, issues), issues


def reconcile_finals(funnel: pd.DataFrame, finals: pd.DataFrame, programmes: pd.DataFrame,
                     tol: int = 1) -> list[Issue]:
    """Plan exit criterion: silver final enrolment == finance/registrar finals per institution within ±tol."""
    finals = finals.rename(columns={c: c.strip().lower() for c in finals.columns})
    need = {"programme_id", "admission_year", "final_enrolled"}
    if not need <= set(finals.columns):
        return [Issue("ERROR", "schema", f"finals file needs columns {sorted(need)}")]
    finals = finals.astype({"admission_year": int, "final_enrolled": int})
    ours = funnel.groupby(["programme_id", "admission_year"]).enrolled_cum.max().rename("silver").reset_index()
    m = finals.merge(ours, on=["programme_id", "admission_year"], how="left")
    m = m.merge(programmes[["programme_id", "entity_id"]], on="programme_id", how="left")
    issues = []
    for r in m[m.silver.isna()].itertuples():
        issues.append(Issue("ERROR", "finals_unmatched", "finals row has no funnel data", 1,
                            r.programme_id, r.admission_year))
    inst = m.dropna(subset=["silver"]).groupby(["entity_id", "admission_year"])[["final_enrolled", "silver"]].sum()
    for (eid, year), r in inst.iterrows():
        diff = int(r.silver - r.final_enrolled)
        if abs(diff) > tol:
            issues.append(Issue("ERROR", "finals_mismatch", f"{eid}: funnel {int(r.silver)} vs finals "
                                f"{int(r.final_enrolled)} (diff {diff:+d}, tolerance ±{tol})", 1, "", int(year)))
    if not issues:
        issues.append(Issue("INFO", "finals_reconciled", f"{len(inst)} institution-years within ±{tol}"))
    return issues


def report_markdown(path: Path, sha: str, funnel: pd.DataFrame, issues: list[Issue], dq: pd.DataFrame | None) -> str:
    counts = pd.Series([i.severity for i in issues]).value_counts().to_dict() if issues else {}
    lines = [
        f"# Admissions ingest report — {date.today().isoformat()}",
        "",
        f"- File: `{Path(path).name}` (sha256 `{sha[:12]}`)",
        (f"- Rows after conform: {len(funnel):,} · programmes {funnel.programme_id.nunique()} · "
        f"years {funnel.admission_year.min()}–{funnel.admission_year.max()} · imputed weeks {int(funnel.imputed.sum())}"),
        f"- Issues: {counts.get('ERROR', 0)} error · {counts.get('WARN', 0)} warn · {counts.get('INFO', 0)} info",
        "",
        "| severity | check | programme | year | rows | detail |",
        "|---|---|---|---|---|---|",
    ]
    order = {"ERROR": 0, "WARN": 1, "INFO": 2}
    for i in sorted(issues, key=lambda i: (order[i.severity], i.check, i.programme_id)):
        lines.append(f"| {i.severity} | {i.check} | {i.programme_id} | {i.admission_year or ''} | {i.rows} | {i.detail} |")
    if dq is not None and len(dq):
        lines += ["", "## Data-quality score at latest week (hold < 0.80)", "", "```text",
                  dq.to_string(index=False), "```"]
    return "\n".join(lines) + "\n"


def issues_frame(issues: list[Issue]) -> pd.DataFrame:
    return pd.DataFrame([asdict(i) for i in issues])
