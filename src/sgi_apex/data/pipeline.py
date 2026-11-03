"""Bronze -> silver -> gold for admissions.

Bronze: immutable source snapshots (one parquet per ingestion, never edited).
Silver: canonical, validated funnel table keyed by programme/year/week.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from sgi_apex import config
from sgi_apex.data import adapters, synthetic
from sgi_apex.entities import registry

SILVER_ADMISSIONS = config.SILVER / "admissions_funnel.parquet"


def ingest() -> pd.DataFrame:
    """Synthetic demo history -> bronze snapshot."""
    programmes = registry.load_programmes()
    raw = synthetic.generate(programmes)
    raw["ingestion_time"] = datetime.now(UTC).isoformat(timespec="seconds")
    config.BRONZE.mkdir(parents=True, exist_ok=True)
    raw.to_parquet(config.BRONZE / "admissions_synthetic.parquet", index=False)
    return raw


def ingest_file(path: Path, live_year: int = config.LIVE_YEAR) -> tuple[pd.DataFrame, list[adapters.Issue], str]:
    """Admissions-office export -> immutable bronze copy + canonical funnel. Raises IngestError on blocking issues."""
    programmes = registry.load_programmes()
    sha = adapters.file_sha256(path)
    raw = adapters.read_file(path)
    config.BRONZE.mkdir(parents=True, exist_ok=True)
    bronze = config.BRONZE / f"admissions_export_{sha[:16]}.parquet"
    if not bronze.exists():  # content-addressed: same bytes, same snapshot; never rewritten
        raw.assign(source_file=Path(path).name, file_sha256=sha,
                   ingestion_time=datetime.now(UTC).isoformat(timespec="seconds")).to_parquet(bronze, index=False)
    funnel, issues = adapters.parse(raw, programmes, live_year)
    funnel["source"] = f"export:{Path(path).name}@{sha[:12]}"
    return funnel, issues, sha


def to_silver(raw: pd.DataFrame) -> pd.DataFrame:
    programmes = registry.load_programmes()
    df = raw.merge(programmes[["programme_id", "entity_id", "campus", "sanctioned_intake"]], on="programme_id", how="left")
    if df.entity_id.isna().any():
        raise ValueError("bronze rows reference programmes missing from configs/entities/programmes.csv")
    df = df.drop_duplicates(["programme_id", "admission_year", "cycle_week"]).sort_values(
        ["programme_id", "admission_year", "cycle_week"]
    )
    config.SILVER.mkdir(parents=True, exist_ok=True)
    df.to_parquet(SILVER_ADMISSIONS, index=False)
    return df


def load_silver() -> pd.DataFrame:
    if not SILVER_ADMISSIONS.exists():
        to_silver(ingest())
    return pd.read_parquet(SILVER_ADMISSIONS)


def snapshot(df: pd.DataFrame, year: int, week: int) -> pd.DataFrame:
    """Everything knowable at (year, week). The only door forecasting code may use."""
    known = (df.admission_year < year) | ((df.admission_year == year) & (df.cycle_week <= week))
    return df.loc[known].copy()
