"""Tests for fusionmatdb.scripts.backfill_quality."""
import json

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
)
from fusionmatdb.scripts.backfill_quality import (
    backfill_quality_assessments,
    backfill_provenance,
    backfill_dedup_clusters,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # ORNL paper + record
        p1 = Paper(id="ornl_42", title="ORNL Report 42", year=2020,
                    access_type="ornl_report",
                    source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-42.pdf")
        m1 = Material(paper_id="ornl_42", name="F82H", class_="rafm_steel")
        session.add_all([p1, m1])
        session.flush()
        irr1 = IrradiationCondition(paper_id="ornl_42", material_id=m1.id, dose_dpa=5.0)
        session.add(irr1)
        session.flush()
        prop1 = MechanicalProperty(
            paper_id="ornl_42", material_id=m1.id, irradiation_id=irr1.id,
            yield_strength_mpa_irradiated=650.0,
            confidence_score=0.85, extraction_method="gemini_vision",
            raw_extraction_json=json.dumps({"page": 12}),
        )
        session.add(prop1)

        # SDC-IC paper + record
        p2 = Paper(id="sdc_ic_material_library", title="SDC-IC", year=2023,
                    access_type="sdc_ic")
        m2 = Material(paper_id="sdc_ic_material_library", name="316L", class_="austenitic_steel")
        session.add_all([p2, m2])
        session.flush()
        irr2 = IrradiationCondition(paper_id="sdc_ic_material_library", material_id=m2.id)
        session.add(irr2)
        session.flush()
        prop2 = MechanicalProperty(
            paper_id="sdc_ic_material_library", material_id=m2.id,
            irradiation_id=irr2.id,
            yield_strength_mpa_unirradiated=200.0,
            confidence_score=1.0, extraction_method="sdc_ic_apdl",
        )
        session.add(prop2)
        session.flush()
        session.commit()
        yield session


def test_backfill_quality_ornl(db_session):
    n = backfill_quality_assessments(db_session)
    db_session.commit()
    assert n == 2
    prop = db_session.query(MechanicalProperty).filter_by(paper_id="ornl_42").first()
    raw = json.loads(prop.raw_extraction_json)
    q = raw["_quality"]
    assert q["quality_level"] == "curated_database"
    assert q["source_institution"] == "ORNL"
    assert q["source_page_number"] == 12
    assert "source_pdf_url" in q


def test_backfill_quality_sdc(db_session):
    backfill_quality_assessments(db_session)
    db_session.commit()
    prop = db_session.query(MechanicalProperty).filter_by(
        paper_id="sdc_ic_material_library"
    ).first()
    raw = json.loads(prop.raw_extraction_json)
    q = raw["_quality"]
    assert q["source_institution"] == "ITER IO"


def test_backfill_quality_idempotent(db_session):
    n1 = backfill_quality_assessments(db_session)
    db_session.commit()
    n2 = backfill_quality_assessments(db_session)
    db_session.commit()
    assert n1 > 0
    assert n2 == 0  # Already backfilled


def test_backfill_provenance(db_session):
    n = backfill_provenance(db_session)
    db_session.commit()
    assert n == 2
    prop = db_session.query(MechanicalProperty).first()
    raw = json.loads(prop.raw_extraction_json)
    prov = raw["_provenance"]
    assert len(prov["content_hash"]) == 64  # SHA-256 hex
    assert prov["is_primary"] is True


def test_backfill_dedup_no_duplicates(db_session):
    n = backfill_dedup_clusters(db_session)
    assert n == 0  # Two different records, no exact dups
