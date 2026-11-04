"""Decision register (PART XIV) and human overrides (PART LXXXVI).

Append-only JSON-lines files. A decision is never edited in place: closing a
decision appends a new event with the outcome and postmortem, so the state at
the time of the decision is always recoverable.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from sgi_apex import config

FIELDS = ["decision_id", "date", "problem", "options", "forecast", "assumptions", "recommended_action",
          "decision_taken", "decision_owner", "expected_value", "risk", "confidence", "deadline",
          "actual_outcome", "postmortem"]
FAILURE_CLASSES = {"data error", "model error", "assumption error", "execution failure", "external shock",
                   "random variance", "none"}


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def register_path() -> Path:
    return config.DECISIONS / "register.jsonl"


def overrides_path() -> Path:
    return config.DECISIONS / "overrides.jsonl"


def _append(path: Path | None, rec: dict) -> None:
    path = path or register_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def events(path: Path | None = None) -> list[dict]:
    path = path or register_path()
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def current(path: Path | None = None) -> dict[str, dict]:
    """Fold the event log into the latest state per decision_id."""
    state: dict[str, dict] = {}
    for e in events(path):
        state.setdefault(e["decision_id"], {}).update({k: v for k, v in e.items() if k != "event"})
    return state


def propose(rec: dict, path: Path | None = None) -> dict:
    missing = [f for f in ("decision_id", "problem", "options", "recommended_action", "decision_owner", "deadline") if f not in rec]
    if missing:
        raise ValueError(f"decision missing {missing}")
    if rec["decision_id"] in current(path):
        return current(path)[rec["decision_id"]]
    full = {f: None for f in FIELDS} | rec | {"event": "proposed", "date": rec.get("date") or _now(), "status": "PROPOSED"}
    _append(path, full)
    return full


def decide(decision_id: str, taken: str, by: str, path: Path | None = None) -> None:
    _append(path, {"decision_id": decision_id, "event": "decided", "decision_taken": taken,
                   "decided_by": by, "decided_at": _now(), "status": "DECIDED"})


def close(decision_id: str, actual_outcome: str, failure_class: str, postmortem: str,
          decision_quality: str, path: Path | None = None) -> None:
    """decision_quality judges the decision given information at the time (PART LXXXIV), not the outcome."""
    if failure_class not in FAILURE_CLASSES:
        raise ValueError(f"failure_class must be one of {sorted(FAILURE_CLASSES)}")
    if decision_quality not in {"GOOD", "POOR"}:
        raise ValueError("decision_quality must be GOOD or POOR")
    _append(path, {"decision_id": decision_id, "event": "closed", "actual_outcome": actual_outcome,
                   "failure_class": failure_class, "postmortem": postmortem,
                   "decision_quality": decision_quality, "closed_at": _now(), "status": "CLOSED"})


def override(person: str, reason: str, evidence: str, target: str, original: float, new_assumption: float,
             path: Path | None = None) -> dict:
    rec = {"timestamp": _now(), "person": person, "reason": reason, "evidence": evidence, "target": target,
           "original_forecast": original, "new_assumption": new_assumption}
    if not reason.strip() or not evidence.strip():
        raise ValueError("overrides require a reason and evidence")
    _append(path or overrides_path(), rec)
    return rec
