"""MatDB4Fusion connector — ingest unirradiated baseline data from KIT/Philipp Lied.

MatDB4Fusion (https://matdb4fusion.app) is a human-curated materials database
maintained by KIT.  The April 2026 export contains 354 rows (5 dummy, 349 real)
covering EUROFER97, W, and W K-doped.

The public API does not expose a CSV download endpoint (returns 404).
Export the CSV manually from https://matdb4fusion.app and pass the file path:

    fusionmatdb ingest-matdb4fusion /path/to/matdb4fusion.csv --db fusionmatdb.sqlite

Or programmatically:

    from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
    from fusionmatdb.storage.database import init_db, get_session

    init_db("fusionmatdb.sqlite")
    session = get_session()
    n = ingest_matdb4fusion_csv("/path/to/matdb4fusion.csv", session)
    session.commit()
    print(f"Ingested {n} records")

Column conventions
------------------
* CSV uses space-separated (Title-Case) column names, e.g. ``Yield Point``.
* Irradiation State: ``unirradiated``, ``irradiated``, or NaN (treated as
  unirradiated — these are Charpy and similar rows lacking an explicit label).
* Dummy rows are identified by ``Title == "dummy data for demo"`` and skipped.
* Mechanical values are routed to the *_unirradiated or *_irradiated columns
  based on the Irradiation State of each row.
"""

from __future__ import annotations

import json
import math
from typing import Optional

import pandas as pd

# ---------------------------------------------------------------------------
# Column maps: CSV column name → FusionMatDB attribute
# ---------------------------------------------------------------------------

# Material-level columns (composition + processing).
# Float columns are stored as-is; string columns are stripped.
MATERIAL_FLOAT_COLS: dict[str, str] = {
    "Al": "Al",
    "C": "C",
    "Cr": "Cr",
    "Mn": "Mn",
    "Mo": "Mo",
    "Ni": "Ni",
    "Si": "Si",
    "Ta": "Ta",
    "Ti": "Ti",
    "V": "V",
    "W": "W",
    "Temper Temp": "temper_temp",
}

MATERIAL_STR_COLS: dict[str, str] = {
    "Manufacturer Name": "manufacturer_name",
    "Product Shape": "product_shape",
}

# MechanicalProperty columns that are always float regardless of irr state
PROP_FLOAT_ALWAYS: dict[str, str] = {
    "Test Temp": "test_temp",
    "Hardness Value": "hardness_value",
    "KV": "kv_joules",
    "JQ": "fracture_toughness_mpa_sqrt_m",
    "Creep Rate": "creep_rate_per_s",
    "Creep Stress": "fatigue_stress_amplitude_mpa",  # best fit available column
    "DBTT_K": "dbtt_k_unirradiated",
}

# MechanicalProperty columns that are routed by irradiation state
PROP_FLOAT_ROUTED: dict[str, tuple[str, str]] = {
    # csv_col: (unirradiated_attr, irradiated_attr)
    "Yield Point": ("yield_strength_mpa_unirradiated", "yield_strength_mpa_irradiated"),
    "Ultimate Tensile Strength": ("uts_mpa_unirradiated", "uts_mpa_irradiated"),
    "Total Elongation": ("elongation_pct_unirradiated", "elongation_pct_irradiated"),
}

PROP_STR_ALWAYS: dict[str, str] = {
    "Experiment Type": "experiment_type",
    "Method": "method",
    "Hardness Type": "hardness_type",
}

# The synthetic Paper record representing the entire MatDB4Fusion dataset
MATDB4FUSION_PAPER = {
    "id": "matdb4fusion_2026",
    "title": "MatDB4Fusion — Unirradiated Baseline Materials Database",
    "year": 2026,
    "access_type": "matdb4fusion_ingest",
    "source_url": "https://matdb4fusion.app",
}

# Rows with this title are demo/dummy entries and must be skipped
_DUMMY_TITLE = "dummy data for demo"

# Material class inference
_CLASS_MAP = {
    "eurofer": "RAFM steel",
    "w, k-doped": "K-doped W",
    "k-doped w": "K-doped W",
}


def _safe_float(val) -> Optional[float]:
    if val is None:
        return None
    try:
        f = float(val)
        return None if math.isnan(f) else f
    except (TypeError, ValueError):
        return None


def _safe_str(val) -> Optional[str]:
    if val is None:
        return None
    s = str(val).strip()
    return s if s and s.lower() not in ("nan", "none", "") else None


def _infer_class(name: str) -> Optional[str]:
    n = name.lower()
    for key, cls in _CLASS_MAP.items():
        if key in n:
            return cls
    if n == "w" or "tungsten" in n:
        return "pure W"
    return None


# ---------------------------------------------------------------------------
# Public ingest function
# ---------------------------------------------------------------------------

