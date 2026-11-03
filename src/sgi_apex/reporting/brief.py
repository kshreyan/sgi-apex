"""Chairman daily brief (PART XXXII), rendered from site data so both always agree."""

from __future__ import annotations

import json
from datetime import date

from sgi_apex import config


def _arrow(x: float) -> str:
    return "↑" if x > 0.5 else "↓" if x < -0.5 else "→"


def render(site: dict) -> str:
    m = site["meta"]
    progs = site["programmes"]
    g = site["group"]["group:SGI"]
    by_id = {p["programme_id"]: p for p in progs}
    delta = m["admissions_health"] - m["admissions_health_prev"]
    lines = [
        "SGI APEX — CHAIRMAN BRIEF",
        date.fromisoformat(m["as_of"]).strftime("%d %b %Y").upper(),
        f"DATA: {m['data_mode']} — not real SGI figures",
        "",
        "ADMISSIONS HEALTH (partial — admissions domain only)",
        f"{m['admissions_health']:.0f}/100 {_arrow(delta)}{abs(delta):.0f}",
        "",
        f"GROUP ENROLMENT FORECAST ({m['year']} cycle, week {m['week']}/{m['cycle_weeks']})",
        f"Expected: {g['expected']:.0f} of {g['intake']} seats",
        f"50% interval: {g['q25']:.0f}–{g['q75']:.0f}   90% interval: {g['q05']:.0f}–{g['q95']:.0f}",
        f"P(group meets {g['target_fill']:.0%} fill target): {g['p_meet_target']:.0%}",
        "",
        "TOP POSITIVES",
    ]
    best = [p for p in sorted(progs, key=lambda p: -p["p_change_wow"]) if p["status"] == "GREEN"][:3]
    if not best:
        lines.append("None this week.")
    for i, p in enumerate(best, 1):
        lines.append(f"{i}. {p['programme']} ({p['campus']}): P(target) {p['p_meet_target']:.0%} ({p['p_change_wow']:+.0%} WoW)")
    lines += ["", "TOP RISKS"]
    risks = [by_id[i] for i in site["attention"]][:3]
    if not risks:
        lines.append("None above threshold.")
    for i, p in enumerate(risks, 1):
        lines.append(f"{i}. {p['status']} {p['programme']} ({p['campus']}): P(target) {p['p_meet_target']:.0%}, "
                     f"expected shortfall {p['expected_shortfall_vs_target']:.0f} seats")
    lines += ["", "DECISIONS REQUIRED"]
    open_d = [d for d in site["decisions"] if d.get("status") == "PROPOSED" and d["risk"] == "RED"]
    for i, d in enumerate(open_d, 1):
        lines.append(f"{i}. {d['decision_id']}: recommend `{d['recommended_action']}` — EV ₹{d['expected_value']:,.0f} "
                     f"[ASSUMPTION-based], {d['confidence']}, owner {d['decision_owner']}, by {d['deadline']}")
    if not open_d:
        lines.append("None.")
    green = m["status_counts"].get("GREEN", 0)
    years = site["backtest"]["validation_years"]
    lines += ["", "NO ACTION REQUIRED", f"{green} programmes within normal range.", "",
              f"Champion model: {m['champion']} (selected on {years[0]}–{years[-1]} rolling-origin backtest)."]
    return "\n".join(lines)


def write(site: dict) -> str:
    text = render(site)
    out = config.ARTIFACTS / "reports"
    out.mkdir(parents=True, exist_ok=True)
    (out / f"chairman_brief_{site['meta']['as_of']}.md").write_text("```text\n" + text + "\n```\n")
    (config.SITE / "data" / "brief.txt").write_text(text + "\n")
    return text


def load_site() -> dict:
    return json.loads((config.SITE / "data" / "apex.json").read_text())
