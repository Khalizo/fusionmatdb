from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from fusionmatdb.storage.schema import Base

_engine = None
_SessionLocal = None


def init_db(db_path: str = "fusionmatdb.sqlite") -> None:
    global _engine, _SessionLocal
    _engine = create_engine(f"sqlite:///{db_path}", echo=False)
    Base.metadata.create_all(_engine)
    _SessionLocal = sessionmaker(bind=_engine)


def get_session() -> Session:
    if _SessionLocal is None:
        raise RuntimeError("Call init_db() first")
    return _SessionLocal()
