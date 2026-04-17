"""Validate FusionMatDB against external reference databases."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import MechanicalProperty, Material, IrradiationCondition


@dataclass
class FieldValidation:
    field_name: str
    n_compared: int = 0
    n_within_tolerance: int = 0
    mean_absolute_error: float = 0.0
    errors: list[float] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.n_within_tolerance / self.n_compared if self.n_compared else 0.0


@dataclass
class CrossDBReport:
    reference_db_name: str
    total_reference_records: int = 0
    total_matched: int = 0
    field_validations: list[FieldValidation] = field(default_factory=list)
    overall_accuracy: float = 0.0


COMPARE_FIELDS = [
    ("yield_strength_mpa_unirradiated", "yield_strength_mpa_unirradiated"),
    ("uts_mpa_unirradiated", "uts_mpa_unirradiated"),
    ("thermal_conductivity_unirradiated", "thermal_conductivity_unirradiated"),
]


def validate_against_sdc_ic(session: Session, tolerance: float = 0.05) -> CrossDBReport:
    """Compare FusionMatDB ORNL records against SDC-IC design curves already in DB."""
    report = CrossDBReport(reference_db_name="SDC-IC Material Library")

    sdc_props = (
        session.query(MechanicalProperty, Material)
        .join(Material)
        .filter(MechanicalProperty.paper_id == "sdc_ic_material_library")
        .all()
    )
    report.total_reference_records = len(sdc_props)

    ornl_props = (
        session.query(MechanicalProperty, Material, IrradiationCondition)
        .join(Material, MechanicalProperty.material_id == Material.id)
        .outerjoin(IrradiationCondition, MechanicalProperty.irradiation_id == IrradiationCondition.id)
        .filter(MechanicalProperty.paper_id.like("ornl_%"))
        .all()
    )

    for db_field, ref_field in COMPARE_FIELDS:
        fv = FieldValidation(field_name=db_field)
        for sdc_prop, sdc_mat in sdc_props:
            sdc_val = getattr(sdc_prop, ref_field, None)
            if sdc_val is None:
                continue
            sdc_temp = sdc_prop.test_temp

            for ornl_prop, ornl_mat, ornl_irr in ornl_props:
                if ornl_mat.name != sdc_mat.name:
                    continue
                if ornl_prop.test_temp is None or sdc_temp is None:
                    continue
                if abs(ornl_prop.test_temp - sdc_temp) > 25:
                    continue

                ornl_val = getattr(ornl_prop, db_field, None)
                if ornl_val is None:
                    continue

                fv.n_compared += 1
                report.total_matched += 1
                error = abs(ornl_val - sdc_val)
                fv.errors.append(error)
                rel_error = error / abs(sdc_val) if sdc_val != 0 else error
                if rel_error <= tolerance:
                    fv.n_within_tolerance += 1

        if fv.errors:
            fv.mean_absolute_error = sum(fv.errors) / len(fv.errors)
        report.field_validations.append(fv)

    total_compared = sum(f.n_compared for f in report.field_validations)
    total_correct = sum(f.n_within_tolerance for f in report.field_validations)
    report.overall_accuracy = total_correct / total_compared if total_compared else 0.0
    return report


def validate_against_matdb4fusion(
    session: Session, csv_path: str | Path, tolerance: float = 0.05
) -> CrossDBReport:
    """Compare FusionMatDB against MatDB4Fusion CSV export."""
    report = CrossDBReport(reference_db_name="MatDB4Fusion (KIT)")
    csv_path = Path(csv_path)
    if not csv_path.exists():
        return report

    ref_df = pd.read_csv(csv_path)
    report.total_reference_records = len(ref_df)

    ornl_props = (
        session.query(MechanicalProperty, Material)
        .join(Material)
        .filter(MechanicalProperty.paper_id.like("ornl_%"))
        .all()
    )

    for _, ref_row in ref_df.iterrows():
        ref_mat = str(ref_row.get("material_name", "")).lower()
        for ornl_prop, ornl_mat in ornl_props:
            if ornl_mat.name.lower() != ref_mat:
                continue
            report.total_matched += 1
            break

    return report
