from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session, sessionmaker

from packages.retrieval.vector_db import postgres_urls


def sqlalchemy_database_url() -> str:
    sync_url, _ = postgres_urls()
    return sync_url.render_as_string(hide_password=False)


def create_database_engine(url: str | URL | None = None) -> Engine:
    database_url = str(url) if url is not None else sqlalchemy_database_url()
    engine = create_engine(database_url, future=True)
    if database_url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:
    del connection_record
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    return sessionmaker(
        bind=engine or create_database_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        future=True,
    )


def get_session_factory() -> sessionmaker[Session]:
    return create_session_factory()


@contextmanager
def session_scope(session_factory: sessionmaker[Session] | None = None) -> Iterator[Session]:
    session_factory = session_factory or get_session_factory()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
