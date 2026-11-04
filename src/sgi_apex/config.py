"""Paths and run-wide constants. Everything that defines a run lives here."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIGS = ROOT / "configs"
DATA = ROOT / "data"
BRONZE = DATA / "bronze"
SILVER = DATA / "silver"
GOLD = DATA / "gold"
MASTER = DATA / "master"
ARTIFACTS = ROOT / "artifacts"
FORECASTS = ARTIFACTS / "forecasts"
BACKTESTS = ARTIFACTS / "backtests"
DECISIONS = ARTIFACTS / "decisions"
SITE = ROOT / "site"

# Admission cycle: week 0 = 1 April, week 26 = end of September.
CYCLE_WEEKS = 26
CYCLE_START_MONTH_DAY = (4, 1)

# Demo replay: history 2017-2025, prospective cycle 2026 viewed mid-cycle.
FIRST_YEAR = 2017
LIVE_YEAR = 2026
LIVE_AS_OF_WEEK = 10

# Forecast protocol (docs/forecasting_protocol.md).
VALIDATION_YEARS = (2020, 2021, 2022, 2023, 2024)  # champion selection
LOCKBOX_YEARS = (2025,)  # evaluated once, never tuned against
BACKTEST_WEEKS = (2, 6, 10, 14, 18, 22)

N_SAMPLES = 4000
SEED = 20261103

# Synthetic-data flag shown everywhere a number appears. Set to "REAL" by a run on an ingested export.
DATA_MODE = "SYNTHETIC_DEMO"


def set_output_root(root: Path) -> None:
    """Redirect every run output (lockbox, register, reports, backtests, gold, site data) under ``root``.

    Real-data runs must use this so nothing lands in the committed artifacts/ or the public site/.
    """
    global ARTIFACTS, FORECASTS, BACKTESTS, DECISIONS, SITE, GOLD
    root = Path(root).resolve()
    ARTIFACTS = root / "artifacts"
    FORECASTS = ARTIFACTS / "forecasts"
    BACKTESTS = ARTIFACTS / "backtests"
    DECISIONS = ARTIFACTS / "decisions"
    SITE = root / "site"
    GOLD = root / "gold"
