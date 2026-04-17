# FusionMatDB Data Quality & Provenance Upgrade

**Date:** 2026-04-17
**Status:** Draft
**Scope:** 8 of 9 original concerns (knowledge graph out of scope, separate project)

## Context

FusionMatDB serves UKAEA and Tokamak Energy (and others) as a trusted source of fusion irradiation materials data for reactor design decisions. Current schema has basic confidence scoring and raw extraction JSON but lacks formal data quality classification, full traceability to source documents, deduplication, uncertainty representation, and engineering trust scoring.

The 22,269 existing records were extracted from 65 ORNL semiannual progress reports via multimodal VLM. Source PDFs are publicly available at `fmp.ornl.gov` with deterministic URLs. Raw VLM responses are cached on disk per page. Each record already carries `paper_id`, `page` number, and `confidence_score`.

## Approach

Three sub-projects executed in parallel, then a sequential backfill phase:

1. **Schema & Metadata Layer** — new tables + columns for quality, traceability, provenance, uncertainty
2. **Validation & QA Framework** — enhanced validators, dedup detection, QA reporting
3. **Observability & Engineering Decision Support** — trust scoring, lineage queries, export enhancements

Sub-project 1 is a dependency for 2 and 3, but 2 and 3 are independent of each other.

After all three merge, a backfill phase populates new fields for existing records using inferrable data (no API calls needed).

---

## Sub-project 1: Schema & Metadata Layer

### New table: `data_quality_assessments`

One row per `MechanicalProperty` record.

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `mechanical_property_id` | Integer FK → mechanical_properties.id | UNIQUE, NOT NULL |
| `quality_level` | String NOT NULL | Enum: `accredited_lab`, `curated_database`, `peer_reviewed_literature`, `simulation`, `inferred` |
| `quality_justification` | Text | Free text explanation |
| `source_page_number` | Integer | Page in source PDF |
| `source_figure_or_table` | String | e.g. "Table 3.2", "Fig 4.1" |
| `source_pdf_url` | Text | Direct URL to source PDF |
| `source_institution` | String | e.g. "ORNL", "JAEA", "KIT" |
| `extraction_accuracy_score` | Float | 0.0-1.0, distinct from confidence |

### New table: `provenance_records`

One row per `MechanicalProperty` record.

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `mechanical_property_id` | Integer FK → mechanical_properties.id | UNIQUE, NOT NULL |
| `root_origin` | Text | Canonical first publication reference |
| `duplicate_cluster_id` | Integer | Groups records representing same measurement |
| `content_hash` | String(64) | SHA256 of key value fields |
| `is_primary` | Boolean | True if this is the canonical record in a duplicate cluster |

### Schema additions to `MechanicalProperty`

Uncertainty bounds (8 new columns):
- `yield_strength_mpa_irradiated_lower`, `yield_strength_mpa_irradiated_upper`
- `uts_mpa_irradiated_lower`, `uts_mpa_irradiated_upper`
- `hardness_lower`, `hardness_upper`
- `dbtt_k_irradiated_lower`, `dbtt_k_irradiated_upper`

Statistical metadata (2 new columns):
- `distribution_type` — String, nullable. Values: `normal`, `uniform`, `empirical`
- `n_specimens` — Integer, nullable. Sample size.

### Schema additions to `IrradiationCondition`

Range bounds (4 new columns):
- `irradiation_temp_lower`, `irradiation_temp_upper`
- `dose_dpa_lower`, `dose_dpa_upper`

### Alembic migration

Create `fusionmatdb/storage/migrations/` with Alembic setup. Single migration file adding all new tables and columns. Existing records get NULL for new columns until backfill.

---

## Sub-project 2: Validation & QA Framework

### Enhanced validator: `fusionmatdb/extraction/validator.py`

Extend existing validator with:
- **Cross-field physics checks**: flag (not reject) when irradiated yield > 2x unirradiated yield, when elongation_irradiated > elongation_unirradiated, when dose=0 but irradiation_state="irradiated"
- **Material-class anomaly detection**: z-score each numeric property against its material-class distribution. Flag records > 3 sigma.
- **Completeness scoring**: separate from confidence — fraction of applicable fields populated for that experiment type.

### New module: `fusionmatdb/qa/__init__.py`

**`fusionmatdb/qa/qa_report.py`**
- `generate_qa_report(db_path) -> QAReport` — per-paper and per-material-class summary
- Fields: % populated, anomaly count, confidence distribution, cross-field flag count
- Output as structured dict and optional CLI table

