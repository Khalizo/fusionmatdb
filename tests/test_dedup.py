import pytest
from fusionmatdb.qa.dedup_detector import compute_content_hash, find_exact_duplicates
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
)


def test_content_hash_deterministic():
    record = {
        "material_name": "EUROFER97",
        "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0,
        "test_temp_c": 25.0,
        "yield_strength_mpa_irradiated": 650.0,
        "uts_mpa_irradiated": 750.0,
        "hardness_value": 250.0,
    }
    h1 = compute_content_hash(record)
    h2 = compute_content_hash(record)
    assert h1 == h2
    assert len(h1) == 64


def test_content_hash_different_for_different_records():
    r1 = {"material_name": "W", "dose_dpa": 10.0, "yield_strength_mpa_irradiated": 650.0}
    r2 = {"material_name": "W", "dose_dpa": 10.0, "yield_strength_mpa_irradiated": 651.0}
    assert compute_content_hash(r1) != compute_content_hash(r2)


def test_content_hash_rounds_floats():
    """Tiny float differences should hash the same."""
    r1 = {"material_name": "W", "dose_dpa": 10.0000001}
    r2 = {"material_name": "W", "dose_dpa": 10.0000002}
    assert compute_content_hash(r1) == compute_content_hash(r2)


def test_find_exact_duplicates():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="p1", title="Test", year=2023, access_type="ornl_report")
        mat = Material(paper_id="p1", name="W", class_="tungsten")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(paper_id="p1", material_id=mat.id, dose_dpa=10.0, irradiation_temp=300.0)
        session.add(irr)
        session.flush()
        # Two identical properties
        for _ in range(2):
            prop = MechanicalProperty(
                paper_id="p1", material_id=mat.id, irradiation_id=irr.id,
                yield_strength_mpa_irradiated=650.0, confidence_score=0.8,
                extraction_method="gemini_vision",
            )
            session.add(prop)
        session.flush()
        session.commit()
        clusters = find_exact_duplicates(session)
        assert len(clusters) >= 1
        assert any(len(c.record_ids) == 2 for c in clusters)
