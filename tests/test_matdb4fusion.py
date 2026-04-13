"""Tests for the MatDB4Fusion CSV connector.

All synthetic CSV helpers use the real MatDB4Fusion column names
(Title-Case with spaces, matching the matdb4fusion.app April 2026 export).

Integration tests against the real export at
  /Users/khalizo/Documents/coding_projects/fusion_energy/data/matdb4fusion.csv
are skipped automatically when the file is absent.
"""

from __future__ import annotations

import json
import os

import pandas as pd
import pytest

_REAL_CSV = (
    "/Users/khalizo/Documents/coding_projects/fusion_energy/data/matdb4fusion.csv"
)
_real_csv_exists = os.path.exists(_REAL_CSV)

# ---------------------------------------------------------------------------
# Synthetic CSV helpers - real column names
# ---------------------------------------------------------------------------

_BASE_COLS = [
    "Source First Author", "Source Year", "Title",
    "Material ID", "Name", "Group", "Subgroup",
    "Al", "B", "C", "Co", "Cr", "Cu", "Mn", "Mo", "N", "Nb",
    "Ni", "O", "P", "S", "Si", "Ta", "Ti", "V", "W",
    "Manufacturer Name", "Product Shape", "Temper Temp",
    "Irradiation State", "Reactor", "Particle", "Irradiation Temp", "Dose",
    "Experiment Type", "Experiment ID", "Method", "Test Temp",
    "Yield Point", "Ultimate Tensile Strength", "Total Elongation",
    "Hardness Value", "Hardness Type", "JQ", "KV", "Creep Stress", "Creep Rate",
]


def _row(**kwargs) -> dict:
    """Build a row dict with all base columns defaulted to None."""
    row = {c: None for c in _BASE_COLS}
    row.update(kwargs)
    return row


