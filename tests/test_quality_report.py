import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
    DataQualityAssessment, ProvenanceRecord,
)
from fusionmatdb.reporting.quality_report import generate_quality_report


@pytest.fixture
def populated_db(tmp_path):
    db_path = tmp_path / "test.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            id="ornl_70", title="ORNL Report 70", year=2024,
            access_type="ornl_report",
            source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-70.pdf",
        )
        mat = Material(paper_id="ornl_70", name="EUROFER97", class_="RAFM_steel")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(
            paper_id="ornl_70", material_id=mat.id,
            dose_dpa=10.0, irradiation_temp=300.0,
        )
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="ornl_70", material_id=mat.id, irradiation_id=irr.id,
            yield_strength_mpa_irradiated=650.0,
            yield_strength_mpa_irradiated_lower=640.0,
            yield_strength_mpa_irradiated_upper=660.0,
            confidence_score=0.85, extraction_method="gemini_vision",
            n_specimens=5, distribution_type="normal",
        )
        session.add(prop)
        session.flush()
        dqa = DataQualityAssessment(
            mechanical_property_id=prop.id,
            quality_level="curated_database",
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
    return str(db_path)


def test_generate_quality_report_creates_html(populated_db, tmp_path):
    output = tmp_path / "report.html"
    result = generate_quality_report(populated_db, str(output))
    assert result.exists()
    html = result.read_text()
    assert "<!DOCTYPE html>" in html
    assert "FusionMatDB" in html


def test_report_contains_all_sections(populated_db, tmp_path):
    output = tmp_path / "report.html"
    result = generate_quality_report(populated_db, str(output))
    html = result.read_text()
    assert "Executive Summary" in html
    assert "Data Quality Hierarchy" in html
    assert "Traceability" in html
    assert "Provenance" in html or "De-duplication" in html
    assert "Uncertainty" in html
    assert "Validation" in html
    assert "Observability" in html or "Transparency" in html
    assert "Engineering Decision" in html or "Trust" in html
    assert "Extraction" in html
    assert "Fraud" in html or "Anomaly" in html
    assert "Benchmark" in html or "Accuracy" in html


def test_report_contains_data(populated_db, tmp_path):
    output = tmp_path / "report.html"
    result = generate_quality_report(populated_db, str(output))
    html = result.read_text()
    assert "EUROFER97" in html
    assert "curated_database" in html
    assert "ORNL" in html
