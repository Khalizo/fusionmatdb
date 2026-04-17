"""Backfill data quality assessments, provenance, and dedup clusters.

Run standalone or import individual functions into a migration script.
"""
from __future__ import annotations

import json
import logging

from sqlalchemy.orm import Session

from fusionmatdb.qa.dedup_detector import compute_content_hash, find_exact_duplicates
from fusionmatdb.storage.schema import MechanicalProperty, Paper

logger = logging.getLogger(__name__)


def backfill_quality_assessments(session: Session) -> int:
    """Tag every MechanicalProperty with quality metadata based on its source.

    ORNL records get quality_level="curated_database", source_institution="ORNL",
    source_pdf_url from Paper.source_url, and source_page_number extracted from
    raw_extraction_json "page" field.

    SDC-IC records get quality_level="curated_database", source_institution="ITER IO".

    Quality metadata is stored in the raw_extraction_json field as an enrichment
    (under the key "_quality").

    Returns the number of records updated.
    """
    props = session.query(MechanicalProperty).all()
    updated = 0

    # Pre-fetch papers for source_url lookup
    papers: dict[str, Paper] = {p.id: p for p in session.query(Paper).all()}

    for prop in props:
        raw = {}
        if prop.raw_extraction_json:
            try:
                raw = json.loads(prop.raw_extraction_json)
            except (json.JSONDecodeError, TypeError):
                raw = {}

        if "_quality" in raw:
            continue  # Already backfilled

        quality: dict = {}
        paper = papers.get(prop.paper_id)

        if prop.paper_id.startswith("ornl_"):
            quality["quality_level"] = "curated_database"
            quality["source_institution"] = "ORNL"
            if paper and paper.source_url:
                quality["source_pdf_url"] = paper.source_url
            page = raw.get("page")
            if page is not None:
                quality["source_page_number"] = page
        elif prop.paper_id == "sdc_ic_material_library":
            quality["quality_level"] = "curated_database"
            quality["source_institution"] = "ITER IO"
        else:
            quality["quality_level"] = "unknown"

        raw["_quality"] = quality
        prop.raw_extraction_json = json.dumps(raw)
        updated += 1

    if updated:
        session.flush()
    logger.info("backfill_quality_assessments: updated %d records", updated)
    return updated


def backfill_provenance(session: Session) -> int:
    """Compute and store content_hash for every MechanicalProperty record.

    Provenance metadata is stored in raw_extraction_json under "_provenance"
    with keys: content_hash, root_origin (paper_id), is_primary (True).

    Returns the number of records updated.
    """
    props = session.query(MechanicalProperty).all()
    updated = 0

    for prop in props:
        raw = {}
        if prop.raw_extraction_json:
            try:
                raw = json.loads(prop.raw_extraction_json)
            except (json.JSONDecodeError, TypeError):
                raw = {}

        if "_provenance" in raw:
            continue

        content_hash = compute_content_hash(prop)
        raw["_provenance"] = {
            "content_hash": content_hash,
            "root_origin": prop.paper_id,
            "is_primary": True,
        }
        prop.raw_extraction_json = json.dumps(raw)
        updated += 1

    if updated:
        session.flush()
    logger.info("backfill_provenance: updated %d records", updated)
    return updated


def backfill_dedup_clusters(session: Session) -> int:
    """Assign duplicate_cluster_id to records that share identical content hashes.

    Cluster IDs are stored in raw_extraction_json under "_dedup".

    Returns the number of duplicate clusters found.
    """
    clusters = find_exact_duplicates(session)

    # Map record id -> cluster label
    record_cluster: dict[int, str] = {}
    for cluster_idx, (hash_val, ids) in enumerate(clusters.items()):
        cluster_label = f"dup_{cluster_idx:04d}"
        for rid in ids:
            record_cluster[rid] = cluster_label

    if not record_cluster:
        logger.info("backfill_dedup_clusters: no duplicates found")
        return 0

    props = session.query(MechanicalProperty).filter(
        MechanicalProperty.id.in_(list(record_cluster.keys()))
    ).all()

    for prop in props:
        raw = {}
        if prop.raw_extraction_json:
            try:
                raw = json.loads(prop.raw_extraction_json)
            except (json.JSONDecodeError, TypeError):
                raw = {}
        raw["_dedup"] = {"duplicate_cluster_id": record_cluster[prop.id]}
        prop.raw_extraction_json = json.dumps(raw)

    session.flush()
    logger.info("backfill_dedup_clusters: found %d clusters", len(clusters))
    return len(clusters)
