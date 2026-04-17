import pytest
from fusionmatdb.trust.trust_score import compute_trust_score


def test_trust_score_accredited_lab_full():
    score = compute_trust_score(
        quality_level="accredited_lab",
        confidence_score=1.0,
        has_uncertainty_bounds=True,
        has_traceability=True,
        reviewed_by_human=True,
        is_primary=True,
    )
    assert score == 100


def test_trust_score_curated_database_typical():
    score = compute_trust_score(
        quality_level="curated_database",
        confidence_score=0.85,
        has_uncertainty_bounds=False,
        has_traceability=True,
        reviewed_by_human=False,
        is_primary=True,
    )
    assert 40 < score < 70


def test_trust_score_inferred_minimal():
    score = compute_trust_score(
        quality_level="inferred",
        confidence_score=0.3,
        has_uncertainty_bounds=False,
        has_traceability=False,
        reviewed_by_human=False,
        is_primary=False,
    )
    assert score < 20


def test_trust_score_simulation():
    score = compute_trust_score(
        quality_level="simulation",
        confidence_score=0.9,
        has_uncertainty_bounds=True,
        has_traceability=True,
        reviewed_by_human=False,
        is_primary=True,
    )
    # simulation=8 + confidence=18 + uncertainty=15 + trace=15 + primary=10 = 66
    assert 60 < score < 70


def test_trust_score_clamps_to_100():
    score = compute_trust_score(
        quality_level="accredited_lab",
        confidence_score=1.0,
        has_uncertainty_bounds=True,
        has_traceability=True,
        reviewed_by_human=True,
        is_primary=True,
    )
    assert score <= 100
