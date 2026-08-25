import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401 — registers ORM models on Base.metadata
from app.config import settings
from app.db import Base, get_db
from app.main import app as fastapi_app

_base_url, _, _ = settings.database_url.rpartition("/")
TEST_DATABASE_URL = f"{_base_url}/ap2_test"


@pytest.fixture(scope="session")
def engine():
    admin_engine = create_engine(f"{_base_url}/postgres", isolation_level="AUTOCOMMIT")
    with admin_engine.connect() as conn:
        exists = conn.execute(
            text("SELECT 1 FROM pg_database WHERE datname = 'ap2_test'")
        ).scalar()
        if not exists:
            conn.execute(text("CREATE DATABASE ap2_test"))
    admin_engine.dispose()

    eng = create_engine(TEST_DATABASE_URL)
    with eng.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
        conn.commit()
    Base.metadata.create_all(eng)

    yield eng

    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def db_session(engine):
    """Each test runs inside a transaction that's rolled back afterward —
    tests never leave state behind or touch the dev database."""
    connection = engine.connect()
    trans = connection.begin()
    session = sessionmaker(bind=connection)()

    yield session

    session.close()
    trans.rollback()
    connection.close()


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    fastapi_app.dependency_overrides[get_db] = override_get_db
    yield TestClient(fastapi_app)
    fastapi_app.dependency_overrides.clear()
