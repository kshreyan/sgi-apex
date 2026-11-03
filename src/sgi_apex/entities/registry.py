"""Entity registry: the single source of organisational truth.

Group-level reporting is blocked until every entity referenced by a programme
resolves to a registry record (PART II: never build group reporting on
unreconciled identities).
"""

from __future__ import annotations

import pandas as pd

from sgi_apex import config

REQUIRED_COLUMNS = [
    "entity_id", "legal_name", "brand_name", "entity_type", "parent_entity",
    "campus", "district", "state", "legal_structure", "established_date",
    "regulators", "affiliating_body", "approved_programmes", "sanctioned_intake",
    "official_website", "current_status", "verification_source", "verified_at",
    "confidence",
]
CONFIDENCE_LEVELS = {"high", "medium", "low", "none"}


class RegistryError(ValueError):
    pass


def load_registry() -> pd.DataFrame:
    df = pd.read_csv(config.CONFIGS / "entities" / "entity_registry.csv", dtype=str).fillna("")
    validate_registry(df)
    return df


def load_programmes() -> pd.DataFrame:
    df = pd.read_csv(config.CONFIGS / "entities" / "programmes.csv")
    return df


def validate_registry(df: pd.DataFrame) -> None:
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise RegistryError(f"registry missing columns: {missing}")
    if df["entity_id"].duplicated().any():
        raise RegistryError(f"duplicate entity_id: {df.loc[df.entity_id.duplicated(), 'entity_id'].tolist()}")
    bad = set(df["confidence"]) - CONFIDENCE_LEVELS
    if bad:
        raise RegistryError(f"invalid confidence values: {bad}")
    ids = set(df["entity_id"])
    for _, row in df.iterrows():
        parent = row["parent_entity"].split(" ")[0]
        if parent and parent not in ids:
            raise RegistryError(f"{row.entity_id}: parent {parent!r} not in registry")


def reconcile(registry: pd.DataFrame, programmes: pd.DataFrame) -> list[str]:
    """Return blocking problems; empty list means group roll-ups are allowed."""
    problems = []
    ids = set(registry["entity_id"])
    for pid, eid in zip(programmes["programme_id"], programmes["entity_id"]):
        if eid not in ids:
            problems.append(f"programme {pid} references unknown entity {eid}")
            continue
        conf = registry.loc[registry.entity_id == eid, "confidence"].iloc[0]
        if conf in ("none", "low"):
            problems.append(f"programme {pid} rolls up to low-confidence entity {eid}")
    if programmes["programme_id"].duplicated().any():
        problems.append("duplicate programme_id")
    return problems


def write_master(registry: pd.DataFrame) -> None:
    config.MASTER.mkdir(parents=True, exist_ok=True)
    registry.to_parquet(config.MASTER / "entity_registry.parquet", index=False)


def unverified_items(registry: pd.DataFrame) -> pd.DataFrame:
    mask = registry.apply(lambda r: r.str.contains("UNVERIFIED|CONFLICT", regex=True).any(), axis=1)
    return registry.loc[mask, ["entity_id", "legal_name", "confidence"]]
