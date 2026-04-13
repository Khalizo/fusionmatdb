import json
import pytest
from unittest.mock import patch, MagicMock
from fusionmatdb.extraction.validator import validate_extraction, score_confidence
from fusionmatdb.extraction.llm_extractor import LLMExtractor


def test_validate_extraction_accepts_valid_record():
    record = {
        "material_name": "W",
        "material_class": "tungsten",
        "irradiation_state": "irradiated",
        "dose_dpa": 5.0,
        "irradiation_temp_c": 500.0,
        "test_temp_c": 25.0,
        "experiment_type": "Mechanical Tensile",
        "yield_strength_mpa_irradiated": 620.0,
    }
    errors = validate_extraction(record)
    assert errors == []


def test_validate_extraction_catches_negative_dose():
    record = {
        "material_name": "W",
        "dose_dpa": -1.0,
    }
    errors = validate_extraction(record)
    assert any("dose_dpa" in e for e in errors)


def test_validate_extraction_catches_extreme_temperature():
    record = {
        "material_name": "W",
        "irradiation_temp_c": 5000.0,
    }
    errors = validate_extraction(record)
    assert any("irradiation_temp" in e for e in errors)


def test_score_confidence_high_for_complete_record():
    record = {
        "material_name": "EUROFER97",
        "material_class": "RAFM_steel",
        "irradiation_state": "irradiated",
        "dose_dpa": 3.0,
        "irradiation_temp_c": 300.0,
        "test_temp_c": 25.0,
        "experiment_type": "Mechanical Tensile",
        "yield_strength_mpa_irradiated": 550.0,
        "uts_mpa_irradiated": 680.0,
    }
    score = score_confidence(record)
    assert score >= 0.7


def test_score_confidence_low_for_sparse_record():
    record = {"material_name": "W"}
    score = score_confidence(record)
    assert score < 0.4


def test_llm_extractor_parses_json_response():
    """LLMExtractor.extract() should handle a mocked Claude response."""
    mock_response_json = json.dumps([{
        "material_name": "W-10%Re",
        "material_class": "tungsten",
        "irradiation_state": "irradiated",
        "dose_dpa": 0.5,
        "irradiation_temp_c": 300.0,
        "test_temp_c": 25.0,
        "experiment_type": "Mechanical Tensile",
        "yield_strength_mpa_irradiated": 700.0,
    }])

    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=mock_response_json)]

    with patch("anthropic.Anthropic") as MockClient:
        mock_client = MockClient.return_value
        mock_client.messages.create.return_value = mock_message
        extractor = LLMExtractor(api_key="test-key")
        results = extractor.extract("some PDF text about W-Re irradiation", paper_id="p1")

    assert len(results) == 1
    assert results[0]["material_name"] == "W-10%Re"
    assert results[0]["dose_dpa"] == 0.5
