from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

engine: Engine | None = None
SessionLocal: sessionmaker | None = None


def init_db(app) -> None:
    global engine, SessionLocal

    database_url = app.config.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is missing from application configuration.")

    engine_kwargs: dict = {
        "future": True,
        "pool_pre_ping": True,
    }

    if database_url.startswith("sqlite"):
        engine_kwargs["connect_args"] = {"check_same_thread": False}

    engine = create_engine(database_url, **engine_kwargs)
    SessionLocal = sessionmaker(
        bind=engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def get_engine() -> Engine:
    if engine is None:
        raise RuntimeError("Database engine is not initialized. Call init_db(app) first.")
    return engine


def get_session_factory() -> sessionmaker:
    if SessionLocal is None:
        raise RuntimeError("SessionLocal is not initialized. Call init_db(app) first.")
    return SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def test_db_connection() -> None:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
        conn.commit()


def create_all_tables() -> None:
    from app.db.base import Base

    Base.metadata.create_all(bind=get_engine())


def dispose_engine() -> None:
    global engine, SessionLocal
    if engine is not None:
        engine.dispose()
    engine = None
    SessionLocal = None
