# FusionMatDB Data Quality & Provenance — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add data quality hierarchy, full traceability, provenance/dedup, uncertainty representation, validation/QA, trust scoring, page triage, cross-page context, and a customer-facing HTML quality report to FusionMatDB.

**Architecture:** 6 sub-projects in 4 phases. Phase 1 (schema + extraction prompt) and Phase 2 (QA + trust) run in parallel worktrees. Phase 3 (backfill) and Phase 4 (sample run + report) run sequentially. Each agent commits atomically to its own branch.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, SQLite, Gemini Flash (Vertex AI), pymupdf, matplotlib, pytest.

**Spec:** `docs/superpowers/specs/2026-04-17-data-quality-provenance-design.md`

---

## File Structure

```
fusionmatdb/
├── storage/
│   ├── schema.py              # MODIFY: add 4 new tables + new columns
│   └── database.py            # MODIFY: no Alembic (use create_all), keep simple
├── extraction/
│   ├── prompts.py             # MODIFY: add traceability/uncertainty fields
│   ├── page_triage.py         # CREATE: PageTriager class
│   └── validator.py           # MODIFY: add cross-field physics checks
├── access/
│   └── vision_extractor.py    # MODIFY: cross-page context, triage integration
├── qa/
│   ├── __init__.py            # CREATE
│   ├── dedup_detector.py      # CREATE
│   ├── qa_report.py           # CREATE
│   ├── review_queue.py        # CREATE
│   └── accuracy_benchmark.py  # CREATE
├── trust/
│   ├── __init__.py            # CREATE
│   ├── trust_score.py         # CREATE
│   └── lineage.py             # CREATE
├── reporting/
│   ├── __init__.py            # CREATE
│   └── quality_report.py      # CREATE
├── knowledge/
│   └── __init__.py            # CREATE (stub)
├── scripts/
│   └── backfill_quality.py    # CREATE
├── cli.py                     # MODIFY: add new commands + FIELD_MAP entries
tests/
├── test_schema_quality.py     # CREATE
├── test_page_triage.py        # CREATE
├── test_review_queue.py       # CREATE
├── test_cross_page_context.py # CREATE
├── test_validator_enhanced.py # CREATE
├── test_dedup.py              # CREATE
├── test_trust_score.py        # CREATE
├── test_lineage.py            # CREATE
├── test_backfill.py           # CREATE
├── test_quality_report.py     # CREATE
```

---

## PHASE 1 — Parallel Agents

### Task 1: Schema & Metadata Layer (Agent A — worktree branch `feat/schema-quality`)

**Files:**
- Modify: `fusionmatdb/storage/schema.py`
- Modify: `fusionmatdb/storage/database.py`
- Modify: `fusionmatdb/cli.py` (FIELD_MAP additions)
- Create: `tests/test_schema_quality.py`

- [ ] **Step 1: Write failing test for new tables and columns**

```python
# tests/test_schema_quality.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
    DataQualityAssessment, ProvenanceRecord, PageTriageResult, ReviewQueueItem,
)


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="test-001", title="Test paper", year=2023, access_type="ornl_report",
                      source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-70.pdf")
        mat = Material(paper_id="test-001", name="EUROFER97", class_="RAFM_steel")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(
            paper_id="test-001", material_id=mat.id,
            irradiation_state="irradiated", dose_dpa=10.0, irradiation_temp=300.0,
            dose_dpa_lower=9.5, dose_dpa_upper=10.5,
            irradiation_temp_lower=290.0, irradiation_temp_upper=310.0,
        )
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="test-001", material_id=mat.id, irradiation_id=irr.id,
            experiment_type="Mechanical Tensile", test_temp=25.0,
            yield_strength_mpa_irradiated=650.0,
            yield_strength_mpa_irradiated_lower=640.0,
            yield_strength_mpa_irradiated_upper=660.0,
            uts_mpa_irradiated=750.0,
            uts_mpa_irradiated_lower=740.0,
            uts_mpa_irradiated_upper=760.0,
            hardness_value=250.0,
            hardness_lower=245.0,
            hardness_upper=255.0,
            dbtt_k_irradiated=350.0,
            dbtt_k_irradiated_lower=340.0,
            dbtt_k_irradiated_upper=360.0,
            distribution_type="normal",
            n_specimens=5,
            extraction_pass="first_pass",
            cross_page_context_used=True,
            confidence_score=0.85,
            extraction_method="gemini_vision",
        )
        session.add(prop)
        session.flush()
        yield session, paper, mat, irr, prop


def test_data_quality_assessment_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    dqa = DataQualityAssessment(
        mechanical_property_id=prop.id,
        quality_level="curated_database",
        quality_justification="ORNL semiannual report, experimental tensile test",
        source_page_number=42,
        source_figure_or_table="Table 3.2",
        source_pdf_url=paper.source_url,
        source_institution="ORNL",
        extraction_accuracy_score=0.9,
    )
    session.add(dqa)
    session.commit()
    result = session.query(DataQualityAssessment).filter_by(mechanical_property_id=prop.id).one()
    assert result.quality_level == "curated_database"
    assert result.source_page_number == 42
    assert result.source_figure_or_table == "Table 3.2"
    assert result.source_institution == "ORNL"
    assert result.extraction_accuracy_score == 0.9


def test_provenance_record_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    prov = ProvenanceRecord(
        mechanical_property_id=prop.id,
        root_origin="ornl_70",
        duplicate_cluster_id=1,
        content_hash="a" * 64,
        is_primary=True,
    )
    session.add(prov)
    session.commit()
    result = session.query(ProvenanceRecord).filter_by(mechanical_property_id=prop.id).one()
    assert result.content_hash == "a" * 64
    assert result.is_primary is True
    assert result.duplicate_cluster_id == 1


def test_uncertainty_bounds_on_mechanical_property(db_session):
    session, paper, mat, irr, prop = db_session
    session.commit()
    result = session.query(MechanicalProperty).get(prop.id)
    assert result.yield_strength_mpa_irradiated_lower == 640.0
    assert result.yield_strength_mpa_irradiated_upper == 660.0
    assert result.distribution_type == "normal"
    assert result.n_specimens == 5


def test_irradiation_condition_bounds(db_session):
    session, paper, mat, irr, prop = db_session
    session.commit()
    result = session.query(IrradiationCondition).get(irr.id)
    assert result.dose_dpa_lower == 9.5
    assert result.dose_dpa_upper == 10.5
    assert result.irradiation_temp_lower == 290.0
    assert result.irradiation_temp_upper == 310.0


def test_extraction_pass_and_cross_page(db_session):
    session, paper, mat, irr, prop = db_session
    session.commit()
    result = session.query(MechanicalProperty).get(prop.id)
    assert result.extraction_pass == "first_pass"
    assert result.cross_page_context_used is True


def test_page_triage_result_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    from datetime import datetime, timezone
    triage = PageTriageResult(
        paper_id="test-001",
        page_number=42,
        classification="clean",
        reason="Clear table with material properties",
        has_extractable_data=True,
        triage_model="gemini-3-flash-preview",
        triage_timestamp=datetime.now(timezone.utc),
    )
    session.add(triage)
    session.commit()
    result = session.query(PageTriageResult).filter_by(paper_id="test-001", page_number=42).one()
    assert result.classification == "clean"
    assert result.has_extractable_data is True


def test_review_queue_item_roundtrip(db_session):
    session, paper, mat, irr, prop = db_session
    item = ReviewQueueItem(
        paper_id="test-001",
        page_number=42,
        mechanical_property_id=prop.id,
        flag_reason="degraded_page",
        flag_detail="Faded scan, low contrast on table borders",
        extraction_path="first_pass",
        review_status="pending",
    )
    session.add(item)
    session.commit()
    result = session.query(ReviewQueueItem).filter_by(mechanical_property_id=prop.id).one()
    assert result.flag_reason == "degraded_page"
    assert result.review_status == "pending"


def test_quality_level_values():
    valid_levels = {"accredited_lab", "curated_database", "peer_reviewed_literature", "simulation", "inferred"}
    for level in valid_levels:
        dqa = DataQualityAssessment(
            mechanical_property_id=1,
            quality_level=level,
        )
        assert dqa.quality_level == level
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_schema_quality.py -v`
Expected: ImportError — DataQualityAssessment, ProvenanceRecord, etc. don't exist yet

- [ ] **Step 3: Implement schema additions in `fusionmatdb/storage/schema.py`**

Add to the end of schema.py, before closing (after `MechanicalProperty` class). Also add new columns to existing classes:

