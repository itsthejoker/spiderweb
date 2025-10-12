from __future__ import annotations

from pathlib import Path
from typing import Union

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session as SASession
from sqlalchemy.pool import NullPool

# Base class for SQLAlchemy models used internally by Spiderweb
Base = declarative_base()

# Type alias for sessions
DBSession = SASession


def create_sqlite_engine(db_path: Union[str, Path]) -> Engine:
    """Create a SQLite engine from a file path.

    Use NullPool so that connections are not held open between tests.
    This avoids ResourceWarning about unclosed sqlite3 connections under coverage.
    """
    path = Path(db_path)
    # Ensure directory exists
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
    return create_engine(
        f"sqlite:///{path}",
        future=True,
        poolclass=NullPool,
    )


def create_session_factory(engine: Engine):
    """Return a configured sessionmaker bound to the given engine."""
    return sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
