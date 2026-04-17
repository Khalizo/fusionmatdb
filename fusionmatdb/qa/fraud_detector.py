"""Fraud and anomaly detection — visual duplicate figures and suspicious data matches."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import MechanicalProperty


@dataclass
class VisualDuplicate:
    paper_id_a: str
    page_a: int
    paper_id_b: str
    page_b: int
    hamming_distance: int
    hash_a: str
    hash_b: str


@dataclass
class SuspiciousMatch:
    record_id_a: int
    record_id_b: int
    matching_fields: list[str] = field(default_factory=list)
    differing_fields: list[str] = field(default_factory=list)


NUMERIC_COMPARE_FIELDS = [
    "yield_strength_mpa_irradiated", "yield_strength_mpa_unirradiated",
    "uts_mpa_irradiated", "uts_mpa_unirradiated",
    "elongation_pct_irradiated", "elongation_pct_unirradiated",
    "hardness_value", "fracture_toughness_mpa_sqrt_m",
    "dbtt_k_irradiated", "volumetric_swelling_pct",
]

CONDITION_FIELDS = ["dose_dpa", "irradiation_temp", "test_temp", "reactor"]


def compute_image_hash(image_bytes: bytes) -> str:
    """Compute perceptual hash of a page image. Requires imagehash + Pillow."""
    try:
        import imagehash
        from PIL import Image
        import io
        img = Image.open(io.BytesIO(image_bytes))
        return str(imagehash.phash(img))
    except ImportError:
        import hashlib
        return hashlib.md5(image_bytes).hexdigest()


def find_visual_duplicates(
    pdf_dir: str | Path, threshold: int = 5
) -> list[VisualDuplicate]:
    """Compare pHash across all extracted page images, flag near-duplicates."""
    import fitz
    pdf_dir = Path(pdf_dir)
    page_hashes: list[tuple[str, int, str]] = []  # (paper_id, page_num, hash)

    for pdf_path in sorted(pdf_dir.glob("ornl_report_*.pdf")):
        report_num = pdf_path.stem.replace("ornl_report_", "")
        paper_id = f"ornl_{report_num}"
        doc = fitz.open(str(pdf_path))
        for i in range(len(doc)):
            page = doc[i]
            pix = page.get_pixmap(matrix=fitz.Matrix(72/72, 72/72))
            img_bytes = pix.tobytes("png")
            h = compute_image_hash(img_bytes)
            page_hashes.append((paper_id, i + 1, h))
        doc.close()

    duplicates = []
    try:
        import imagehash
        for i in range(len(page_hashes)):
            for j in range(i + 1, len(page_hashes)):
                pid_a, pg_a, h_a = page_hashes[i]
                pid_b, pg_b, h_b = page_hashes[j]
                if pid_a == pid_b:
                    continue  # Only cross-report duplicates
                ha = imagehash.hex_to_hash(h_a)
                hb = imagehash.hex_to_hash(h_b)
                dist = ha - hb
                if dist <= threshold:
                    duplicates.append(VisualDuplicate(
                        paper_id_a=pid_a, page_a=pg_a,
                        paper_id_b=pid_b, page_b=pg_b,
                        hamming_distance=dist, hash_a=h_a, hash_b=h_b,
                    ))
    except ImportError:
        pass  # Fall back: no visual duplicate detection without imagehash

    return duplicates


def find_suspicious_data_matches(
    session: Session, min_matching_fields: int = 5
) -> list[SuspiciousMatch]:
    """Flag records from different papers with identical numeric values but different conditions."""
    props = session.query(MechanicalProperty).all()
    matches = []

    for i in range(len(props)):
        for j in range(i + 1, len(props)):
            a, b = props[i], props[j]
            if a.paper_id == b.paper_id:
                continue

            matching = []
            for f in NUMERIC_COMPARE_FIELDS:
                va = getattr(a, f, None)
                vb = getattr(b, f, None)
                if va is not None and vb is not None and va == vb:
                    matching.append(f)

            if len(matching) >= min_matching_fields:
                differing = []
                irr_a = a.irradiation_condition
                irr_b = b.irradiation_condition
                if irr_a and irr_b:
                    for f in CONDITION_FIELDS:
                        va = getattr(irr_a, f, None)
                        vb = getattr(irr_b, f, None)
                        if va != vb:
                            differing.append(f)

                if differing:
                    matches.append(SuspiciousMatch(
                        record_id_a=a.id, record_id_b=b.id,
                        matching_fields=matching, differing_fields=differing,
                    ))

    return matches