```python
# Add to IrradiationCondition class:
    irradiation_temp_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    irradiation_temp_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dose_dpa_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dose_dpa_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

# Add to MechanicalProperty class:
    # Uncertainty bounds
    yield_strength_mpa_irradiated_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yield_strength_mpa_irradiated_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uts_mpa_irradiated_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uts_mpa_irradiated_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hardness_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hardness_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dbtt_k_irradiated_lower: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dbtt_k_irradiated_upper: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Statistical metadata
    distribution_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    n_specimens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # Extraction pipeline metadata
    extraction_pass: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cross_page_context_used: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)


class DataQualityAssessment(Base):
    __tablename__ = "data_quality_assessments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mechanical_property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mechanical_properties.id"), unique=True, nullable=False
    )
    quality_level: Mapped[str] = mapped_column(String, nullable=False)
    quality_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_page_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    source_figure_or_table: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_pdf_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_institution: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    extraction_accuracy_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    mechanical_property: Mapped["MechanicalProperty"] = relationship("MechanicalProperty", backref="quality_assessment")


class ProvenanceRecord(Base):
    __tablename__ = "provenance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    mechanical_property_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("mechanical_properties.id"), unique=True, nullable=False
    )
    root_origin: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duplicate_cluster_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    content_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    is_primary: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)

    mechanical_property: Mapped["MechanicalProperty"] = relationship("MechanicalProperty", backref="provenance")


class PageTriageResult(Base):
    __tablename__ = "page_triage_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    classification: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    has_extractable_data: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    triage_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    triage_timestamp: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    paper: Mapped["Paper"] = relationship("Paper")


class ReviewQueueItem(Base):
    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id"), nullable=False)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    mechanical_property_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("mechanical_properties.id"), nullable=True
    )
    flag_reason: Mapped[str] = mapped_column(String, nullable=False)
    flag_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    extraction_path: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    review_status: Mapped[str] = mapped_column(String, nullable=False, default="pending")
    reviewer: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reviewer_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    paper: Mapped["Paper"] = relationship("Paper")
    mechanical_property: Mapped[Optional["MechanicalProperty"]] = relationship("MechanicalProperty")
```

- [ ] **Step 4: Add FIELD_MAP entries in `fusionmatdb/cli.py`**

Add to `FIELD_MAP` dict (after existing entries):

```python
    # Uncertainty bounds
    "yield_strength_mpa_irradiated_lower": "yield_strength_mpa_irradiated_lower",
    "yield_strength_mpa_irradiated_upper": "yield_strength_mpa_irradiated_upper",
    "uts_mpa_irradiated_lower": "uts_mpa_irradiated_lower",
    "uts_mpa_irradiated_upper": "uts_mpa_irradiated_upper",
    "hardness_lower": "hardness_lower",
    "hardness_upper": "hardness_upper",
    "dbtt_k_irradiated_lower": "dbtt_k_irradiated_lower",
    "dbtt_k_irradiated_upper": "dbtt_k_irradiated_upper",
    # Statistical metadata
    "n_specimens": "n_specimens",
```

Add to `_store_records` function, in the prop_kwargs dict construction (after `raw_extraction_json`):

```python
            distribution_type=rec.get("distribution_type") or None,
            n_specimens=rec.get("n_specimens"),
            extraction_pass=rec.get("extraction_pass", "first_pass"),
            cross_page_context_used=rec.get("cross_page_context_used", False),
```

Also add to `IrradiationCondition` creation in `_store_records`:

```python
                    dose_dpa_lower=rec.get("dose_dpa_lower"),
                    dose_dpa_upper=rec.get("dose_dpa_upper"),
                    irradiation_temp_lower=rec.get("irradiation_temp_lower"),
                    irradiation_temp_upper=rec.get("irradiation_temp_upper"),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_schema_quality.py -v`
Expected: All 8 tests PASS

- [ ] **Step 6: Verify existing tests still pass**

Run: `pytest tests/test_schema.py tests/test_database.py tests/test_exporter.py -v`
Expected: All existing tests PASS (new columns are nullable, so backwards compatible)

- [ ] **Step 7: Commit**

```bash
git add fusionmatdb/storage/schema.py fusionmatdb/cli.py tests/test_schema_quality.py
git commit -m "feat: add data quality, provenance, triage, review queue tables and uncertainty columns"
```

---

### Task 2: Extraction Prompt & Cross-Page Context (Agent B — worktree branch `feat/extraction-upgrade`)

**Files:**
- Modify: `fusionmatdb/extraction/prompts.py`
- Create: `fusionmatdb/extraction/page_triage.py`
- Modify: `fusionmatdb/access/vision_extractor.py`
- Create: `fusionmatdb/qa/__init__.py`
- Create: `fusionmatdb/qa/review_queue.py`
- Create: `tests/test_page_triage.py`
- Create: `tests/test_cross_page_context.py`

- [ ] **Step 1: Write failing test for updated prompt fields**

```python
# tests/test_cross_page_context.py
import json
import pytest


def test_fields_definition_contains_traceability():
    from fusionmatdb.extraction.prompts import _FIELDS
    assert "source_reference" in _FIELDS
    assert "source_institution" in _FIELDS
    assert "n_specimens" in _FIELDS
    assert "data_origin" in _FIELDS
    assert "experimental_method_detail" in _FIELDS


def test_fields_definition_contains_uncertainty_bounds():
    from fusionmatdb.extraction.prompts import _FIELDS
    assert "yield_strength_mpa_irradiated_lower" in _FIELDS
    assert "yield_strength_mpa_irradiated_upper" in _FIELDS
    assert "hardness_lower" in _FIELDS
    assert "dose_dpa_lower" in _FIELDS


def test_vision_prompt_contains_cross_page_instructions():
    from fusionmatdb.extraction.prompts import VISION_EXTRACTION_PROMPT
    assert "source_reference" in VISION_EXTRACTION_PROMPT
    assert "source_institution" in VISION_EXTRACTION_PROMPT


def test_first_pass_prompt_contains_context_placeholders():
    from fusionmatdb.extraction.prompts import FIRST_PASS_VISION_PROMPT
    assert "CONTEXT FROM PREVIOUS PAGE" in FIRST_PASS_VISION_PROMPT
    assert "CONTEXT FROM NEXT PAGE" in FIRST_PASS_VISION_PROMPT
    assert "Do NOT extract data from the context text" in FIRST_PASS_VISION_PROMPT


def test_second_pass_prompt_contains_middle_page_instruction():
    from fusionmatdb.extraction.prompts import SECOND_PASS_VISION_PROMPT
    assert "MIDDLE page only" in SECOND_PASS_VISION_PROMPT
    assert "Do NOT extract data from the first or last page" in SECOND_PASS_VISION_PROMPT


def test_parse_response_handles_new_fields():
    """VLM response with new fields should parse correctly."""
    from fusionmatdb.access.vision_extractor import VertexVisionExtractor
    ext = VertexVisionExtractor.__new__(VertexVisionExtractor)
    raw = json.dumps([{
        "material_name": "EUROFER97",
        "material_class": "RAFM_steel",
        "irradiation_state": "irradiated",
        "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0,
        "yield_strength_mpa_irradiated": 650.0,
        "yield_strength_mpa_irradiated_lower": 640.0,
        "yield_strength_mpa_irradiated_upper": 660.0,
        "source_reference": "Table 3.2",
        "source_institution": "ORNL",
        "n_specimens": 5,
        "data_origin": "primary_measurement",
        "experimental_method_detail": "miniature tensile, gauge length 5mm",
    }])
    records = ext._parse_response(raw, "ornl_70", 42)
    assert len(records) == 1
    rec = records[0]
    assert rec["source_reference"] == "Table 3.2"
    assert rec["source_institution"] == "ORNL"
    assert rec["n_specimens"] == 5
    assert rec["yield_strength_mpa_irradiated_lower"] == 640.0


def test_incomplete_record_detection():
    """Records missing material_name or irradiation conditions should be flagged."""
    from fusionmatdb.extraction.page_triage import is_record_incomplete
    # Missing material name
    assert is_record_incomplete({"yield_strength_mpa_irradiated": 650.0})
    # Missing irradiation conditions
    assert is_record_incomplete({"material_name": "W", "yield_strength_mpa_irradiated": 650.0})
    # Complete record
    assert not is_record_incomplete({
        "material_name": "W", "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0, "yield_strength_mpa_irradiated": 650.0,
    })
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cross_page_context.py -v`
Expected: ImportError or assertion errors

- [ ] **Step 3: Update extraction prompts in `fusionmatdb/extraction/prompts.py`**

Add new field sections to `_FIELDS` string (append before the closing `"""`):

```python
# Append to _FIELDS after the METADATA section:

TRACEABILITY & PROVENANCE:
- source_reference: string or null  (exact table/figure ID, e.g. "Table 3.2", "Fig. 4.1a", "p.15 paragraph 2")
- source_institution: string or null  (lab/institution that produced the data, e.g. "ORNL", "JAEA", "KIT", "PNNL")
- experimental_method_detail: string or null  (e.g. "miniature tensile, gauge length 5mm", "Vickers HV10 1kg load")
- n_specimens: integer or null  (number of specimens tested, if stated)
- data_origin: "primary_measurement" or "derived" or "cited_from_other_work" or null

UNCERTAINTY BOUNDS (extract when reported as ranges, error bars, or ± values):
- yield_strength_mpa_irradiated_lower: number or null
- yield_strength_mpa_irradiated_upper: number or null
- uts_mpa_irradiated_lower: number or null
- uts_mpa_irradiated_upper: number or null
- hardness_lower: number or null
- hardness_upper: number or null
- dbtt_k_irradiated_lower: number or null
- dbtt_k_irradiated_upper: number or null
- irradiation_temp_lower: number or null  (°C, if range reported)
- irradiation_temp_upper: number or null
- dose_dpa_lower: number or null
- dose_dpa_upper: number or null
```

