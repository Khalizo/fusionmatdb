# fusionmatdb/fusionmatdb/cli.py
"""FusionMatDB CLI — build, stats, export."""
import json
import os
from pathlib import Path
import click


# ---------------------------------------------------------------------------
# Field maps: Gemini output keys → schema column names
# ---------------------------------------------------------------------------

FIELD_MAP = {
    # Tensile
    "yield_strength_mpa_unirradiated": "yield_strength_mpa_unirradiated",
    "yield_strength_mpa_irradiated": "yield_strength_mpa_irradiated",
    "yield_strength_mpa_std": "yield_strength_mpa_std",
    "uts_mpa_unirradiated": "uts_mpa_unirradiated",
    "uts_mpa_irradiated": "uts_mpa_irradiated",
    "elongation_pct_unirradiated": "elongation_pct_unirradiated",
    "elongation_pct_irradiated": "elongation_pct_irradiated",
    # Fracture
    "fracture_toughness_mpa_sqrt_m": "fracture_toughness_mpa_sqrt_m",
    "dbtt_k_unirradiated": "dbtt_k_unirradiated",
    "dbtt_k_irradiated": "dbtt_k_irradiated",
    "dbtt_k_std": "dbtt_k_std",
    # Hardness
    "hardness_value": "hardness_value",
    "hardness_std": "hardness_std",
    # Charpy
    "charpy_energy_j": "kv_joules",
    # Electrical
    "electrical_resistivity_uohm_cm_unirradiated": "electrical_resistivity_uohm_cm_unirradiated",
    "electrical_resistivity_uohm_cm_irradiated": "electrical_resistivity_uohm_cm_irradiated",
    "electrical_resistivity_pct_change": "electrical_resistivity_pct_change",
    "electrical_conductivity_iacs_pct": "electrical_conductivity_iacs_pct",
    # Dielectric
    "dielectric_breakdown_kv_per_mm_unirradiated": "dielectric_breakdown_kv_per_mm_unirradiated",
    "dielectric_breakdown_kv_per_mm_irradiated": "dielectric_breakdown_kv_per_mm_irradiated",
    "dielectric_breakdown_pct_change": "dielectric_breakdown_pct_change",
    "flexural_strength_mpa_unirradiated": "flexural_strength_mpa_unirradiated",
    "flexural_strength_mpa_irradiated": "flexural_strength_mpa_irradiated",
    # Creep / fatigue
    "creep_rate_per_s": "creep_rate_per_s",
    "creep_strain_pct": "creep_strain_pct",
    "fatigue_cycles_to_failure": "fatigue_cycles_to_failure",
    "fatigue_stress_amplitude_mpa": "fatigue_stress_amplitude_mpa",
    # Thermal
    "thermal_conductivity_unirradiated": "thermal_conductivity_unirradiated",
    "thermal_conductivity_irradiated": "thermal_conductivity_irradiated",
    # Microstructure
    "volumetric_swelling_pct": "volumetric_swelling_pct",
    "void_density_per_m3": "void_density_per_m3",
    "void_diameter_nm": "void_diameter_nm",
    "dislocation_loop_density_per_m3": "dislocation_loop_density_per_m3",
    "dislocation_loop_diameter_nm": "dislocation_loop_diameter_nm",
    # Uncertainty bounds
    "yield_strength_mpa_irradiated_lower": "yield_strength_mpa_irradiated_lower",
    "yield_strength_mpa_irradiated_upper": "yield_strength_mpa_irradiated_upper",
    "uts_mpa_irradiated_lower": "uts_mpa_irradiated_lower",
    "uts_mpa_irradiated_upper": "uts_mpa_irradiated_upper",
    "hardness_lower": "hardness_lower",
    "hardness_upper": "hardness_upper",
    "dbtt_k_irradiated_lower": "dbtt_k_irradiated_lower",
    "dbtt_k_irradiated_upper": "dbtt_k_irradiated_upper",
    # Statistical metadata
    "n_specimens": "n_specimens",
}

MATERIAL_FIELD_MAP = {
    "grain_size_um": "grain_size_um",
    "layer_material_a": "layer_material_a",
    "layer_material_b": "layer_material_b",
    "layer_spacing_nm": "layer_spacing_nm",
}