**`fusionmatdb/qa/dedup_detector.py`**
- `compute_content_hash(record) -> str` — SHA256 of (material_name, dose_dpa, irradiation_temp, test_temp, yield_strength, uts, hardness) normalized and rounded
- `find_exact_duplicates(db_path) -> list[DuplicateCluster]` — group by content_hash
- `find_near_duplicates(db_path, threshold=0.95) -> list[DuplicateCluster]` — cosine similarity on numeric property vectors

**`fusionmatdb/qa/accuracy_benchmark.py`**
- `benchmark_extraction(db_path, reference_records) -> AccuracyReport` — compare VLM-extracted values against manually verified reference set
- Metrics: per-field precision, recall, mean absolute error
- Reference set format: JSON file with manually verified records

### CLI additions

```
fusionmatdb qa-report --db fusionmatdb.sqlite
fusionmatdb dedup-scan --db fusionmatdb.sqlite [--threshold 0.95]
fusionmatdb validate --db fusionmatdb.sqlite --strict
```

---

## Sub-project 3: Observability & Engineering Decision Support

### New module: `fusionmatdb/trust/__init__.py`

**`fusionmatdb/trust/trust_score.py`**
- `compute_trust_score(record, quality_assessment, provenance) -> int` — 0-100 composite score
- Weights:
  - `quality_level`: 30 points (accredited_lab=30, curated_database=22, peer_reviewed=15, simulation=8, inferred=3)
  - `confidence_score`: 20 points (scaled from 0.0-1.0)
  - `has_uncertainty_bounds`: 15 points
  - `has_traceability` (page + figure/table): 15 points
  - `reviewed_by_human`: 10 points
  - `is_primary` (not duplicate): 10 points

**`fusionmatdb/trust/lineage.py`**
- `get_lineage(db_path, record_id) -> LineageReport` — full provenance chain
- Output: paper title, DOI, source PDF URL, page number, figure/table ref, institution, extraction method, confidence, quality level, trust score, validation flags, duplicate cluster info

### Export enhancements

- Parquet export: include quality_level, trust_score, source_pdf_url, source_page_number, content_hash, is_primary, uncertainty bounds
- New filter: `--min-trust N` (0-100)
- World Model export: add provenance metadata to `state_before` dict

### CLI additions

```
fusionmatdb lineage <record_id> --db fusionmatdb.sqlite
fusionmatdb export --format parquet --min-trust 70 --db fusionmatdb.sqlite
```

---

## Sub-project 4: Backfill (sequential, after 1-3 merge)

Runs against existing 22,269 records. No API calls — uses data already in DB and on disk.

### Quality assessments backfill
- ORNL records: `quality_level="curated_database"`, `source_institution="ORNL"`, `source_pdf_url` from paper source_url, `source_page_number` from raw_extraction_json `page` field
- SDC-IC records: `quality_level="curated_database"`, `source_institution` from SDC-IC metadata

### Provenance backfill
- Compute `content_hash` for all records
- Run exact-match dedup, assign `duplicate_cluster_id` and `is_primary`
- `root_origin` set to paper_id for records with no known prior publication

### Trust score backfill
- Compute and store trust scores for all records after quality + provenance populated

---

## Sub-project 5: Updated VLM Extraction & Validation Run

### Page quality triage: `fusionmatdb/extraction/page_triage.py`

A cheap, fast LLM pre-screening step that classifies each PDF page before extraction.

**New class: `PageTriager`**
- Uses Gemini Flash (same model, minimal prompt) for classification
- Sends page image with a short prompt: "Classify this page's readability for data extraction. Respond with JSON: {classification, reason, has_data}"
- Classifications:
  - `clean` — clear text/tables/figures, proceed with extraction
  - `degraded` — partially readable (faded scan, overlapping text, poor resolution) — extract but flag
  - `unreadable` — cannot reliably extract (corrupted scan, handwritten, redacted) — skip, log for manual review
  - `no_data` — page is readable but contains no extractable materials data (title pages, references, etc.) — skip
- Cost: ~$1-2 for all 65 reports (tiny prompt, text-only response)

**New table: `page_triage_results`**

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `paper_id` | String FK → papers.id | NOT NULL |
| `page_number` | Integer NOT NULL | 1-indexed |
| `classification` | String NOT NULL | `clean`, `degraded`, `unreadable`, `no_data` |
| `reason` | Text | LLM's explanation for the classification |
| `has_extractable_data` | Boolean | Whether the page appears to contain materials data |
| `triage_model` | String | Model used for classification |
| `triage_timestamp` | DateTime | When the triage was performed |

