import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from fusionmatdb.storage.schema import (
    Base, Paper, Material, IrradiationCondition, MechanicalProperty, ReviewQueueItem,
)
from fusionmatdb.qa.review_queue import flag_for_review, get_pending_reviews, resolve_review


@pytest.fixture
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        paper = Paper(id="test-001", title="Test", year=2023, access_type="ornl_report")
        mat = Material(paper_id="test-001", name="W", class_="tungsten")
        session.add_all([paper, mat])
        session.flush()
        irr = IrradiationCondition(paper_id="test-001", material_id=mat.id)
        session.add(irr)
        session.flush()
        prop = MechanicalProperty(
            paper_id="test-001", material_id=mat.id, irradiation_id=irr.id,
            confidence_score=0.8, extraction_method="gemini_vision",
        )
        session.add(prop)
        session.flush()
        yield session, prop


def test_flag_for_review_creates_item(db_session):
    session, prop = db_session
    item = flag_for_review(
        session, "test-001", 42, "degraded_page", "Faded scan",
        mechanical_property_id=prop.id,
    )
    session.flush()
    assert item.id is not None
    assert item.review_status == "pending"


def test_get_pending_reviews(db_session):
    session, prop = db_session
    flag_for_review(session, "test-001", 42, "degraded_page", "Faded")
    flag_for_review(session, "test-001", 43, "physics_check_anomaly", "Yield too high")
    session.flush()
    pending = get_pending_reviews(session)
    assert len(pending) == 2


def test_resolve_review(db_session):
    session, prop = db_session
    item = flag_for_review(session, "test-001", 42, "degraded_page", "Faded")
    session.flush()
    resolved = resolve_review(session, item.id, "approved", "reviewer1", "Looks fine")
    assert resolved.review_status == "approved"
    assert resolved.reviewer == "reviewer1"
    assert resolved.reviewed_at is not None


def test_get_pending_reviews_filters_by_paper(db_session):
    session, prop = db_session
    flag_for_review(session, "test-001", 42, "degraded_page", "Faded")
    session.flush()
    assert len(get_pending_reviews(session, paper_id="test-001")) == 1
    assert len(get_pending_reviews(session, paper_id="other")) == 0