def ingest_matdb4fusion_csv(csv_path: str, db_session) -> int:
    """Ingest a MatDB4Fusion CSV export into FusionMatDB.

    Parameters
    ----------
    csv_path:
        Path to the CSV file exported from https://matdb4fusion.app.
    db_session:
        An active SQLAlchemy Session (already bound to an initialised DB).

    Returns
    -------
    int
        Number of MechanicalProperty rows inserted.
    """
    from fusionmatdb.storage.schema import (
        IrradiationCondition,
        Material,
        MechanicalProperty,
        Paper,
    )

    # ------------------------------------------------------------------
    # 1. Upsert the Paper record
    # ------------------------------------------------------------------
    paper_id = MATDB4FUSION_PAPER["id"]
    if db_session.get(Paper, paper_id) is None:
        db_session.add(Paper(**MATDB4FUSION_PAPER))
        db_session.flush()

    # ------------------------------------------------------------------
    # 2. Load CSV — all columns as strings initially
    # ------------------------------------------------------------------
    df = pd.read_csv(csv_path, dtype=str)
    df.columns = [c.strip() for c in df.columns]

    # ------------------------------------------------------------------
    # 3. Filter out dummy / demo rows
    # ------------------------------------------------------------------
    if "Title" in df.columns:
        df = df[df["Title"].fillna("") != _DUMMY_TITLE].copy()

    # ------------------------------------------------------------------
    # 4. Per-row ingestion
    # ------------------------------------------------------------------
    # Material dedup: key = (paper_id, name, composition+processing fingerprint)
    # IrradiationCondition dedup: key = (paper_id, material_id, state, dose, irr_temp)
    mat_cache: dict[tuple, int] = {}
    irr_cache: dict[tuple, int] = {}

    stored = 0

    for _, row in df.iterrows():
        # ---- Material name ----
        mat_name = _safe_str(row.get("Name")) or "Unknown"

        # ---- Build material kwargs ----
        mat_kwargs: dict = {"paper_id": paper_id, "name": mat_name}
        mat_fp: list = [paper_id, mat_name]

        for csv_col, attr in MATERIAL_FLOAT_COLS.items():
            val = _safe_float(row.get(csv_col))
            mat_kwargs[attr] = val
            mat_fp.append(val)

        for csv_col, attr in MATERIAL_STR_COLS.items():
            val = _safe_str(row.get(csv_col))
            mat_kwargs[attr] = val
            mat_fp.append(val)

        # crystal_structure is not in the real CSV; skip it
        mat_fp_key = tuple(mat_fp)

        if mat_fp_key in mat_cache:
            material_id = mat_cache[mat_fp_key]
        else:
            # Fetch existing or create
            existing_mat = (
                db_session.query(Material)
                .filter_by(paper_id=paper_id, name=mat_name)
                .first()
            )
            if existing_mat:
                material_id = existing_mat.id
            else:
                mat_kwargs["class_"] = _infer_class(mat_name)
                mat_id_raw = _safe_str(row.get("Material ID"))
                mat_kwargs["matdb4fusion_id"] = mat_id_raw
                mat_obj = Material(**mat_kwargs)
                db_session.add(mat_obj)
                db_session.flush()
                material_id = mat_obj.id
            mat_cache[mat_fp_key] = material_id

        # ---- Irradiation state ----
        irr_state_raw = _safe_str(row.get("Irradiation State"))
        # NaN irradiation state → treat as unirradiated (Charpy rows missing explicit label)
        irr_state = irr_state_raw if irr_state_raw else "unirradiated"
        is_irradiated = irr_state == "irradiated"

        dose = _safe_float(row.get("Dose"))
        irr_temp = _safe_float(row.get("Irradiation Temp"))
        reactor = _safe_str(row.get("Reactor"))
        particle = _safe_str(row.get("Particle"))

        irr_key = (paper_id, material_id, irr_state, dose, irr_temp)
        if irr_key in irr_cache:
            irr_id = irr_cache[irr_key]
        else:
            existing_irr = (
                db_session.query(IrradiationCondition)
                .filter_by(
                    paper_id=paper_id,
                    material_id=material_id,
                    irradiation_state=irr_state,
                    dose_dpa=dose,
                    irradiation_temp=irr_temp,
                )
                .first()
            )
            if existing_irr:
                irr_id = existing_irr.id
            else:
                irr_obj = IrradiationCondition(
                    paper_id=paper_id,
                    material_id=material_id,
                    irradiation_state=irr_state,
                    dose_dpa=dose,
                    irradiation_temp=irr_temp,
                    reactor=reactor,
                    particle=particle,
                )
                db_session.add(irr_obj)
                db_session.flush()
                irr_id = irr_obj.id
            irr_cache[irr_key] = irr_id

        # ---- MechanicalProperty kwargs ----
        prop_kwargs: dict = {
            "paper_id": paper_id,
            "material_id": material_id,
            "irradiation_id": irr_id,
            "confidence_score": 1.0,
            "extraction_method": "matdb4fusion_ingest",
            "reviewed_by_human": True,
            "matdb4fusion_entry_id": _safe_str(row.get("Experiment ID")),
        }

        for csv_col, attr in PROP_FLOAT_ALWAYS.items():
            prop_kwargs[attr] = _safe_float(row.get(csv_col))

        for csv_col, attr in PROP_STR_ALWAYS.items():
            prop_kwargs[attr] = _safe_str(row.get(csv_col))

        for csv_col, (unirr_attr, irr_attr) in PROP_FLOAT_ROUTED.items():
            val = _safe_float(row.get(csv_col))
            prop_kwargs[irr_attr if is_irradiated else unirr_attr] = val

        # Persist raw row for traceability
        prop_kwargs["raw_extraction_json"] = json.dumps(
            dict(row.items()), default=str
        )

        # Skip rows that carry no measurable property
        _MEASUREMENT_ATTRS = (
            "yield_strength_mpa_unirradiated",
            "yield_strength_mpa_irradiated",
            "uts_mpa_unirradiated",
            "uts_mpa_irradiated",
            "elongation_pct_unirradiated",
            "elongation_pct_irradiated",
            "hardness_value",
            "kv_joules",
            "fracture_toughness_mpa_sqrt_m",
            "creep_rate_per_s",
            "fatigue_stress_amplitude_mpa",
        )
        if not any(prop_kwargs.get(a) is not None for a in _MEASUREMENT_ATTRS):
            continue

        db_session.add(MechanicalProperty(**prop_kwargs))
        stored += 1

    return stored
