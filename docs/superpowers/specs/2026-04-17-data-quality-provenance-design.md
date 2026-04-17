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

---

## Files Changed (estimated)

| Sub-project | New files | Modified files |
|---|---|---|
| 1: Schema | `storage/migrations/`, `storage/schema.py` additions | `storage/database.py` (Alembic init) |
| 2: QA | `qa/__init__.py`, `qa/qa_report.py`, `qa/dedup_detector.py`, `qa/accuracy_benchmark.py` | `extraction/validator.py`, `cli.py` |
| 3: Trust | `trust/__init__.py`, `trust/trust_score.py`, `trust/lineage.py` | `cli.py`, export logic |
| 4: Backfill | `scripts/backfill_quality.py` | — |
| Stubs | `knowledge/__init__.py` | `README.md` |
| Tests | `tests/test_quality_assessment.py`, `tests/test_provenance.py`, `tests/test_dedup.py`, `tests/test_trust_score.py`, `tests/test_lineage.py`, `tests/test_backfill.py` | — |
