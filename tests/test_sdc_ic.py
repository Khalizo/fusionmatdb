"""Tests for the SDC-IC Material Library ingestion module.

These tests run against the actual cloned repo at /tmp/sdc_ic_library (if available),
falling back to a small synthetic APDL snippet for CI/offline environments.
"""

from __future__ import annotations

import pytest
from pathlib import Path

# Path to cloned SDC-IC repo (cloned during development / CI setup step)
SDC_IC_REPO = Path("/tmp/sdc_ic_library")

REQUIRED_FIELDS = {
    "material_name",
    "material_class",
    "source_file",
    "test_temp_c",
    "property_name",
    "value",
    "irradiation_state",
    "confidence_score",
    "extraction_method",
}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def sdc_ic_records():
    """Parse the real SDC-IC repo (or skip if not available)."""
    if not SDC_IC_REPO.exists():
        pytest.skip("SDC-IC repo not cloned at /tmp/sdc_ic_library — run: "
                    "git clone --depth=1 https://github.com/Structural-Mechanics/"
                    "SDC-IC-Material-Library.git /tmp/sdc_ic_library")
    from fusionmatdb.ingestion.sdc_ic import parse_sdc_ic_repo
    return parse_sdc_ic_repo(SDC_IC_REPO)


# ---------------------------------------------------------------------------
# Test 1: parse_sdc_ic_repo returns a non-empty list
# ---------------------------------------------------------------------------

def test_parse_returns_nonempty_list(sdc_ic_records):
    """Parser must return at least one record from the real repo."""
    assert isinstance(sdc_ic_records, list), "Result must be a list"
    assert len(sdc_ic_records) > 0, "Result list must not be empty"


# ---------------------------------------------------------------------------
# Test 2: All records contain the required fields
# ---------------------------------------------------------------------------

def test_all_records_have_required_fields(sdc_ic_records):
    """Every record must contain all required keys."""
    for i, rec in enumerate(sdc_ic_records):
        missing = REQUIRED_FIELDS - rec.keys()
        assert not missing, (
            f"Record {i} is missing fields: {missing}\n  record={rec}"
        )


# ---------------------------------------------------------------------------
# Test 3: Confidence score is always 1.0
# ---------------------------------------------------------------------------

def test_confidence_score_is_1(sdc_ic_records):
    """SDC-IC is human-curated; every record must have confidence_score=1.0."""
    for rec in sdc_ic_records:
        assert rec["confidence_score"] == 1.0, (
            f"Expected confidence_score=1.0, got {rec['confidence_score']}"
        )


# ---------------------------------------------------------------------------
# Test 4: extraction_method is always 'sdc_ic_parse'
# ---------------------------------------------------------------------------

def test_extraction_method(sdc_ic_records):
    """extraction_method must be 'sdc_ic_parse' for all records."""
    for rec in sdc_ic_records:
        assert rec["extraction_method"] == "sdc_ic_parse"


# ---------------------------------------------------------------------------
# Test 5: Known materials are present
# ---------------------------------------------------------------------------

def test_known_materials_present(sdc_ic_records):
    """All 16 SDC-IC materials must appear in the parsed output."""
    expected_materials = {
        "304L Stainless Steel",
        "316L Stainless Steel",
        "316L (N-IG) Stainless Steel",
        "GRADE 660 Stainless Steel",
        "XM-19 Steel",
        "Alloy 625",
        "Ti-6Al-4V Alloy",
        "Pure Copper",
        "Copper-Chromium-Zirconium Alloy",
        "Dispersion-Strengthened Copper",
        "Aluminium-Nickel Bronze",
        "Alloy 718",
        "Beryllium",
        "Tungsten",
        "CFC EU Grade",
        "CFC CX-2002U Grade",
    }
    found = {rec["material_name"] for rec in sdc_ic_records}
    missing = expected_materials - found
    assert not missing, f"Missing materials in parsed output: {missing}"


