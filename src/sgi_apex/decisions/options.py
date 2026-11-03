"""Action options for an at-risk programme, compared by simulation.

Each option's uplift is an explicit ASSUMPTION range from
configs/models/admissions_interventions.json. Robustness is tested by
re-ranking with every option at the low end, then at the high end of its range
(PART LXXXVII): same winner in all three -> ROBUST, in two -> MODERATE, else FRAGILE.
"""

from __future__ import annotations

import json

import numpy as np

from sgi_apex import config


def _load():
    opts = json.loads((config.CONFIGS / "models" / "admissions_interventions.json").read_text())["options"]
    econ = json.loads((config.CONFIGS / "metrics" / "unit_economics.json").read_text())["contribution_per_seat_inr"]
    return opts, econ


def _simulate(samples, enrolled, intake, target, uplift, rng):
    remaining = np.maximum(samples - enrolled, 0)
    new = np.minimum(np.round(enrolled + remaining * (1 + uplift)), intake)
    return new, float((new >= target - 1e-9).mean())


def evaluate(samples: np.ndarray, enrolled: int, intake: int, target_fill: float, level: str,
             weeks_left: int, seed: int = config.SEED) -> dict:
    opts, econ = _load()
    value_per_seat = econ.get(level, 50000)
    target = target_fill * intake
    base_mean = float(samples.mean())
    results = []
    winners = []
    for mode in ("draw", "low", "high"):
        rng = np.random.default_rng(seed)
        scored = []
        for o in opts:
            if weeks_left < o["min_weeks_left"]:
                continue
            if mode == "draw":
                u = rng.uniform(o["uplift_low"], o["uplift_high"], len(samples))
            else:
                u = o[f"uplift_{mode}"]
            new, p = _simulate(samples, enrolled, intake, target, u, rng)
            added = float(new.mean()) - base_mean
            net = added * value_per_seat - o["cost_inr"]
            scored.append((o, added, p, net, new))
        winners.append(max(scored, key=lambda s: s[3])[0]["id"])
        if mode == "draw":
            for o, added, p, net, new in scored:
                results.append({
                    "id": o["id"], "label": o["label"], "cost_inr": o["cost_inr"],
                    "assumed_uplift": [o["uplift_low"], o["uplift_high"]],
                    "added_enrolments_mean": round(added, 1),
                    "added_enrolments_p10_p90": [round(float(np.quantile(new - samples, q)), 1) for q in (0.1, 0.9)],
                    "p_meet_target": round(p, 3),
                    "expected_net_value_inr": round(net),
                    "cost_per_added_enrolment_inr": round(o["cost_inr"] / added) if added > 0.5 else None,
                })
    best = winners[0]
    agree = winners.count(best)
    robustness = {3: "ROBUST", 2: "MODERATE"}.get(agree, "FRAGILE")
    return {
        "options": sorted(results, key=lambda r: -r["expected_net_value_inr"]),
        "recommended": best,
        "robustness": robustness,
        "winners_low_draw_high": {"draw": winners[0], "low": winners[1], "high": winners[2]},
        "value_per_seat_inr": value_per_seat,
        "basis": "ASSUMPTION: uplift priors + PLACEHOLDER unit economics",
    }
