import pytest
from fusionmatdb.storage.database import init_db, get_session
from fusionmatdb.storage.schema import Paper


def test_get_session_before_init_raises():
    """get_session() must raise RuntimeError if init_db() not called first."""
    import fusionmatdb.storage.database as db_module
    # Reset module state
    db_module._engine = None
    db_module._SessionLocal = None
    with pytest.raises(RuntimeError, match="Call init_db()"):
        db_module.get_session()


def test_init_db_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.sqlite")
    init_db(db_path)
    session = get_session()
    # Should be able to add a paper
    paper = Paper(id="db-test-1", title="DB test", access_type="ornl_report")
    session.add(paper)
    session.commit()
    result = session.get(Paper, "db-test-1")
    assert result is not None
    session.close()
