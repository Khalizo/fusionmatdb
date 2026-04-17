import json
import pytest
from fusionmatdb.extraction.page_triage import (
    TriageResult, is_record_incomplete, get_adjacent_page_text, PageTriager,
)


def test_is_record_incomplete_missing_material():
    assert is_record_incomplete({"yield_strength_mpa_irradiated": 650.0})


def test_is_record_incomplete_missing_conditions():
    assert is_record_incomplete({
        "material_name": "W",
        "yield_strength_mpa_irradiated": 650.0,
    })


def test_is_record_incomplete_complete():
    assert not is_record_incomplete({
        "material_name": "W",
        "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0,
        "yield_strength_mpa_irradiated": 650.0,
    })


def test_is_record_incomplete_no_property():
    """Records with no property values are not flagged as incomplete."""
    assert not is_record_incomplete({"material_name": "W"})


def test_parse_triage_valid_json():
    triager = PageTriager.__new__(PageTriager)
    raw = json.dumps({
        "classification": "degraded",
        "reason": "Faded scan",
        "has_extractable_data": True,
    })
    result = triager._parse_triage(raw, 42)
    assert result.classification == "degraded"
    assert result.has_extractable_data is True
    assert result.page_number == 42


def test_parse_triage_markdown_fence():
    triager = PageTriager.__new__(PageTriager)
    raw = '```json\n{"classification": "no_data", "reason": "References page", "has_extractable_data": false}\n```'
    result = triager._parse_triage(raw, 5)
    assert result.classification == "no_data"
    assert result.has_extractable_data is False


def test_parse_triage_invalid_json_defaults_clean():
    triager = PageTriager.__new__(PageTriager)
    result = triager._parse_triage("not json at all", 10)
    assert result.classification == "clean"
    assert result.has_extractable_data is True
