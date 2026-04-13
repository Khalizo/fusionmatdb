import pytest
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import Base, Paper, Material, MechanicalProperty
from fusionmatdb.storage.exporter import export_parquet, export_world_model


def make_test_db_with_data():
    """Create in-memory DB with one complete irradiated property record."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="p1", title="W irradiation study", year=2020, access_type="ornl_report")
        mat = Material(paper_id="p1", name="W", class_="tungsten", W=100.0)
        session.add_all([paper, mat])
        session.flush()
        prop = MechanicalProperty(
            paper_id="p1",
            material_id=mat.id,
            experiment_type="Mechanical Tensile",
            test_temp=25.0,
            yield_strength_mpa_unirradiated=550.0,
            yield_strength_mpa_irradiated=650.0,
            confidence_score=0.85,
            extraction_method="llm_fulltext",
        )
        session.add(prop)
        session.commit()
    return engine


def test_export_parquet_returns_count(tmp_path):
    engine = make_test_db_with_data()
    with Session(engine) as session:
        path = str(tmp_path / "test.parquet")
        n = export_parquet(session, path, min_confidence=0.7)
    assert n == 1


def test_export_parquet_file_exists(tmp_path):
    import pandas as pd
    engine = make_test_db_with_data()
    with Session(engine) as session:
        path = str(tmp_path / "test.parquet")
        export_parquet(session, path, min_confidence=0.7)
    df = pd.read_parquet(path)
    assert len(df) == 1
    assert "delta_yield_strength_mpa" in df.columns
    assert df["delta_yield_strength_mpa"].iloc[0] == 100.0  # 650 - 550


def test_export_parquet_empty_below_confidence(tmp_path):
    engine = make_test_db_with_data()
    with Session(engine) as session:
        path = str(tmp_path / "test.parquet")
        n = export_parquet(session, path, min_confidence=0.95)
    assert n == 0


def test_export_parquet_empty_creates_file(tmp_path):
    import pandas as pd
    engine = make_test_db_with_data()
    with Session(engine) as session:
        path = str(tmp_path / "empty.parquet")
        n = export_parquet(session, path, min_confidence=0.99)  # nothing above 0.99
    assert n == 0
    # File should still exist (empty DataFrame)
    df = pd.read_parquet(path)
    assert len(df) == 0
    assert "delta_yield_strength_mpa" in df.columns


def test_export_world_model_structure(tmp_path):
    engine = make_test_db_with_data()
    with Session(engine) as session:
        path = str(tmp_path / "world_model.json")
        n = export_world_model(session, path, min_confidence=0.7)
    assert n == 1
    with open(path) as f:
        data = json.load(f)
    assert len(data) == 1
    example = data[0]
    assert "state_before" in example
    assert "action" in example
    assert "state_after" in example
    assert example["state_before"]["yield_strength_mpa"] == 550.0
    assert example["state_after"]["yield_strength_mpa"] == 650.0
    assert example["action"]["experiment_type"] == "Mechanical Tensile"  # matches what we inserted
