"""SQLAlchemy ORM schema for fusionmatdb."""

from __future__ import annotations

from typing import List, Optional

from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Paper(Base):
    __tablename__ = "papers"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    journal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array string
    abstract: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text_available: Mapped[bool] = mapped_column(Boolean, default=False)
    access_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    doi: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)

    materials: Mapped[List["Material"]] = relationship(
        "Material", back_populates="paper", cascade="all, delete-orphan"
    )
    irradiation_conditions: Mapped[List["IrradiationCondition"]] = relationship(
        "IrradiationCondition", back_populates="paper", cascade="all, delete-orphan"
    )
    mechanical_properties: Mapped[List["MechanicalProperty"]] = relationship(
        "MechanicalProperty", back_populates="paper", cascade="all, delete-orphan"
    )


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id"), nullable=False)
    matdb4fusion_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    class_: Mapped[Optional[str]] = mapped_column("class", String, nullable=True)

    # Element weight percentages
    W: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Cr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    V: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Ta: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Ti: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Fe: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    C: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Mn: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Mo: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Ni: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Si: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    Al: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Processing
    manufacturer_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    product_shape: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    temper_temp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    crystal_structure: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Microstructure (critical for radiation response prediction)
    grain_size_um: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    prior_cold_work_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Nano-laminate specific (Helion Cu-Fe / Cu-Nb magnets)
    layer_material_a: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # e.g. "Cu"
    layer_material_b: Mapped[Optional[str]] = mapped_column(String, nullable=True)   # e.g. "Fe", "Nb"
    layer_spacing_nm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # bilayer thickness

    paper: Mapped["Paper"] = relationship("Paper", back_populates="materials")
    irradiation_conditions: Mapped[List["IrradiationCondition"]] = relationship(
        "IrradiationCondition", back_populates="material"
    )
    mechanical_properties: Mapped[List["MechanicalProperty"]] = relationship(
        "MechanicalProperty", back_populates="material"
    )


class IrradiationCondition(Base):
    __tablename__ = "irradiation_conditions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id"), nullable=False)

    irradiation_state: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    reactor: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    medium: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    particle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    irradiation_temp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dose_dpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dose_dpa_uncertainty: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thermal_fluence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fast_fluence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    helium_appm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hydrogen_appm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    neutron_spectrum: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    paper: Mapped["Paper"] = relationship("Paper", back_populates="irradiation_conditions")
    material: Mapped["Material"] = relationship("Material", back_populates="irradiation_conditions")
    mechanical_properties: Mapped[List["MechanicalProperty"]] = relationship(
        "MechanicalProperty", back_populates="irradiation_condition"
    )


class MechanicalProperty(Base):
    __tablename__ = "mechanical_properties"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    paper_id: Mapped[str] = mapped_column(String, ForeignKey("papers.id"), nullable=False)
    material_id: Mapped[int] = mapped_column(Integer, ForeignKey("materials.id"), nullable=False)
    irradiation_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("irradiation_conditions.id"), nullable=True
    )

    matdb4fusion_entry_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    experiment_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    method: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    test_temp: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Tensile properties
    yield_strength_mpa_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    yield_strength_mpa_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uts_mpa_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uts_mpa_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elongation_pct_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    elongation_pct_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Fracture properties
    fracture_toughness_mpa_sqrt_m: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dbtt_k_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dbtt_k_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Charpy
    kv_joules: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Hardness
    hardness_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hardness_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Thermal / electrical
    thermal_conductivity_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    thermal_conductivity_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    electrical_resistivity_uohm_cm_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    electrical_resistivity_uohm_cm_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    electrical_resistivity_pct_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    electrical_conductivity_iacs_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # % IACS (nano-laminates)
    critical_current_density_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Dielectric (Helion ceramic insulators: Al2O3, MgAl2O4, AlN, SiC, BN, ZrO2)
    dielectric_breakdown_kv_per_mm_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dielectric_breakdown_kv_per_mm_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dielectric_breakdown_pct_change: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flexural_strength_mpa_unirradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    flexural_strength_mpa_irradiated: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    compressive_strength_mpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Volumetric / dimensional
    volumetric_swelling_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Creep (already extracted by Gemini — 126 points in Report 70 alone)
    creep_rate_per_s: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    creep_strain_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Fatigue (pulsed fusion machines — Helion millions of cycles)
    fatigue_cycles_to_failure: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fatigue_stress_amplitude_mpa: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    fatigue_strain_amplitude_pct: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Radiation microstructure (feeds FusionUQ cascade simulations)
    void_density_per_m3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    void_diameter_nm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dislocation_loop_density_per_m3: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dislocation_loop_diameter_nm: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    frenkel_pair_production_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Measurement uncertainty (essential for GP/Bayesian ML)
    yield_strength_mpa_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    uts_mpa_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    hardness_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dbtt_k_std: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ML metadata
    extraction_method: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    raw_extraction_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    reviewed_by_human: Mapped[bool] = mapped_column(Boolean, default=False)

    paper: Mapped["Paper"] = relationship("Paper", back_populates="mechanical_properties")
    material: Mapped["Material"] = relationship("Material", back_populates="mechanical_properties")
    irradiation_condition: Mapped[Optional["IrradiationCondition"]] = relationship(
        "IrradiationCondition", back_populates="mechanical_properties"
    )
