# tests/test_schema_quality.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
    DataQualityAssessment, ProvenanceRecord, PageTriageResult, ReviewQueueItem,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="test-001", title="Test paper", year=2023, access_type="ornl_report",
                      source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-70.pdf")
        mat = Material(paper_id="test-001", name="EUROFER97", class_="RAFM_steel")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(
            paper_id="test-001", material_id=mat.id,
            irradiation_state="irradiated", dose_dpa=10.0, irradiation_temp=300.0,
            dose_dpa_lower=9.5, dose_dpa_upper=10.5,
            irradiation_temp_lower=290.0, irradiation_temp_upper=310.0,
        )
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="test-001", material_id=mat.id, irradiation_id=irr.id,
            experiment_type="Mechanical Tensile", test_temp=25.0,
            yield_strength_mpa_irradiated=650.0,
            yield_strength_mpa_irradiated_lower=640.0,
            yield_strength_mpa_irradiated_upper=660.0,
            uts_mpa_irradiated=750.0,
            uts_mpa_irradiated_lower=740.0,
            uts_mpa_irradiated_upper=760.0,
            hardness_value=250.0,
            hardness_lower=245.0,
            hardness_upper=255.0,
            dbtt_k_irradiated=350.0,
            dbtt_k_irradiated_lower=340.0,
            dbtt_k_irradiated_upper=360.0,
            distribution_type="normal",
            n_specimens=5,
            extraction_pass="first_pass",
            cross_page_context_used=True,
            confidence_score=0.85,
            extraction_method="gemini_vision",
        )
        session.add(prop)
        session.flush()
        yield session, paper, mat, irr, prop


def test_data_quality_assessment_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    dqa = DataQualityAssessment(
        mechanical_property_id=prop.id,
        quality_level="curated_database",
        quality_justification="ORNL semiannual report, experimental tensile test",
        source_page_number=42,
        source_figure_or_table="Table 3.2",
        source_pdf_url=paper.source_url,
        source_institution="ORNL",
        extraction_accuracy_score=0.9,
    )
    session.add(dqa)
    session.commit()
    result = session.query(DataQualityAssessment).filter_by(mechanical_property_id=prop.id).one()
    assert result.quality_level == "curated_database"
    assert result.source_page_number == 42
    assert result.source_figure_or_table == "Table 3.2"
    assert result.source_institution == "ORNL"
    assert result.extraction_accuracy_score == 0.9


def test_provenance_record_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    prov = ProvenanceRecord(
        mechanical_property_id=prop.id,
        root_origin="ornl_70",
        duplicate_cluster_id=1,
        content_hash="a" * 64,
        is_primary=True,
    )
    session.add(prov)
    session.commit()
    result = session.query(ProvenanceRecord).filter_by(mechanical_property_id=prop.id).one()
    assert result.content_hash == "a" * 64
    assert result.is_primary is True
    assert result.duplicate_cluster_id == 1


def test_uncertainty_bounds_on_mechanical_property(db_session):
    session, paper, mat, irr, prop = db_session
    session.commit()
    result = session.query(MechanicalProperty).get(prop.id)
    assert result.yield_strength_mpa_irradiated_lower == 640.0
    assert result.yield_strength_mpa_irradiated_upper == 660.0
    assert result.distribution_type == "normal"
    assert result.n_specimens == 5


def test_irradiation_condition_bounds(db_session):
    session, paper, mat, irr, prop = db_session
    session.commit()
    result = session.query(IrradiationCondition).get(irr.id)
    assert result.dose_dpa_lower == 9.5
    assert result.dose_dpa_upper == 10.5
    assert result.irradiation_temp_lower == 290.0
    assert result.irradiation_temp_upper == 310.0


def test_extraction_pass_and_cross_page(db_session):
    session, paper, mat, irr, prop = db_session
    session.commit()
    result = session.query(MechanicalProperty).get(prop.id)
    assert result.extraction_pass == "first_pass"
    assert result.cross_page_context_used is True


def test_page_triage_result_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    from datetime import datetime, timezone
    triage = PageTriageResult(
        paper_id="test-001",
        page_number=42,
        classification="clean",
        reason="Clear table with material properties",
        has_extractable_data=True,
        triage_model="gemini-3-flash-preview",
        triage_timestamp=datetime.now(timezone.utc),
    )
    session.add(triage)
    session.commit()
    result = session.query(PageTriageResult).filter_by(paper_id="test-001", page_number=42).one()
    assert result.classification == "clean"
    assert result.has_extractable_data is True


def test_review_queue_item_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    item = ReviewQueueItem(
        paper_id="test-001",
        page_number=42,
        mechanical_property_id=prop.id,
        flag_reason="degraded_page",
        flag_detail="Faded scan, low contrast on table borders",
        extraction_path="first_pass",
        review_status="pending",
    )
    session.add(item)
    session.commit()
    result = session.query(ReviewQueueItem).filter_by(mechanical_property_id=prop.id).one()
    assert result.flag_reason == "degraded_page"
    assert result.review_status == "pending"


def test_quality_level_values():
    valid_levels = {"accredited_lab", "curated_database", "peer_reviewed_literature", "simulation", "inferred"}
    for level in valid_levels:
        dqa = DataQualityAssessment(
            mechanical_property_id=1,
            quality_level=level,
        )
        assert dqa.quality_level == level