Add instructions to `VISION_EXTRACTION_PROMPT` (append before the closing `"""`):

```python
- For EVERY datapoint, record which table or figure it came from in source_reference
- Note the institution/lab that performed the experiment in source_institution
- If the paper cites data from another publication rather than reporting original measurements, set data_origin to "cited_from_other_work"
- Extract upper/lower bounds when shown as error bars, ranges (e.g. "350-400 MPa"), or ± notation
- Record number of specimens (n) when stated (e.g. "n=3", "average of 5 specimens")
- Include experimental method details when given (specimen geometry, test standard, loading rate)
```

Add two new prompt constants:

```python
FIRST_PASS_VISION_PROMPT = """You are analyzing a page from a fusion materials research document.

CONTEXT FROM PREVIOUS PAGE:
{{prev_page_text}}

CONTEXT FROM NEXT PAGE:
{{next_page_text}}

Extract ALL numerical data about material properties and irradiation effects from the IMAGE below.
Use the text context above to resolve missing material names, irradiation conditions, or experimental
details that may have been defined on adjacent pages. Do NOT extract data from the context text — only
use it to fill gaps in the image data.

Return a JSON array where each object has these fields (null for missing):
{fields}

Important:
- Extract data from BOTH tables and figures (read axis labels and data points carefully)
- Include uncertainty values (± numbers) where shown
- For EVERY datapoint, record which table or figure it came from in source_reference
- Note the institution/lab that performed the experiment in source_institution
- If the paper cites data from another publication, set data_origin to "cited_from_other_work"
- Extract upper/lower bounds when shown as error bars, ranges, or ± notation
- Record number of specimens (n) when stated
- Include experimental method details when given
- Return ONLY the JSON array, no other text
""".format(fields=_FIELDS)


SECOND_PASS_VISION_PROMPT = """You are analyzing pages from a fusion materials research document.
You are given 3 consecutive pages. Extract data from the MIDDLE page only.
The surrounding pages provide context — use them to identify material names, irradiation
conditions, and experimental details. Do NOT extract data from the first or last page.

Return a JSON array where each object has these fields (null for missing):
{fields}

Important:
- Extract data from BOTH tables and figures on the MIDDLE page only
- Use the first and last pages to fill in missing context (material names, conditions, methods)
- Include uncertainty values (± numbers) where shown
- For EVERY datapoint, record which table or figure it came from in source_reference
- Note the institution/lab that performed the experiment in source_institution
- Extract upper/lower bounds when shown as error bars, ranges, or ± notation
- Record number of specimens (n) when stated
- Return ONLY the JSON array, no other text
""".format(fields=_FIELDS)


PAGE_TRIAGE_PROMPT = """Classify this page from a fusion materials research document for data extraction readability.

Respond with ONLY a JSON object (no other text):
{{
  "classification": "<clean|degraded|unreadable|no_data>",
  "reason": "<brief explanation>",
  "has_extractable_data": <true|false>
}}

Classifications:
- clean: Clear text, tables, or figures containing material property data
- degraded: Partially readable (faded scan, overlapping text, poor resolution) but data may be extractable
- unreadable: Cannot reliably extract data (corrupted scan, handwritten, heavily redacted)
- no_data: Page is readable but contains no extractable materials/irradiation data (title pages, references, table of contents, acknowledgements)
"""
```

- [ ] **Step 4: Create page triage module `fusionmatdb/extraction/page_triage.py`**

```python
"""Page quality triage — cheap LLM pre-screening before extraction."""
from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from pathlib import Path

import fitz

from fusionmatdb.extraction.prompts import PAGE_TRIAGE_PROMPT


@dataclass
class TriageResult:
    page_number: int
    classification: str
    reason: str
    has_extractable_data: bool


def is_record_incomplete(record: dict) -> bool:
    """Check if an extracted record is missing critical context fields."""
    has_property = any(
        record.get(f) is not None
        for f in [
            "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
            "uts_mpa_irradiated", "hardness_value", "fracture_toughness_mpa_sqrt_m",
            "dbtt_k_irradiated", "volumetric_swelling_pct",
        ]
    )
    if not has_property:
        return False
    if not record.get("material_name"):
        return True
    has_conditions = (
        record.get("dose_dpa") is not None or record.get("irradiation_temp_c") is not None
    )
    if not has_conditions:
        return True
    return False


def get_adjacent_page_text(doc: fitz.Document, page_idx: int) -> tuple[str, str]:
    """Extract text from pages adjacent to page_idx using pymupdf."""
    prev_text = ""
    next_text = ""
    if page_idx > 0:
        prev_text = doc[page_idx - 1].get_text()
    if page_idx < len(doc) - 1:
        next_text = doc[page_idx + 1].get_text()
    return prev_text, next_text


class PageTriager:
    """Classify PDF pages for extraction readability using a cheap LLM call."""

    MAX_CONCURRENT = 20

    def __init__(self):
        self._client = None
        self._model = None

    def _get_client(self):
        if self._client is None:
            import os
            from google import genai
            vertex_api_key = os.environ.get("GOOGLE_CLOUD_API_KEY")
            if vertex_api_key:
                self._client = genai.Client(vertexai=True, api_key=vertex_api_key)
                self._model = "gemini-3-flash-preview"
            else:
                api_key = os.environ.get("GOOGLE_API_KEY")
                if not api_key:
                    raise RuntimeError("No Google API key found. Set GOOGLE_CLOUD_API_KEY or GOOGLE_API_KEY.")
                self._client = genai.Client(api_key=api_key)
                self._model = "gemini-2.5-flash"
        return self._client

    def _page_to_image(self, page: fitz.Page) -> bytes:
        mat = fitz.Matrix(72 / 72, 72 / 72)  # Lower DPI for triage — saves tokens
        pix = page.get_pixmap(matrix=mat)
        return pix.tobytes("png")

    def _parse_triage(self, raw: str, page_num: int) -> TriageResult:
        raw = raw.strip()
        if raw.startswith("```"):
            parts = raw.split("```")
            raw = parts[1] if len(parts) > 1 else raw
            if raw.startswith("json"):
                raw = raw[4:]
        raw = raw.strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return TriageResult(page_num, "clean", "Failed to parse triage response", True)
        return TriageResult(
            page_number=page_num,
            classification=data.get("classification", "clean"),
            reason=data.get("reason", ""),
            has_extractable_data=data.get("has_extractable_data", True),
        )

    def triage_pdf(self, pdf_path: str | Path) -> list[TriageResult]:
        """Triage all pages in a PDF. Returns classification per page."""
        return asyncio.run(self._triage_pdf_async(pdf_path))

    async def _triage_pdf_async(self, pdf_path: str | Path) -> list[TriageResult]:
        from google.genai import types
        client = self._get_client()
        doc = fitz.open(str(pdf_path))
        semaphore = asyncio.Semaphore(self.MAX_CONCURRENT)

        async def process_page(i: int) -> TriageResult:
            page_num = i + 1
            async with semaphore:
                loop = asyncio.get_event_loop()
                img_bytes = await loop.run_in_executor(None, lambda: self._page_to_image(doc[i]))
                try:
                    resp = await loop.run_in_executor(
                        None,
                        lambda: client.models.generate_content(
                            model=self._model,
                            contents=[
                                types.Part.from_bytes(data=img_bytes, mime_type="image/png"),
                                PAGE_TRIAGE_PROMPT,
                            ],
                            config=types.GenerateContentConfig(
                                temperature=0,
                                thinking_config=types.ThinkingConfig(thinking_budget=0),
                            ),
                        ),
                    )
                    return self._parse_triage(resp.text, page_num)
                except Exception:
                    return TriageResult(page_num, "clean", "Triage failed, defaulting to clean", True)

        tasks = [process_page(i) for i in range(len(doc))]
        return await asyncio.gather(*tasks)
```

- [ ] **Step 5: Create review queue module `fusionmatdb/qa/__init__.py` and `fusionmatdb/qa/review_queue.py`**

```python
# fusionmatdb/qa/__init__.py
"""Quality assurance modules for FusionMatDB."""
```

```python
# fusionmatdb/qa/review_queue.py
"""Human review queue — flag records for manual inspection."""
from __future__ import annotations

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import ReviewQueueItem


def flag_for_review(
    session: Session,
    paper_id: str,
    page_number: int,
    flag_reason: str,
    flag_detail: str,
    extraction_path: str = "first_pass",
    mechanical_property_id: int | None = None,
) -> ReviewQueueItem:
    """Add a record to the human review queue."""
    item = ReviewQueueItem(
        paper_id=paper_id,
        page_number=page_number,
        mechanical_property_id=mechanical_property_id,
        flag_reason=flag_reason,
        flag_detail=flag_detail,
        extraction_path=extraction_path,
        review_status="pending",
    )
    session.add(item)
    return item


