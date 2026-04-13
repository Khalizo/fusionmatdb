"""
Normalise material names from Gemini extraction to canonical database names.

Gemini sometimes returns ambiguous names like "steel", "alloy", "WHA", "723"
that need mapping to the canonical forms used consistently in the database.
"""
from __future__ import annotations
import re

# Canonical name lookup: lowercased partial match → canonical name
# Order matters: more specific patterns first
CANONICAL_LOOKUP: list[tuple[str, str]] = [
    # RAFM steels
    ("eurofer97",          "EUROFER97"),
    ("eurofer",            "EUROFER97"),
    ("f82h-ia",            "F82H-IEA"),
    ("f82h-iea",           "F82H-IEA"),
    ("f82h",               "F82H"),
    ("54fe",               "54Fe-F82H"),
    ("grade 91",           "Grade 91"),
    ("gr91",               "Grade 91"),
    ("9cr",                "9Cr steel"),
    ("t91",                "T91"),
    ("p91",                "P91"),
    ("hcm12a",             "HCM12A"),
    ("nf616",              "NF616"),
    ("rafm",               "RAFM steel"),
    # ODS steels
    ("ma957",              "MA957"),
    ("ma956",              "MA956"),
    ("pm2000",             "PM2000"),
    ("14ywtc",             "14YWT"),
    ("14ywt",              "14YWT"),
    ("ml20",               "ML20"),
    ("ods",                "ODS steel"),
    # Tungsten and alloys
    ("k-doped w-3%re",     "K-doped W-3%Re"),
    ("la-doped w-3%re",    "La-doped W-3%Re"),
    ("w-3%re",             "W-3%Re"),
    ("w-re",               "W-Re"),
    ("k-doped w",          "K-doped W"),
    ("la-doped w",         "La-doped W"),
    ("pure w",             "W"),
    ("tungsten single",    "W single crystal"),
    ("tungsten",           "W"),
    # Vanadium alloys
    ("v-4cr-4ti",          "V-4Cr-4Ti"),
    ("v-cr-ti",            "V-Cr-Ti"),
    ("vanadium",           "V alloy"),
    # SiC composites
    ("sic/sic",            "SiC/SiC"),
    ("sic composite",      "SiC/SiC"),
    ("sic",                "SiC"),
    # Cu alloys / nano-laminates
    ("cu-fe nanolaminate", "Cu-Fe nanolaminate"),
    ("cu-nb nanolaminate", "Cu-Nb nanolaminate"),
    ("cu-fe",              "Cu-Fe"),
    ("cucrzr",             "CuCrZr"),
    # Nickel alloys
    ("alloy 718",          "Alloy 718"),
    ("alloy 617",          "Alloy 617"),
    ("inconel 625",        "Inconel 625"),
    ("inconel 718",        "Alloy 718"),
    ("inconel",            "Inconel"),
    ("bam-11",             "BAM-11"),
    ("ni-w",               "Ni-W alloy"),
    ("pure nickel",        "Ni"),
    # Austenitic stainless steels
    ("316ln",              "316LN SS"),
    ("316l",               "316L SS"),
    ("316 stainless",      "316 SS"),
    ("316ss",              "316 SS"),
    ("316 ss",             "316 SS"),
    ("j316",               "316 SS"),
    ("jpca",               "JPCA"),
    ("pca",                "PCA"),
    ("304 stainless",      "304 SS"),
    ("304ss",              "304 SS"),
    ("type 316",           "316 SS"),
    ("e316",               "316 SS"),
    ("annealed 304",       "304 SS"),
    ("austenitic stainless", "austenitic SS"),
    # Fe-Cr and Fe-Cr-Ni model alloys
    ("fe-15cr-16ni",       "Fe-15Cr-16Ni"),
    ("fe-15cr-25ni",       "Fe-15Cr-25Ni"),
    ("fe-15cr-45ni",       "Fe-15Cr-45Ni"),
    ("fe-15cr-35ni",       "Fe-15Cr-35Ni"),
    ("fe-15cr-20ni",       "Fe-15Cr-20Ni"),
    ("fe-15cr",            "Fe-15Cr"),
    ("fe-18cr",            "Fe-18Cr"),
    ("fe-14cr",            "Fe-14Cr"),
    ("fe-12cr",            "Fe-12Cr"),
    ("fe-10cr",            "Fe-10Cr"),
    ("fe-6cr",             "Fe-6Cr"),
    ("fe-3cr",             "Fe-3Cr"),
    ("fe-cr",              "Fe-Cr"),
    ("alpha-fe",           "Fe"),
    # Refractory metals
    ("mo-41re",            "Mo-41Re"),
    ("mo-re",              "Mo-Re"),
    ("molybdenum",         "Mo"),
    ("nb-1zr",             "Nb-1Zr"),
    # Carbon materials
    ("h451",               "H451 graphite"),
    ("ig-110",             "IG-110 graphite"),
    ("graphite",           "graphite"),
    # MAX phase ceramics
    ("ti2alc",             "Ti2AlC"),
    ("ti3alc",             "Ti3AlC"),
    ("ti3sic",             "Ti3SiC2"),
    # Specific numbered alloys
    ("723",                "Alloy 723"),
    ("wha",                "W heavy alloy"),
    ("90w",                "W-NiFe WHA"),
    # Ceramics
    ("al2o3",              "Al2O3"),
    ("mgal2o4",            "MgAl2O4"),
    ("aln",                "AlN"),
    ("si3n4",              "Si3N4"),
    ("bn",                 "BN"),
    ("zro2",               "ZrO2"),
    ("beo",                "BeO"),
]

