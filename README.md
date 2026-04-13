# FusionMatDB

**The missing fusion irradiation materials database.** Extracts structured, ML-ready data from 65+ ORNL semiannual progress reports and open-access literature using Gemini 3 Flash vision on Vertex AI.

No publicly accessible, ML-ready fusion irradiation database exists. EUROfusion EDDI (~3,000 records) is locked behind EU consortium access. MatDB4Fusion covers unirradiated baselines only. FusionMatDB fills the gap: irradiation effects data extracted from decades of publicly available PDFs.

---

## Dataset Card

### Overview

| | |
|---|---|
| **Records** | 22,600 total (20,318 vision-extracted, 331 human-curated MatDB4Fusion, 1,951 SDC-IC ITER) |
| **High-confidence records (≥0.7)** | 18,902 |
| **Irradiated yield strength records** | 2,267 |
| **Complete GP training rows** (yield + dose + temp) | 1,594 |
| **Source documents** | 65 ORNL semiannual progress reports (1990–2024) + MatDB4Fusion CSV + SDC-IC Material Library |
| **Materials covered** | RAFM steels, ODS steels, vanadium alloys, tungsten alloys, SiC composites, copper alloys, ceramics, beryllium |
| **Date extracted** | April 2026 |
| **Extraction model** | Gemini 3 Flash (Vertex AI), temperature=0, thinking disabled |
| **License** | Source data: public domain (ORNL/DOE) + EUPL (SDC-IC). Database: MIT |

---

### Key Features

Each record in `mechanical_properties` is a single (material, condition, measurement) triple:

**Material identification**
- `material_name` — canonical name (e.g. `"EUROFER97"`, `"V-4Cr-4Ti"`, `"F82H"`)
- `material_class` — one of: `RAFM_steel`, `ODS_steel`, `vanadium_alloy`, `tungsten`, `tungsten_alloy`, `SiC_composite`, `copper_alloy`, `ceramic_insulator`, `nanolaminate`, `beryllium`, `other`
- Composition: element weight % columns `W`, `Cr`, `V`, `Ta`, `Fe`, `C`, `Mn`, `Mo`, `Ni`, `Si`, `Ti`, `Al`
- Processing: `manufacturer_name`, `product_shape`, `temper_temp`, `grain_size_um`
- Nano-laminate fields: `layer_material_a`, `layer_material_b`, `layer_spacing_nm`

**Irradiation conditions**
- `dose_dpa` — displacement per atom (validated 0–500 dpa)
- `irradiation_temp` — irradiation temperature (°C, includes cryogenic values at 10–300 K)
- `reactor` — facility (HFIR, BOR-60, ATR, EBR-II, ion_beam, ...)
- `neutron_spectrum` — `fission`, `fast`, `mixed`, or `ion`
- `helium_appm`, `hydrogen_appm` — transmutation gas content

**Mechanical properties** (irradiated and unirradiated where available)
- Tensile: `yield_strength_mpa`, `uts_mpa`, `elongation_pct` (+ `_std` uncertainty columns)
- Fracture: `dbtt_k`, `fracture_toughness_mpa_sqrt_m`, `kv_joules`
- Hardness: `hardness_value`, `hardness_type`
- Creep: `creep_rate_per_s`, `creep_strain_pct`
- Radiation microstructure: `void_diameter_nm`, `void_density_per_m3`, `dislocation_loop_diameter_nm`
- Swelling: `volumetric_swelling_pct`
- Electrical: `electrical_resistivity_uohm_cm_irradiated`
- Dielectric: `dielectric_breakdown_kv_per_mm_irradiated` (ceramics)

**ML metadata**
- `confidence_score` (0.0–1.0) — extraction quality; based on field completeness
- `extraction_method` — `gemini_vision` | `matdb4fusion_ingest` | `sdc_ic_parse`
- `reviewed_by_human` — True for MatDB4Fusion and SDC-IC records
- `raw_extraction_json` — full Gemini response for the record (enables re-parsing)
- `_review_flag` in raw JSON — marks 202 records with dose 150–500 dpa for expert verification