# ---------------------------------------------------------------------------
# Helper: store extracted records into the DB
# ---------------------------------------------------------------------------

def _store_records(session, paper_id: str, records: list[dict], min_confidence: float) -> int:
    """Persist extracted records to the DB.

    Returns the number of MechanicalProperty rows inserted.
    """
    from fusionmatdb.storage.schema import Material, IrradiationCondition, MechanicalProperty
    from fusionmatdb.normalisation.material_normaliser import normalise_material_name, normalise_material_class

    # Caches keyed within this PDF to avoid duplicate INSERT queries
    mat_cache: dict[tuple, int] = {}      # (paper_id, name) → material.id
    irr_cache: dict[tuple, int] = {}      # (material_id, dose, temp, reactor, particle) → irr.id

    stored = 0
    for rec in records:
        if rec.get("confidence_score", 0) < min_confidence:
            continue

        # --- Material dedup ---
        mat_name = normalise_material_name(rec.get("material_name"))
        if not mat_name:
            continue  # skip — name too ambiguous
        mat_class = normalise_material_class(rec.get("material_class"), mat_name)

        mat_key = (paper_id, mat_name)
        if mat_key in mat_cache:
            material_id = mat_cache[mat_key]
        else:
            # Check DB first (in case of re-run)
            existing_mat = (
                session.query(Material)
                .filter_by(paper_id=paper_id, name=mat_name)
                .first()
            )
            if existing_mat:
                material_id = existing_mat.id
            else:
                mat_kwargs = dict(paper_id=paper_id, name=mat_name, class_=mat_class)
                for src_field, col in MATERIAL_FIELD_MAP.items():
                    val = rec.get(src_field)
                    if val is not None:
                        mat_kwargs[col] = val
                mat_obj = Material(**mat_kwargs)
                session.add(mat_obj)
                session.flush()  # populate mat_obj.id
                material_id = mat_obj.id
            mat_cache[mat_key] = material_id

        # --- IrradiationCondition dedup ---
        dose = rec.get("dose_dpa")
        irr_temp = rec.get("irradiation_temp_c")
        reactor = rec.get("reactor") or None
        particle = rec.get("particle") or None

        irr_key = (material_id, dose, irr_temp, reactor, particle)
        if irr_key in irr_cache:
            irr_id = irr_cache[irr_key]
        else:
            existing_irr = (
                session.query(IrradiationCondition)
                .filter_by(
                    paper_id=paper_id,
                    material_id=material_id,
                    dose_dpa=dose,
                    irradiation_temp=irr_temp,
                    reactor=reactor,
                    particle=particle,
                )
                .first()
            )
            if existing_irr:
                irr_id = existing_irr.id
            else:
                irr_obj = IrradiationCondition(
                    paper_id=paper_id,
                    material_id=material_id,
                    dose_dpa=dose,
                    irradiation_temp=irr_temp,
                    reactor=reactor,
                    particle=particle,
                    irradiation_state=rec.get("irradiation_state") or None,
                    medium=rec.get("medium") or None,
                    helium_appm=rec.get("helium_appm") or None,
                    hydrogen_appm=rec.get("hydrogen_appm") or None,
                    dose_dpa_lower=rec.get("dose_dpa_lower"),
                    dose_dpa_upper=rec.get("dose_dpa_upper"),
                    irradiation_temp_lower=rec.get("irradiation_temp_lower"),
                    irradiation_temp_upper=rec.get("irradiation_temp_upper"),
                )
                session.add(irr_obj)
                session.flush()
                irr_id = irr_obj.id
            irr_cache[irr_key] = irr_id

        # --- MechanicalProperty ---
        prop_kwargs: dict = dict(
            paper_id=paper_id,
            material_id=material_id,
            irradiation_id=irr_id,
            experiment_type=rec.get("experiment_type"),
            method=rec.get("method") or None,
            test_temp=rec.get("test_temp_c"),
            confidence_score=rec.get("confidence_score", min_confidence),
            extraction_method=rec.get("extraction_method", "gemini_vision"),
            raw_extraction_json=json.dumps(rec),
            distribution_type=rec.get("distribution_type") or None,
            n_specimens=rec.get("n_specimens"),
            extraction_pass=rec.get("extraction_pass", "first_pass"),
            cross_page_context_used=rec.get("cross_page_context_used", False),
        )
        for src_field, col in FIELD_MAP.items():
            val = rec.get(src_field)
            if val is not None:
                prop_kwargs[col] = val

        prop = MechanicalProperty(**prop_kwargs)
        session.add(prop)
        stored += 1

    return stored


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """FusionMatDB — fusion irradiation materials database."""


