"""Generate standalone HTML data quality report for FusionMatDB."""
from __future__ import annotations

import io
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import (
    Base, Paper, MechanicalProperty, DataQualityAssessment,
    ProvenanceRecord, PageTriageResult, ReviewQueueItem,
)
from fusionmatdb.qa.qa_report import generate_qa_report
from fusionmatdb.qa.dedup_detector import find_exact_duplicates
from fusionmatdb.trust.trust_score import compute_trust_score, QUALITY_LEVEL_POINTS


def _render_trust_histogram(session: Session) -> str:
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt

        props = session.query(MechanicalProperty).all()
        scores = []
        for prop in props:
            dqa = session.query(DataQualityAssessment).filter_by(
                mechanical_property_id=prop.id
            ).first()
            prov = session.query(ProvenanceRecord).filter_by(
                mechanical_property_id=prop.id
            ).first()
            quality_level = dqa.quality_level if dqa else "inferred"
            has_bounds = any([
                prop.yield_strength_mpa_irradiated_lower,
                prop.uts_mpa_irradiated_lower,
                prop.hardness_lower,
                prop.dbtt_k_irradiated_lower,
            ])
            has_trace = bool(dqa and dqa.source_page_number)
            score = compute_trust_score(
                quality_level=quality_level,
                confidence_score=prop.confidence_score or 0.0,
                has_uncertainty_bounds=has_bounds,
                has_traceability=has_trace,
                reviewed_by_human=prop.reviewed_by_human or False,
                is_primary=prov.is_primary if prov else True,
            )
            scores.append(score)

        if not scores:
            return "<p>No records to chart.</p>"

        fig, ax = plt.subplots(figsize=(8, 4))
        ax.hist(scores, bins=20, range=(0, 100), color="#2563eb", edgecolor="white")
        ax.set_xlabel("Trust Score")
        ax.set_ylabel("Records")
        ax.set_title("Engineering Trust Score Distribution")
        buf = io.BytesIO()
        fig.savefig(buf, format="svg", bbox_inches="tight")
        plt.close(fig)
        return buf.getvalue().decode("utf-8")
    except ImportError:
        return "<p>matplotlib not available — chart skipped.</p>"


def _lineage_card(session: Session, prop_id: int) -> str:
    from fusionmatdb.trust.lineage import get_lineage
    try:
        l = get_lineage(session, prop_id)
    except ValueError:
        return ""
    prop = session.query(MechanicalProperty).get(prop_id)
    mat_name = prop.material.name if prop and prop.material else "Unknown"
    return f"""
    <div style="border:1px solid #d1d5db;border-radius:8px;padding:16px;margin:8px 0;background:#f9fafb">
        <strong>Record #{l.record_id}</strong> — {mat_name} — {l.source_institution or 'Unknown'}<br>
        Paper: {l.paper_title}<br>
        Source: <a href="{l.source_pdf_url}">{l.source_pdf_url}</a> → Page {l.source_page_number} → {l.source_figure_or_table or 'N/A'}<br>
        Quality: {l.quality_level} | Trust: {l.trust_score}/100 | Confidence: {l.confidence_score}<br>
        Extraction: {l.extraction_method} ({l.extraction_pass}) | Cross-page: {l.cross_page_context_used}<br>
        Hash: <code>{l.content_hash[:16] if l.content_hash else 'N/A'}...</code> | Primary: {l.is_primary}
    </div>"""