**Integration with extraction pipeline:**
- Triage runs first for all pages (async, 20 concurrent, same as extraction)
- `clean` pages → proceed to extraction
- `degraded` pages → extract, but auto-flag resulting records for human review
- `unreadable` pages → skip extraction, add to review queue with page image reference
- `no_data` pages → skip entirely

### Human review queue: `fusionmatdb/qa/review_queue.py`

**New table: `review_queue`**

| Column | Type | Description |
|---|---|---|
| `id` | Integer PK | Auto-increment |
| `paper_id` | String FK → papers.id | NOT NULL |
| `page_number` | Integer NOT NULL | |
| `mechanical_property_id` | Integer FK, nullable | NULL if page was unreadable (no record created) |
| `flag_reason` | String NOT NULL | `degraded_page`, `unreadable_page`, `incomplete_after_enrichment`, `physics_check_anomaly`, `cross_field_inconsistency`, `figure_value_estimation` |
| `flag_detail` | Text | Specific explanation |
| `extraction_path` | String | `first_pass`, `second_pass_enriched`, `skipped` |
| `review_status` | String NOT NULL | `pending`, `approved`, `corrected`, `rejected` |
| `reviewer` | String, nullable | Who reviewed it |
| `reviewer_notes` | Text, nullable | |
| `reviewed_at` | DateTime, nullable | |

**Sources that populate the review queue:**
1. Page triage: `degraded` and `unreadable` pages
2. Cross-page enrichment: records still incomplete after second pass
3. Post-extraction validation: physics check anomalies, cross-field inconsistencies
4. VLM extraction: records where model indicated low certainty about figure readings

**CLI additions:**
```
fusionmatdb review-queue --db fusionmatdb.sqlite [--status pending]
fusionmatdb review <record_id> --status approved|corrected|rejected --notes "..."
```

---

### Cross-page context strategy

ORNL reports frequently split context across pages — experimental setup on one page, results table on the next. Two-pass approach to handle this:

**First pass: text context injection (every page, ~$0 extra cost)**

For each page N being extracted, pymupdf text from pages N-1 and N+1 is prepended to the VLM prompt as text context. Page N itself is sent as an image (the extraction target).

```
VLM receives:
  - Text: "CONTEXT FROM PREVIOUS PAGE:\n[pymupdf text of page N-1]"
  - Text: "CONTEXT FROM NEXT PAGE:\n[pymupdf text of page N+1]"
  - Image: [page N at 120 DPI]
  - Prompt: "Extract data from the IMAGE. Use the text context to resolve
             missing material names, irradiation conditions, or experimental
             details that may have been defined on adjacent pages. Do NOT
             extract data from the context text — only use it to fill gaps."
```

Rationale: cross-page dependencies are predominantly prose (section headings, experimental descriptions, condition lists). pymupdf captures prose reliably. Text tokens are ~100x cheaper than image tokens. This handles ~80% of cross-page cases at near-zero extra cost.

**Second pass: image context enrichment (flagged pages only, ~$4-8 extra)**

After first pass, identify incomplete records using these heuristics:
- Has property values but no `material_name`
- Has `material_name` but no irradiation conditions (`dose_dpa` and `irradiation_temp` both NULL)
- Page starts mid-table (first record on page has data but no headers/context)
- Record has NULL `source_reference` despite being on a data-rich page
- Page triage classified the page as `degraded`

For flagged pages, re-extract with all three pages (N-1, N, N+1) as **images**:

```
VLM receives:
  - Image: [page N-1 at 120 DPI]
  - Image: [page N at 120 DPI]
  - Image: [page N+1 at 120 DPI]
  - Prompt: "Extract data from the MIDDLE page only. The surrounding pages
             provide context — use them to identify material names, irradiation
             conditions, and experimental details. Do NOT extract data from
             the first or last page."
```

Second pass results replace first pass records for those pages. Records still incomplete after second pass are added to the review queue with `flag_reason="incomplete_after_enrichment"`.

**New fields on `MechanicalProperty`:**
- `extraction_pass` — String: `first_pass` or `second_pass_enriched`
- `cross_page_context_used` — Boolean: whether adjacent page context was used

