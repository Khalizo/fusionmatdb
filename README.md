<p align="center">
  <h1 align="center">⚛️ FusionMatDB</h1>
</p>

<p align="center">
  <strong>The first open-source fusion irradiation materials database.</strong><br>
  22,269 structured records extracted from 65 ORNL reports (1990–2024) using Gemini 3 Flash vision.
</p>

<p align="center">
  <a href="https://github.com/Khalizo/fusionmatdb"><img src="https://img.shields.io/badge/python-3.12+-blue?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.12+"></a>
  <a href="https://github.com/Khalizo/fusionmatdb"><img src="https://img.shields.io/badge/tests-65%20passed-brightgreen?style=for-the-badge" alt="Tests"></a>
  <a href="https://huggingface.co/datasets/Khalizo/fusionmatdb"><img src="https://img.shields.io/badge/🤗%20HuggingFace-Dataset-yellow?style=for-the-badge" alt="HuggingFace"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue?style=for-the-badge" alt="MIT License"></a>
</p>

<p align="center">
  <a href="#quick-start">Quick Start</a> · <a href="#extraction-pipeline">Pipeline</a> · <a href="#dataset-card">Dataset Card</a> · <a href="#what-you-can-train">ML Training</a> · <a href="https://huggingface.co/datasets/Khalizo/fusionmatdb">HuggingFace</a> · <a href="https://github.com/Khalizo/fusionguide">FusionGuide</a> · <a href="https://github.com/Khalizo/fusionuq">FusionUQ</a>
</p>

---

No publicly accessible, ML-ready fusion irradiation database exists. EUROfusion EDDI (~3,000 records) is locked behind EU consortium access. MatDB4Fusion covers unirradiated baselines only. **FusionMatDB fills the gap**: irradiation effects data extracted from decades of publicly available PDFs — for ~$40 and 44 minutes of Vertex AI compute.

> *"An open-access, single source of truth for high-quality fusion materials data... is essential for this new phase of technology development."*
> — Jim Pickles, Head of Materials, Tokamak Energy (COP29, November 2024)

---

## Quick Start

```bash
pip install -e .

# Ingest SDC-IC ITER material curves (free, instant)
fusionmatdb ingest-sdc-ic --repo-path /path/to/SDC-IC-Material-Library --db fusionmatdb.sqlite

# Extract all 65 ORNL reports (~$40, ~44 mins on Vertex AI)
export GOOGLE_CLOUD_API_KEY="your-vertex-ai-express-key"
fusionmatdb build --pdf-dir data/ornl_pdfs --db fusionmatdb.sqlite

# Check what you have
fusionmatdb stats --db fusionmatdb.sqlite

# Export for ML training
fusionmatdb export --format parquet --output data/export --db fusionmatdb.sqlite
fusionmatdb export --format world_model --output data/export --db fusionmatdb.sqlite
```

---

## Extraction Pipeline

```
╔══════════════════════════════════════════════════════════════════════════╗
║                    FUSIONMATDB EXTRACTION PIPELINE                      ║
╚══════════════════════════════════════════════════════════════════════════╝

  ORNL fmp.ornl.gov (65 PDFs)    SDC-IC GitHub (16 ITER materials)
         │                              │
         ▼                              │
  ┌─────────────────┐                   │
  │ ORNLDownloader   │                   │
  │ Probes URLs 1–80 │                   │
  │ Skips 404s       │                   │
  └────────┬────────┘                   │
           │ 65 PDFs                    │
           ▼                            │
  ┌─────────────────┐                   │
  │ pymupdf (fitz)   │                   │
  │ 120 DPI → PNG    │                   │
  │ ~14,950 pages    │                   │
  └────────┬────────┘                   │
           │ (asyncio x 20)             │
           ▼                            │
  ┌──────────────────────────────┐      │
  │  GEMINI 3 FLASH — VERTEX AI  │      │
  │  20 concurrent · temp=0      │      │
  │  Reads: tables + figures     │      │
  │  Cost: ~$40 · Time: ~44 min  │      │
  └──────────┬───────────────────┘      │
             │                          │
             ▼                          ▼
  ┌──────────────────────────────────────────┐
  │  VALIDATION + NORMALISATION               │
  │  • Physical range checks (dose, temp)     │
  │  • 60+ canonical material name mappings   │
  │  • Material class inference               │
  │  • Confidence scoring (0.0–1.0)           │
  └──────────────────┬───────────────────────┘
                     │
                     ▼
  ┌──────────────────────────────────────────┐
  │  SQLITE DATABASE — 22,269 records         │
  │  papers → materials → irradiation_conds   │
  │                     → mechanical_props     │
  │  raw_extraction_json preserved per record  │
  └──────────────────┬───────────────────────┘
                     │
          ┌──────────┼──────────┐
          ▼          ▼          ▼
     Parquet    World Model   HuggingFace
     (GP/NN)    (digital twin) (publish)
          │          │
          ▼          ▼
    FusionGuide   FusionUQ
```