def get_pending_reviews(session: Session, paper_id: str | None = None) -> list[ReviewQueueItem]:
    """Get all pending review queue items, optionally filtered by paper."""
    query = session.query(ReviewQueueItem).filter_by(review_status="pending")
    if paper_id:
        query = query.filter_by(paper_id=paper_id)
    return query.all()


def resolve_review(
    session: Session,
    review_id: int,
    status: str,
    reviewer: str,
    notes: str | None = None,
) -> ReviewQueueItem:
    """Mark a review queue item as resolved."""
    item = session.query(ReviewQueueItem).get(review_id)
    if item is None:
        raise ValueError(f"Review queue item {review_id} not found")
    item.review_status = status
    item.reviewer = reviewer
    item.reviewer_notes = notes
    from datetime import datetime, timezone
    item.reviewed_at = datetime.now(timezone.utc).isoformat()
    return item
```

- [ ] **Step 6: Write page triage tests**

```python
# tests/test_page_triage.py
import json
import pytest
from fusionmatdb.extraction.page_triage import (
    TriageResult, is_record_incomplete, get_adjacent_page_text, PageTriager,
)


def test_is_record_incomplete_missing_material():
    assert is_record_incomplete({"yield_strength_mpa_irradiated": 650.0})


def test_is_record_incomplete_missing_conditions():
    assert is_record_incomplete({
        "material_name": "W",
        "yield_strength_mpa_irradiated": 650.0,
    })


def test_is_record_incomplete_complete():
    assert not is_record_incomplete({
        "material_name": "W",
        "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0,
        "yield_strength_mpa_irradiated": 650.0,
    })


def test_is_record_incomplete_no_property():
    """Records with no property values are not flagged as incomplete."""
    assert not is_record_incomplete({"material_name": "W"})


def test_parse_triage_valid_json():
    triager = PageTriager.__new__(PageTriager)
    raw = json.dumps({
        "classification": "degraded",
        "reason": "Faded scan",
        "has_extractable_data": True,
    })
    result = triager._parse_triage(raw, 42)
    assert result.classification == "degraded"
    assert result.has_extractable_data is True
    assert result.page_number == 42


def test_parse_triage_markdown_fence():
    triager = PageTriager.__new__(PageTriager)
    raw = '```json\n{"classification": "no_data", "reason": "References page", "has_extractable_data": false}\n```'
    result = triager._parse_triage(raw, 5)
    assert result.classification == "no_data"
    assert result.has_extractable_data is False


def test_parse_triage_invalid_json_defaults_clean():
    triager = PageTriager.__new__(PageTriager)
    result = triager._parse_triage("not json at all", 10)
    assert result.classification == "clean"
    assert result.has_extractable_data is True
```

- [ ] **Step 7: Write review queue tests**

```python
# tests/test_review_queue.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty, ReviewQueueItem,
)
from fusionmatdb.qa.review_queue import flag_for_review, get_pending_reviews, resolve_review


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="test-001", title="Test", year=2023, access_type="ornl_report")
        mat = Material(paper_id="test-001", name="W", class_="tungsten")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(paper_id="test-001", material_id=mat.id)
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="test-001", material_id=mat.id, irradiation_id=irr.id,
            confidence_score=0.8, extraction_method="gemini_vision",
        )
        session.add(prop)
        session.flush()
        yield session, prop


def test_flag_for_review_creates_item(db_session):
    session, prop = db_session
    item = flag_for_review(
        session, "test-001", 42, "degraded_page", "Faded scan",
        mechanical_property_id=prop.id,
    )
    session.flush()
    assert item.id is not None
    assert item.review_status == "pending"


def test_get_pending_reviews(db_session):
    session, prop = db_session
    flag_for_review(session, "test-001", 42, "degraded_page", "Faded")
    flag_for_review(session, "test-001", 43, "physics_check_anomaly", "Yield too high")
    session.flush()
    pending = get_pending_reviews(session)
    assert len(pending) == 2


def test_resolve_review(db_session):
    session, prop = db_session
    item = flag_for_review(session, "test-001", 42, "degraded_page", "Faded")
    session.flush()
    resolved = resolve_review(session, item.id, "approved", "reviewer1", "Looks fine")
    assert resolved.review_status == "approved"
    assert resolved.reviewer == "reviewer1"
    assert resolved.reviewed_at is not None


def test_get_pending_reviews_filters_by_paper(db_session):
    session, prop = db_session
    flag_for_review(session, "test-001", 42, "degraded_page", "Faded")
    session.flush()
    assert len(get_pending_reviews(session, paper_id="test-001")) == 1
    assert len(get_pending_reviews(session, paper_id="other")) == 0
```

- [ ] **Step 8: Run all new tests**

Run: `pytest tests/test_cross_page_context.py tests/test_page_triage.py tests/test_review_queue.py -v`
Expected: All PASS

- [ ] **Step 9: Commit**

```bash
git add fusionmatdb/extraction/prompts.py fusionmatdb/extraction/page_triage.py \
       fusionmatdb/qa/__init__.py fusionmatdb/qa/review_queue.py \
       tests/test_cross_page_context.py tests/test_page_triage.py tests/test_review_queue.py
git commit -m "feat: add traceability/uncertainty extraction fields, page triage, cross-page context, review queue"
```

---

## PHASE 2 — Parallel Agents (depends on Phase 1 schema being merged)

### Task 3: Validation & QA Framework (Agent C — worktree branch `feat/qa-framework`)

**Files:**
- Modify: `fusionmatdb/extraction/validator.py`
- Create: `fusionmatdb/qa/dedup_detector.py`
- Create: `fusionmatdb/qa/qa_report.py`
- Create: `fusionmatdb/qa/accuracy_benchmark.py`
- Modify: `fusionmatdb/cli.py`
- Create: `tests/test_validator_enhanced.py`
- Create: `tests/test_dedup.py`

- [ ] **Step 1: Write failing tests for enhanced validator**

```python
# tests/test_validator_enhanced.py
import pytest
from fusionmatdb.extraction.validator import (
    validate_extraction, score_confidence, cross_field_checks, completeness_score,
)


def test_cross_field_irradiated_yield_too_high():
    record = {
        "material_name": "F82H",
        "yield_strength_mpa_unirradiated": 300.0,
        "yield_strength_mpa_irradiated": 900.0,  # 3x unirradiated — suspicious
    }
    flags = cross_field_checks(record)
    assert any("irradiated yield" in f.lower() or "yield" in f.lower() for f in flags)


def test_cross_field_elongation_increase():
    record = {
        "material_name": "F82H",
        "elongation_pct_unirradiated": 15.0,
        "elongation_pct_irradiated": 20.0,  # Elongation should decrease with irradiation
    }
    flags = cross_field_checks(record)
    assert any("elongation" in f.lower() for f in flags)


def test_cross_field_zero_dose_irradiated():
    record = {
        "material_name": "F82H",
        "irradiation_state": "irradiated",
        "dose_dpa": 0,
    }
    flags = cross_field_checks(record)
    assert any("dose" in f.lower() for f in flags)


def test_cross_field_clean_record():
    record = {
        "material_name": "F82H",
        "irradiation_state": "irradiated",
        "dose_dpa": 10.0,
        "yield_strength_mpa_unirradiated": 300.0,
        "yield_strength_mpa_irradiated": 450.0,
        "elongation_pct_unirradiated": 15.0,
        "elongation_pct_irradiated": 10.0,
    }
    flags = cross_field_checks(record)
    assert len(flags) == 0


def test_completeness_score_full_tensile():
    record = {
        "material_name": "W",
        "material_class": "tungsten",
        "irradiation_state": "irradiated",
        "dose_dpa": 5.0,
        "irradiation_temp_c": 500.0,
        "test_temp_c": 25.0,
        "yield_strength_mpa_irradiated": 650.0,
        "uts_mpa_irradiated": 700.0,
        "elongation_pct_irradiated": 5.0,
        "experiment_type": "Mechanical Tensile",
        "reactor": "HFIR",
    }
    score = completeness_score(record)
    assert score > 0.8


def test_completeness_score_minimal():
    record = {"material_name": "W", "hardness_value": 350.0}
    score = completeness_score(record)
    assert score < 0.3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_validator_enhanced.py -v`
Expected: ImportError — cross_field_checks, completeness_score don't exist

- [ ] **Step 3: Implement enhanced validator**

Add to `fusionmatdb/extraction/validator.py`:

```python
def cross_field_checks(record: dict) -> list[str]:
    """Flag physically suspicious cross-field relationships. Returns list of flag strings."""
    flags = []
    irr_yield = record.get("yield_strength_mpa_irradiated")
    unirr_yield = record.get("yield_strength_mpa_unirradiated")
    if irr_yield is not None and unirr_yield is not None and unirr_yield > 0:
        if irr_yield > 2 * unirr_yield:
            flags.append(
                f"Irradiated yield ({irr_yield} MPa) > 2x unirradiated ({unirr_yield} MPa)"
            )

    irr_elong = record.get("elongation_pct_irradiated")
    unirr_elong = record.get("elongation_pct_unirradiated")
    if irr_elong is not None and unirr_elong is not None:
        if irr_elong > unirr_elong:
            flags.append(
                f"Irradiated elongation ({irr_elong}%) > unirradiated ({unirr_elong}%) — unusual"
            )

    dose = record.get("dose_dpa")
    irr_state = record.get("irradiation_state")
    if irr_state == "irradiated" and dose is not None and dose == 0:
        flags.append("Dose is 0 dpa but irradiation_state is 'irradiated'")

    return flags