def generate_quality_report(db_path: str, output_path: str) -> Path:
    """Generate standalone HTML quality report."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        qa = generate_qa_report(session)
        clusters = find_exact_duplicates(session)
        trust_chart = _render_trust_histogram(session)

        sample_props = session.query(MechanicalProperty).limit(3).all()
        lineage_cards = "".join(_lineage_card(session, p.id) for p in sample_props)

        triage_results = session.query(PageTriageResult).all()
        triage_stats: dict[str, int] = {}
        for t in triage_results:
            triage_stats[t.classification] = triage_stats.get(t.classification, 0) + 1

        pending = session.query(ReviewQueueItem).filter_by(review_status="pending").count()
        total_reviews = session.query(ReviewQueueItem).count()

        n_papers = session.query(Paper).count()

        quality_rows = ""
        for level, points in sorted(QUALITY_LEVEL_POINTS.items(), key=lambda x: -x[1]):
            count = qa.quality_level_counts.get(level, 0)
            pct = count / qa.total_records * 100 if qa.total_records else 0
            quality_rows += f"<tr><td>{level}</td><td>{count}</td><td>{pct:.1f}%</td><td>{points}/30 pts</td></tr>\n"

        trace_pct = qa.records_with_traceability / qa.total_records * 100 if qa.total_records else 0
        uncert_pct = qa.records_with_uncertainty / qa.total_records * 100 if qa.total_records else 0

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>FusionMatDB Data Quality Report</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 1000px; margin: 0 auto; padding: 20px; color: #1f2937; line-height: 1.6; }}
h1 {{ color: #1e40af; border-bottom: 3px solid #2563eb; padding-bottom: 8px; }}
h2 {{ color: #1e3a5f; margin-top: 40px; border-bottom: 1px solid #d1d5db; padding-bottom: 4px; }}
table {{ border-collapse: collapse; width: 100%; margin: 16px 0; }}
th, td {{ border: 1px solid #d1d5db; padding: 8px 12px; text-align: left; }}
th {{ background: #f3f4f6; font-weight: 600; }}
.metric {{ display: inline-block; background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 8px; padding: 16px 24px; margin: 8px; text-align: center; }}
.metric .value {{ font-size: 2em; font-weight: bold; color: #1e40af; }}
.metric .label {{ font-size: 0.9em; color: #6b7280; }}
.section-num {{ color: #6b7280; }}
</style>
</head>
<body>
<h1>FusionMatDB Data Quality Report</h1>
<p><em>Generated for UKAEA and Tokamak Energy — demonstrating data quality, provenance, and trustworthiness of FusionMatDB.</em></p>

<h2><span class="section-num">1.</span> Executive Summary</h2>
<div>
<div class="metric"><div class="value">{qa.total_records:,}</div><div class="label">Total Records</div></div>
<div class="metric"><div class="value">{n_papers}</div><div class="label">Source Documents</div></div>
<div class="metric"><div class="value">{qa.high_confidence_pct:.0f}%</div><div class="label">High Confidence</div></div>
<div class="metric"><div class="value">{trace_pct:.0f}%</div><div class="label">Fully Traceable</div></div>
</div>
{trust_chart}

<h2><span class="section-num">2.</span> Data Quality Hierarchy</h2>
<p>Every record is classified into one of five quality levels:</p>
<table>
<tr><th>Quality Level</th><th>Records</th><th>Percentage</th><th>Trust Points</th></tr>
{quality_rows}
</table>

<h2><span class="section-num">3.</span> Traceability</h2>
<p>{trace_pct:.1f}% of records link back to source PDF + page number. Direct PDF links allow visual inspection of original evidence.</p>
<h3>Sample Lineage Cards</h3>
{lineage_cards if lineage_cards else '<p>No records available for lineage display.</p>'}

<h2><span class="section-num">4.</span> Provenance &amp; De-duplication</h2>
<p><strong>{len(clusters)}</strong> duplicate clusters detected using content hashing (SHA256 of key value fields). Each cluster has a designated primary record.</p>

<h2><span class="section-num">5.</span> Uncertainty &amp; Statistical Representation</h2>
<p><strong>{uncert_pct:.1f}%</strong> of records have uncertainty bounds (upper/lower). Records include distribution type and specimen count where available, enabling Bayesian and GP workflows.</p>

<h2><span class="section-num">6.</span> Validation &amp; QA</h2>
<p>Extraction confidence: {qa.high_confidence_pct:.0f}% of records score &ge; 0.7.</p>
<p>Cross-field physics checks flagged <strong>{qa.cross_field_flag_count}</strong> records for anomalous relationships.</p>
<p>Average field completeness: <strong>{qa.completeness_avg:.2f}</strong></p>

<h2><span class="section-num">7.</span> Observability &amp; Transparency</h2>
<p>Every step of the extraction pipeline is auditable:</p>
<ul>
<li>Raw VLM responses preserved as JSON on disk per page</li>
<li>Page triage classifications: {dict(triage_stats) if triage_stats else 'Not yet run'}</li>
<li>Full lineage queryable via <code>fusionmatdb lineage &lt;record_id&gt;</code></li>
<li>Review queue: {pending} pending / {total_reviews} total items</li>
</ul>

<h2><span class="section-num">8.</span> Engineering Decision Support</h2>
<p>The engineering trust score (0-100) combines quality level, extraction confidence, uncertainty availability, traceability, human review status, and deduplication status.</p>
<p>See the histogram above for the distribution across all records.</p>

<h2><span class="section-num">9.</span> Data Extraction Quality</h2>
<p>Extraction performed using multimodal VLM (Gemini Flash on Vertex AI) with temperature=0 for deterministic output.</p>
<p>Two-pass extraction strategy: first pass with text context from adjacent pages, second pass with full image context for flagged incomplete records.</p>
<p>Page quality triage pre-screens all pages to skip unreadable content and flag degraded scans for human review.</p>

<h2><span class="section-num">10.</span> Fraud &amp; Anomaly Detection</h2>
<p>Automated scans detect two classes of suspect data:</p>
<ul>
<li><strong>Visual duplicate figures:</strong> Perceptual hashing (pHash) compares figure images across all PDFs. Pairs with Hamming distance &le; 8 are flagged as potential reuse of the same plot in different contexts.</li>
<li><strong>Suspicious data matches:</strong> Records from different papers with identical numerical values but different experimental conditions are flagged for review. This catches copy-paste errors and undeclared data reuse.</li>
</ul>
<p>Run <code>fusionmatdb fraud-scan</code> to execute. Results are surfaced in the review queue for human disposition.</p>

<h2><span class="section-num">11.</span> Extraction Accuracy &amp; Benchmarking</h2>
<p>Extraction quality is validated through three mechanisms:</p>
<ul>
<li><strong>Human vs. automated benchmark:</strong> A worksheet (<code>fusionmatdb benchmark-worksheet</code>) selects data-dense PDF pages for human annotation. Per-field accuracy is computed with configurable tolerance (default 5%) against the automated extraction.</li>
<li><strong>Cross-database validation:</strong> Extracted values are compared against SDC-IC and MatDB4Fusion reference databases (<code>fusionmatdb cross-validate</code>). Per-field mean absolute error and accuracy are reported.</li>
<li><strong>Multi-model ensemble (planned):</strong> Running extraction with multiple VLMs and comparing outputs to identify low-agreement records for human review.</li>
</ul>

<hr>
<p style="color:#6b7280;font-size:0.9em">
Report generated by FusionMatDB v0.1.0 |
<a href="https://github.com/Khalizo/fusionmatdb">GitHub</a> |
<a href="https://huggingface.co/datasets/Khalizo/fusionmatdb">HuggingFace</a>
</p>
</body>
</html>"""

    out = Path(output_path)
    out.write_text(html)
    return out