# Names to reject outright (too ambiguous to be useful)
REJECT_PATTERNS = {
    "none", "unspecified", "unspecified_material", "material", "alloy",
    "steel", "metal", "sample", "specimen", "unknown", "not specified",
    "generic", "fusion", "reactor", "fe", "iron",  # too generic without qualifier
    "various", "several", "all materials", "multiple",
}


def normalise_material_name(raw: str | None) -> str | None:
    """Map raw Gemini extraction name to canonical form.

    Returns None if the name is too ambiguous to be useful.
    Returns the canonical name if a match is found.
    Returns the cleaned raw name if no match but name is acceptable.
    """
    if not raw or not isinstance(raw, str):
        return None

    cleaned = raw.strip()
    if len(cleaned) < 2:
        return None

    lower = cleaned.lower()

    # Reject ambiguous names
    if lower in REJECT_PATTERNS:
        return None
    # Reject names that are just numbers or single characters
    if re.match(r'^\d+$', cleaned):
        return None
    # Reject very long names that are likely sentences not material names
    if len(cleaned) > 60:
        return None

    # Try canonical lookup (most specific first)
    for pattern, canonical in CANONICAL_LOOKUP:
        if pattern in lower:
            return canonical

    # Return cleaned original if nothing matched but it's plausible
    return cleaned


