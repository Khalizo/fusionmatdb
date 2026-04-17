"""Generate reference extraction worksheets for human vs automated comparison."""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import fitz


@dataclass
class WorksheetPage:
    report_number: int
    page_number: int
    page_image_path: str
    pymupdf_text: str
    ground_truth_records: list[dict] = field(default_factory=list)


@dataclass
class BenchmarkWorksheet:
    pages: list[WorksheetPage] = field(default_factory=list)
    notes: str = ""


def generate_worksheet(
    pdf_dir: str | Path,
    report_numbers: list[int],
    pages_per_report: int = 2,
    output_dir: str | Path = "benchmark",
) -> Path:
    """Generate a benchmark worksheet for human extraction.

    Selects data-dense pages from each report, exports page images,
    and creates a JSON worksheet template for expert annotation.
    """
    pdf_dir = Path(pdf_dir)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    images_dir = output_dir / "page_images"
    images_dir.mkdir(exist_ok=True)

    worksheet = BenchmarkWorksheet(
        notes="Fill in ground_truth_records for each page by manually reading the page image. "
              "Each record should be a dict with fields matching the FusionMatDB extraction schema."
    )

    for report_num in report_numbers:
        pdf_path = pdf_dir / f"ornl_report_{report_num}.pdf"
        if not pdf_path.exists():
            continue
        doc = fitz.open(str(pdf_path))

        # Score pages by text density to find data-rich pages
        page_scores = []
        for i in range(len(doc)):
            text = doc[i].get_text()
            score = 0
            for keyword in ["Table", "MPa", "dpa", "°C", "yield", "tensile", "hardness",
                           "elongation", "fracture", "DBTT", "swelling"]:
                score += text.lower().count(keyword.lower())
            page_scores.append((i, score))

        # Pick top pages by score
        page_scores.sort(key=lambda x: -x[1])
        selected = page_scores[:pages_per_report]

        for page_idx, score in selected:
            page_num = page_idx + 1
            page = doc[page_idx]

            # Export page image
            pix = page.get_pixmap(matrix=fitz.Matrix(150/72, 150/72))
            img_path = images_dir / f"report_{report_num}_page_{page_num}.png"
            pix.save(str(img_path))

            text = page.get_text()
            worksheet.pages.append(WorksheetPage(
                report_number=report_num,
                page_number=page_num,
                page_image_path=str(img_path),
                pymupdf_text=text,
                ground_truth_records=[],
            ))
        doc.close()

    # Save worksheet as JSON
    output_path = output_dir / "benchmark_worksheet.json"
    data = {
        "notes": worksheet.notes,
        "instructions": [
            "For each page, examine the page image and extract ALL data points.",
            "Each record should include: material_name, irradiation_state, dose_dpa, "
            "irradiation_temp_c, test_temp_c, and any measured property values.",
            "Use null for fields that are not present on the page.",
            "This is the ground truth — be as accurate as possible.",
        ],
        "pages": [
            {
                "report_number": p.report_number,
                "page_number": p.page_number,
                "page_image_path": p.page_image_path,
                "pymupdf_text_preview": p.pymupdf_text[:500],
                "ground_truth_records": p.ground_truth_records,
            }
            for p in worksheet.pages
        ],
    }
    output_path.write_text(json.dumps(data, indent=2))
    return output_path


@dataclass
class FieldComparison:
    field_name: str
    n_compared: int = 0
    n_within_tolerance: int = 0
    absolute_errors: list[float] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        return self.n_within_tolerance / self.n_compared if self.n_compared else 0.0

    @property
    def mean_absolute_error(self) -> float:
        return sum(self.absolute_errors) / len(self.absolute_errors) if self.absolute_errors else 0.0


@dataclass
class BenchmarkReport:
    field_comparisons: list[FieldComparison] = field(default_factory=list)
    total_human_records: int = 0
    total_automated_records: int = 0
    overall_accuracy: float = 0.0


BENCHMARK_NUMERIC_FIELDS = [
    "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
    "uts_mpa_irradiated", "uts_mpa_unirradiated",
    "dose_dpa", "irradiation_temp_c", "test_temp_c",
    "hardness_value", "elongation_pct_irradiated",
    "fracture_toughness_mpa_sqrt_m", "dbtt_k_irradiated",
]


def compare_worksheet(
    worksheet_path: str | Path,
    extracted_records: list[dict],
    tolerance: float = 0.05,
) -> BenchmarkReport:
    """Compare human ground truth against automated extraction."""
    worksheet = json.loads(Path(worksheet_path).read_text())
    report = BenchmarkReport()

    human_records = []
    for page in worksheet["pages"]:
        human_records.extend(page.get("ground_truth_records", []))
    report.total_human_records = len(human_records)
    report.total_automated_records = len(extracted_records)

    for field_name in BENCHMARK_NUMERIC_FIELDS:
        fc = FieldComparison(field_name=field_name)
        for human in human_records:
            human_val = human.get(field_name)
            if human_val is None:
                continue
            match = _find_matching_record(human, extracted_records)
            if match is None:
                continue
            auto_val = match.get(field_name)
            if auto_val is None:
                continue
            fc.n_compared += 1
            error = abs(auto_val - human_val)
            fc.absolute_errors.append(error)
            rel_error = error / abs(human_val) if human_val != 0 else error
            if rel_error <= tolerance:
                fc.n_within_tolerance += 1
        report.field_comparisons.append(fc)

    total_compared = sum(f.n_compared for f in report.field_comparisons)
    total_correct = sum(f.n_within_tolerance for f in report.field_comparisons)
    report.overall_accuracy = total_correct / total_compared if total_compared else 0.0
    return report


def _find_matching_record(human: dict, extracted: list[dict]) -> dict | None:
    """Find extracted record matching a human annotation by material + conditions."""
    h_mat = (human.get("material_name") or "").lower()
    h_dose = human.get("dose_dpa")
    h_temp = human.get("irradiation_temp_c")
    for ext in extracted:
        if (ext.get("material_name") or "").lower() != h_mat:
            continue
        if h_dose is not None and ext.get("dose_dpa") != h_dose:
            continue
        if h_temp is not None and ext.get("irradiation_temp_c") != h_temp:
            continue
        return ext
    return None
