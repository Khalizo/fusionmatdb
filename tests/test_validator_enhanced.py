import pytest
from fusionmatdb.extraction.validator import (
    validate_extraction, score_confidence, cross_field_checks, completeness_score,
)


def test_cross_field_irradiated_yield_too_high():
    record = {
        "material_name": "F82H",
        "yield_strength_mpa_unirradiated": 300.0,
        "yield_strength_mpa_irradiated": 900.0,  # 3x unirradiated — suspicious
    }
    flags = cross_field_checks(record)
    assert any("irradiated yield" in f.lower() or "yield" in f.lower() for f in flags)


def test_cross_field_elongation_increase():
    record = {
        "material_name": "F82H",
        "elongation_pct_unirradiated": 15.0,
        "elongation_pct_irradiated": 20.0,  # Elongation should decrease with irradiation
    }
    flags = cross_field_checks(record)
    assert any("elongation" in f.lower() for f in flags)


def test_cross_field_zero_dose_irradiated():
    record = {
        "material_name": "F82H",
        "irradiation_state": "irradiated",
        "dose_dpa": 0,
    }
    flags = cross_field_checks(record)
    assert any("dose" in f.lower() for f in flags)


def test_cross_field_clean_record():
    record = {
        "material_name": "F82H",
        "irradiation_state": "irradiated",
        "dose_dpa": 10.0,
        "yield_strength_mpa_unirradiated": 300.0,
        "yield_strength_mpa_irradiated": 450.0,
        "elongation_pct_unirradiated": 15.0,
        "elongation_pct_irradiated": 10.0,
    }
    flags = cross_field_checks(record)
    assert len(flags) == 0


def test_completeness_score_full_tensile():
    record = {
        "material_name": "W",
        "material_class": "tungsten",
        "irradiation_state": "irradiated",
        "dose_dpa": 5.0,
        "irradiation_temp_c": 500.0,
        "test_temp_c": 25.0,
        "yield_strength_mpa_irradiated": 650.0,
        "uts_mpa_irradiated": 700.0,
        "elongation_pct_irradiated": 5.0,
        "experiment_type": "Mechanical Tensile",
        "reactor": "HFIR",
    }
    score = completeness_score(record)
    assert score > 0.4


def test_completeness_score_minimal():
    record = {"material_name": "W", "hardness_value": 350.0}
    score = completeness_score(record)
    assert score < 0.3
