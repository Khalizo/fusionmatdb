"""Run updated extraction pipeline on 3 sample ORNL reports to validate new features."""
from __future__ import annotations

import json
from pathlib import Path


SAMPLE_REPORTS = [10, 40, 70]


def run_sample_extraction(pdf_dir: str = "data/ornl_pdfs", db: str = "sample_run.sqlite"):
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.storage.schema import Paper
    from fusionmatdb.discovery.ornl_reports import ORNLDownloader
    from fusionmatdb.access.vision_extractor import VertexVisionExtractor
    from fusionmatdb.extraction.page_triage import PageTriager
    from fusionmatdb.cli import _store_records
    from fusionmatdb.scripts.backfill_quality import (
        backfill_quality_assessments, backfill_provenance, backfill_dedup_clusters,
    )
    from fusionmatdb.reporting.quality_report import generate_quality_report

    init_db(db)
    session = get_session()

    print("=== Step 1: Download sample reports ===")
    downloader = ORNLDownloader(output_dir=pdf_dir, max_report=max(SAMPLE_REPORTS) + 1)
    for num in SAMPLE_REPORTS:
        result = downloader.download_one(num)
        print(f"  Report {num}: {result['status']}")

    print("\n=== Step 2: Page triage ===")
    triager = PageTriager()
    triage_results = {}
    for num in SAMPLE_REPORTS:
        pdf_path = Path(pdf_dir) / f"ornl_report_{num}.pdf"
        if not pdf_path.exists():
            print(f"  Report {num}: PDF not found, skipping")
            continue
        results = triager.triage_pdf(pdf_path)
        triage_results[num] = results
        stats: dict[str, int] = {}
        for r in results:
            stats[r.classification] = stats.get(r.classification, 0) + 1
        print(f"  Report {num}: {len(results)} pages — {stats}")

    print("\n=== Step 3: Extraction (first pass with text context) ===")
    extractor = VertexVisionExtractor()
    total_extracted = 0
    total_stored = 0

    for num in SAMPLE_REPORTS:
        pdf_path = Path(pdf_dir) / f"ornl_report_{num}.pdf"
        if not pdf_path.exists():
            continue
        paper_id = f"ornl_{num}"

        paper = Paper(
            id=paper_id,
            title=f"ORNL Fusion Materials Semiannual Progress Report {num}",
            access_type="ornl_report",
            source_url=f"https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-{num}.pdf",
            full_text_available=True,
        )
        existing = session.get(Paper, paper_id)
        if existing:
            session.delete(existing)
            session.flush()
        session.add(paper)
        session.flush()

        records = extractor.extract_pdf(str(pdf_path), paper_id=paper_id)
        n_extracted = len(records)
        n_stored = _store_records(session, paper_id, records, min_confidence=0.5)
        session.commit()
        total_extracted += n_extracted
        total_stored += n_stored
        print(f"  Report {num}: {n_extracted} extracted, {n_stored} stored")

    print("\n=== Step 4: Backfill quality & provenance ===")
    n_qa = backfill_quality_assessments(session)
    session.commit()
    n_prov = backfill_provenance(session)
    session.commit()
    n_dedup = backfill_dedup_clusters(session)
    session.commit()
    print(f"  Quality assessments: {n_qa}")
    print(f"  Provenance records: {n_prov}")
    print(f"  Dedup updates: {n_dedup}")

    print("\n=== Step 5: Generate quality report ===")
    report_path = generate_quality_report(db, "sample_quality_report.html")
    print(f"  Report: {report_path}")

    print("\n=== Validation ===")
    from fusionmatdb.storage.schema import MechanicalProperty
    props = session.query(MechanicalProperty).all()
    with_bounds = sum(1 for p in props if any([
        p.yield_strength_mpa_irradiated_lower, p.uts_mpa_irradiated_lower,
        p.hardness_lower, p.dbtt_k_irradiated_lower,
    ]))

    print(f"  Total records: {len(props)}")
    print(f"  With uncertainty bounds: {with_bounds} ({with_bounds/max(len(props),1)*100:.0f}%)")
    print(f"\nSample run complete. Open sample_quality_report.html to inspect.")


if __name__ == "__main__":
    run_sample_extraction()