def make_test_csv(path: str) -> None:
    """Three clean rows: 2x EUROFER97 tensile (unirradiated) + 1x W tensile."""
    rows = [
        _row(**{
            "Source First Author": "A", "Source Year": 2020, "Title": "P1",
            "Material ID": "EUR_01", "Name": "EUROFER97",
            "Group": "Structural materials", "Subgroup": "Steel",
            "C": 0.1, "Cr": 9.0, "Mn": 0.5, "V": 0.2, "Ta": 0.14,
            "Manufacturer Name": "FZK", "Product Shape": "rolled plate",
            "Temper Temp": 760.0, "Irradiation State": "unirradiated",
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "exp_001",
            "Test Temp": 25.0, "Yield Point": 550.0,
            "Ultimate Tensile Strength": 680.0, "Total Elongation": 16.0,
        }),
        _row(**{
            "Source First Author": "A", "Source Year": 2020, "Title": "P1",
            "Material ID": "EUR_01", "Name": "EUROFER97",
            "Group": "Structural materials", "Subgroup": "Steel",
            "C": 0.1, "Cr": 9.0, "Mn": 0.5, "V": 0.2, "Ta": 0.14,
            "Manufacturer Name": "FZK", "Product Shape": "rolled plate",
            "Temper Temp": 760.0, "Irradiation State": "unirradiated",
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "exp_002",
            "Test Temp": 300.0, "Yield Point": 480.0,
            "Ultimate Tensile Strength": 600.0, "Total Elongation": 18.0,
        }),
        _row(**{
            "Source First Author": "B", "Source Year": 2021, "Title": "P2",
            "Material ID": "W_01", "Name": "W",
            "Group": "High heat flux materials", "Subgroup": "Tungsten",
            "W": 99.95, "Manufacturer Name": "Plansee",
            "Product Shape": "rod", "Irradiation State": "unirradiated",
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "exp_003",
            "Test Temp": 20.0, "Yield Point": 900.0,
            "Ultimate Tensile Strength": 1050.0, "Total Elongation": 2.5,
        }),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def make_charpy_csv(path: str) -> None:
    """One Charpy row with NaN Irradiation State (mirrors real file pattern)."""
    rows = [
        _row(**{
            "Source First Author": "A", "Source Year": 2020, "Title": "P1",
            "Material ID": "EUR_01", "Name": "EUROFER97",
            "Group": "Structural materials",
            "C": 0.1, "Cr": 9.0, "Mn": 0.5, "V": 0.2, "Ta": 0.14,
            "Manufacturer Name": "FZK", "Product Shape": "rolled plate",
            "Temper Temp": 760.0,
            # Irradiation State intentionally left None -> NaN in CSV
            "Experiment Type": "Mechanical Charpy", "Experiment ID": "charpy_001",
            "Test Temp": -50.0, "KV": 8.5,
        }),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def make_irradiated_csv(path: str) -> None:
    """One irradiated tensile row - values should go to *_irradiated columns."""
    rows = [
        _row(**{
            "Source First Author": "A", "Source Year": 2020, "Title": "P1",
            "Material ID": "EUR_01", "Name": "EUROFER97",
            "Group": "Structural materials",
            "C": 0.1, "Cr": 9.0, "Mn": 0.5, "V": 0.2, "Ta": 0.14,
            "Manufacturer Name": "FZK", "Product Shape": "rolled plate",
            "Temper Temp": 760.0, "Irradiation State": "irradiated",
            "Reactor": "BOR-60", "Particle": "neutron",
            "Irradiation Temp": 325.0, "Dose": 2.5,
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "irr_001",
            "Test Temp": 25.0, "Yield Point": 700.0,
            "Ultimate Tensile Strength": 820.0, "Total Elongation": 8.0,
        }),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def make_dummy_mixed_csv(path: str) -> None:
    """One dummy row (filtered) + one real row."""
    rows = [
        _row(**{
            "Source First Author": None, "Source Year": None,
            "Title": "dummy data for demo",
            "Material ID": "W-K_example_1", "Name": "W, K-doped",
            "Group": "High heat flux materials",
            "Irradiation State": "irradiated",
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "dummy_001",
            "Test Temp": 20.0, "Yield Point": 1588.32,
            "Ultimate Tensile Strength": 1806.94, "Total Elongation": 4.39,
        }),
        _row(**{
            "Source First Author": "Real Author", "Source Year": 2021,
            "Title": "Real Paper",
            "Material ID": "EUR_01", "Name": "EUROFER97",
            "Group": "Structural materials",
            "C": 0.1, "Cr": 9.0, "Mn": 0.5, "V": 0.2, "Ta": 0.14,
            "Manufacturer Name": "FZK", "Irradiation State": "unirradiated",
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "real_001",
            "Test Temp": 25.0, "Yield Point": 550.0,
            "Ultimate Tensile Strength": 680.0, "Total Elongation": 16.0,
        }),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


def make_empty_properties_csv(path: str) -> None:
    """A row with no measurable property - should be skipped."""
    rows = [
        _row(**{
            "Source First Author": "A", "Source Year": 2020, "Title": "P1",
            "Material ID": "EUR_01", "Name": "EUROFER97",
            "Group": "Structural materials",
            "C": 0.1, "Cr": 9.0,
            "Irradiation State": "unirradiated",
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "no_data",
            "Test Temp": 25.0,
            # all measurement columns remain None
        }),
    ]
    pd.DataFrame(rows).to_csv(path, index=False)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_session(tmp_path):
    """Fresh, isolated SQLite session for each test."""
    import fusionmatdb.storage.database as db_module

    db_module._engine = None
    db_module._SessionLocal = None
    db_module.init_db(str(tmp_path / "test.sqlite"))
    session = db_module.get_session()
    yield session
    session.close()
    db_module._engine = None
    db_module._SessionLocal = None


# ---------------------------------------------------------------------------
# Unit tests (synthetic CSV)
# ---------------------------------------------------------------------------

class TestReturnCount:
    def test_ingest_returns_correct_count(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        n = ingest_matdb4fusion_csv(csv_path, db_session)
        assert n == 3

    def test_mechanical_property_rows_match(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()
        assert db_session.query(MechanicalProperty).count() == 3

    def test_spec_two_row_subset(self, db_session, tmp_path):
        """Spec example: 2 EUROFER97 rows -> n=2."""
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        rows = [
            _row(**{
                "Source First Author": "A", "Source Year": 2020, "Title": "P1",
                "Material ID": "EUR_01", "Name": "EUROFER97",
                "Group": "Structural materials",
                "C": 0.1, "Cr": 9.0, "Mn": 0.5, "V": 0.2, "Ta": 0.14,
                "Manufacturer Name": "FZK", "Product Shape": "rolled plate",
                "Temper Temp": 760.0, "Irradiation State": "unirradiated",
                "Experiment Type": "Mechanical Tensile", "Experiment ID": "e1",
                "Test Temp": 25.0, "Yield Point": 550.0,
                "Ultimate Tensile Strength": 680.0, "Total Elongation": 16.0,
            }),
            _row(**{
                "Source First Author": "A", "Source Year": 2020, "Title": "P1",
                "Material ID": "EUR_01", "Name": "EUROFER97",
                "Group": "Structural materials",
                "C": 0.1, "Cr": 9.0, "Mn": 0.5, "V": 0.2, "Ta": 0.14,
                "Manufacturer Name": "FZK", "Product Shape": "rolled plate",
                "Temper Temp": 760.0, "Irradiation State": "unirradiated",
                "Experiment Type": "Mechanical Tensile", "Experiment ID": "e2",
                "Test Temp": 300.0, "Yield Point": 480.0,
                "Ultimate Tensile Strength": 600.0, "Total Elongation": 18.0,
            }),
        ]
        csv_path = str(tmp_path / "spec.csv")
        pd.DataFrame(rows).to_csv(csv_path, index=False)

        n = ingest_matdb4fusion_csv(csv_path, db_session)
        assert n == 2
        assert db_session.query(MechanicalProperty).count() == 2


class TestPaperRecord:
    def test_paper_created(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Paper

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        paper = db_session.get(Paper, "matdb4fusion_2026")
        assert paper is not None
        assert paper.year == 2026
        assert paper.source_url == "https://matdb4fusion.app"
        assert paper.access_type == "matdb4fusion_ingest"

    def test_paper_not_duplicated_on_reingest(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Paper

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        assert db_session.query(Paper).filter_by(id="matdb4fusion_2026").count() == 1


class TestMaterialRows:
    def test_two_distinct_material_names(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Material

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        names = {m.name for m in db_session.query(Material).all()}
        assert "EUROFER97" in names
        assert "W" in names

    def test_eurofer_composition_mapped(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Material

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        mat = db_session.query(Material).filter_by(name="EUROFER97").first()
        assert mat is not None
        assert mat.Cr == pytest.approx(9.0)
        assert mat.C == pytest.approx(0.1)
        assert mat.V == pytest.approx(0.2)
        assert mat.Ta == pytest.approx(0.14)

    def test_material_class_rafm_steel(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Material

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        mat = db_session.query(Material).filter_by(name="EUROFER97").first()
        assert mat.class_ == "RAFM steel"

    def test_material_class_pure_w(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Material

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        mat = db_session.query(Material).filter_by(name="W").first()
        assert mat.class_ == "pure W"

    def test_material_class_k_doped_w(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Material

        rows = [_row(**{
            "Source First Author": "A", "Source Year": 2020, "Title": "P",
            "Material ID": "KW_01", "Name": "W, K-doped",
            "Group": "High heat flux materials", "W": 99.9,
            "Manufacturer Name": "Plansee", "Product Shape": "rod",
            "Irradiation State": "unirradiated",
            "Experiment Type": "Mechanical Tensile", "Experiment ID": "kw_001",
            "Test Temp": 25.0, "Yield Point": 750.0,
            "Ultimate Tensile Strength": 900.0, "Total Elongation": 3.0,
        })]
        csv_path = str(tmp_path / "kw.csv")
        pd.DataFrame(rows).to_csv(csv_path, index=False)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        mat = db_session.query(Material).filter_by(name="W, K-doped").first()
        assert mat.class_ == "K-doped W"

    def test_matdb4fusion_id_stored_on_material(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Material

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        eurofer = db_session.query(Material).filter_by(name="EUROFER97").first()
        assert eurofer.matdb4fusion_id == "EUR_01"


class TestMechanicalProperties:
    def test_confidence_is_one(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        props = db_session.query(MechanicalProperty).all()
        assert all(p.confidence_score == pytest.approx(1.0) for p in props)

    def test_extraction_method_tag(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        props = db_session.query(MechanicalProperty).all()
        assert all(p.extraction_method == "matdb4fusion_ingest" for p in props)

    def test_reviewed_by_human_true(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        props = db_session.query(MechanicalProperty).all()
        assert all(p.reviewed_by_human is True for p in props)

    def test_yield_strength_unirradiated_routed(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        w_prop = (
            db_session.query(MechanicalProperty)
            .filter(MechanicalProperty.test_temp == 20.0)
            .first()
        )
        assert w_prop is not None
        assert w_prop.yield_strength_mpa_unirradiated == pytest.approx(900.0)
        assert w_prop.yield_strength_mpa_irradiated is None

    def test_test_temps_all_present(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        temps = {p.test_temp for p in db_session.query(MechanicalProperty).all()}
        assert {25.0, 300.0, 20.0}.issubset(temps)

    def test_charpy_kv_mapped(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "charpy.csv")
        make_charpy_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        prop = db_session.query(MechanicalProperty).first()
        assert prop is not None
        assert prop.kv_joules == pytest.approx(8.5)

    def test_charpy_nan_irr_state_treated_as_unirradiated(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import IrradiationCondition

        csv_path = str(tmp_path / "charpy.csv")
        make_charpy_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        cond = db_session.query(IrradiationCondition).first()
        assert cond.irradiation_state == "unirradiated"
        assert cond.dose_dpa is None

    def test_irradiated_row_routed_to_irradiated_columns(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import IrradiationCondition, MechanicalProperty

        csv_path = str(tmp_path / "irr.csv")
        make_irradiated_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        prop = db_session.query(MechanicalProperty).first()
        assert prop is not None
        assert prop.yield_strength_mpa_irradiated == pytest.approx(700.0)
        assert prop.uts_mpa_irradiated == pytest.approx(820.0)
        assert prop.yield_strength_mpa_unirradiated is None

        irr = db_session.query(IrradiationCondition).first()
        assert irr.irradiation_state == "irradiated"
        assert irr.dose_dpa == pytest.approx(2.5)
        assert irr.irradiation_temp == pytest.approx(325.0)
        assert irr.reactor == "BOR-60"

    def test_raw_json_stored(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        prop = db_session.query(MechanicalProperty).first()
        assert prop.raw_extraction_json is not None
        parsed = json.loads(prop.raw_extraction_json)
        assert "Name" in parsed

    def test_unirradiated_irradiation_conditions(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import IrradiationCondition

        csv_path = str(tmp_path / "test.csv")
        make_test_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        conditions = db_session.query(IrradiationCondition).all()
        assert all(c.irradiation_state == "unirradiated" for c in conditions)
        assert all(c.dose_dpa is None for c in conditions)


class TestEdgeCases:
    def test_dummy_rows_filtered(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "dummy.csv")
        make_dummy_mixed_csv(csv_path)
        n = ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        assert n == 1
        assert db_session.query(MechanicalProperty).count() == 1

    def test_rows_without_measurements_skipped(self, db_session, tmp_path):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        csv_path = str(tmp_path / "empty.csv")
        make_empty_properties_csv(csv_path)
        ingest_matdb4fusion_csv(csv_path, db_session)
        db_session.commit()

        assert db_session.query(MechanicalProperty).count() == 0


# ---------------------------------------------------------------------------
# Integration tests - real CSV (skipped when file not present)
# ---------------------------------------------------------------------------

@pytest.mark.skipif(not _real_csv_exists, reason="Real MatDB4Fusion CSV not present")
class TestRealCSVIntegration:
    def test_total_records_gt_300(self, db_session):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        n = ingest_matdb4fusion_csv(_REAL_CSV, db_session)
        db_session.commit()

        count = db_session.query(MechanicalProperty).count()
        assert count > 300, f"Expected >300 records, got {count}"
        assert n == count

    def test_dummy_rows_excluded(self, db_session):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv

        n = ingest_matdb4fusion_csv(_REAL_CSV, db_session)
        assert n < 354

    def test_three_material_names(self, db_session):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Material

        ingest_matdb4fusion_csv(_REAL_CSV, db_session)
        db_session.commit()

        names = {m.name for m in db_session.query(Material).all()}
        assert {"EUROFER97", "W", "W, K-doped"}.issubset(names)

    def test_paper_record_correct(self, db_session):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import Paper

        ingest_matdb4fusion_csv(_REAL_CSV, db_session)
        db_session.commit()

        paper = db_session.get(Paper, "matdb4fusion_2026")
        assert paper.year == 2026
        assert paper.access_type == "matdb4fusion_ingest"

    def test_all_confidence_scores_are_one(self, db_session):
        from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
        from fusionmatdb.storage.schema import MechanicalProperty

        ingest_matdb4fusion_csv(_REAL_CSV, db_session)
        db_session.commit()

        non_one = (
            db_session.query(MechanicalProperty)
            .filter(MechanicalProperty.confidence_score != 1.0)
            .count()
        )
        assert non_one == 0
