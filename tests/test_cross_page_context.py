import json
import pytest


def test_fields_definition_contains_traceability():
    from fusionmatdb.extraction.prompts import _FIELDS
    assert "source_reference" in _FIELDS
    assert "source_institution" in _FIELDS
    assert "n_specimens" in _FIELDS
    assert "data_origin" in _FIELDS
    assert "experimental_method_detail" in _FIELDS


def test_fields_definition_contains_uncertainty_bounds():
    from fusionmatdb.extraction.prompts import _FIELDS
    assert "yield_strength_mpa_irradiated_lower" in _FIELDS
    assert "yield_strength_mpa_irradiated_upper" in _FIELDS
    assert "hardness_lower" in _FIELDS
    assert "dose_dpa_lower" in _FIELDS


def test_vision_prompt_contains_cross_page_instructions():
    from fusionmatdb.extraction.prompts import VISION_EXTRACTION_PROMPT
    assert "source_reference" in VISION_EXTRACTION_PROMPT
    assert "source_institution" in VISION_EXTRACTION_PROMPT


def test_first_pass_prompt_contains_context_placeholders():
    from fusionmatdb.extraction.prompts import FIRST_PASS_VISION_PROMPT
    assert "CONTEXT FROM PREVIOUS PAGE" in FIRST_PASS_VISION_PROMPT
    assert "CONTEXT FROM NEXT PAGE" in FIRST_PASS_VISION_PROMPT
    assert "Do NOT extract data from the context text" in FIRST_PASS_VISION_PROMPT


def test_second_pass_prompt_contains_middle_page_instruction():
    from fusionmatdb.extraction.prompts import SECOND_PASS_VISION_PROMPT
    assert "MIDDLE page only" in SECOND_PASS_VISION_PROMPT
    assert "Do NOT extract data from the first or last page" in SECOND_PASS_VISION_PROMPT


def test_parse_response_handles_new_fields():
    """VLM response with new fields should parse correctly."""
    from fusionmatdb.access.vision_extractor import VertexVisionExtractor
    ext = VertexVisionExtractor.__new__(VertexVisionExtractor)
    raw = json.dumps([{
        "material_name": "EUROFER97",
        "material_class": "RAFM_steel",
        "irradiation_state": "irradiated",
        "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0,
        "yield_strength_mpa_irradiated": 650.0,
        "yield_strength_mpa_irradiated_lower": 640.0,
        "yield_strength_mpa_irradiated_upper": 660.0,
        "source_reference": "Table 3.2",
        "source_institution": "ORNL",
        "n_specimens": 5,
        "data_origin": "primary_measurement",
        "experimental_method_detail": "miniature tensile, gauge length 5mm",
    }])
    records = ext._parse_response(raw, "ornl_70", 42)
    assert len(records) == 1
    rec = records[0]
    assert rec["source_reference"] == "Table 3.2"
    assert rec["source_institution"] == "ORNL"
    assert rec["n_specimens"] == 5
    assert rec["yield_strength_mpa_irradiated_lower"] == 640.0


def test_incomplete_record_detection():
    """Records missing material_name or irradiation conditions should be flagged."""
    from fusionmatdb.extraction.page_triage import is_record_incomplete
    # Missing material name
    assert is_record_incomplete({"yield_strength_mpa_irradiated": 650.0})
    # Missing irradiation conditions
    assert is_record_incomplete({"material_name": "W", "yield_strength_mpa_irradiated": 650.0})
    # Complete record
    assert not is_record_incomplete({
        "material_name": "W", "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0, "yield_strength_mpa_irradiated": 650.0,
    })