# ---------------------------------------------------------------------------
# Test 6: Young's modulus values for 304L are physically plausible
# ---------------------------------------------------------------------------

def test_youngs_modulus_304L_plausible(sdc_ic_records):
    """Young's modulus for 304L SS at 20°C should be ~200 GPa."""
    recs_ex = [
        r for r in sdc_ic_records
        if r["material_name"] == "304L Stainless Steel"
        and r["property_name"] == "youngs_modulus_gpa"
        and abs(r["test_temp_c"] - 20.0) < 1e-3
    ]
    assert recs_ex, "No E_x record for 304L at 20°C"
    value = recs_ex[0]["value"]
    # SDC-IC reports E=200 GPa at 20°C for 304L
    assert 190.0 <= value <= 210.0, (
        f"Young's modulus at 20°C for 304L expected ~200 GPa, got {value}"
    )


# ---------------------------------------------------------------------------
# Test 7: Yield strength records are present for materials that define them
# ---------------------------------------------------------------------------

def test_yield_strength_records_present(sdc_ic_records):
    """Yield strength (min) records must be present for at least some materials."""
    sy_recs = [
        r for r in sdc_ic_records
        if "yield_strength" in r["property_name"]
    ]
    assert len(sy_recs) > 0, "No yield strength records found"


# ---------------------------------------------------------------------------
# Test 8: Synthetic/unit test using a minimal APDL snippet (no repo required)
# ---------------------------------------------------------------------------

_SYNTHETIC_APDL = """\
*if,MAT_NAME,eq,MATNAMES_ARRAY(1,1),or,MAT_NUMBER,eq,MATNUMBERS_ARRAY(1),then

    *if,PROP_ARRAY(1,I),eq,'EX',then
        mptemp
        mptemp,  1, 20.0, 100.0,
        mpdata, EX,   101,    1, 200.0e9, 193.0e9,
    *endif

    *if,PROP_ARRAY(1,I),eq,'SY_MIN_101',then
        *dim, SY_MIN_101, table, 2,,, TEMP
        *taxis, SY_MIN_101(1), 1, 20.0, 100.0,
        SY_MIN_101(1)=180000000.0, 145000000.0,
    *endif

*endif
"""


def test_synthetic_parse(tmp_path):
    """Parser works correctly on a minimal synthetic APDL snippet."""
    # Write a minimal .mac file
    mac = tmp_path / "SDC-IC_Mat_Lib.mac"
    mac.write_text(_SYNTHETIC_APDL, encoding="utf-8")

    from fusionmatdb.ingestion.sdc_ic import parse_sdc_ic_repo
    records = parse_sdc_ic_repo(tmp_path)

    assert len(records) > 0, "Synthetic parse must return records"

    # Check required fields
    for rec in records:
        missing = REQUIRED_FIELDS - rec.keys()
        assert not missing, f"Missing fields: {missing}"

    # Check Young's modulus record
    ex_recs = [r for r in records if r["property_name"] == "youngs_modulus_gpa"]
    assert len(ex_recs) == 2, f"Expected 2 E records, got {len(ex_recs)}"

    ex_20 = next((r for r in ex_recs if abs(r["test_temp_c"] - 20.0) < 1e-3), None)
    assert ex_20 is not None, "Missing E record at 20°C"
    assert abs(ex_20["value"] - 200.0) < 0.1, (
        f"Expected E=200 GPa at 20°C, got {ex_20['value']}"
    )

    # Check yield strength record
    sy_recs = [r for r in records if "yield_strength" in r["property_name"]]
    assert len(sy_recs) == 2, f"Expected 2 SY records, got {len(sy_recs)}"

    sy_20 = next((r for r in sy_recs if abs(r["test_temp_c"] - 20.0) < 1e-3), None)
    assert sy_20 is not None, "Missing Sy record at 20°C"
    assert abs(sy_20["value"] - 180.0) < 0.1, (
        f"Expected Sy_min=180 MPa at 20°C, got {sy_20['value']}"
    )
