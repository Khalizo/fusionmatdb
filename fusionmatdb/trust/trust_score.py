"""Composite engineering trust score for FusionMatDB records."""
from __future__ import annotations

QUALITY_LEVEL_POINTS = {
    "accredited_lab": 30,
    "curated_database": 22,
    "peer_reviewed_literature": 15,
    "simulation": 8,
    "inferred": 3,
}


def compute_trust_score(
    quality_level: str,
    confidence_score: float,
    has_uncertainty_bounds: bool,
    has_traceability: bool,
    reviewed_by_human: bool,
    is_primary: bool,
) -> int:
    """Compute 0-100 trust score from quality dimensions."""
    score = 0
    score += QUALITY_LEVEL_POINTS.get(quality_level, 0)
    score += int(confidence_score * 20)
    if has_uncertainty_bounds:
        score += 15
    if has_traceability:
        score += 15
    if reviewed_by_human:
        score += 10
    if is_primary:
        score += 10
    return min(score, 100)
