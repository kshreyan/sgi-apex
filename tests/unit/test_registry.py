import pandas as pd
import pytest

from sgi_apex.entities import registry


def test_registry_valid_and_reconciles(programmes):
    reg = registry.load_registry()
    assert registry.reconcile(reg, programmes) == []


def test_unverified_hospital_is_never_high_confidence():
    reg = registry.load_registry().set_index("entity_id")
    assert reg.loc["HOSP-CHAKIA", "confidence"] == "none"
    assert "UNVERIFIED" in reg.loc["HOSP-CHAKIA", "legal_name"]


def test_duplicate_entity_rejected():
    reg = registry.load_registry()
    with pytest.raises(registry.RegistryError):
        registry.validate_registry(pd.concat([reg, reg.head(1)]))


def test_programme_on_low_confidence_entity_blocks_rollup(programmes):
    reg = registry.load_registry()
    bad = programmes.copy()
    bad.loc[0, "entity_id"] = "HOSP-CHAKIA"
    assert registry.reconcile(reg, bad)