---

### Property Coverage

| Property | Records | Irradiated | Unirradiated |
|---|---|---|---|
| Yield strength (MPa) | 4,880 | 2,267 | 2,601 |
| Ultimate tensile strength (MPa) | 3,681 | 1,757 | 1,924 |
| Elongation (%) | 1,920 | 1,920 | — |
| Hardness (HV) | 1,496 | — | — |
| Volumetric swelling (%) | 2,066 | 2,066 | — |
| Fracture toughness (MPa√m) | 1,262 | 1,262 | — |
| DBTT (K) | 510 | 510 | — |
| Void diameter (nm) | 796 | 796 | — |
| Creep rate (s⁻¹) | 216 | 216 | — |
| Electrical resistivity (µΩ·cm) | 254 | 254 | — |

---

### Material Coverage

| Material class | Example materials | Records |
|---|---|---|
| `RAFM_steel` | F82H, EUROFER97, HT-9, 9Cr, T91, Grade 91 | 1,196 |
| `copper_alloy` | CuCrZr, GlidCop, MARZ copper, OFHC Cu | 698 |
| `vanadium_alloy` | V-4Cr-4Ti, V-5Cr-5Ti, V-2.5Ti-1Si | 590 |
| `austenitic_steel` | 316 SS, 304 SS, JPCA, PCA, Fe-Cr-Ni alloys | 450 |
| `ceramic_insulator` | Al₂O₃, MgAl₂O₄, AlN, SiC, BN, BeO | 343 |
| `SiC_composite` | SiC/SiC, Hi-Nicalon fibre composites | 266 |
| `tungsten_alloy` | W-Re, K-doped W, La-doped W, W-NiFe | 260 |
| `ODS_steel` | MA957, PM2000, 14YWT, ML20 | 251 |
| `tungsten` | Pure W, W single crystal | 221 |
| `ferritic_model_alloy` | Fe-3Cr, Fe-12Cr, Fe-18Cr, alpha-Fe | 125 |
| `nickel_alloy` | Ni, Inconel, BAM-11, Alloy 718 | 73 |
| `beryllium` | Be, BeO | 60 |
| `refractory_metal` | Mo, Mo-Re, Cr, Nb-1Zr | 42 |
| `carbon_graphite` | H451, IG-110, graphite | 38 |
| `nanolaminate` | Cu-Fe, Cu-Nb (Helion magnets) | 34 |
| `titanium_alloy` | Ti-6Al-4V | 29 |
| `HTS_tape` | REBCO, YBCO | 26 |
| `max_phase` | Ti₂AlC, Ti₃SiC₂ | 10 |
| `zirconium_alloy` | Zircaloy | 6 |
| `other` | Multi-material descriptions, ambiguous | 1,173 |

**Note on `other` (20%):** Remaining unclassified records are genuinely ambiguous — multi-material experiment descriptions, very specific processing variants, and LWR-specific materials outside the fusion domain. These are retained with `material_class = "other"` and can be reclassified manually or excluded by filtering on class.

---

### What You Can Train

**✅ Gaussian Process property predictors (recommended, train now)**

Best candidates with sufficient data:

| Target material | GP training rows | Input features | Recommended? |
|---|---|---|---|
| F82H / RAFM steels | 457 | dose, temp → yield | ✅ Yes |
| Vanadium alloys (V-4Cr-4Ti) | 371 | dose, temp → yield | ✅ Yes (Digilab demo) |
| Copper alloys | 156 | dose, temp → yield | ✅ Yes |
| Tungsten | 109 | dose, temp → yield | ⚠️ Thin dose range (0–2.9 dpa) |
| ODS steels | 43 | dose, temp → yield | ⚠️ Marginal |

Each GP uses `dose_dpa` + `irradiation_temp_C` as inputs, `yield_strength_mpa_irradiated` as target. Load from `fusionmatdb_export.parquet` filtered by `material_class`.

