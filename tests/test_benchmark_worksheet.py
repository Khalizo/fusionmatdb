import json
import pytest
from pathlib import Path
from fusionmatdb.qa.benchmark_worksheet import (
    generate_worksheet, compare_worksheet, BenchmarkReport,
)


def test_compare_worksheet_perfect_match(tmp_path):
    worksheet = {
        "notes": "test",
        "instructions": [],
        "pages": [{
            "report_number": 70,
            "page_number": 42,
            "page_image_path": "test.png",
            "pymupdf_text_preview": "test",
            "ground_truth_records": [{
                "material_name": "W",
                "dose_dpa": 10.0,
                "irradiation_temp_c": 300.0,
                "yield_strength_mpa_irradiated": 650.0,
            }],
        }],
    }
    ws_path = tmp_path / "worksheet.json"
    ws_path.write_text(json.dumps(worksheet))

    extracted = [{
        "material_name": "W",
        "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0,
        "yield_strength_mpa_irradiated": 650.0,
    }]
    report = compare_worksheet(ws_path, extracted)
    assert report.overall_accuracy == 1.0
    assert report.total_human_records == 1


def test_compare_worksheet_with_error(tmp_path):
    worksheet = {
        "notes": "test", "instructions": [],
        "pages": [{"report_number": 70, "page_number": 42,
                    "page_image_path": "test.png", "pymupdf_text_preview": "",
                    "ground_truth_records": [{"material_name": "W", "dose_dpa": 10.0,
                                              "yield_strength_mpa_irradiated": 650.0}]}],
    }
    ws_path = tmp_path / "worksheet.json"
    ws_path.write_text(json.dumps(worksheet))
    # 10% off — should fail 5% tolerance
    extracted = [{"material_name": "W", "dose_dpa": 10.0, "yield_strength_mpa_irradiated": 715.0}]
    report = compare_worksheet(ws_path, extracted, tolerance=0.05)
    assert report.overall_accuracy < 1.0
