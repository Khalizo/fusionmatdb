"""Tests for fusionmatdb.qa.fraud_detector."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fusionmatdb.qa.fraud_detector import (
    compute_image_hash, find_suspicious_data_matches, SuspiciousMatch,
)
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
)


def test_compute_image_hash_deterministic():
    img = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
    h1 = compute_image_hash(img)
    h2 = compute_image_hash(img)
    assert h1 == h2
    assert isinstance(h1, str)


def test_find_suspicious_matches_flags_identical_values():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # Two papers
        p1 = Paper(id="p1", title="Paper 1", year=2020, access_type="ornl_report")
        p2 = Paper(id="p2", title="Paper 2", year=2021, access_type="ornl_report")
        m1 = Material(paper_id="p1", name="W", class_="tungsten")
        m2 = Material(paper_id="p2", name="W", class_="tungsten")
        session.add_all([p1, p2, m1, m2])
        session.flush()
        irr1 = IrradiationCondition(paper_id="p1", material_id=m1.id, dose_dpa=10.0, irradiation_temp=300.0, reactor="HFIR")
        irr2 = IrradiationCondition(paper_id="p2", material_id=m2.id, dose_dpa=20.0, irradiation_temp=500.0, reactor="BOR-60")
        session.add_all([irr1, irr2])
        session.flush()
        # Same numeric values, different conditions
        for irr, pid, mid in [(irr1, "p1", m1.id), (irr2, "p2", m2.id)]:
            prop = MechanicalProperty(
                paper_id=pid, material_id=mid, irradiation_id=irr.id,
                yield_strength_mpa_irradiated=650.0,
                yield_strength_mpa_unirradiated=400.0,
                uts_mpa_irradiated=750.0,
                uts_mpa_unirradiated=500.0,
                elongation_pct_irradiated=8.0,
                hardness_value=250.0,
                confidence_score=0.8,
                extraction_method="gemini_vision",
            )
            session.add(prop)
        session.flush()
        session.commit()
        matches = find_suspicious_data_matches(session, min_matching_fields=5)
        assert len(matches) >= 1
        assert len(matches[0].matching_fields) >= 5
        assert len(matches[0].differing_fields) > 0


def test_find_suspicious_matches_ignores_same_paper():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        p1 = Paper(id="p1", title="Paper 1", year=2020, access_type="ornl_report")
        m1 = Material(paper_id="p1", name="W", class_="tungsten")
        session.add_all([p1, m1])
        session.flush()
        irr1 = IrradiationCondition(paper_id="p1", material_id=m1.id, dose_dpa=10.0)
        session.add(irr1)
        session.flush()
        for _ in range(2):
            prop = MechanicalProperty(
                paper_id="p1", material_id=m1.id, irradiation_id=irr1.id,
                yield_strength_mpa_irradiated=650.0,
                uts_mpa_irradiated=750.0,
                elongation_pct_irradiated=8.0,
                hardness_value=250.0,
                fracture_toughness_mpa_sqrt_m=50.0,
                confidence_score=0.8, extraction_method="gemini_vision",
            )
            session.add(prop)
        session.flush()
        session.commit()
        matches = find_suspicious_data_matches(session, min_matching_fields=5)
        assert len(matches) == 0  # Same paper, should not flag
