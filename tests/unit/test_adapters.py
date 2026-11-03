import pandas as pd
import pytest

from sgi_apex.data import adapters, synthetic

KEY = ["programme_id", "admission_year", "cycle_week"]


def _as_strings(df):
    return df.astype(str)


def test_round_trip_matches_synthetic(programmes):
    raw = synthetic.generate(programmes)
    funnel, issues = adapters.parse(_as_strings(raw[adapters.CANONICAL]), programmes)
    assert not [i for i in issues if i.severity == "ERROR"]
    merged = raw.merge(funnel, on=KEY, suffixes=("", "_p"))
    assert len(merged) == len(raw) == len(funnel)
    for c in adapters.COUNTS:
        assert (merged[c] == merged[f"{c}_p"]).all()
    assert not funnel.imputed.any()


def test_aliases_names_and_dates(programmes):
    raw = pd.DataFrame({
        "Course Name": ["B.Ed", "B.Ed", "mba"],
        "Campus": ["Siwan", "Siwan", ""],
        "Report Date": ["01/04/2025", "16/04/2025", "16/04/2025"],
        "Enquiries": ["10", "1,020", "5"], "Forms": ["2", "30", "1"], "Admitted": ["0", "12", "0"],
    })
    funnel, _ = adapters.parse(raw, programmes, live_year=2025)
    bed = funnel[funnel.programme_id == "SIW-BED"].set_index("cycle_week")
    assert list(bed.index) == [0, 1, 2]  # 16 Apr = week 2, live year stops at last observed week
    assert bed.loc[1, "enrolled_cum"] == 0 and bed.loc[1, "imputed"]  # carried forward, flagged
    assert bed.loc[2, "enquiries_cum"] == 1020
    assert "BET-MBA" in set(funnel.programme_id)  # unique name resolves without campus


def test_closed_cycle_extended_to_final_week(programmes):
    raw = pd.DataFrame({"programme_id": ["SIW-BED"] * 2, "admission_year": ["2024"] * 2, "cycle_week": ["0", "20"],
                        "enquiries_cum": ["5", "300"], "applications_cum": ["1", "120"], "enrolled_cum": ["0", "90"]})
    funnel, issues = adapters.parse(raw, programmes, live_year=2026)
    assert funnel.cycle_week.max() == 26 and funnel.enrolled_cum.iloc[-1] == 90
    checks = {i.check for i in issues}
    assert {"gap_filled", "incomplete_cycle", "short_history"} <= checks


@pytest.mark.parametrize("mutate, check", [
    (lambda d: d.assign(programme_id=d.programme_id.where(d.index > 0, "NOPE")), "unknown_programme"),
    (lambda d: d.assign(enrolled_cum=d.enrolled_cum.where(d.index > 0, "-3")), "bad_number"),
    (lambda d: d.assign(cycle_week=d.cycle_week.where(d.index > 0, "40")), "week_range"),
    (lambda d: pd.concat([d, d.iloc[[5]].assign(enrolled_cum="999")]), "conflicting_duplicate"),
    (lambda d: d.drop(columns="enrolled_cum"), "schema"),
])
def test_blocking_errors(programmes, mutate, check):
    raw = _as_strings(synthetic.generate(programmes)[adapters.CANONICAL].head(60)).reset_index(drop=True)
    with pytest.raises(adapters.IngestError) as e:
        adapters.parse(mutate(raw), programmes)
    assert check in {i.check for i in e.value.issues}


def test_warnings_pass_through(programmes):
    raw = synthetic.generate(programmes)[adapters.CANONICAL]
    raw = raw[raw.programme_id == "SIW-BED"].copy()
    hit = (raw.admission_year == 2020) & (raw.cycle_week == 26)
    raw.loc[hit, "enrolled_cum"] = 500  # above intake and above applications
    _funnel, issues = adapters.parse(_as_strings(raw), programmes)
    checks = {i.check for i in issues if i.severity == "WARN"}
    assert {"over_intake", "funnel_inverted"} <= checks
    assert "programme_absent" in {i.check for i in issues if i.severity == "INFO"}


def test_reconcile_finals(programmes):
    raw = synthetic.generate(programmes)
    funnel, _ = adapters.parse(_as_strings(raw[adapters.CANONICAL]), programmes)
    finals = funnel.groupby(["programme_id", "admission_year"]).enrolled_cum.max().rename("final_enrolled").reset_index()
    assert [i.check for i in adapters.reconcile_finals(funnel, finals, programmes)] == ["finals_reconciled"]
    finals.loc[0, "final_enrolled"] += 5
    issues = adapters.reconcile_finals(funnel, finals, programmes)
    assert [i.check for i in issues] == ["finals_mismatch"]


def test_imputed_weeks_lower_completeness(programmes):
    from sgi_apex.data import pipeline, quality
    raw = synthetic.generate(programmes)[adapters.CANONICAL]
    raw = raw[(raw.programme_id == "SIW-BED") & (raw.cycle_week % 2 == 0)]
    funnel, _ = adapters.parse(_as_strings(raw), programmes)
    snap = pipeline.snapshot(funnel.assign(source="export:test"), 2026, 10)
    s = quality.score_programme(snap, 100, 2026, 10)
    assert s["completeness"] == pytest.approx(6 / 11)