**Escalation chain:**
```
Page triage → clean/degraded/unreadable
                    ↓
    clean → First pass (image + text context from neighbours)
 degraded → First pass + auto-flag for review
unreadable → Skip → review queue
                    ↓
         First pass complete → check for incomplete records
                    ↓
        incomplete → Second pass (3 images, extract middle only)
         complete → done
                    ↓
    Second pass complete → still incomplete?
                    ↓
              yes → review queue
               no → done
```

---

### Extraction prompt update: `fusionmatdb/extraction/prompts.py`

Add new fields to `_FIELDS` and update `VISION_EXTRACTION_PROMPT`:

**New fields in `_FIELDS`:**
```
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

**Updated vision prompt instructions (appended to existing):**
```
- For EVERY datapoint, record which table or figure it came from in source_reference
- Note the institution/lab that performed the experiment in source_institution
- If the paper cites data from another publication rather than reporting original measurements, set data_origin to "cited_from_other_work"
- Extract upper/lower bounds when shown as error bars, ranges (e.g. "350-400 MPa"), or ± notation
- Record number of specimens (n) when stated (e.g. "n=3", "average of 5 specimens")
- Include experimental method details when given (specimen geometry, test standard, loading rate)
```

### Sample extraction run

Run updated extraction on 3 ORNL reports selected for diversity:
- **Report 70** (recent, good data density, has creep data)
- **Report 40** (mid-era, different formatting)
- **Report 10** (early era, tests extraction on older document style)

Process:
1. Download the 3 PDFs via `ORNLDownloader`
2. Run page triage on all pages — classify clean/degraded/unreadable/no_data
3. Run first pass extraction with text context from adjacent pages
4. Identify incomplete records, run second pass with image context on flagged pages
5. Ingest into fresh SQLite DB with new schema
6. Run backfill (quality assessments, provenance, trust scores)
7. Populate review queue from triage flags, enrichment failures, physics checks
8. Validate: check new fields populated, inspect sample records, verify lineage end-to-end
9. Generate data quality report

**Success criteria:**
- Page triage classifies all pages with >90% sensible classifications (no_data pages are actually empty, unreadable pages are actually unreadable)
- >50% of extracted records have `source_reference` populated
- >80% have `source_institution` populated
- >20% of records with numeric properties have at least one uncertainty bound
- `n_specimens` populated where stated in source
- Second pass enrichment fills at least some previously-missing fields on flagged records
- All records get quality assessment, provenance hash, and trust score
- Lineage query returns complete chain for any record
- Review queue populated with sensible items (degraded pages, incomplete records, anomalies)
- Data quality report generates valid HTML with all 9 sections

### Output: comparison report

Generate a before/after comparison showing the same records extracted with old vs. new prompt, highlighting the additional metadata captured. This feeds into the data quality report.

---

## Sub-project 6: Data Quality Report Generator

### New module: `fusionmatdb/reporting/__init__.py`

**`fusionmatdb/reporting/quality_report.py`**

Generates a standalone HTML report (single file, embedded CSS, no JS dependencies) that addresses each of the 8 concerns with data evidence.

**Report sections:**

1. **Executive Summary**
   - Total records, material classes, source documents
   - Overall trust score distribution (histogram)
   - Key headline numbers: "X% of records fully traceable to source PDF + page"

2. **Data Quality Hierarchy** (Concern 1)
   - Breakdown by quality_level: count, %, examples
   - Table showing quality_level definitions and how each was assigned
   - Pie chart of quality distribution

3. **Traceability** (Concern 2)
   - % of records with source_pdf_url, source_page_number, source_figure_or_table
   - 3 sample "lineage cards" — full trace from record → page → PDF → institution
   - Direct links to source PDFs (clickable `fmp.ornl.gov` URLs)

4. **Provenance & De-duplication** (Concern 3)
   - Total duplicate clusters found, records deduplicated
   - Methodology description (content hash + numeric similarity)
   - Example duplicate cluster showing the records and which was marked primary

5. **Uncertainty & Statistical Representation** (Concern 4)
   - % of records with uncertainty bounds
   - % with n_specimens
   - Sample property with full uncertainty: value, bounds, distribution type, n
   - Note on how this enables Bayesian/GP workflows (link to FusionUQ)

6. **Validation & QA** (Concern 5)
   - Extraction confidence distribution (histogram, building on existing Fig 4)
   - Cross-field physics check results: N flagged, N passed
   - Anomaly detection results: N outliers flagged
   - Extraction accuracy benchmark (if reference set available): per-field precision/recall

7. **Observability & Transparency** (Concern 6)
   - Description of the extraction pipeline with provenance at each step
   - Raw VLM response preservation (link to cached JSON)
   - "Every record can be inspected" — show CLI lineage command example

8. **Engineering Decision Support** (Concern 8)
   - Trust score distribution and interpretation guide
   - "Records suitable for design basis" (trust ≥ 70): count, material classes covered
   - Comparison table: FusionMatDB vs EDDI vs MatDB4Fusion on these quality dimensions

9. **Data Extraction Quality** (Concern 9)
   - VLM model and parameters used
   - Extraction methodology description
   - Accuracy metrics (if benchmark available)
   - Before/after comparison from prompt update (from sub-project 5)

**Report generation:**
- `generate_quality_report(db_path, output_path) -> Path` — produces `fusionmatdb_quality_report.html`
- Uses Python string templating (no Jinja2 dependency) with embedded CSS
- Charts rendered as inline SVG (matplotlib → SVG buffer → embedded)
- Self-contained single HTML file, viewable in any browser, printable to PDF

### CLI addition

```
fusionmatdb quality-report --db fusionmatdb.sqlite --output fusionmatdb_quality_report.html
```

---

## Knowledge Graph (Out of Scope)

Covered by a separate project. Stub module `fusionmatdb/knowledge/__init__.py` with TODO comment. README updated to note this is planned.

---

## Testing Strategy

Each sub-project includes tests in `tests/`:
- Schema migration: test round-trip create/query with new tables and columns
- Validator: test cross-field checks with known-good and known-bad records
- Dedup: test content hash determinism, exact and near-duplicate detection
- Trust score: test scoring formula with fixture records at each quality level
- Lineage: test full chain assembly
- Export: test new columns appear in Parquet, test --min-trust filter
- Backfill: test default assignment logic on small fixture DB

Standalone test functions, no classes. Fixtures via pytest fixtures or inline factory functions.

- Page triage: test classification parsing, test pipeline integration (mock triage → extraction skips unreadable)
- Review queue: test flagging from all sources (triage, enrichment, physics checks), test status transitions
- Cross-page context: test text context injection (mock pymupdf output prepended to prompt), test second pass trigger heuristics
- Extraction prompt: test that new fields appear in VLM output (mock VLM response with new fields, verify parsing)
- Quality report: test HTML generation with fixture DB, verify all 9 sections present, verify embedded charts render

---

## Files Changed (estimated)

| Sub-project | New files | Modified files |
|---|---|---|
| 1: Schema | `storage/migrations/`, `storage/schema.py` additions | `storage/database.py` (Alembic init) |
| 2: QA | `qa/__init__.py`, `qa/qa_report.py`, `qa/dedup_detector.py`, `qa/accuracy_benchmark.py` | `extraction/validator.py`, `cli.py` |
| 3: Trust | `trust/__init__.py`, `trust/trust_score.py`, `trust/lineage.py` | `cli.py`, export logic |
| 4: Backfill | `scripts/backfill_quality.py` | — |
| 5: Extraction | `extraction/page_triage.py`, `qa/review_queue.py` | `extraction/prompts.py`, `access/vision_extractor.py` (parse new fields, triage integration, cross-page context), `cli.py`, `storage/schema.py` (page_triage_results + review_queue tables, extraction_pass + cross_page_context_used columns) |
| 6: Report | `reporting/__init__.py`, `reporting/quality_report.py` | `cli.py` |
| Stubs | `knowledge/__init__.py` | `README.md` |
| Tests | `tests/test_quality_assessment.py`, `tests/test_provenance.py`, `tests/test_dedup.py`, `tests/test_trust_score.py`, `tests/test_lineage.py`, `tests/test_backfill.py`, `tests/test_page_triage.py`, `tests/test_review_queue.py`, `tests/test_cross_page_context.py`, `tests/test_extraction_prompt.py`, `tests/test_quality_report.py` | — |

## Execution Order

```
Phase 1 (parallel):  Sub-project 1 (Schema)
                      Sub-project 5 (Extraction prompt update)

Phase 2 (parallel):  Sub-project 2 (QA framework)     — depends on schema
                      Sub-project 3 (Trust/lineage)    — depends on schema

Phase 3 (sequential): Sub-project 4 (Backfill)         — depends on 1+2+3

Phase 4 (sequential): Sub-project 5 contd (Sample run)  — depends on 1+5 prompt
                       Sub-project 6 (Quality report)   — depends on all above
```

The user provides GOOGLE_CLOUD_API_KEY before Phase 4 begins. Phases 1-3 require no API access.
