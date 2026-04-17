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
- For EVERY datapoint, record which table or figure it came from in source_reference
- Note the institution/lab that performed the experiment in source_institution
- If the paper cites data from another publication rather than reporting original measurements, set data_origin to "cited_from_other_work"
- Extract upper/lower bounds when shown as error bars, ranges (e.g. "350-400 MPa"), or ± notation
- Record number of specimens (n) when stated (e.g. "n=3", "average of 5 specimens")
- Include experimental method details when given (specimen geometry, test standard, loading rate)
- Return ONLY the JSON array, no other text
""".format(fields=_FIELDS)


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
