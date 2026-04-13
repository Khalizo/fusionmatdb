# fusionmatdb/fusionmatdb/extraction/prompts.py

EXTRACTION_SYSTEM_PROMPT = """You are a fusion materials science data extraction specialist.
Extract irradiation effects data from fusion materials research text or images.
Return ONLY a JSON array. Each element is one (material, irradiation condition, property measurement) triple.
If no irradiation or materials data is present, return an empty array [].
"""

# Shared field definitions used by both text and vision prompts
_FIELDS = """
MATERIAL IDENTIFICATION:
- material_name: string (e.g. "W", "EUROFER97", "V-4Cr-4Ti", "Al2O3", "Cu-Fe nanolaminate")
- material_class: one of [tungsten, tungsten_alloy, RAFM_steel, ODS_steel, SiC_composite,
    vanadium_alloy, copper_alloy, nanolaminate, ceramic_insulator, HTS_tape, beryllium, other]
- layer_spacing_nm: number or null  (nano-laminates only — e.g. Cu-Fe bilayer thickness)
- layer_material_a: string or null  (e.g. "Cu")
- layer_material_b: string or null  (e.g. "Fe", "Nb")
- grain_size_um: number or null

IRRADIATION CONDITIONS:
- irradiation_state: "irradiated" or "unirradiated"
- reactor: string or null  (e.g. "HFIR", "BOR-60", "ATR", "ion_beam")
- particle: "neutron", "proton", or "ion" or null
- dose_dpa: number or null
- dose_dpa_uncertainty: number or null
- irradiation_temp_c: number or null  (°C)
- helium_appm: number or null
- hydrogen_appm: number or null
- neutron_spectrum: "DT_fusion", "fission", "fast", "mixed" or null
- test_temp_c: number or null  (°C)

MECHANICAL PROPERTIES (all in standard units, before and after irradiation where available):
- yield_strength_mpa_unirradiated: number or null
- yield_strength_mpa_irradiated: number or null
- yield_strength_mpa_std: number or null  (measurement uncertainty ±)
- uts_mpa_unirradiated: number or null
- uts_mpa_irradiated: number or null
- elongation_pct_unirradiated: number or null
- elongation_pct_irradiated: number or null
- fracture_toughness_mpa_sqrt_m: number or null
- dbtt_k_unirradiated: number or null
- dbtt_k_irradiated: number or null
- dbtt_k_std: number or null
- hardness_value: number or null
- hardness_type: string or null  (e.g. "HV", "HV10", "nanoindentation")
- hardness_std: number or null
- charpy_energy_j: number or null
- flexural_strength_mpa_unirradiated: number or null   (ceramics — 3-point bending)
- flexural_strength_mpa_irradiated: number or null
- compressive_strength_mpa: number or null
- fatigue_cycles_to_failure: number or null            (pulsed machines — millions of cycles)
- fatigue_stress_amplitude_mpa: number or null
- creep_rate_per_s: number or null
- creep_strain_pct: number or null

ELECTRICAL / DIELECTRIC (critical for Helion magnets and ceramic insulators):
- electrical_resistivity_uohm_cm_unirradiated: number or null
- electrical_resistivity_uohm_cm_irradiated: number or null
- electrical_resistivity_pct_change: number or null     (% increase after irradiation)
- electrical_conductivity_iacs_pct: number or null      (% IACS — nano-laminates)
- dielectric_breakdown_kv_per_mm_unirradiated: number or null
- dielectric_breakdown_kv_per_mm_irradiated: number or null
- dielectric_breakdown_pct_change: number or null       (% degradation after irradiation)
- critical_current_density_irradiated: number or null   (HTS tapes — A/m²)

THERMAL:
- thermal_conductivity_unirradiated: number or null     (W/m·K)
- thermal_conductivity_irradiated: number or null

RADIATION MICROSTRUCTURE (feeds atomistic simulations):
- volumetric_swelling_pct: number or null
- void_density_per_m3: number or null
- void_diameter_nm: number or null
- dislocation_loop_density_per_m3: number or null
- dislocation_loop_diameter_nm: number or null

METADATA:
- source: "table", "figure", or "text"
- experiment_type: one of [Mechanical Tensile, Mechanical Creep, Mechanical Charpy,
    Mechanical Hardness, Mechanical Fracture, Mechanical Fatigue, Dielectric, Electrical,
    Thermal, Microstructure, Swelling] or null
"""

EXTRACTION_USER_TEMPLATE = """Extract all irradiation effects data from this text.
Return a JSON array where each object has these fields (use null for missing values):
{fields}

TEXT:
{{text}}
""".format(fields=_FIELDS)

# Vision prompt for PDF page images — used with Gemini on Vertex AI
VISION_EXTRACTION_PROMPT = """You are analyzing a page from a fusion materials research document (ORNL semiannual report or journal paper).

Extract ALL numerical data about material properties and irradiation effects. Return a JSON array where each object has these fields (null for missing):
{fields}

Important:
- Extract data from BOTH tables and figures (read axis labels and data points carefully)
- Include uncertainty values (± numbers) where shown
- For nano-laminates, capture layer spacing if mentioned
- For ceramic insulators, prioritise dielectric breakdown and flexural strength
- For electrical data, note if value is resistivity (uOhm.cm) or conductivity (% IACS or S/m)
- Return ONLY the JSON array, no other text
""".format(fields=_FIELDS)
