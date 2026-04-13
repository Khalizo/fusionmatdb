# fusionmatdb/fusionmatdb/storage/exporter.py
"""Export FusionMatDB to Parquet, HuggingFace SFT, and world model formats."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import MechanicalProperty, Paper, Material


def export_parquet(session: Session, output_path: str, min_confidence: float = 0.7) -> int:
    """Export irradiation property data to Parquet for ML training."""
    rows = (
        session.query(MechanicalProperty, Material, Paper)
        .join(Material, MechanicalProperty.material_id == Material.id)
        .join(Paper, MechanicalProperty.paper_id == Paper.id)
        .filter(MechanicalProperty.confidence_score >= min_confidence)
        .all()
    )
    records = []
    for prop, mat, paper in rows:
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
            "delta_yield_strength_mpa": delta,
            "confidence_score": prop.confidence_score,
        })
    df = pd.DataFrame(records) if records else pd.DataFrame(columns=[
        "paper_id", "year", "material_name", "material_class",
        "W", "Cr", "V", "Ta", "experiment_type", "test_temp_c",
        "yield_strength_mpa_unirradiated", "yield_strength_mpa_irradiated",
        "delta_yield_strength_mpa", "confidence_score",
    ])
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