IDENTITY_FIELDS = [
    "material_name", "material_class", "irradiation_state", "dose_dpa",
    "irradiation_temp_c", "test_temp_c", "reactor", "particle",
]

PROPERTY_CONTEXT_FIELDS = [
    "experiment_type", "method", "source_reference", "source_institution",
    "n_specimens", "data_origin",
]

ALL_COMPLETENESS_FIELDS = IDENTITY_FIELDS + PROPERTY_CONTEXT_FIELDS + PROPERTY_FIELDS


def completeness_score(record: dict) -> float:
    """Fraction of applicable fields that are populated (0.0–1.0)."""
    populated = sum(1 for f in ALL_COMPLETENESS_FIELDS if record.get(f) is not None)
    return populated / len(ALL_COMPLETENESS_FIELDS) if ALL_COMPLETENESS_FIELDS else 0.0
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_validator_enhanced.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add fusionmatdb/extraction/validator.py tests/test_validator_enhanced.py
git commit -m "feat: add cross-field physics checks and completeness scoring to validator"
```

- [ ] **Step 6: Write failing dedup tests**

```python
# tests/test_dedup.py
import pytest
from fusionmatdb.qa.dedup_detector import compute_content_hash, find_exact_duplicates
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty, ProvenanceRecord,
)


def test_content_hash_deterministic():
    record = {
        "material_name": "EUROFER97",
        "dose_dpa": 10.0,
        "irradiation_temp_c": 300.0,
        "test_temp_c": 25.0,
        "yield_strength_mpa_irradiated": 650.0,
        "uts_mpa_irradiated": 750.0,
        "hardness_value": 250.0,
    }
    h1 = compute_content_hash(record)
    h2 = compute_content_hash(record)
    assert h1 == h2
    assert len(h1) == 64


def test_content_hash_different_for_different_records():
    r1 = {"material_name": "W", "dose_dpa": 10.0, "yield_strength_mpa_irradiated": 650.0}
    r2 = {"material_name": "W", "dose_dpa": 10.0, "yield_strength_mpa_irradiated": 651.0}
    assert compute_content_hash(r1) != compute_content_hash(r2)


def test_content_hash_rounds_floats():
    """Tiny float differences should hash the same."""
    r1 = {"material_name": "W", "dose_dpa": 10.0000001}
    r2 = {"material_name": "W", "dose_dpa": 10.0000002}
    assert compute_content_hash(r1) == compute_content_hash(r2)


def test_find_exact_duplicates():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="p1", title="Test", year=2023, access_type="ornl_report")
        mat = Material(paper_id="p1", name="W", class_="tungsten")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(paper_id="p1", material_id=mat.id, dose_dpa=10.0, irradiation_temp=300.0)
        session.add(irr)
        session.flush()
        # Two identical properties
        for _ in range(2):
            prop = MechanicalProperty(
                paper_id="p1", material_id=mat.id, irradiation_id=irr.id,
                yield_strength_mpa_irradiated=650.0, confidence_score=0.8,
                extraction_method="gemini_vision",
            )
            session.add(prop)
        session.flush()
        session.commit()
        clusters = find_exact_duplicates(session)
        assert len(clusters) >= 1
        assert any(len(c.record_ids) == 2 for c in clusters)
```

- [ ] **Step 7: Implement dedup detector**

```python
# fusionmatdb/qa/dedup_detector.py
"""Duplicate detection for FusionMatDB records."""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import MechanicalProperty, Material, IrradiationCondition

HASH_FIELDS = [
    "material_name", "dose_dpa", "irradiation_temp", "test_temp",
    "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
    "uts_mpa_irradiated", "hardness_value",
]


def _normalize_value(val) -> str:
    if val is None:
        return "null"
    if isinstance(val, float):
        return f"{val:.4f}"
    return str(val)


def compute_content_hash(record: dict) -> str:
    """SHA256 of key fields, normalized and rounded."""
    field_map = {
        "material_name": "material_name",
        "dose_dpa": "dose_dpa",
        "irradiation_temp_c": "irradiation_temp",
        "irradiation_temp": "irradiation_temp",
        "test_temp_c": "test_temp",
        "test_temp": "test_temp",
        "yield_strength_mpa_irradiated": "yield_strength_mpa_irradiated",
        "yield_strength_mpa_unirradiated": "yield_strength_mpa_unirradiated",
        "uts_mpa_irradiated": "uts_mpa_irradiated",
        "hardness_value": "hardness_value",
    }
    canonical = {}
    for src, dst in field_map.items():
        if src in record and dst not in canonical:
            canonical[dst] = record[src]
    parts = [f"{k}={_normalize_value(canonical.get(k))}" for k in HASH_FIELDS]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


@dataclass
class DuplicateCluster:
    content_hash: str
    record_ids: list[int] = field(default_factory=list)
    primary_id: int | None = None


def find_exact_duplicates(session: Session) -> list[DuplicateCluster]:
    """Find records with identical content hashes."""
    props = session.query(MechanicalProperty).all()
    hash_to_ids: dict[str, list[int]] = {}
    for prop in props:
        record = {
            "material_name": prop.material.name if prop.material else None,
            "dose_dpa": prop.irradiation_condition.dose_dpa if prop.irradiation_condition else None,
            "irradiation_temp": prop.irradiation_condition.irradiation_temp if prop.irradiation_condition else None,
            "test_temp": prop.test_temp,
            "yield_strength_mpa_irradiated": prop.yield_strength_mpa_irradiated,
            "yield_strength_mpa_unirradiated": prop.yield_strength_mpa_unirradiated,
            "uts_mpa_irradiated": prop.uts_mpa_irradiated,
            "hardness_value": prop.hardness_value,
        }
        h = compute_content_hash(record)
        hash_to_ids.setdefault(h, []).append(prop.id)

    clusters = []
    for h, ids in hash_to_ids.items():
        if len(ids) > 1:
            clusters.append(DuplicateCluster(
                content_hash=h,
                record_ids=ids,
                primary_id=ids[0],
            ))
    return clusters
```

- [ ] **Step 8: Run dedup tests**

Run: `pytest tests/test_dedup.py -v`
Expected: All PASS

- [ ] **Step 9: Create QA report module**

```python
# fusionmatdb/qa/qa_report.py
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
    quality_level_counts: dict[str, int] = field(default_factory=dict)
    cross_field_flag_count: int = 0
    completeness_avg: float = 0.0
    records_with_uncertainty: int = 0
    records_with_traceability: int = 0


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
        ])
        if has_bounds:
            report.records_with_uncertainty += 1

        dqa = prop.quality_assessment
        if dqa:
            level = dqa[0].quality_level if isinstance(dqa, list) else dqa.quality_level
            report.quality_level_counts[level] = report.quality_level_counts.get(level, 0) + 1
            if dqa[0].source_page_number if isinstance(dqa, list) else dqa.source_page_number:
                report.records_with_traceability += 1

    report.high_confidence_pct = report.high_confidence_count / report.total_records * 100
    report.completeness_avg = completeness_sum / report.total_records
    return report
```

- [ ] **Step 10: Create accuracy benchmark stub**

```python
# fusionmatdb/qa/accuracy_benchmark.py
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
```

- [ ] **Step 11: Add CLI commands to `fusionmatdb/cli.py`**

Add after the existing `export` command:

```python
@cli.command("qa-report")
@click.option("--db", default="fusionmatdb.sqlite")
def qa_report_cmd(db):
    """Print QA summary report."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.qa.qa_report import generate_qa_report
    init_db(db)
    session = get_session()
    report = generate_qa_report(session)
    click.echo(f"Total records:            {report.total_records}")
    click.echo(f"High confidence (>=0.7):  {report.high_confidence_count} ({report.high_confidence_pct:.1f}%)")
    click.echo(f"Cross-field flags:        {report.cross_field_flag_count}")
    click.echo(f"Avg completeness:         {report.completeness_avg:.2f}")
    click.echo(f"Records with uncertainty:  {report.records_with_uncertainty}")
    click.echo(f"Records with traceability: {report.records_with_traceability}")
    if report.quality_level_counts:
        click.echo("Quality levels:")
        for level, count in sorted(report.quality_level_counts.items()):
            click.echo(f"  {level}: {count}")


@cli.command("dedup-scan")
@click.option("--db", default="fusionmatdb.sqlite")
def dedup_scan_cmd(db):
    """Scan for duplicate records."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.qa.dedup_detector import find_exact_duplicates
    init_db(db)
    session = get_session()
    clusters = find_exact_duplicates(session)
    if not clusters:
        click.echo("No exact duplicates found.")
        return
    click.echo(f"Found {len(clusters)} duplicate clusters:")
    for c in clusters[:10]:
        click.echo(f"  Hash: {c.content_hash[:12]}... IDs: {c.record_ids} (primary: {c.primary_id})")
    if len(clusters) > 10:
        click.echo(f"  ... and {len(clusters) - 10} more")


