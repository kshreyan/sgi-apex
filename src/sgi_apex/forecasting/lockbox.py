"""Prediction lockbox: forecasts are frozen before outcomes and never overwritten.

Each frozen forecast is a JSON file named ``<target>_<year>_w<week>.json``
containing the forecast, model, timestamp, data-snapshot hash and a content
hash. Actuals are stored in a separate ``.outcome.json`` file next to it so
the original prediction is physically untouched.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from sgi_apex import config


class LockboxError(RuntimeError):
    pass


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def data_snapshot_hash(snap: pd.DataFrame) -> str:
    cols = ["programme_id", "admission_year", "cycle_week", "enrolled_cum", "applications_cum"]
    return hashlib.sha256(pd.util.hash_pandas_object(snap[cols], index=False).values.tobytes()).hexdigest()


def path_for(target: str, year: int, week: int, root: Path | None = None) -> Path:
    return (root or config.FORECASTS) / f"{target}_{year}_w{week:02d}.json"


def freeze(target: str, year: int, week: int, model: str, payload: dict, snapshot_hash: str,
           root: Path | None = None) -> Path:
    path = path_for(target, year, week, root)
    if path.exists():
        existing = json.loads(path.read_text())
        if existing["content_hash"] == _hash(payload):
            return path  # idempotent re-run of an identical forecast
        raise LockboxError(f"{path.name} is frozen; refusing to overwrite a locked forecast")
    record = {
        "target": target, "year": year, "week": week, "model": model,
        "frozen_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "data_snapshot_hash": snapshot_hash, "data_mode": config.DATA_MODE,
        "forecast": payload, "content_hash": _hash(payload),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record, indent=2, default=str))
    return path


def load(target: str, year: int, week: int, root: Path | None = None) -> dict:
    rec = json.loads(path_for(target, year, week, root).read_text())
    if rec["content_hash"] != _hash(rec["forecast"]):
        raise LockboxError(f"{target}_{year}_w{week}: content hash mismatch (tampered)")
    return rec


def record_outcome(target: str, year: int, week: int, actuals: dict, root: Path | None = None) -> Path:
    out = path_for(target, year, week, root).with_suffix(".outcome.json")
    out.write_text(json.dumps({"recorded_at": datetime.now(UTC).isoformat(timespec="seconds"),
                               "actuals": actuals}, indent=2))
    return out