**✅ Radiation damage world model (limited but unique)**

142 records with explicitly paired `yield_strength_mpa_unirradiated` + `yield_strength_mpa_irradiated` in the same row. Format: `{state_before, action, state_after}`. This is the most data-efficient representation for learning irradiation response functions.

**✅ Materials NLP / information extraction**

Full text of 65 ORNL reports available. Each record has `raw_extraction_json` linking it to the source page. Useful for training materials NER models, relation extraction, and evaluating LLM extraction accuracy.

**✅ Active learning for experiment planning**

FusionBAL (`../fusionbal/`) loads the Parquet export as GP prior data and recommends which experiments to run next. V-4Cr-4Ti with 84 complete data points replicates the Digilab Bristol result (30→9 experiments to threshold).

**❌ General fusion materials neural network**
Not enough data yet. Needs 5,000+ records per material class for a deep learning model. Current dataset is ideal for GPs, not neural nets.

---

### Known Limitations

**1. Extraction accuracy is estimated, not verified**
All records from ORNL reports are extracted by Gemini 3 Flash vision. Accuracy was validated by spot-checking 10 random high-confidence records against source PDFs (all correct) and cross-checking known values (EUROFER97 RT yield = 580 MPa, W yield range physically plausible). However, systematic validation of all 20,318 vision-extracted records has not been performed. `reviewed_by_human = False` for these records.

**2. Paired irradiated/unirradiated data is sparse**
Only 142 records have both irradiated and unirradiated yield strength in the same row. Most ORNL papers report either baseline OR irradiated data, not both. The `delta_yield_strength` world model training signal is therefore limited.

**3. Material name fragmentation**
68 distinct RAFM steel variants (F82H, F82H-IEA, F82H mod., HT-9, HT9, etc.) are stored separately. For GP training across the full RAFM class, these should be treated as one material type with composition as the distinguishing feature. The `material_class` column enables this grouping.

**4. High-dose records require expert review**
202 records have `dose_dpa > 150` (flagged with `_review_flag` in `raw_extraction_json`). Doses of 150–250 dpa are physically achievable in fast reactors (EBR-II, FFTF). Values previously >500 dpa have been nulled as likely fluence misreadings.

**5. Cryogenic temperatures**
51 irradiation condition records have `irradiation_temp < -50°C`. These are **correct** cryogenic temperatures (10–196 K = liquid helium to liquid nitrogen range), not unit errors. Store and query accordingly.

**6. `other` material class (20%)**
1,173 records (20%) remain in `other`. Common specific sub-classes (316 SS, Fe-Cr model alloys, Ni, Mo, graphite) have been separated into dedicated classes. The remaining `other` records are multi-material descriptions, highly specific processing variants, or LWR-specific materials outside the fusion domain. Filter by `material_class != "other"` to work with the classified 80%.

**7. Neutron spectrum proxy**
All ORNL data uses fission reactor neutron spectra (HFIR, BOR-60, EBR-II). No DT fusion neutron data exists — IFMIF is not yet operational. Fission data is the standard proxy for fusion neutron conditions; results are not directly equivalent.

---

### Comparison to Existing Databases

| Database | Records | Irradiation data | Access | ML-ready |
|---|---|---|---|---|
| **FusionMatDB** | **22,600** | **Yes — core focus** | **Open source** | **Yes** |
| EUROfusion EDDI | ~3,000 | Yes | EU consortium only | No |
| MatDB4Fusion (KIT) | 353 | No (baseline only) | Public CSV | Partial |
| JRC ODIN | >20,000 | Some | Tiered | No |
| ITER MPH | Unknown | Yes | Closed | No |

FusionMatDB is the first publicly accessible, ML-ready fusion irradiation effects database.

---

### Citation

If you use FusionMatDB in research, please cite:

```
FusionMatDB: An open-source fusion irradiation materials database.
Extracted from ORNL Fusion Materials Program semiannual progress reports (1990–2024)
using Gemini 3 Flash vision on Vertex AI.
https://github.com/[your-repo]/fusionmatdb
```

