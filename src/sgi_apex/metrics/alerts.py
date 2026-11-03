"""Exception classification (PART XII).

GREEN  normal
AMBER  executive attention
RED    chairman awareness/action
BLACK  critical legal/safety/liquidity event — never raised by the admissions engine

Thresholds require both a probability signal and a material expected
shortfall, so small programmes with one-seat noise do not page the chairman.
"""

from __future__ import annotations

import json

from sgi_apex import config

DEFAULT = {
    "red_p_below": 0.40,
    "amber_p_below": 0.75,
    "min_shortfall_seats": 3,
    "min_shortfall_share": 0.05,
}


def thresholds() -> dict:
    path = config.CONFIGS / "alerts" / "admissions.json"
    return {**DEFAULT, **(json.loads(path.read_text()) if path.exists() else {})}


def classify(row: dict, t: dict | None = None) -> str:
    t = t or thresholds()
    if row["data_quality"]["hold"]:
        return "DQ-HOLD"
    material = row["expected_shortfall_vs_target"] >= max(t["min_shortfall_seats"], t["min_shortfall_share"] * row["intake"])
    p = row["p_meet_target"]
    if p < t["red_p_below"] and material:
        return "RED"
    if p < t["amber_p_below"] and material:
        return "AMBER"
    return "GREEN"
