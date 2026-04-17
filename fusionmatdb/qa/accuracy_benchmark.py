"""Benchmark VLM extraction accuracy against manually verified reference records."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FieldAccuracy:
    field_name: str
    n_compared: int = 0
    n_correct: int = 0
    mean_absolute_error: float | None = None


@dataclass
class AccuracyReport:
    fields: list[FieldAccuracy] = field(default_factory=list)
    overall_precision: float = 0.0
    overall_recall: float = 0.0


NUMERIC_FIELDS = [
    "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
    "uts_mpa_irradiated", "dose_dpa", "irradiation_temp_c",
    "hardness_value", "dbtt_k_irradiated",
]


def benchmark_extraction(
    extracted_records: list[dict],
    reference_path: str | Path,
    tolerance: float = 0.05,
) -> AccuracyReport:
    """Compare extracted records against a reference set.

    Args:
        extracted_records: Records from VLM extraction.
        reference_path: Path to JSON file with manually verified records.
        tolerance: Relative tolerance for numeric comparison (default 5%).
    """
    ref_records = json.loads(Path(reference_path).read_text())
    report = AccuracyReport()

    for field_name in NUMERIC_FIELDS:
        fa = FieldAccuracy(field_name=field_name)
        errors = []
        for ref in ref_records:
            ref_val = ref.get(field_name)
            if ref_val is None:
                continue
            # Find matching extracted record by material + conditions
            match = _find_match(ref, extracted_records)
            if match is None:
                continue
            ext_val = match.get(field_name)
            if ext_val is None:
                continue
            fa.n_compared += 1
            rel_err = abs(ext_val - ref_val) / abs(ref_val) if ref_val != 0 else abs(ext_val)
            errors.append(rel_err)
            if rel_err <= tolerance:
                fa.n_correct += 1
        if errors:
            fa.mean_absolute_error = sum(errors) / len(errors)
        report.fields.append(fa)

    total_compared = sum(f.n_compared for f in report.fields)
    total_correct = sum(f.n_correct for f in report.fields)
    report.overall_precision = total_correct / total_compared if total_compared else 0.0
    return report


def _find_match(ref: dict, extracted: list[dict]) -> dict | None:
    """Find the extracted record that best matches a reference record."""
    ref_mat = ref.get("material_name", "").lower()
    ref_dose = ref.get("dose_dpa")
    ref_temp = ref.get("irradiation_temp_c")
    for ext in extracted:
        if ext.get("material_name", "").lower() != ref_mat:
            continue
        if ref_dose is not None and ext.get("dose_dpa") != ref_dose:
            continue
        if ref_temp is not None and ext.get("irradiation_temp_c") != ref_temp:
            continue
        return ext
    return None