Source data attribution:
- ORNL Fusion Materials Program reports: U.S. Department of Energy, public domain
- MatDB4Fusion baseline data: Lied et al., KIT, EUPL license
- SDC-IC Material Library: ITER structural design criteria, EUPL license

---

## Extraction Pipeline

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    FUSIONMATDB EXTRACTION PIPELINE                           ║
╚══════════════════════════════════════════════════════════════════════════════╝

  ┌─────────────────────────────────────────────────────────────────────────┐
  │                        DATA SOURCES                                      │
  │                                                                          │
  │  ┌──────────────────┐  ┌────────────────┐  ┌──────────────────────────┐ │
  │  │  ORNL fmp.ornl.gov│  │MatDB4Fusion CSV│  │SDC-IC GitHub             │ │
  │  │  65 PDFs (~1.5GB) │  │354 rows (KIT)  │  │SDC-IC_Mat_Lib.mac        │ │
  │  │  1984–2024        │  │EUROFER97, W    │  │16 ITER materials         │ │
  │  └────────┬─────────┘  └───────┬────────┘  └──────────┬───────────────┘ │
  └───────────┼───────────────────┼──────────────────────┼──────────────────┘
              │                   │                       │
              ▼                   │                       │
  ┌───────────────────────┐       │                       │
  │  ORNLDownloader        │       │                       │
  │  • Probes URLs 1–80    │       │                       │
  │  • Skips 404s silently │       │                       │
  │  • Deduplicates on disk│       │                       │
  └───────────┬───────────┘       │                       │
              │ 65 PDFs           │                       │
              ▼                   │                       │
  ┌───────────────────────┐       │                       │
  │  pymupdf (fitz)        │       │                       │
  │  • 120 DPI rasterise   │       │                       │
  │  • PNG bytes per page  │       │                       │
  │  • ~14,950 page images │       │                       │
  └───────────┬───────────┘       │                       │
              │ PNG images        │                       │
              │ (asyncio × 20)    │                       │
              ▼                   │                       │
  ┌─────────────────────────────────────────────────────────────────────┐
  │               GEMINI 3 FLASH — VERTEX AI EXPRESS                    │
  │               20 concurrent · ~343 RPM · temperature=0              │
  │                                                                     │
  │   [PNG page] + [VISION_EXTRACTION_PROMPT]  →  JSON array            │
  │                                                                     │
  │   Reads: tables, figures, graphs, axis labels, data points          │
  │   Returns: {material, property, value, uncertainty, dose_dpa,       │
  │             irradiation_temp_C, test_temp_C, reactor, source}       │
  │                                                                     │
  │   Cost: ~$5 total · Time: ~44 mins for all 65 reports               │
  │   Auth: GOOGLE_CLOUD_API_KEY (AQ. prefix Vertex AI Express key)     │
  └──────────────────────────┬──────────────────────────────────────────┘
                              │ raw JSON records
                              ▼
  ┌───────────────────────────────────────────────────────────────────────┐
  │                    VALIDATION + NORMALISATION                          │
  │                                                                        │
  │  validator.py              normaliser.py                               │
  │  • Physical range checks   • 60+ canonical mappings                   │
  │  • dose_dpa ≥ 0            • "steel" → None (skip)                    │
  │  • temp −273 to 3000°C     • "EUROFER97 steel" → "EUROFER97"          │
  │  • strength 0–5000 MPa     • "pure W" → "W"                          │
  │  • ≤2 errors → keep        • Infer material_class from name           │
  │  • confidence_score 0–1                                               │
  └───────────────────────────────┬───────────────────────────────────────┘
                                  │
           ┌──────────────────────┼─────────────────────────────┐
           │                      │                             │
           ▼ (ORNL vision)        ▼ (MatDB4Fusion CSV)          ▼ (SDC-IC APDL)
  confidence ~0.5-0.9       confidence = 1.0             confidence = 1.0
  ~18,000 records           331 records                  ~1,400 records
  gemini_vision             matdb4fusion_ingest          sdc_ic_parse
           │                      │                             │
           └──────────────────────┼─────────────────────────────┘
                                  │
                                  ▼
  ┌─────────────────────────────────────────────────────────────────────────┐
  │                         SQLITE DATABASE                                  │
  │                                                                          │
  │  papers ──────────────────────────────────────────────────────────────  │
  │  │ id · title · year · access_type · source_url · full_text             │
  │  │                                                                       │
  │  ├── materials ──────────────────────────────────────────────────────── │
  │  │   │ name · class_ · W/Cr/V/Fe/... (wt%) · grain_size                │
  │  │   │ manufacturer · layer_spacing_nm (nano-laminates)                 │
  │  │   │                                                                   │
  │  │   ├── irradiation_conditions ──────────────────────────────────────  │
  │  │   │   │ dose_dpa · irradiation_temp · reactor · particle             │
  │  │   │   │ neutron_spectrum · helium_appm                               │
  │  │   │   │                                                               │
  │  │   │   └── mechanical_properties ──────────────────────────────────── │
  │  │           yield_strength (irr + unirr + std)                         │
  │  │           UTS · elongation · DBTT · hardness · fracture_toughness    │
  │  │           electrical_resistivity · dielectric_breakdown              │
  │  │           creep_rate · fatigue_cycles · void_density                 │
  │  │           confidence_score · extraction_method · reviewed_by_human   │
  │  │           raw_extraction_json  ← full Gemini output preserved        │
  └─────────────────────────────────────────────────────────────────────────┘
                                  │
              ┌───────────────────┼───────────────────┐
              ▼                   ▼                   ▼
  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐
  │  PARQUET EXPORT  │  │  WORLD MODEL JSON│  │  HUGGINGFACE DATASET  │
  │  Flat feature    │  │  state_before    │  │  (step 6 — publish)   │
  │  vectors for GP  │  │  action          │  │  Citeable, DOI,       │
  │  / neural net    │  │  state_after     │  │  open access          │
  └──────────┬───────┘  └────────┬─────────┘  └───────────────────────┘
             │                   │
             ▼                   ▼
  ┌──────────────────┐  ┌──────────────────────────────────┐
  │   FusionBAL      │  │   FusionUQ                       │
  │   Loads Parquet  │  │   Calibrates MACE-MP-0           │
  │   as GP prior    │  │   uncertainty against            │
  │   → experiment   │  │   experimental data              │
  │   recommendations│  │   → digital twin                 │
  └──────────────────┘  └──────────────────────────────────┘
