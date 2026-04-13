"""SDC-IC Material Library ingestion module.

Parses the ANSYS APDL macro file from the ITER Structural Design Criteria for
In-vessel Components (SDC-IC) Material Library, extracting temperature-dependent
material properties from mptemp/mpdata command blocks and *taxis/*dim table blocks.

Source: https://github.com/Structural-Mechanics/SDC-IC-Material-Library
Human-curated ITER design curves → confidence_score = 1.0
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Material metadata: number → (name, class)
# ---------------------------------------------------------------------------

MATERIAL_MAP: dict[int, tuple[str, str]] = {
    101: ("304L Stainless Steel", "austenitic_steel"),
    102: ("316L Stainless Steel", "austenitic_steel"),
    103: ("316L (N-IG) Stainless Steel", "austenitic_steel"),
    104: ("GRADE 660 Stainless Steel", "austenitic_steel"),
    105: ("XM-19 Steel", "austenitic_steel"),
    106: ("Alloy 625", "nickel_alloy"),
    107: ("Ti-6Al-4V Alloy", "titanium_alloy"),
    108: ("Pure Copper", "copper"),
    109: ("Copper-Chromium-Zirconium Alloy", "copper_alloy"),
    110: ("Dispersion-Strengthened Copper", "copper_alloy"),
    111: ("Aluminium-Nickel Bronze", "copper_alloy"),
    112: ("Alloy 718", "nickel_alloy"),
    113: ("Beryllium", "beryllium"),
    114: ("Tungsten", "tungsten"),
    115: ("CFC EU Grade", "carbon_fibre_composite"),
    116: ("CFC CX-2002U Grade", "carbon_fibre_composite"),
}

# Map APDL property tags → (FusionMatDB property_name, unit, scale_factor)
# scale_factor converts from SI to the target unit (e.g. Pa → GPa, Pa → MPa)
MPDATA_PROP_MAP: dict[str, tuple[str, str, float]] = {
    "EX":   ("youngs_modulus_gpa",         "GPa",        1e-9),
    "ALPX": ("thermal_expansion_coeff_per_k", "1/K",     1.0),
    "CTEX": ("thermal_expansion_coeff_instant_per_k", "1/K", 1.0),
    "PRXY": ("poissons_ratio",             "dimensionless", 1.0),
    "DENS": ("density_kg_m3",              "kg/m3",      1.0),
    "KXX":  ("thermal_conductivity_w_mk",  "W/m/K",      1.0),
    "KYY":  ("thermal_conductivity_y_w_mk","W/m/K",      1.0),
    "KZZ":  ("thermal_conductivity_z_w_mk","W/m/K",      1.0),
    "C":    ("specific_heat_j_kg_k",       "J/kg/K",     1.0),
}

# *dim/*taxis property tags → (FusionMatDB property_name, scale_factor)
TABLE_PROP_MAP: dict[str, tuple[str, float]] = {
    "SY_MIN":     ("yield_strength_min_mpa",  1e-6),
    "SY_AV":      ("yield_strength_avg_mpa",  1e-6),
    "SU_MIN":     ("uts_min_mpa",             1e-6),
    "SU_AV":      ("uts_avg_mpa",             1e-6),
    "SM":         ("allowable_stress_mpa",    1e-6),
    "SY_IRR_MIN": ("yield_strength_irr_min_mpa", 1e-6),
    "SY_IRR_AV":  ("yield_strength_irr_avg_mpa", 1e-6),
    "SU_IRR_MIN": ("uts_irr_min_mpa",         1e-6),
    "SU_IRR_AV":  ("uts_irr_avg_mpa",         1e-6),
}

# Properties flagged as irradiated
IRRADIATED_PROPS = {"SY_IRR_MIN", "SY_IRR_AV", "SU_IRR_MIN", "SU_IRR_AV"}

SOURCE_FILE = "SDC-IC_Mat_Lib.mac"


# ---------------------------------------------------------------------------
# Helper: strip APDL comments and leading/trailing whitespace from a line
# ---------------------------------------------------------------------------

def _clean(line: str) -> str:
    """Remove APDL inline comments (! ...) and strip whitespace."""
    idx = line.find("!")
    if idx >= 0:
        line = line[:idx]
    return line.strip()


# ---------------------------------------------------------------------------
# Section splitter: identify which material number owns each line
# ---------------------------------------------------------------------------

# Pattern to detect material block header
_MAT_BLOCK_RE = re.compile(
    r"\*if,MAT_NAME,eq,MATNAMES_ARRAY\(1,(\d+)\)", re.IGNORECASE
)


def _split_material_sections(lines: list[str]) -> dict[int, list[str]]:
    """Return {mat_index (1-based) → lines} for each material block."""
    sections: dict[int, list[str]] = {}
    current: int | None = None
    buf: list[str] = []

    for line in lines:
        m = _MAT_BLOCK_RE.search(line)
        if m:
            if current is not None:
                sections[current] = buf
            current = int(m.group(1))
            buf = [line]
        elif current is not None:
            buf.append(line)

    if current is not None:
        sections[current] = buf

    return sections


# ---------------------------------------------------------------------------
# mptemp + mpdata parser
# ---------------------------------------------------------------------------

_MPTEMP_RE = re.compile(
    r"^mptemp\s*,\s*(\d+)\s*,(.*)", re.IGNORECASE
)
_MPDATA_RE = re.compile(
    r"^mpdata\s*,\s*(\w+)\s*,\s*\d+\s*,\s*(\d+)\s*,(.*)", re.IGNORECASE
)
_MP_SCALAR_RE = re.compile(
    r"^mp\s*,\s*(\w+)\s*,\s*\d+\s*,\s*([\d.eE+\-]+)", re.IGNORECASE
)


def _parse_floats(text: str) -> list[float]:
    """Extract all floating-point numbers from a comma-separated string."""
    values = []
    for tok in text.split(","):
        tok = tok.strip().rstrip(",")
        if not tok:
            continue
        try:
            values.append(float(tok))
        except ValueError:
            pass
    return values


def _parse_mptemp_mpdata(
    lines: list[str],
) -> dict[str, list[tuple[float, float]]]:
    """
    Parse mptemp / mpdata blocks within a material section.

    Returns {prop_tag: [(temp_C, value), ...]}
    """
    # Build temperature table: slot_index (1-based) → temperature
    temps: dict[int, float] = {}
    # Accumulate (slot, values) per prop for later pairing
    prop_slots: dict[str, list[tuple[int, list[float]]]] = {}

    for line in lines:
        cleaned = _clean(line)
        if not cleaned:
            continue

        # mptemp reset
        if re.match(r"^mptemp\s*$", cleaned, re.IGNORECASE):
            temps.clear()
            continue

        # mptemp, slot, t1, t2, ...
        m = _MPTEMP_RE.match(cleaned)
        if m:
            slot = int(m.group(1))
            vals = _parse_floats(m.group(2))
            for i, v in enumerate(vals):
                temps[slot + i] = v
            continue

        # mpdata, PROP, matid, slot, v1, v2, ...
        m = _MPDATA_RE.match(cleaned)
        if m:
            prop = m.group(1).upper()
            slot = int(m.group(2))
            vals = _parse_floats(m.group(3))
            prop_slots.setdefault(prop, []).append((slot, vals))
            continue

        # mp, PRXY, matid, value  (scalar, no temperature dependence)
        m = _MP_SCALAR_RE.match(cleaned)
        if m:
            prop = m.group(1).upper()
            val = float(m.group(2))
            # Represent as a single point at 20 °C (room temperature)
            prop_slots.setdefault(prop, []).append((1, [val]))
            if 1 not in temps:
                temps[1] = 20.0
            continue

    # Assemble (temp, value) pairs per property
    result: dict[str, list[tuple[float, float]]] = {}
    for prop, slot_data in prop_slots.items():
        pairs: list[tuple[float, float]] = []
        for slot, vals in slot_data:
            for i, v in enumerate(vals):
                idx = slot + i
                temp = temps.get(idx)
                if temp is not None:
                    pairs.append((temp, v))
        if pairs:
            result[prop] = pairs

    return result


# ---------------------------------------------------------------------------
# *dim / *taxis / assignment parser (for SY_MIN, SY_AV, SU_MIN, SM …)
# ---------------------------------------------------------------------------

_DIM_RE = re.compile(
    r"^\*dim\s*,\s*(\w+)\s*,\s*table\s*,\s*(\d+)", re.IGNORECASE
)
_TAXIS_RE = re.compile(
    r"^\*taxis\s*,\s*(\w+)\s*\(\s*(\d+)\s*\)\s*,\s*\d+\s*,(.*)", re.IGNORECASE
)
_ASSIGN_RE = re.compile(
    r"^(\w+)\s*\(\s*(\d+)\s*\)\s*=\s*(.*)", re.IGNORECASE
)


def _parse_table_props(
    lines: list[str],
    mat_number: int,
) -> dict[str, list[tuple[float, float]]]:
    """
    Parse *dim / *taxis / assignment blocks for scalar table properties.

    Returns {canonical_prop_key: [(temp_C, value), ...]}
    where canonical_prop_key is the SDC-IC tag without the _<matnum> suffix,
    e.g. "SY_MIN" for "SY_MIN_101".
    """
    # Collect table names that correspond to recognised properties
    active_tables: set[str] = set()  # full var names e.g. "SY_MIN_101"
    # Map: var_name → {slot → temp_C}
    table_temps: dict[str, dict[int, float]] = {}
    # Map: var_name → [(slot, values)]
    table_values: dict[str, list[tuple[int, list[float]]]] = {}

    for line in lines:
        cleaned = _clean(line)
        if not cleaned:
            continue

        # *dim, VARNAME, table, N  — detect recognised table names
        m = _DIM_RE.match(cleaned)
        if m:
            var = m.group(1).upper()
            # Check if var matches any known TABLE_PROP_MAP key (possibly with suffix)
            for key in TABLE_PROP_MAP:
                pattern = key.replace("_", r"_")
                if re.match(rf"^{pattern}(_\w+)?$", var, re.IGNORECASE):
                    active_tables.add(var)
                    break
            continue

        # *taxis, VARNAME(slot), 1, t1, t2, ...
        m = _TAXIS_RE.match(cleaned)
        if m:
            var = m.group(1).upper()
            if var not in active_tables:
                continue
            start_slot = int(m.group(2))
            temps_vals = _parse_floats(m.group(3))
            tmap = table_temps.setdefault(var, {})
            for i, t in enumerate(temps_vals):
                tmap[start_slot + i] = t
            continue

        # VARNAME(slot) = v1, v2, ...
        m = _ASSIGN_RE.match(cleaned)
        if m:
            var = m.group(1).upper()
            if var not in active_tables:
                continue
            start_slot = int(m.group(2))
            vals = _parse_floats(m.group(3))
            table_values.setdefault(var, []).append((start_slot, vals))
            continue

    # Assemble (temp, value) pairs, keyed by canonical prop name
    result: dict[str, list[tuple[float, float]]] = {}
    for var, slot_data in table_values.items():
        tmap = table_temps.get(var, {})
        if not tmap:
            continue
        pairs: list[tuple[float, float]] = []
        for start_slot, vals in slot_data:
            for i, v in enumerate(vals):
                temp = tmap.get(start_slot + i)
                if temp is not None:
                    pairs.append((temp, v))
        if not pairs:
            continue
        # Map var name back to canonical key
        canonical = _var_to_canonical(var)
        if canonical:
            result.setdefault(canonical, []).extend(pairs)

    return result


def _var_to_canonical(var: str) -> str | None:
    """Map a full APDL variable name (e.g. SY_MIN_101) to a canonical key (e.g. SY_MIN)."""
    for key in TABLE_PROP_MAP:
        # Match exact key or key followed by underscore + anything
        if var == key or re.match(rf"^{re.escape(key)}(_\w+)?$", var):
            return key
    return None


# ---------------------------------------------------------------------------
# Main public API
# ---------------------------------------------------------------------------

def parse_sdc_ic_repo(repo_path: str | Path) -> list[dict[str, Any]]:
    """Parse all material data from the SDC-IC Material Library APDL file.

    Parameters
    ----------
    repo_path:
        Path to the cloned SDC-IC Material Library repository root.

    Returns
    -------
    List of property record dicts compatible with the FusionMatDB schema spec.
    """
    repo = Path(repo_path)
    mac_file = repo / "SDC-IC_Mat_Lib.mac"
    if not mac_file.exists():
        raise FileNotFoundError(f"APDL macro not found at {mac_file}")

    text = mac_file.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()

    sections = _split_material_sections(lines)
    records: list[dict[str, Any]] = []

    for mat_idx, section_lines in sorted(sections.items()):
        mat_number = 100 + mat_idx  # index 1 → mat 101, etc.
        mat_name, mat_class = MATERIAL_MAP.get(mat_number, (f"Material_{mat_number}", "unknown"))

        # --- mpdata (temperature-dependent continuous properties) ---
        mp_data = _parse_mptemp_mpdata(section_lines)
        for prop_tag, pairs in mp_data.items():
            if prop_tag not in MPDATA_PROP_MAP:
                continue
            prop_name, _unit, scale = MPDATA_PROP_MAP[prop_tag]
            for temp_c, raw_val in pairs:
                records.append(
                    _make_record(
                        material_name=mat_name,
                        material_class=mat_class,
                        source_file=SOURCE_FILE,
                        test_temp_c=temp_c,
                        property_name=prop_name,
                        value=raw_val * scale,
                        irradiation_state="unirradiated",
                    )
                )

        # --- table properties (yield / UTS / allowable stress) ---
        tbl_data = _parse_table_props(section_lines, mat_number)
        for canonical_key, pairs in tbl_data.items():
            prop_name, scale = TABLE_PROP_MAP[canonical_key]
            irr_state = "irradiated" if canonical_key in IRRADIATED_PROPS else "unirradiated"
            for temp_c, raw_val in pairs:
                records.append(
                    _make_record(
                        material_name=mat_name,
                        material_class=mat_class,
                        source_file=SOURCE_FILE,
                        test_temp_c=temp_c,
                        property_name=prop_name,
                        value=raw_val * scale,
                        irradiation_state=irr_state,
                    )
                )

    return records


def _make_record(
    *,
    material_name: str,
    material_class: str,
    source_file: str,
    test_temp_c: float,
    property_name: str,
    value: float,
    irradiation_state: str,
) -> dict[str, Any]:
    return {
        "material_name": material_name,
        "material_class": material_class,
        "source_file": source_file,
        "test_temp_c": test_temp_c,
        "property_name": property_name,
        "value": value,
        "irradiation_state": irradiation_state,
        "confidence_score": 1.0,
        "extraction_method": "sdc_ic_parse",
    }