@cli.command("validate")
@click.option("--db", default="fusionmatdb.sqlite")
@click.option("--strict", is_flag=True, help="Fail on any cross-field flag")
def validate_cmd(db, strict):
    """Run enhanced validation on all records."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.storage.schema import MechanicalProperty
    from fusionmatdb.extraction.validator import validate_extraction, cross_field_checks
    init_db(db)
    session = get_session()
    props = session.query(MechanicalProperty).all()
    total_flags = 0
    for prop in props:
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
            total_flags += 1
            if strict:
                for f in flags:
                    click.echo(f"  [ID {prop.id}] {f}")
    click.echo(f"\nValidation complete: {total_flags} records flagged out of {len(props)}")


@cli.command("review-queue")
@click.option("--db", default="fusionmatdb.sqlite")
@click.option("--status", default="pending", help="Filter by status")
def review_queue_cmd(db, status):
    """Show review queue items."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.qa.review_queue import get_pending_reviews
    from fusionmatdb.storage.schema import ReviewQueueItem
    init_db(db)
    session = get_session()
    if status == "pending":
        items = get_pending_reviews(session)
    else:
        items = session.query(ReviewQueueItem).filter_by(review_status=status).all()
    if not items:
        click.echo(f"No items with status '{status}'.")
        return
    click.echo(f"{len(items)} items ({status}):")
    for item in items:
        click.echo(f"  [{item.id}] Paper: {item.paper_id} Page: {item.page_number} "
                    f"Reason: {item.flag_reason} Path: {item.extraction_path}")
```

- [ ] **Step 12: Run all tests**

Run: `pytest tests/test_validator_enhanced.py tests/test_dedup.py -v`
Expected: All PASS

- [ ] **Step 13: Commit**

```bash
git add fusionmatdb/qa/dedup_detector.py fusionmatdb/qa/qa_report.py \
       fusionmatdb/qa/accuracy_benchmark.py fusionmatdb/cli.py \
       tests/test_dedup.py
git commit -m "feat: add dedup detection, QA reporting, accuracy benchmark, CLI commands"
```

---

### Task 4: Trust Scoring & Lineage (Agent D — worktree branch `feat/trust-lineage`)

**Files:**
- Create: `fusionmatdb/trust/__init__.py`
- Create: `fusionmatdb/trust/trust_score.py`
- Create: `fusionmatdb/trust/lineage.py`
- Modify: `fusionmatdb/storage/exporter.py`
- Modify: `fusionmatdb/cli.py`
- Create: `tests/test_trust_score.py`
- Create: `tests/test_lineage.py`

- [ ] **Step 1: Write failing trust score test**

```python
# tests/test_trust_score.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_trust_score.py -v`
Expected: ImportError

- [ ] **Step 3: Implement trust score**

```python
# fusionmatdb/trust/__init__.py
"""Trust and lineage modules for FusionMatDB."""
```

```python
# fusionmatdb/trust/trust_score.py
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
```

- [ ] **Step 4: Run test**

Run: `pytest tests/test_trust_score.py -v`
Expected: All PASS

- [ ] **Step 5: Write failing lineage test**

```python
# tests/test_lineage.py
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
    DataQualityAssessment, ProvenanceRecord,
)
from fusionmatdb.trust.lineage import get_lineage


@pytest.fixture
def populated_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            id="ornl_70", title="ORNL Report 70", year=2024,
            access_type="ornl_report", doi="10.1234/test",
            source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-70.pdf",
        )
        mat = Material(paper_id="ornl_70", name="EUROFER97", class_="RAFM_steel")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(
            paper_id="ornl_70", material_id=mat.id,
            irradiation_state="irradiated", dose_dpa=10.0, irradiation_temp=300.0,
            reactor="HFIR",
        )
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="ornl_70", material_id=mat.id, irradiation_id=irr.id,
            experiment_type="Mechanical Tensile", test_temp=25.0,
            yield_strength_mpa_irradiated=650.0,
            confidence_score=0.85, extraction_method="gemini_vision",
            extraction_pass="first_pass", cross_page_context_used=True,
        )
        session.add(prop)
        session.flush()
        dqa = DataQualityAssessment(
            mechanical_property_id=prop.id,
            quality_level="curated_database",
            quality_justification="ORNL report, experimental tensile",
            source_page_number=42,
            source_figure_or_table="Table 3.2",
            source_pdf_url=paper.source_url,
            source_institution="ORNL",
        )
        prov = ProvenanceRecord(
            mechanical_property_id=prop.id,
            root_origin="ornl_70",
            content_hash="a" * 64,
            is_primary=True,
        )
        session.add_all([dqa, prov])
        session.commit()
        yield session, prop.id


def test_lineage_returns_full_chain(populated_session):
    session, prop_id = populated_session
    lineage = get_lineage(session, prop_id)
    assert lineage.paper_title == "ORNL Report 70"
    assert lineage.source_pdf_url.endswith("70.pdf")
    assert lineage.source_page_number == 42
    assert lineage.source_figure_or_table == "Table 3.2"
    assert lineage.source_institution == "ORNL"
    assert lineage.quality_level == "curated_database"
    assert lineage.content_hash == "a" * 64
    assert lineage.trust_score > 0
    assert lineage.extraction_method == "gemini_vision"
    assert lineage.extraction_pass == "first_pass"


def test_lineage_missing_record(populated_session):
    session, _ = populated_session
    with pytest.raises(ValueError, match="not found"):
        get_lineage(session, 99999)
```

- [ ] **Step 6: Implement lineage**

```python
# fusionmatdb/trust/lineage.py
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
```

- [ ] **Step 7: Run lineage tests**

Run: `pytest tests/test_lineage.py -v`
Expected: All PASS

- [ ] **Step 8: Add export enhancements to `fusionmatdb/storage/exporter.py`**

Modify `export_parquet` to include new metadata columns. Add `min_trust` parameter. In the records loop, add:

```python
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
```

- [ ] **Step 9: Add CLI commands for lineage and updated export**

Add to `fusionmatdb/cli.py`:

```python
@cli.command("lineage")
@click.argument("record_id", type=int)
@click.option("--db", default="fusionmatdb.sqlite")
def lineage_cmd(record_id, db):
    """Show full provenance lineage for a record."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.trust.lineage import get_lineage
    init_db(db)
    session = get_session()
    try:
        l = get_lineage(session, record_id)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"Record ID:       {l.record_id}")
    click.echo(f"Paper:           {l.paper_title}")
    click.echo(f"DOI:             {l.paper_doi or 'N/A'}")
    click.echo(f"Source PDF:      {l.source_pdf_url or 'N/A'}")
    click.echo(f"Page:            {l.source_page_number or 'N/A'}")
    click.echo(f"Figure/Table:    {l.source_figure_or_table or 'N/A'}")
    click.echo(f"Institution:     {l.source_institution or 'N/A'}")
    click.echo(f"Quality:         {l.quality_level or 'N/A'}")
    click.echo(f"Confidence:      {l.confidence_score or 'N/A'}")
    click.echo(f"Trust Score:     {l.trust_score}/100")
    click.echo(f"Extraction:      {l.extraction_method} ({l.extraction_pass})")
    click.echo(f"Cross-page:      {l.cross_page_context_used}")
    click.echo(f"Content Hash:    {l.content_hash or 'N/A'}")
    click.echo(f"Primary:         {l.is_primary}")
    click.echo(f"Duplicate Group: {l.duplicate_cluster_id or 'N/A'}")
```

Update the `export` command to accept `--min-trust`:

```python
@cli.command()
@click.option("--db", default="fusionmatdb.sqlite")
@click.option("--format", "fmt", type=click.Choice(["parquet", "world_model"]), default="parquet")
@click.option("--output", "-o", default="fusionmatdb_export")
@click.option("--min-trust", type=int, default=None, help="Minimum trust score (0-100)")
def export(db, fmt, output, min_trust):
    """Export database to ML training formats."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.storage.exporter import export_parquet, export_world_model
    init_db(db)
    session = get_session()
    if fmt == "parquet":
        path = f"{output}.parquet"
        n = export_parquet(session, path, min_trust=min_trust)
        click.echo(f"Exported {n} records to {path}")
    elif fmt == "world_model":
        path = f"{output}_world_model.json"
        n = export_world_model(session, path)
        click.echo(f"Exported {n} world model examples to {path}")
```

- [ ] **Step 10: Run all tests**

Run: `pytest tests/test_trust_score.py tests/test_lineage.py -v`
Expected: All PASS

- [ ] **Step 11: Commit**

```bash
git add fusionmatdb/trust/__init__.py fusionmatdb/trust/trust_score.py \
       fusionmatdb/trust/lineage.py fusionmatdb/storage/exporter.py \
       fusionmatdb/cli.py tests/test_trust_score.py tests/test_lineage.py
git commit -m "feat: add trust scoring, lineage queries, enhanced export with --min-trust"
```

---

## PHASE 3 — Sequential (depends on Phases 1+2 merged)