@cli.command()
@click.option("--pdf-dir", default="data/ornl_pdfs", help="Directory for ORNL PDFs")
@click.option("--db", default="fusionmatdb.sqlite", help="SQLite database path")
@click.option("--max-reports", default=80, help="Max ORNL report numbers to try")
@click.option(
    "--extractor",
    type=click.Choice(["vision", "text"]),
    default="vision",
    help="vision=Gemini on Vertex AI (reads figures); text=Claude API (text only)",
)
@click.option("--min-confidence", default=0.5, type=float, help="Minimum confidence score to store")
def build(pdf_dir, db, max_reports, extractor, min_confidence):
    """Download ORNL reports and extract data into the database."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.discovery.ornl_reports import ORNLDownloader
    from fusionmatdb.storage.schema import Paper

    click.echo("=== FusionMatDB Build ===")
    click.echo(f"  Extractor: {extractor}  |  min-confidence: {min_confidence}")
    init_db(db)

    # ------------------------------------------------------------------
    # Step 1: Download ORNL PDFs
    # ------------------------------------------------------------------
    click.echo(f"\n[1/3] Downloading ORNL reports → {pdf_dir}")
    downloader = ORNLDownloader(output_dir=pdf_dir, max_report=max_reports)
    results = downloader.download_all(delay=1.5)
    pdfs = [
        Path(r["path"])
        for r in results
        if r["status"] in ("downloaded", "skipped") and "path" in r
    ]
    click.echo(f"  {len(pdfs)} PDFs available for processing")

    # ------------------------------------------------------------------
    # Step 2: Build extractor
    # ------------------------------------------------------------------
    click.echo(f"\n[2/3] Extracting data with {'Gemini Vision (Vertex AI)' if extractor == 'vision' else 'Claude API (text)'}...")

    if extractor == "vision":
        from fusionmatdb.access.vision_extractor import VertexVisionExtractor
        ext = VertexVisionExtractor()
    else:
        from fusionmatdb.extraction.llm_extractor import LLMExtractor
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        ext = LLMExtractor(api_key=api_key)

    session = get_session()
    total_extracted = 0
    total_stored = 0

    # ------------------------------------------------------------------
    # Step 3: Process each PDF
    # ------------------------------------------------------------------
    for pdf_path in pdfs:
        report_num = pdf_path.stem.replace("ornl_report_", "").replace("ornl_", "")
        paper_id = f"ornl_{report_num}"

        existing = session.get(Paper, paper_id)
        if existing and existing.full_text_available:
            continue

        paper = Paper(
            id=paper_id,
            title=f"ORNL Fusion Materials Semiannual Progress Report {report_num}",
            access_type="ornl_report",
            source_url=(
                f"https://fmp.ornl.gov/semiannual-progress-reports/"
                f"fusion-materials-semiannual-progress-report-{report_num}.pdf"
            ),
            full_text_available=True,
        )
        if existing:
            session.delete(existing)
            session.flush()
        session.add(paper)
        session.flush()

        try:
            if extractor == "vision":
                records = ext.extract_pdf(str(pdf_path), paper_id=paper_id)
            else:
                from fusionmatdb.access.text_extractor import extract_with_pdfplumber
                text = extract_with_pdfplumber(pdf_path)
                records = ext.extract(text, paper_id=paper_id)
        except Exception as e:
            click.echo(f"  [{pdf_path.name}] ERROR (extraction): {e}")
            session.commit()
            continue

        n_extracted = len(records)
        total_extracted += n_extracted

        try:
            n_stored = _store_records(session, paper_id, records, min_confidence)
            session.commit()
        except Exception as e:
            session.rollback()
            click.echo(f"  [{pdf_path.name}] ERROR (storage): {e}")
            continue

        total_stored += n_stored
        click.echo(f"  [{pdf_path.name}]: {n_extracted} records extracted, {n_stored} stored")

    click.echo(
        f"\n[3/3] Build complete. "
        f"Total extracted: {total_extracted}, stored: {total_stored}"
    )


@cli.command()
@click.option("--db", default="fusionmatdb.sqlite")
def stats(db):
    """Show database statistics."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.storage.schema import Paper, MechanicalProperty
    init_db(db)
    session = get_session()
    n_papers = session.query(Paper).count()
    n_props = session.query(MechanicalProperty).count()
    high_conf = session.query(MechanicalProperty).filter(
        MechanicalProperty.confidence_score >= 0.7
    ).count()
    click.echo(f"Papers indexed:         {n_papers}")
    click.echo(f"Total data points:      {n_props}")
    click.echo(f"High confidence (>=0.7): {high_conf}")


