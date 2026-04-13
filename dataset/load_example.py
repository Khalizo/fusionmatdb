"""
Load and explore FusionMatDB from HuggingFace.

Install: pip install datasets pandas
"""
from datasets import load_dataset
import pandas as pd

# Load from HuggingFace
ds = load_dataset("Khalizo/fusionmatdb")
train = ds["train"].to_pandas()

print(f"Training set: {len(train):,} records")
print(f"Columns: {len(train.columns)}")

# ── Example 1: GP training data for RAFM steels ──────────────────────────
rafm_gp = train[
    (train["material_class"] == "RAFM_steel") &
    train["yield_strength_mpa_irradiated"].notna() &
    train["dose_dpa"].notna() &
    train["irradiation_temp_C"].notna()
][["material_name", "dose_dpa", "irradiation_temp_C",
   "yield_strength_mpa_irradiated", "confidence_score"]]

print(f"\nRAFM steel GP training rows: {len(rafm_gp)}")
print(f"Dose range: {rafm_gp['dose_dpa'].min():.1f}–{rafm_gp['dose_dpa'].max():.1f} dpa")
print(rafm_gp.head())

# ── Example 2: World model pairs (irr + unirr in same row) ───────────────
paired = train[
    train["yield_strength_mpa_irradiated"].notna() &
    train["yield_strength_mpa_unirradiated"].notna()
].copy()
paired["delta_yield_MPa"] = (
    paired["yield_strength_mpa_irradiated"] - paired["yield_strength_mpa_unirradiated"]
)
print(f"\nPaired irr/unirr records: {len(paired)}")
print(f"Mean yield increase: {paired['delta_yield_MPa'].mean():.0f} MPa")

# ── Example 3: Filter to high-confidence ORNL-only records ───────────────
ornl_hq = train[
    (train["source"] == "gemini_vision") &
    (train["confidence_score"] >= 0.8) &
    (train["material_class"] != "other")
]
print(f"\nHigh-confidence ORNL records: {len(ornl_hq):,}")
print("Material class distribution:")
print(ornl_hq["material_class"].value_counts().head(8).to_string())
