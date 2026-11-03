import json

import pytest

from sgi_apex.forecasting import lockbox


def test_freeze_is_immutable(tmp_path):
    lockbox.freeze("t", 2026, 10, "m", {"x": 1}, "h", root=tmp_path)
    lockbox.freeze("t", 2026, 10, "m", {"x": 1}, "h", root=tmp_path)  # identical re-run is fine
    with pytest.raises(lockbox.LockboxError):
        lockbox.freeze("t", 2026, 10, "m", {"x": 2}, "h", root=tmp_path)


def test_tamper_detected(tmp_path):
    p = lockbox.freeze("t", 2026, 10, "m", {"x": 1}, "h", root=tmp_path)
    rec = json.loads(p.read_text())
    rec["forecast"]["x"] = 999
    p.write_text(json.dumps(rec))
    with pytest.raises(lockbox.LockboxError):
        lockbox.load("t", 2026, 10, root=tmp_path)


def test_outcome_stored_separately(tmp_path):
    p = lockbox.freeze("t", 2026, 10, "m", {"x": 1}, "h", root=tmp_path)
    before = p.read_text()
    lockbox.record_outcome("t", 2026, 10, {"x": 5}, root=tmp_path)
    assert p.read_text() == before
