"""Human review queue — flag records for manual inspection."""
from __future__ import annotations

from sqlalchemy.orm import Session

from fusionmatdb.storage.schema import ReviewQueueItem


def flag_for_review(
    session: Session,
    paper_id: str,
    page_number: int,
    flag_reason: str,
    flag_detail: str,
    extraction_path: str = "first_pass",
    mechanical_property_id: int | None = None,
) -> ReviewQueueItem:
    """Add a record to the human review queue."""
    item = ReviewQueueItem(
        paper_id=paper_id,
        page_number=page_number,
        mechanical_property_id=mechanical_property_id,
        flag_reason=flag_reason,
        flag_detail=flag_detail,
        extraction_path=extraction_path,
        review_status="pending",
    )
    session.add(item)
    return item


def get_pending_reviews(session: Session, paper_id: str | None = None) -> list[ReviewQueueItem]:
    """Get all pending review queue items, optionally filtered by paper."""
    query = session.query(ReviewQueueItem).filter_by(review_status="pending")
    if paper_id:
        query = query.filter_by(paper_id=paper_id)
    return query.all()


def resolve_review(
    session: Session,
    review_id: int,
    status: str,
    reviewer: str,
    notes: str | None = None,
) -> ReviewQueueItem:
    """Mark a review queue item as resolved."""
    item = session.query(ReviewQueueItem).get(review_id)
    if item is None:
        raise ValueError(f"Review queue item {review_id} not found")
    item.review_status = status
    item.reviewer = reviewer
    item.reviewer_notes = notes
    from datetime import datetime, timezone
    item.reviewed_at = datetime.now(timezone.utc).isoformat()
    return item
