import pytest

from sgi_apex.decisions import register

BASE = {"decision_id": "D1", "problem": "p", "options": ["a", "b"], "recommended_action": "a",
        "decision_owner": "DG", "deadline": "2026-06-17"}


def test_append_only_lifecycle(tmp_path):
    path = tmp_path / "r.jsonl"
    register.propose(BASE, path)
    register.decide("D1", "a", "Chairman", path)
    register.close("D1", "filled 58/60", "none", "worked", "GOOD", path)
    assert len(register.events(path)) == 3
    assert register.current(path)["D1"]["status"] == "CLOSED"
    assert register.events(path)[0]["status"] == "PROPOSED"  # history preserved


def test_close_requires_valid_classes(tmp_path):
    path = tmp_path / "r.jsonl"
    register.propose(BASE, path)
    with pytest.raises(ValueError):
        register.close("D1", "x", "bad luck", "", "GOOD", path)


def test_override_requires_reason_and_evidence(tmp_path):
    with pytest.raises(ValueError):
        register.override("HoA", "", "", "BET-LLB", 50, 55, tmp_path / "o.jsonl")