@cli.command()
@click.option("--db", default="fusionmatdb.sqlite")
@click.option("--format", "fmt", type=click.Choice(["parquet", "world_model"]), default="parquet")
@click.option("--output", "-o", default="fusionmatdb_export")
@click.option("--min-trust", type=int, default=None, help="Minimum trust score (0-100)")
def export(db, fmt, output, min_trust):
    """Export database to ML training formats."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.storage.exporter import export_parquet, export_world_model
    init_db(db)
    session = get_session()
    if fmt == "parquet":
        path = f"{output}.parquet"
        n = export_parquet(session, path, min_trust=min_trust)
        click.echo(f"Exported {n} records to {path}")
    elif fmt == "world_model":
        path = f"{output}_world_model.json"
        n = export_world_model(session, path)
        click.echo(f"Exported {n} world model examples to {path}")


@cli.command("qa-report")
@click.option("--db", default="fusionmatdb.sqlite")
def qa_report_cmd(db):
    """Print QA summary report."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.qa.qa_report import generate_qa_report
    init_db(db)
    session = get_session()
    report = generate_qa_report(session)
    click.echo(f"Total records:            {report.total_records}")
    click.echo(f"High confidence (>=0.7):  {report.high_confidence_count} ({report.high_confidence_pct:.1f}%)")
    click.echo(f"Cross-field flags:        {report.cross_field_flag_count}")
    click.echo(f"Avg completeness:         {report.completeness_avg:.2f}")
    click.echo(f"Records with uncertainty:  {report.records_with_uncertainty}")
    click.echo(f"Records with traceability: {report.records_with_traceability}")


@cli.command("dedup-scan")
@click.option("--db", default="fusionmatdb.sqlite")
def dedup_scan_cmd(db):
    """Scan for duplicate records."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.qa.dedup_detector import find_exact_duplicates
    init_db(db)
    session = get_session()
    clusters = find_exact_duplicates(session)
    if not clusters:
        click.echo("No exact duplicates found.")
        return
    click.echo(f"Found {len(clusters)} duplicate clusters:")
    for c in clusters[:10]:
        click.echo(f"  Hash: {c.content_hash[:12]}... IDs: {c.record_ids} (primary: {c.primary_id})")
    if len(clusters) > 10:
        click.echo(f"  ... and {len(clusters) - 10} more")


@cli.command("validate")
@click.option("--db", default="fusionmatdb.sqlite")
@click.option("--strict", is_flag=True, help="Fail on any cross-field flag")
def validate_cmd(db, strict):
    """Run enhanced validation on all records."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.storage.schema import MechanicalProperty
    from fusionmatdb.extraction.validator import validate_extraction, cross_field_checks
    init_db(db)
    session = get_session()
    props = session.query(MechanicalProperty).all()
    total_flags = 0
    for prop in props:
        record = {
            "material_name": prop.material.name if prop.material else None,
            "yield_strength_mpa_irradiated": prop.yield_strength_mpa_irradiated,
            "yield_strength_mpa_unirradiated": prop.yield_strength_mpa_unirradiated,
            "elongation_pct_irradiated": prop.elongation_pct_irradiated,
            "elongation_pct_unirradiated": prop.elongation_pct_unirradiated,
            "irradiation_state": prop.irradiation_condition.irradiation_state if prop.irradiation_condition else None,
            "dose_dpa": prop.irradiation_condition.dose_dpa if prop.irradiation_condition else None,
        }
        flags = cross_field_checks(record)
        if flags:
            total_flags += 1
            if strict:
                for f in flags:
                    click.echo(f"  [ID {prop.id}] {f}")
    click.echo(f"\nValidation complete: {total_flags} records flagged out of {len(props)}")


