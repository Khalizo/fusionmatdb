import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
)
from fusionmatdb.qa.cross_db_validator import validate_against_sdc_ic


def test_validate_against_sdc_ic_with_matching_records():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        # SDC-IC record
        sdc_paper = Paper(id="sdc_ic_material_library", title="SDC-IC", access_type="sdc_ic")
        sdc_mat = Material(paper_id="sdc_ic_material_library", name="EUROFER97", class_="RAFM_steel")
        session.add_all([sdc_paper, sdc_mat])
        session.flush()
        sdc_irr = IrradiationCondition(paper_id="sdc_ic_material_library", material_id=sdc_mat.id)
        session.add(sdc_irr)
        session.flush()
        sdc_prop = MechanicalProperty(
            paper_id="sdc_ic_material_library", material_id=sdc_mat.id,
            irradiation_id=sdc_irr.id, test_temp=25.0,
            yield_strength_mpa_unirradiated=500.0,
            confidence_score=1.0, extraction_method="sdc_ic",
        )
        session.add(sdc_prop)

        # ORNL record for same material
        ornl_paper = Paper(id="ornl_70", title="ORNL 70", access_type="ornl_report")
        ornl_mat = Material(paper_id="ornl_70", name="EUROFER97", class_="RAFM_steel")
        session.add_all([ornl_paper, ornl_mat])
        session.flush()
        ornl_irr = IrradiationCondition(paper_id="ornl_70", material_id=ornl_mat.id)
        session.add(ornl_irr)
        session.flush()
        ornl_prop = MechanicalProperty(
            paper_id="ornl_70", material_id=ornl_mat.id,
            irradiation_id=ornl_irr.id, test_temp=25.0,
            yield_strength_mpa_unirradiated=510.0,  # 2% off
            confidence_score=0.85, extraction_method="gemini_vision",
        )
        session.add(ornl_prop)
        session.commit()

        report = validate_against_sdc_ic(session, tolerance=0.05)
        assert report.total_matched > 0


def test_validate_empty_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        report = validate_against_sdc_ic(session)
        assert report.total_reference_records == 0
        assert report.overall_accuracy == 0.0
