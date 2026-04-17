"""Full provenance lineage for a FusionMatDB record."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import (
    MechanicalProperty, DataQualityAssessment, ProvenanceRecord,
)
from fusionmatdb.trust.trust_score import compute_trust_score


@dataclass
class LineageReport:
    record_id: int
    paper_id: str
    paper_title: str
    paper_doi: str | None
    source_pdf_url: str | None
    source_page_number: int | None
    source_figure_or_table: str | None
    source_institution: str | None
    quality_level: str | None
    quality_justification: str | None
    confidence_score: float | None
    trust_score: int
    extraction_method: str | None
    extraction_pass: str | None
    cross_page_context_used: bool | None
    content_hash: str | None
    is_primary: bool | None
    duplicate_cluster_id: int | None
    root_origin: str | None


def get_lineage(session: Session, record_id: int) -> LineageReport:
    """Build full provenance chain for a MechanicalProperty record."""
    prop = session.query(MechanicalProperty).get(record_id)
    if prop is None:
        raise ValueError(f"Record {record_id} not found")

    paper = prop.paper
    dqa = session.query(DataQualityAssessment).filter_by(
        mechanical_property_id=record_id
    ).first()
    prov = session.query(ProvenanceRecord).filter_by(
        mechanical_property_id=record_id
    ).first()

    quality_level = dqa.quality_level if dqa else None
    has_bounds = any([
        prop.yield_strength_mpa_irradiated_lower,
        prop.uts_mpa_irradiated_lower,
        prop.hardness_lower,
        prop.dbtt_k_irradiated_lower,
    ])
    has_trace = bool(dqa and dqa.source_page_number)

    trust = compute_trust_score(
        quality_level=quality_level or "inferred",
        confidence_score=prop.confidence_score or 0.0,
        has_uncertainty_bounds=has_bounds,
        has_traceability=has_trace,
        reviewed_by_human=prop.reviewed_by_human or False,
        is_primary=prov.is_primary if prov else True,
    )

    return LineageReport(
        record_id=record_id,
        paper_id=paper.id,
        paper_title=paper.title,
        paper_doi=paper.doi,
        source_pdf_url=dqa.source_pdf_url if dqa else paper.source_url,
        source_page_number=dqa.source_page_number if dqa else None,
        source_figure_or_table=dqa.source_figure_or_table if dqa else None,
        source_institution=dqa.source_institution if dqa else None,
        quality_level=quality_level,
        quality_justification=dqa.quality_justification if dqa else None,
        confidence_score=prop.confidence_score,
        trust_score=trust,
        extraction_method=prop.extraction_method,
        extraction_pass=prop.extraction_pass,
        cross_page_context_used=prop.cross_page_context_used,
        content_hash=prov.content_hash if prov else None,
        is_primary=prov.is_primary if prov else None,
        duplicate_cluster_id=prov.duplicate_cluster_id if prov else None,
        root_origin=prov.root_origin if prov else None,
    )