@cli.command("ingest-sdc-ic")
@click.option("--repo-path", required=True, help="Path to cloned SDC-IC Material Library repo")
@click.option("--db", default="fusionmatdb.sqlite", help="SQLite database path")
def ingest_sdc_ic(repo_path, db):
    """Ingest ITER SDC-IC Material Library (human-curated, confidence=1.0).

    Parse temperature-dependent material property curves from the ANSYS APDL
    macro file and store them in the FusionMatDB database.

    Example::

        git clone --depth=1 https://github.com/Structural-Mechanics/SDC-IC-Material-Library.git /tmp/sdc_ic
        fusionmatdb ingest-sdc-ic --repo-path /tmp/sdc_ic --db fusionmatdb.sqlite
    """
    import json
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.storage.schema import Paper, Material, IrradiationCondition, MechanicalProperty
    from fusionmatdb.ingestion.sdc_ic import parse_sdc_ic_repo

    click.echo("=== SDC-IC Material Library Ingestion ===")
    click.echo(f"  Repo:     {repo_path}")
    click.echo(f"  Database: {db}")

    init_db(db)
    session = get_session()

    # Parse APDL file
    click.echo("\n[1/3] Parsing APDL macro file...")
    try:
        records = parse_sdc_ic_repo(repo_path)
    except FileNotFoundError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo(f"  Parsed {len(records)} property data points across 16 materials")

    # Ensure a Paper entry exists for this source
    paper_id = "sdc_ic_material_library"
    existing_paper = session.get(Paper, paper_id)
    if not existing_paper:
        paper = Paper(
            id=paper_id,
            title="SDC-IC Material Library — ITER Structural Design Criteria for In-vessel Components, Appendix A",
            access_type="sdc_ic",
            source_url="https://github.com/Structural-Mechanics/SDC-IC-Material-Library",
            full_text_available=True,
        )
        session.add(paper)
        session.flush()
    click.echo(f"\n[2/3] Upserting paper record: {paper_id}")

    # Property name → MechanicalProperty column mapping (SDC-IC specific)
    SDC_FIELD_MAP: dict[str, str] = {
        "yield_strength_min_mpa":     "yield_strength_mpa_unirradiated",
        "yield_strength_avg_mpa":     "yield_strength_mpa_unirradiated",
        "uts_min_mpa":                "uts_mpa_unirradiated",
        "uts_avg_mpa":                "uts_mpa_unirradiated",
        "yield_strength_irr_min_mpa": "yield_strength_mpa_irradiated",
        "yield_strength_irr_avg_mpa": "yield_strength_mpa_irradiated",
        "uts_irr_min_mpa":            "uts_mpa_irradiated",
        "uts_irr_avg_mpa":            "uts_mpa_irradiated",
        "thermal_conductivity_w_mk":  "thermal_conductivity_unirradiated",
    }

    # Store records
    click.echo("\n[3/3] Storing records...")
    mat_cache: dict[str, int] = {}    # mat_name → material.id
    irr_cache: dict[tuple, int] = {}  # (mat_id, irr_state) → irradiation_condition.id
    stored = 0

    for rec in records:
        mat_name = rec["material_name"]
        mat_class = rec["material_class"]

        # --- Material dedup ---
        if mat_name not in mat_cache:
            existing_mat = (
                session.query(Material)
                .filter_by(paper_id=paper_id, name=mat_name)
                .first()
            )
            if existing_mat:
                mat_id = existing_mat.id
            else:
                mat_obj = Material(paper_id=paper_id, name=mat_name, class_=mat_class)
                session.add(mat_obj)
                session.flush()
                mat_id = mat_obj.id
            mat_cache[mat_name] = mat_id
        mat_id = mat_cache[mat_name]

        # --- IrradiationCondition dedup ---
        irr_state = rec["irradiation_state"]
        irr_key = (mat_id, irr_state)
        if irr_key not in irr_cache:
            existing_irr = (
                session.query(IrradiationCondition)
                .filter_by(paper_id=paper_id, material_id=mat_id, irradiation_state=irr_state)
                .first()
            )
            if existing_irr:
                irr_id = existing_irr.id
            else:
                irr_obj = IrradiationCondition(
                    paper_id=paper_id,
                    material_id=mat_id,
                    irradiation_state=irr_state,
                )
                session.add(irr_obj)
                session.flush()
                irr_id = irr_obj.id
            irr_cache[irr_key] = irr_id
        irr_id = irr_cache[irr_key]

        # --- MechanicalProperty ---
        prop_kwargs: dict = dict(
            paper_id=paper_id,
            material_id=mat_id,
            irradiation_id=irr_id,
            experiment_type="design_curve",
            test_temp=rec["test_temp_c"],
            confidence_score=rec["confidence_score"],
            extraction_method=rec["extraction_method"],
            raw_extraction_json=json.dumps(rec),
        )

        col = SDC_FIELD_MAP.get(rec["property_name"])
        if col:
            prop_kwargs[col] = rec["value"]

        prop = MechanicalProperty(**prop_kwargs)
        session.add(prop)
        stored += 1

    try:
        session.commit()
    except Exception as exc:
        session.rollback()
        raise click.ClickException(f"Database commit failed: {exc}") from exc

    click.echo(f"\nIngestion complete.")
    click.echo(f"  Records stored:  {stored}")
    click.echo(f"  Materials:       {len(mat_cache)}")


