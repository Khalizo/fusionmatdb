import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import Base, Paper, Material, IrradiationCondition, MechanicalProperty

def test_schema_creates_all_tables():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            id="test-001",
            title="Test paper",
            year=2023,
            access_type="ornl_report",
        )
        session.add(paper)
        session.commit()
        result = session.get(Paper, "test-001")
        assert result.title == "Test paper"

def test_mechanical_property_links_to_paper():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="p1", title="W irradiation", year=2020, access_type="ornl_report")
        mat = Material(paper_id="p1", name="W", class_="tungsten")
        session.add_all([paper, mat])
        session.flush()
        prop = MechanicalProperty(
            paper_id="p1",
            material_id=mat.id,
            experiment_type="Mechanical Tensile",
            test_temp=25.0,
            yield_strength_mpa_unirradiated=550.0,
            confidence_score=0.85,
            extraction_method="llm_fulltext",
        )
        session.add(prop)
        session.commit()
        assert session.query(MechanicalProperty).count() == 1
