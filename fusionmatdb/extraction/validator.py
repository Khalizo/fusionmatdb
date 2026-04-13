# fusionmatdb/fusionmatdb/extraction/validator.py
"""Validate and score extracted data records."""
from __future__ import annotations

REQUIRED_FIELDS = ["material_name"]
PROPERTY_FIELDS = [
    "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
    "uts_mpa_irradiated", "dose_dpa", "irradiation_temp_c",
    "hardness_value", "fracture_toughness_mpa_sqrt_m", "dbtt_k_irradiated",
]
CONTEXT_FIELDS = [
    "irradiation_state", "test_temp_c", "experiment_type",
    "reactor", "material_class",
]


def validate_extraction(record: dict) -> list[str]:
    """Return list of validation error strings. Empty = valid."""
    errors = []
    if not record.get("material_name"):
        errors.append("material_name: required field missing")
    dose = record.get("dose_dpa")
    if dose is not None and dose < 0:
        errors.append(f"dose_dpa: must be >= 0 (got {dose})")
    irr_temp = record.get("irradiation_temp_c")
    if irr_temp is not None and (irr_temp < -273 or irr_temp > 3000):
        errors.append(f"irradiation_temp_c: out of physical range (got {irr_temp})")
    test_temp = record.get("test_temp_c")
    if test_temp is not None and (test_temp < -273 or test_temp > 2000):
        errors.append(f"test_temp_c: out of physical range (got {test_temp})")
    for field in ["yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
                  "uts_mpa_irradiated", "uts_mpa_unirradiated"]:
        val = record.get(field)
        if val is not None and (val < 0 or val > 5000):
            errors.append(f"{field}: out of range (got {val} MPa)")
    return errors


def score_confidence(record: dict) -> float:
    """Score 0.0–1.0 based on field completeness and consistency."""
    score = 0.0
    if record.get("material_name"):
        score += 0.1
    has_condition = any(record.get(f) is not None for f in ["dose_dpa", "irradiation_temp_c"])
    if has_condition:
        score += 0.3
    has_property = any(record.get(f) is not None for f in PROPERTY_FIELDS)
    if has_property:
        score += 0.3
    for f in CONTEXT_FIELDS[:4]:
        if record.get(f) is not None:
            score += 0.05
    if (record.get("yield_strength_mpa_irradiated") is not None and
            record.get("yield_strength_mpa_unirradiated") is not None):
        score += 0.1
    return min(score, 1.0)