### Task 5: Backfill Existing Records

**Files:**
- Create: `fusionmatdb/scripts/backfill_quality.py`
- Create: `tests/test_backfill.py`

- [ ] **Step 1: Write failing backfill test**

```python
# tests/test_backfill.py
import json
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
    DataQualityAssessment, ProvenanceRecord,
)


@pytest.fixture
def db_with_records():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            id="ornl_70", title="ORNL Report 70", year=2024,
            access_type="ornl_report",
            source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-70.pdf",
        )
        mat = Material(paper_id="ornl_70", name="EUROFER97", class_="RAFM_steel")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(
            paper_id="ornl_70", material_id=mat.id,
            dose_dpa=10.0, irradiation_temp=300.0,
        )
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="ornl_70", material_id=mat.id, irradiation_id=irr.id,
            yield_strength_mpa_irradiated=650.0,
            confidence_score=0.85, extraction_method="gemini_vision",
            raw_extraction_json=json.dumps({"page": 42, "material_name": "EUROFER97"}),
        )
        session.add(prop)
        session.commit()
        yield session, prop.id


def test_backfill_creates_quality_assessment(db_with_records):
    from fusionmatdb.scripts.backfill_quality import backfill_quality_assessments
    session, prop_id = db_with_records
    n = backfill_quality_assessments(session)
    session.commit()
    assert n > 0
    dqa = session.query(DataQualityAssessment).filter_by(mechanical_property_id=prop_id).first()
    assert dqa is not None
    assert dqa.quality_level == "curated_database"
    assert dqa.source_institution == "ORNL"
    assert dqa.source_page_number == 42
    assert "ornl" in dqa.source_pdf_url.lower()


def test_backfill_creates_provenance(db_with_records):
    from fusionmatdb.scripts.backfill_quality import backfill_provenance
    session, prop_id = db_with_records
    n = backfill_provenance(session)
    session.commit()
    assert n > 0
    prov = session.query(ProvenanceRecord).filter_by(mechanical_property_id=prop_id).first()
    assert prov is not None
    assert prov.content_hash is not None
    assert len(prov.content_hash) == 64
    assert prov.root_origin == "ornl_70"


def test_backfill_idempotent(db_with_records):
    from fusionmatdb.scripts.backfill_quality import backfill_quality_assessments
    session, _ = db_with_records
    n1 = backfill_quality_assessments(session)
    session.commit()
    n2 = backfill_quality_assessments(session)
    session.commit()
    assert n2 == 0  # No new records created on second run
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_backfill.py -v`
Expected: ImportError

- [ ] **Step 3: Implement backfill script**

```python
# fusionmatdb/scripts/backfill_quality.py
"""Backfill quality assessments and provenance for existing records."""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import (
    MechanicalProperty, DataQualityAssessment, ProvenanceRecord, Paper,
)
from fusionmatdb.qa.dedup_detector import compute_content_hash


def backfill_quality_assessments(session: Session) -> int:
    """Create DataQualityAssessment for records that don't have one."""
    props = (
        session.query(MechanicalProperty)
        .outerjoin(DataQualityAssessment)
        .filter(DataQualityAssessment.id.is_(None))
        .all()
    )
    created = 0
    for prop in props:
        paper = session.query(Paper).get(prop.paper_id)
        page_num = None
        if prop.raw_extraction_json:
            try:
                raw = json.loads(prop.raw_extraction_json)
                page_num = raw.get("page")
            except (json.JSONDecodeError, TypeError):
                pass

        if paper and paper.access_type == "ornl_report":
            institution = "ORNL"
            quality_level = "curated_database"
            justification = "ORNL Fusion Materials Semiannual Progress Report"
        elif paper and paper.access_type == "sdc_ic":
            institution = "ITER IO"
            quality_level = "curated_database"
            justification = "SDC-IC Material Library (ITER design curves)"
        else:
            institution = None
            quality_level = "peer_reviewed_literature"
            justification = None

        dqa = DataQualityAssessment(
            mechanical_property_id=prop.id,
            quality_level=quality_level,
            quality_justification=justification,
            source_page_number=page_num,
            source_pdf_url=paper.source_url if paper else None,
            source_institution=institution,
        )
        session.add(dqa)
        created += 1

    return created


def backfill_provenance(session: Session) -> int:
    """Create ProvenanceRecord for records that don't have one."""
    props = (
        session.query(MechanicalProperty)
        .outerjoin(ProvenanceRecord)
        .filter(ProvenanceRecord.id.is_(None))
        .all()
    )
    created = 0
    for prop in props:
        record = {
            "material_name": prop.material.name if prop.material else None,
            "dose_dpa": prop.irradiation_condition.dose_dpa if prop.irradiation_condition else None,
            "irradiation_temp": prop.irradiation_condition.irradiation_temp if prop.irradiation_condition else None,
            "test_temp": prop.test_temp,
            "yield_strength_mpa_irradiated": prop.yield_strength_mpa_irradiated,
            "yield_strength_mpa_unirradiated": prop.yield_strength_mpa_unirradiated,
            "uts_mpa_irradiated": prop.uts_mpa_irradiated,
            "hardness_value": prop.hardness_value,
        }
        content_hash = compute_content_hash(record)
        prov = ProvenanceRecord(
            mechanical_property_id=prop.id,
            root_origin=prop.paper_id,
            content_hash=content_hash,
            is_primary=True,
        )
        session.add(prov)
        created += 1

    return created


def backfill_dedup_clusters(session: Session) -> int:
    """Assign duplicate_cluster_id to provenance records with matching hashes."""
    from fusionmatdb.qa.dedup_detector import find_exact_duplicates
    clusters = find_exact_duplicates(session)
    updated = 0
    for i, cluster in enumerate(clusters):
        for j, rid in enumerate(cluster.record_ids):
            prov = session.query(ProvenanceRecord).filter_by(mechanical_property_id=rid).first()
            if prov:
                prov.duplicate_cluster_id = i + 1
                prov.is_primary = (j == 0)
                updated += 1
    return updated
```

- [ ] **Step 4: Create `fusionmatdb/scripts/__init__.py`**

```python
# fusionmatdb/scripts/__init__.py
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_backfill.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add fusionmatdb/scripts/__init__.py fusionmatdb/scripts/backfill_quality.py tests/test_backfill.py
git commit -m "feat: add backfill script for quality assessments and provenance records"
```

---

### Task 6: Knowledge Graph Stub & README Update

**Files:**
- Create: `fusionmatdb/knowledge/__init__.py`
- Modify: `README.md`

- [ ] **Step 1: Create stub**

```python
# fusionmatdb/knowledge/__init__.py
# Material knowledge graph — planned, implemented in a separate project.
# See: https://github.com/Khalizo/fusionmatdb for status.
```

- [ ] **Step 2: Update README**

Add a new section after "Known Limitations":

```markdown
## Data Quality & Provenance

FusionMatDB includes a comprehensive data quality framework:

- **Quality hierarchy**: Each record classified as `accredited_lab`, `curated_database`, `peer_reviewed_literature`, `simulation`, or `inferred`
- **Full traceability**: Every record links to source PDF, page number, figure/table reference, and institution
- **Provenance & de-duplication**: Content hashing detects exact duplicates; each record carries a provenance chain
- **Uncertainty bounds**: Upper/lower bounds, distribution type, and specimen count where available
- **Engineering trust score**: 0-100 composite score combining quality level, confidence, traceability, uncertainty, and human review status
- **Page quality triage**: Automated pre-screening classifies PDF pages before extraction
- **Human review queue**: Flagged records queued for manual inspection with full audit trail

Generate a quality report: `fusionmatdb quality-report --db fusionmatdb.sqlite --output report.html`

> **Material knowledge graph** is planned and covered by a separate project.
```

- [ ] **Step 3: Commit**

```bash
git add fusionmatdb/knowledge/__init__.py README.md
git commit -m "docs: add data quality section to README, knowledge graph stub"
```

---

## PHASE 4 — Sequential (requires API key + all above merged)

### Task 7: Data Quality Report Generator

