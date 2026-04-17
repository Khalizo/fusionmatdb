"""Generate QA summary reports."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import MechanicalProperty, DataQualityAssessment


@dataclass
class QAReport:
    total_records: int = 0
    high_confidence_count: int = 0
    high_confidence_pct: float = 0.0
    cross_field_flag_count: int = 0
    completeness_avg: float = 0.0
    records_with_uncertainty: int = 0
    records_with_traceability: int = 0
    quality_level_counts: dict[str, int] = field(default_factory=dict)


def generate_qa_report(session: Session) -> QAReport:
    """Generate a QA summary from the database."""
    from fusionmatdb.extraction.validator import cross_field_checks, completeness_score

    report = QAReport()
    props = session.query(MechanicalProperty).all()
    report.total_records = len(props)

    if not props:
        return report

    completeness_sum = 0.0
    for prop in props:
        if prop.confidence_score is not None and prop.confidence_score >= 0.7:
            report.high_confidence_count += 1

        # Build record dict for validator
        record = {
            "material_name": prop.material.name if prop.material else None,
            "yield_strength_mpa_irradiated": prop.yield_strength_mpa_irradiated,
            "yield_strength_mpa_unirradiated": prop.yield_strength_mpa_unirradiated,
            "elongation_pct_irradiated": prop.elongation_pct_irradiated,
            "elongation_pct_unirradiated": prop.elongation_pct_unirradiated,
            "irradiation_state": prop.irradiation_condition.irradiation_state if prop.irradiation_condition else None,
            "dose_dpa": prop.irradiation_condition.dose_dpa if prop.irradiation_condition else None,
        }
        flags = cross_field_checks(record)
        if flags:
            report.cross_field_flag_count += 1

        completeness_sum += completeness_score(record)

        has_bounds = any([
            prop.yield_strength_mpa_irradiated_lower,
            prop.uts_mpa_irradiated_lower,
            prop.hardness_lower,
            prop.dbtt_k_irradiated_lower,
            prop.yield_strength_mpa_std,
            prop.uts_mpa_std,
            prop.hardness_std,
            prop.dbtt_k_std,
        ])
        if has_bounds:
            report.records_with_uncertainty += 1

        dqa = session.query(DataQualityAssessment).filter_by(
            mechanical_property_id=prop.id
        ).first()
        if dqa:
            report.quality_level_counts[dqa.quality_level] = (
                report.quality_level_counts.get(dqa.quality_level, 0) + 1
            )
            if dqa.source_page_number is not None:
                report.records_with_traceability += 1

    report.high_confidence_pct = report.high_confidence_count / report.total_records * 100
    report.completeness_avg = completeness_sum / report.total_records
    return report
