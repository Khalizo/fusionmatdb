import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
    DataQualityAssessment, ProvenanceRecord,
)
from fusionmatdb.trust.lineage import get_lineage


@pytest.fixture
def populated_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            id="ornl_70", title="ORNL Report 70", year=2024,
            access_type="ornl_report", doi="10.1234/test",
            source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-70.pdf",
        )
        mat = Material(paper_id="ornl_70", name="EUROFER97", class_="RAFM_steel")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(
            paper_id="ornl_70", material_id=mat.id,
            irradiation_state="irradiated", dose_dpa=10.0, irradiation_temp=300.0,
            reactor="HFIR",
        )
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="ornl_70", material_id=mat.id, irradiation_id=irr.id,
            experiment_type="Mechanical Tensile", test_temp=25.0,
            yield_strength_mpa_irradiated=650.0,
            confidence_score=0.85, extraction_method="gemini_vision",
            extraction_pass="first_pass", cross_page_context_used=True,
        )
        session.add(prop)
        session.flush()
        dqa = DataQualityAssessment(
            mechanical_property_id=prop.id,
            quality_level="curated_database",
            quality_justification="ORNL report, experimental tensile",
            source_page_number=42,
            source_figure_or_table="Table 3.2",
            source_pdf_url=paper.source_url,
            source_institution="ORNL",
        )
        prov = ProvenanceRecord(
            mechanical_property_id=prop.id,
            root_origin="ornl_70",
            content_hash="a" * 64,
            is_primary=True,
        )
        session.add_all([dqa, prov])
        session.commit()
        yield session, prop.id


def test_lineage_returns_full_chain(populated_session):
    session, prop_id = populated_session
    lineage = get_lineage(session, prop_id)
    assert lineage.paper_title == "ORNL Report 70"
    assert lineage.source_pdf_url.endswith("70.pdf")
    assert lineage.source_page_number == 42
    assert lineage.source_figure_or_table == "Table 3.2"
    assert lineage.source_institution == "ORNL"
    assert lineage.quality_level == "curated_database"
    assert lineage.content_hash == "a" * 64
    assert lineage.trust_score > 0
    assert lineage.extraction_method == "gemini_vision"
    assert lineage.extraction_pass == "first_pass"


def test_lineage_missing_record(populated_session):
    session, _ = populated_session
    with pytest.raises(ValueError, match="not found"):
        get_lineage(session, 99999)
