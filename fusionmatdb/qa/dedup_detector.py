"""Duplicate detection for FusionMatDB records."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import MechanicalProperty, Material, IrradiationCondition

HASH_FIELDS = [
    "material_name", "dose_dpa", "irradiation_temp", "test_temp",
    "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
    "uts_mpa_irradiated", "hardness_value",
]


def _normalize_value(val) -> str:
    if val is None:
        return "null"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def compute_content_hash(record: dict) -> str:
    """SHA256 of key fields, normalized and rounded."""
    field_map = {
        "material_name": "material_name",
        "dose_dpa": "dose_dpa",
        "irradiation_temp_c": "irradiation_temp",
        "irradiation_temp": "irradiation_temp",
        "test_temp_c": "test_temp",
        "test_temp": "test_temp",
        "yield_strength_mpa_irradiated": "yield_strength_mpa_irradiated",
        "yield_strength_mpa_unirradiated": "yield_strength_mpa_unirradiated",
        "uts_mpa_irradiated": "uts_mpa_irradiated",
        "hardness_value": "hardness_value",
    }
    canonical = {}
    for src, dst in field_map.items():
        if src in record and dst not in canonical:
            canonical[dst] = record[src]
    parts = [f"{k}={_normalize_value(canonical.get(k))}" for k in HASH_FIELDS]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@dataclass
class DuplicateCluster:
    content_hash: str
    record_ids: list[int] = field(default_factory=list)
    primary_id: int | None = None


def find_exact_duplicates(session: Session) -> list[DuplicateCluster]:
    """Find records with identical content hashes."""
    props = session.query(MechanicalProperty).all()
    hash_to_ids: dict[str, list[int]] = {}
    for prop in props:
        record = {
            "material_name": prop.material.name if prop.material else None,
            "dose_dpa": prop.irradiation_condition.dose_dpa if prop.irradiation_condition else None,
            "irradiation_temp": prop.irradiation_condition.irradiation_temp if prop.irradiation_condition else None,
            "test_temp": prop.test_temp,
            "yield_strength_mpa_irradiated": prop.yield_strength_mpa_irradiated,
            "yield_strength_mpa_unirradiated": prop.yield_strength_mpa_unirradiated,
            "uts_mpa_irradiated": prop.uts_mpa_irradiated,
            "hardness_value": prop.hardness_value,
        }
        h = compute_content_hash(record)
        hash_to_ids.setdefault(h, []).append(prop.id)

    clusters = []
    for h, ids in hash_to_ids.items():
        if len(ids) > 1:
            clusters.append(DuplicateCluster(
                content_hash=h,
                record_ids=ids,
                primary_id=ids[0],
            ))
    return clusters