**Files:**
- Create: `fusionmatdb/reporting/__init__.py`
- Create: `fusionmatdb/reporting/quality_report.py`
- Modify: `fusionmatdb/cli.py`
- Create: `tests/test_quality_report.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_quality_report.py
import json
import pytest
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty,
    DataQualityAssessment, ProvenanceRecord,
)
from fusionmatdb.reporting.quality_report import generate_quality_report


@pytest.fixture
def populated_db(tmp_path):
    db_path = tmp_path / "test.sqlite"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(
            id="ornl_70", title="ORNL Report 70", year=2024,
            access_type="ornl_report",
            source_url="https://fmp.ornl.gov/semiannual-progress-reports/fusion-materials-semiannual-progress-report-70.pdf",
        )
        mat = Material(paper_id="ornl_70", name="EUROFER97", class_="RAFM_steel")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(
            paper_id="ornl_70", material_id=mat.id,
            dose_dpa=10.0, irradiation_temp=300.0,
        )
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="ornl_70", material_id=mat.id, irradiation_id=irr.id,
            yield_strength_mpa_irradiated=650.0,
            yield_strength_mpa_irradiated_lower=640.0,
            yield_strength_mpa_irradiated_upper=660.0,
            confidence_score=0.85, extraction_method="gemini_vision",
            n_specimens=5, distribution_type="normal",
        )
        session.add(prop)
        session.flush()
        dqa = DataQualityAssessment(
            mechanical_property_id=prop.id,
            quality_level="curated_database",
            source_page_number=42,
            source_figure_or_table="Table 3.2",
            source_pdf_url=paper.source_url,
            source_institution="ORNL",
        )
        prov = ProvenanceRecord(
            mechanical_property_id=prop.id,
            root_origin="ornl_70",
            content_hash="a" * 64,
            is_primary=True,
        )
        session.add_all([dqa, prov])
        session.commit()
    return str(db_path)


def test_generate_quality_report_creates_html(populated_db, tmp_path):
    output = tmp_path / "report.html"
    result = generate_quality_report(populated_db, str(output))
    assert result.exists()
    html = result.read_text()
    assert "<!DOCTYPE html>" in html
    assert "FusionMatDB" in html


def test_report_contains_all_sections(populated_db, tmp_path):
    output = tmp_path / "report.html"
    result = generate_quality_report(populated_db, str(output))
    html = result.read_text()
    assert "Executive Summary" in html
    assert "Data Quality Hierarchy" in html
    assert "Traceability" in html
    assert "Provenance" in html or "De-duplication" in html
    assert "Uncertainty" in html
    assert "Validation" in html
    assert "Observability" in html or "Transparency" in html
    assert "Engineering Decision" in html or "Trust" in html
    assert "Extraction" in html


def test_report_contains_data(populated_db, tmp_path):
    output = tmp_path / "report.html"
    result = generate_quality_report(populated_db, str(output))
    html = result.read_text()
    assert "EUROFER97" in html
    assert "curated_database" in html
    assert "ORNL" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_quality_report.py -v`
Expected: ImportError

- [ ] **Step 3: Implement report generator**

```python
# fusionmatdb/reporting/__init__.py
"""Report generation modules for FusionMatDB."""
```

```python
# fusionmatdb/reporting/quality_report.py
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
    """Render trust score distribution as inline SVG."""
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
    """Generate a single lineage card as HTML."""
    from fusionmatdb.trust.lineage import get_lineage
    try:
        l = get_lineage(session, prop_id)
    except ValueError:
        return ""
    return f"""
    <div style="border:1px solid #d1d5db;border-radius:8px;padding:16px;margin:8px 0;background:#f9fafb">
        <strong>Record #{l.record_id}</strong> — {l.source_institution or 'Unknown'}<br>
        Paper: {l.paper_title}<br>
        Source: <a href="{l.source_pdf_url}">{l.source_pdf_url}</a> → Page {l.source_page_number} → {l.source_figure_or_table or 'N/A'}<br>
        Quality: {l.quality_level} | Trust: {l.trust_score}/100 | Confidence: {l.confidence_score}<br>
        Extraction: {l.extraction_method} ({l.extraction_pass}) | Cross-page: {l.cross_page_context_used}<br>
        Hash: <code>{l.content_hash[:16]}...</code> | Primary: {l.is_primary}
    </div>"""


def generate_quality_report(db_path: str, output_path: str) -> Path:
    """Generate standalone HTML quality report."""
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        qa = generate_qa_report(session)
        clusters = find_exact_duplicates(session)
        trust_chart = _render_trust_histogram(session)

        # Sample lineage cards (up to 3)
        sample_props = session.query(MechanicalProperty).limit(3).all()
        lineage_cards = "".join(_lineage_card(session, p.id) for p in sample_props)

        # Triage stats
        triage_results = session.query(PageTriageResult).all()
        triage_stats = {}
        for t in triage_results:
            triage_stats[t.classification] = triage_stats.get(t.classification, 0) + 1

        # Review queue stats
        pending = session.query(ReviewQueueItem).filter_by(review_status="pending").count()
        total_reviews = session.query(ReviewQueueItem).count()

        n_papers = session.query(Paper).count()

        # Quality level breakdown
        quality_rows = ""
        for level, points in sorted(QUALITY_LEVEL_POINTS.items(), key=lambda x: -x[1]):
            count = qa.quality_level_counts.get(level, 0)
            pct = count / qa.total_records * 100 if qa.total_records else 0
            quality_rows += f"<tr><td>{level}</td><td>{count}</td><td>{pct:.1f}%</td><td>{points}/30 pts</td></tr>\n"

        # Traceability percentages
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
```

- [ ] **Step 4: Add CLI command**

Add to `fusionmatdb/cli.py`:

```python
@cli.command("quality-report")
@click.option("--db", default="fusionmatdb.sqlite")
@click.option("--output", "-o", default="fusionmatdb_quality_report.html")
def quality_report_cmd(db, output):
    """Generate standalone HTML data quality report."""
    from fusionmatdb.reporting.quality_report import generate_quality_report
    path = generate_quality_report(db, output)
    click.echo(f"Quality report generated: {path}")
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_quality_report.py -v`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add fusionmatdb/reporting/__init__.py fusionmatdb/reporting/quality_report.py \
       fusionmatdb/cli.py tests/test_quality_report.py
git commit -m "feat: add HTML data quality report generator"
```

---

### Task 8: Sample Extraction Run (requires GOOGLE_CLOUD_API_KEY)

This task runs the full updated pipeline on 3 ORNL reports to validate everything works end-to-end.

**Files:**
- Create: `scripts/sample_extraction_run.py`

- [ ] **Step 1: Create sample run script**

```python
# scripts/sample_extraction_run.py
"""Run updated extraction pipeline on 3 sample ORNL reports to validate new features."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

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

    # Step 1: Download
    print("=== Step 1: Download sample reports ===")
    downloader = ORNLDownloader(output_dir=pdf_dir, max_report=max(SAMPLE_REPORTS) + 1)
    for num in SAMPLE_REPORTS:
        result = downloader.download_one(num)
        print(f"  Report {num}: {result['status']}")

    # Step 2: Triage
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
        stats = {}
        for r in results:
            stats[r.classification] = stats.get(r.classification, 0) + 1
        print(f"  Report {num}: {len(results)} pages — {stats}")

    # Step 3: Extract with updated pipeline
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

    # Step 4: Backfill
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

    # Step 5: Generate report
    print("\n=== Step 5: Generate quality report ===")
    report_path = generate_quality_report(db, "sample_quality_report.html")
    print(f"  Report: {report_path}")

    # Step 6: Validate success criteria
    print("\n=== Validation ===")
    from fusionmatdb.storage.schema import MechanicalProperty, DataQualityAssessment
    props = session.query(MechanicalProperty).all()
    with_source_ref = sum(1 for p in props if p.raw_extraction_json and
                          json.loads(p.raw_extraction_json).get("source_reference"))
    with_institution = sum(1 for p in props if p.raw_extraction_json and
                           json.loads(p.raw_extraction_json).get("source_institution"))
    with_bounds = sum(1 for p in props if any([
        p.yield_strength_mpa_irradiated_lower, p.uts_mpa_irradiated_lower,
        p.hardness_lower, p.dbtt_k_irradiated_lower,
    ]))

    print(f"  Total records: {len(props)}")
    print(f"  With source_reference: {with_source_ref} ({with_source_ref/max(len(props),1)*100:.0f}%)")
    print(f"  With source_institution: {with_institution} ({with_institution/max(len(props),1)*100:.0f}%)")
    print(f"  With uncertainty bounds: {with_bounds} ({with_bounds/max(len(props),1)*100:.0f}%)")
    print(f"\nSample run complete. Open sample_quality_report.html to inspect.")


if __name__ == "__main__":
    run_sample_extraction()
```

- [ ] **Step 2: Run the sample extraction**

Run: `GOOGLE_CLOUD_API_KEY=<your-key> python scripts/sample_extraction_run.py`
Expected: Downloads 3 PDFs, triages pages, extracts data, backfills quality/provenance, generates HTML report

- [ ] **Step 3: Inspect the generated report**

Open `sample_quality_report.html` in a browser. Verify all 9 sections render with real data.

- [ ] **Step 4: Commit**

```bash
git add scripts/sample_extraction_run.py
git commit -m "feat: add sample extraction run script for pipeline validation"
```

---

## Agent Dispatch Summary

| Phase | Agent | Branch | Tasks | Depends On |
|-------|-------|--------|-------|------------|
| 1 | Agent A | `feat/schema-quality` | Task 1 (schema) | — |
| 1 | Agent B | `feat/extraction-upgrade` | Task 2 (prompts, triage, review queue) | — |
| 2 | Agent C | `feat/qa-framework` | Task 3 (validator, dedup, QA) | Phase 1 merged |
| 2 | Agent D | `feat/trust-lineage` | Task 4 (trust, lineage, export) | Phase 1 merged |
| 3 | Inline | `master` | Task 5 (backfill), Task 6 (stubs) | Phase 2 merged |
| 4 | Inline | `master` | Task 7 (report), Task 8 (sample run) | Phase 3 + API key |