@cli.command("lineage")
@click.argument("record_id", type=int)
@click.option("--db", default="fusionmatdb.sqlite")
def lineage_cmd(record_id, db):
    """Show full provenance lineage for a record."""
    from fusionmatdb.storage.database import init_db, get_session
    from fusionmatdb.trust.lineage import get_lineage
    init_db(db)
    session = get_session()
    try:
        l = get_lineage(session, record_id)
    except ValueError as e:
        raise click.ClickException(str(e))
    click.echo(f"Record ID:       {l.record_id}")
    click.echo(f"Paper:           {l.paper_title}")
    click.echo(f"DOI:             {l.paper_doi or 'N/A'}")
    click.echo(f"Source PDF:      {l.source_pdf_url or 'N/A'}")
    click.echo(f"Page:            {l.source_page_number or 'N/A'}")
    click.echo(f"Figure/Table:    {l.source_figure_or_table or 'N/A'}")
    click.echo(f"Institution:     {l.source_institution or 'N/A'}")
    click.echo(f"Quality:         {l.quality_level or 'N/A'}")
    click.echo(f"Confidence:      {l.confidence_score or 'N/A'}")
    click.echo(f"Trust Score:     {l.trust_score}/100")
    click.echo(f"Extraction:      {l.extraction_method} ({l.extraction_pass})")
    click.echo(f"Cross-page:      {l.cross_page_context_used}")
    click.echo(f"Content Hash:    {l.content_hash or 'N/A'}")
    click.echo(f"Primary:         {l.is_primary}")
    click.echo(f"Duplicate Group: {l.duplicate_cluster_id or 'N/A'}")


def main():
    cli()


@cli.command("ingest-matdb4fusion")
@click.argument("csv_path")
@click.option("--db", default="fusionmatdb.sqlite", help="SQLite database path")
def ingest_matdb4fusion_cmd(csv_path, db):
    """Ingest MatDB4Fusion CSV export (unirradiated baseline, confidence=1.0).

    CSV_PATH is the path to the CSV exported from https://matdb4fusion.app.

    MatDB4Fusion (KIT/Philipp Lied) contains human-curated unirradiated
    baseline mechanical property data for EUROFER97, W, and W K-doped.
    All records are ingested with confidence=1.0 and reviewed_by_human=True.
    """
    from fusionmatdb.ingestion.matdb4fusion import ingest_matdb4fusion_csv
    from fusionmatdb.storage.database import get_session, init_db

    click.echo("=== MatDB4Fusion Ingest ===")
    click.echo(f"  CSV:      {csv_path}")
    click.echo(f"  Database: {db}")

    init_db(db)
    session = get_session()

    try:
        n = ingest_matdb4fusion_csv(csv_path, session)
        session.commit()
        click.echo(
            f"  Ingested: {n} records "
            f"(confidence=1.0, reviewed_by_human=True)"
        )
    except Exception as exc:
        session.rollback()
        raise click.ClickException(str(exc)) from exc
    finally:
        session.close()