---

## Dataset Card

| | |
|---|---|
| **Total records** | 22,269 |
| **High confidence (≥0.7)** | 18,902 (85%) |
| **Irradiated yield strength** | 2,267 records |
| **GP-ready rows** (yield + dose + temp) | 1,594 |
| **Material classes** | 19 |
| **Source documents** | 65 ORNL reports + SDC-IC ITER library |
| **Extraction model** | Gemini 3 Flash (Vertex AI, temperature=0) |
| **Cost to reproduce** | ~$40 |

### Property Coverage

| Property | Records | Notes |
|---|---|---|
| Yield strength (MPa) | 4,868 | 2,267 irradiated + 2,601 unirradiated |
| UTS (MPa) | 3,681 | |
| Volumetric swelling (%) | 2,066 | |
| Elongation (%) | 1,920 | |
| Hardness (HV) | 1,496 | |
| Fracture toughness (MPa√m) | 1,262 | |
| DBTT (K) | 510 | |
| Void diameter (nm) | 796 | Feeds FusionUQ cascade simulations |
| Electrical resistivity (µΩ·cm) | 254 | Nano-laminate / magnet applications |

### Material Coverage

| Class | Records | Examples |
|---|---|---|
| RAFM steels | 5,512 | F82H, EUROFER97, HT-9, 9Cr, T91 |
| Vanadium alloys | 2,956 | V-4Cr-4Ti, V-5Cr-5Ti |
| Copper alloys | 2,415 | CuCrZr, GlidCop, OFHC Cu |
| Austenitic steels | 2,118 | 316 SS, 304 SS, JPCA |
| Ceramics | 1,094 | Al₂O₃, MgAl₂O₄, SiC, BN |
| SiC composites | 887 | SiC/SiC |
| ODS steels | 784 | MA957, PM2000, 14YWT |
| Tungsten + alloys | 1,350 | W, W-Re, K-doped W |
| + 11 more classes | 3,153 | Ni alloys, Be, graphite, nano-laminates, Ti, Zr, HTS... |

---

## What You Can Train

**✅ Gaussian Process property predictors** — RAFM steels (457 pts), V-4Cr-4Ti (371 pts), Cu alloys (156 pts)

**✅ Bayesian active learning** — load as GP prior in [FusionGuide](https://github.com/Khalizo/fusionguide) to plan experiments

**✅ World model** — 142 paired irradiated/unirradiated records in `{state_before, action, state_after}` format

**✅ Materials NLP** — 65 ORNL reports with page-level extraction tracing

**❌ Deep learning** — not enough data per class yet (need 5,000+)

---

## Known Limitations

1. **Extraction accuracy estimated, not fully verified** — spot-checked against source PDFs, not systematically validated
2. **Fission proxy, not fusion neutrons** — all data uses fission reactor spectra; IFMIF not yet operational
3. **202 high-dose records flagged** — `dose_dpa > 150` flagged for expert review
4. **20% "other" material class** — ambiguous names that couldn't be auto-classified
5. **Sparse paired data** — only 142 records with both irradiated AND unirradiated yield strength

---

## Comparison

| Database | Records | Irradiation data | Access | ML-ready |
|---|---|---|---|---|
| **FusionMatDB** | **22,269** | **Yes** | **Open** | **Yes** |
| EUROfusion EDDI | ~3,000 | Yes | EU consortium only | No |
| MatDB4Fusion (KIT) | 353 | No (baseline) | Public CSV | Partial |
| JRC ODIN | >20,000 | Some | Tiered | No |

---

## Related Projects

| | |
|---|---|
| ⚛️ [FusionMatDB](https://github.com/Khalizo/fusionmatdb) | This repo — the database and extraction pipeline |
| 🧭 [FusionGuide](https://github.com/Khalizo/fusionguide) | Bayesian active learning for experiment planning |
| 🔬 [FusionUQ](https://github.com/Khalizo/fusionuq) | Uncertainty quantification for ML interatomic potentials |
| 📊 [FusionMatDB Dataset](https://huggingface.co/datasets/Khalizo/fusionmatdb) | HuggingFace dataset with train/val/test splits |

---

## Citation

```bibtex
@dataset{fusionmatdb2026,
  title  = {FusionMatDB: An Open-Source Fusion Irradiation Materials Database},
  author = {Khalizo},
  year   = {2026},
  url    = {https://huggingface.co/datasets/Khalizo/fusionmatdb},
  note   = {22,269 records from 65 ORNL reports (1990-2024), extracted with Gemini 3 Flash.}
}
```
