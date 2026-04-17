# fusionmatdb/fusionmatdb/storage/exporter.py
"""Export FusionMatDB to Parquet, HuggingFace SFT, and world model formats."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import MechanicalProperty, Paper, Material


def export_parquet(session: Session, output_path: str, min_confidence: float = 0.7, min_trust: int | None = None) -> int:
    """Export irradiation property data to Parquet for ML training."""
    from fusionmatdb.storage.schema import DataQualityAssessment, ProvenanceRecord
    from fusionmatdb.trust.trust_score import compute_trust_score

    rows = (
        session.query(MechanicalProperty, Material, Paper)
        .join(Material, MechanicalProperty.material_id == Material.id)
        .join(Paper, MechanicalProperty.paper_id == Paper.id)
        .filter(MechanicalProperty.confidence_score >= min_confidence)
        .all()
    )
    records = []
    for prop, mat, paper in rows:
        dqa = session.query(DataQualityAssessment).filter_by(
            mechanical_property_id=prop.id
        ).first()
        prov = session.query(ProvenanceRecord).filter_by(
            mechanical_property_id=prop.id
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

        if min_trust is not None and trust < min_trust:
            continue

        delta = None
        if prop.yield_strength_mpa_irradiated is not None and prop.yield_strength_mpa_unirradiated is not None:
            delta = prop.yield_strength_mpa_irradiated - prop.yield_strength_mpa_unirradiated

        records.append({
            "paper_id": paper.id,
            "year": paper.year,
            "material_name": mat.name,
            "material_class": mat.class_,
            "W": mat.W, "Cr": mat.Cr, "V": mat.V, "Ta": mat.Ta,
            "experiment_type": prop.experiment_type,
            "test_temp_c": prop.test_temp,
            "yield_strength_mpa_unirradiated": prop.yield_strength_mpa_unirradiated,
            "yield_strength_mpa_irradiated": prop.yield_strength_mpa_irradiated,
            "yield_strength_mpa_irradiated_lower": prop.yield_strength_mpa_irradiated_lower,
            "yield_strength_mpa_irradiated_upper": prop.yield_strength_mpa_irradiated_upper,
            "delta_yield_strength_mpa": delta,
            "confidence_score": prop.confidence_score,
            "quality_level": quality_level,
            "trust_score": trust,
            "source_pdf_url": dqa.source_pdf_url if dqa else paper.source_url,
            "source_page_number": dqa.source_page_number if dqa else None,
            "content_hash": prov.content_hash if prov else None,
            "is_primary": prov.is_primary if prov else None,
            "n_specimens": prop.n_specimens,
            "distribution_type": prop.distribution_type,
        })

    df = pd.DataFrame(records) if records else pd.DataFrame()
    df.to_parquet(output_path, index=False)
    return len(records)


def export_world_model(session: Session, output_path: str, min_confidence: float = 0.7) -> int:
    """Export as world model format: {state_before, action, state_after}."""
    rows = (
        session.query(MechanicalProperty, Material)
        .join(Material, MechanicalProperty.material_id == Material.id)
        .filter(
            MechanicalProperty.confidence_score >= min_confidence,
            MechanicalProperty.yield_strength_mpa_irradiated.isnot(None),
            MechanicalProperty.yield_strength_mpa_unirradiated.isnot(None),
        )
        .all()
    )
    examples = []
    for prop, mat in rows:
        examples.append({
            "state_before": {
                "material_name": mat.name,
                "material_class": mat.class_,
                "yield_strength_mpa": prop.yield_strength_mpa_unirradiated,
                "uts_mpa": prop.uts_mpa_unirradiated,
            },
            "action": {
                "experiment_type": prop.experiment_type,
                "test_temp_c": prop.test_temp,
            },
            "state_after": {
                "yield_strength_mpa": prop.yield_strength_mpa_irradiated,
                "uts_mpa": prop.uts_mpa_irradiated,
            },
        })
    with open(output_path, "w") as f:
        json.dump(examples, f, indent=2)
    return len(examples)