```

---

## What it does

1. **Downloads** all accessible ORNL Fusion Materials semiannual progress reports (65 of 77 volumes, ~1.5 GB of PDFs)
2. **Extracts** structured data from every page using Gemini 2.5 Flash vision on Vertex AI — reads figures, graphs, and tables that text parsers miss
3. **Stores** in SQLite with a schema aligned to MatDB4Fusion (the unirradiated baseline layer), enabling before/after irradiation delta calculations
4. **Exports** to Parquet (for GP/neural network training) and world model JSON (state_before, action, state_after) for digital twin training

---

## Install

```bash
cd fusionmatdb
pip install -e .
```

Requires:
- Python 3.12+
- GCP service account key with Vertex AI access (set path in `VertexVisionExtractor` or use `GOOGLE_API_KEY` for slower free-tier fallback)
- `ANTHROPIC_API_KEY` for text-only LLM extraction (optional, vision is preferred)

---

## Usage

### Full build (downloads + extracts all reports)

```bash
fusionmatdb build --pdf-dir data/ornl_pdfs --db fusionmatdb.sqlite
```

### Check what's in the database

```bash
fusionmatdb stats --db fusionmatdb.sqlite
```

### Export for ML training

```bash
# Parquet — flat feature vectors for GP/neural network training
fusionmatdb export --format parquet --output fusionmatdb_export