def normalise_material_class(raw: str | None, material_name: str | None = None) -> str | None:
    """Infer or validate material class from name and raw class."""
    valid_classes = {
        "tungsten", "tungsten_alloy", "RAFM_steel", "ODS_steel",
        "SiC_composite", "vanadium_alloy", "copper_alloy", "nanolaminate",
        "ceramic_insulator", "HTS_tape", "beryllium", "other",
        # Extended classes added for 'other' reclassification:
        "austenitic_steel",      # 316 SS, 304 SS, JPCA, PCA, Fe-Cr-Ni model alloys
        "ferritic_model_alloy",  # Fe-xCr binary/ternary model alloys, alpha-Fe
        "nickel_alloy",          # Ni, Inconel, BAM-11, Ni-W
        "refractory_metal",      # Mo, Mo-Re, Cr, Nb alloys (not W — separate)
        "carbon_graphite",       # Graphite varieties, H451, IG-110
        "max_phase",             # Ti2AlC, Ti3SiC2 etc.
    }

    # If Gemini gave a valid class, trust it
    if raw and raw in valid_classes:
        return raw

    # Infer from canonical name
    if not material_name:
        return raw if raw in valid_classes else "other"

    name_lower = material_name.lower()

    # RAFM steels
    if any(x in name_lower for x in ["eurofer", "f82h", "grade 91", "t91", "p91", "rafm",
                                       "9cr steel", "hcm12a", "nf616", "ht-9", "ht9",
                                       "12cr-1movw", "12cr-2w", "jlf", "ep-450", "ep-823"]):
        return "RAFM_steel"
    # ODS steels
    if any(x in name_lower for x in ["ma957", "ma956", "pm2000", "14ywt", "ml20", "ods"]):
        return "ODS_steel"
    # Austenitic stainless steels
    if any(x in name_lower for x in ["316", "304", "jpca", "jpca", "pca", "austenitic ss",
                                       "316ln", "316l", "e316", "316ss", "j316",
                                       "austenitic stainless"]):
        return "austenitic_steel"
    # Fe-Cr model alloys (binary and ternary without Ni)
    if any(x in name_lower for x in ["fe-3cr", "fe-6cr", "fe-10cr", "fe-12cr", "fe-14cr",
                                       "fe-15cr", "fe-18cr", "alpha-fe", "fe-cr"]) and \
       "ni" not in name_lower:
        return "ferritic_model_alloy"
    # Fe-Cr-Ni model alloys → austenitic
    if "fe-15cr" in name_lower and "ni" in name_lower:
        return "austenitic_steel"
    # SiC composites
    if any(x in name_lower for x in ["sic/sic", "sic composite"]):
        return "SiC_composite"
    # Vanadium alloys
    if "v-4cr" in name_lower or "v-cr" in name_lower or "v-ti" in name_lower:
        return "vanadium_alloy"
    # Nano-laminates
    if "nanolaminate" in name_lower:
        return "nanolaminate"
    # Ceramic insulators
    if any(x in name_lower for x in ["al2o3", "mgal2o4", "aln", "si3n4", "bn", "zro2",
                                       "beo", "ceramic"]):
        return "ceramic_insulator"
    # SiC (not composite — standalone ceramic)
    if name_lower in ["sic"] or name_lower.startswith("sic "):
        return "ceramic_insulator"
    # Copper alloys
    if any(x in name_lower for x in ["cucrzr", "cu-fe", "cu-nb", "glidcop", "marz copper",
                                       "ofhc", "copper"]):
        return "copper_alloy"
    # Pure tungsten
    if name_lower in ["w", "w single crystal", "k-doped w", "la-doped w", "pure w"]:
        return "tungsten"
    # Tungsten alloys
    if any(x in name_lower for x in ["w-re", "w-3%re", "w alloy", "wha", "w heavy",
                                       "k-doped w", "la-doped w"]):
        return "tungsten_alloy"
    # Nickel alloys
    if any(x in name_lower for x in ["inconel", "bam-11", "ni-w", "pure nickel",
                                       "alloy 718", "alloy 617"]) or \
       name_lower in ["ni", "nickel"]:
        return "nickel_alloy"
    # Refractory metals (non-W)
    if any(x in name_lower for x in ["mo-re", "mo-41re", "molybdenum", "nb-1zr"]) or \
       name_lower in ["mo", "cr", "nb"]:
        return "refractory_metal"
    # Carbon / graphite
    if any(x in name_lower for x in ["graphite", "h451", "ig-110", "carbon"]):
        return "carbon_graphite"
    # MAX phase
    if any(x in name_lower for x in ["ti2alc", "ti3alc", "ti3sic", "max phase"]):
        return "max_phase"
    # Beryllium
    if any(x in name_lower for x in ["beryllium", "beo"]) or name_lower == "be":
        return "beryllium"
    # Nickel — catch high-purity and processing variants
    if name_lower.startswith("nickel") or "% nickel" in name_lower or \
       name_lower.startswith("ni ") or name_lower == "ni":
        return "nickel_alloy"
    # Titanium alloys
    if any(x in name_lower for x in ["ti-6al", "ti-6-4", "titanium", "tial"]):
        return "titanium_alloy"
    # Zirconium alloys
    if any(x in name_lower for x in ["zircaloy", "zirconium", "zr-"]):
        return "zirconium_alloy"
    # Fe-Mn and other Fe-X model alloys
    if re.match(r'^fe-\d', name_lower):
        return "ferritic_model_alloy"

    return raw if (raw and raw in valid_classes) else "other"
