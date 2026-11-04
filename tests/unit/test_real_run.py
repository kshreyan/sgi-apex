from pathlib import Path

import pytest

from sgi_apex import config
from sgi_apex.data import adapters, synthetic
from sgi_apex.reporting import build


def _real_like(programmes, drop=("BET-MPHARM",)):
    raw = synthetic.generate(programmes)[adapters.CANONICAL]
    raw = raw[~((raw.admission_year == 2026) & (raw.cycle_week > 10)) & ~raw.programme_id.isin(drop)]
    funnel, _ = adapters.parse(raw.astype(str), programmes)
    return funnel


def test_plan_derives_years_and_week_from_data(programmes):
    plan = build.plan_real_run(_real_like(programmes), programmes)
    assert (plan["year"], plan["week"]) == (2026, 10)
    assert plan["lockbox_years"] == (2025,)
    assert plan["validation_years"] == (2020, 2021, 2022, 2023, 2024)
    assert plan["excluded"] == ["BET-MPHARM"]


def test_plan_needs_enough_history(programmes):
    funnel = _real_like(programmes)
    with pytest.raises(SystemExit, match="closed cycles"):
        build.plan_real_run(funnel[funnel.admission_year >= 2023], programmes)


@pytest.mark.parametrize("out, allowed", [
    (config.ROOT / "site" / "private", False),
    (config.ROOT / "artifacts", False),
    (config.ROOT, False),
    (config.DATA / "private_run", True),
    (Path("/tmp/elsewhere"), True),
])
def test_private_output_guard(out, allowed):
    if allowed:
        assert build._check_private(out) == out.resolve()
    else:
        with pytest.raises(SystemExit, match="public repo"):
            build._check_private(out)