# World model JSON — (state_before, action, state_after) for digital twin
fusionmatdb export --format world_model --output fusionmatdb_export
```

### Use the vision extractor directly

```python
from fusionmatdb.access.vision_extractor import VertexVisionExtractor

extractor = VertexVisionExtractor()
records = extractor.extract_pdf("path/to/report.pdf", paper_id="ornl_70")
# records: list of validated dicts with confidence scores
# Processes 249 pages in ~5 minutes using 20 concurrent Vertex AI requests
```

---

## Schema

Four SQLAlchemy tables:

**papers** — source document (ORNL report, journal paper)
- Provenance, year, access type, full text

**materials** — alloy/ceramic specification
- Composition (element weight % — W, Cr, V, Ta, Fe, C, Mn, Mo, Ni, Si, Al, Ti)
- Processing (manufacturer, temper temp, crystal structure, grain size)
- Nano-laminate fields: layer_material_a/b, layer_spacing_nm
- Linked to MatDB4Fusion via `matdb4fusion_id`

**irradiation_conditions** — what the reactor did to the sample
- Reactor (HFIR, BOR-60, ATR, ion_beam...)
- dose_dpa, irradiation_temp_C, neutron_spectrum, helium_appm, hydrogen_appm

**mechanical_properties** — measured outcomes (before and after)
- Tensile: yield_strength, UTS, elongation (irradiated + unirradiated + std)
- Fracture: DBTT, fracture_toughness, Charpy energy
- Hardness: HV with uncertainty
- Electrical: resistivity (µΩ·cm), conductivity (% IACS for nano-laminates)
- Dielectric: breakdown (kV/mm) before/after irradiation — for ceramic insulators
- Creep rate, fatigue cycles to failure
- Radiation microstructure: void density/diameter, dislocation loop density/diameter
- ML metadata: confidence_score, extraction_method, reviewed_by_human

### Why this schema matters for ML

The key training signal is the **irradiation delta**: `yield_strength_mpa_irradiated - yield_strength_mpa_unirradiated`. This is the radiation hardening response function. Every other ML approach has to infer this from separate unirradiated and irradiated databases. FusionMatDB stores both in the same row.

---

## Data sources

| Source | Records (est.) | Access |
|---|---|---|
| ORNL semiannual reports (65 volumes) | ~40,000 pts | Public PDF |
| SDC-IC Material Library | ~500 pts | Public GitHub |
| OSTI.gov API (DOE publications) | TBD | Public API |
| MatDB4Fusion connector | ~353 rows | Public CSV (KIT) |

---

## ML export formats

**Parquet** — one row per measurement, flat feature vector:
```
material_name, W_wt_pct, Cr_wt_pct, ..., dose_dpa, irradiation_temp_C,
yield_strength_mpa_unirradiated, yield_strength_mpa_irradiated,
delta_yield_strength_mpa, confidence_score
```

**World model JSON** — for digital twin / foundation model training:
```json
{
  "state_before": {"material_name": "EUROFER97", "yield_strength_mpa": 612},
  "action": {"dose_dpa": 66, "irradiation_temp_c": 302, "reactor": "HFIR"},
  "state_after": {"yield_strength_mpa": 1198, "uts_mpa": 1203}
}
```

---

## Relationship to other tools

- **FusionBAL** (`../fusionbal/`) — loads FusionMatDB Parquet as GP prior data, tells you which experiments to run next
- **FusionUQ** (`../fusionuq/`) — uses FusionMatDB experimental data to calibrate MACE-MP-0 uncertainty estimates
- **MatDB4Fusion** (KIT, external) — unirradiated baseline layer; FusionMatDB is the irradiation effects layer built to be compatible with their schema

---

## Context

Announced at COP29 (November 2024) by Jim Pickles (Head of Materials, Tokamak Energy) as a priority: *"An open-access, single source of truth for high-quality fusion materials data... is essential for this new phase of technology development."* FusionMatDB is that infrastructure, open-sourced.
