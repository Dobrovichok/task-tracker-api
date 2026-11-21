from pathlib import Path
from secrets import token_urlsafe
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.schema import CreateSchema, DropSchema

from app.config import DatabaseSettings, get_auth_settings
from app.database import get_db
from app.main import app


@pytest.fixture(scope="session")
def postgres_engine():
    engine = create_engine(DatabaseSettings().url)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def sessions(postgres_engine):
    schema = f"task_tracker_test_{uuid4().hex}"
    with postgres_engine.begin() as connection:
        connection.execute(CreateSchema(schema))

    engine = create_engine(postgres_engine.url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        config = Config(Path(__file__).resolve().parents[1] / "alembic.ini")
        with engine.begin() as connection:
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
        yield sessionmaker(engine, expire_on_commit=False)
    finally:
        engine.dispose()
        with postgres_engine.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))


@pytest.fixture
def client(sessions, monkeypatch):
    def isolated_db():
        with sessions() as session:
            yield session

    monkeypatch.setenv("JWT_SECRET", token_urlsafe(48))
    monkeypatch.setenv("ACCESS_TOKEN_MINUTES", "30")
    monkeypatch.setitem(app.dependency_overrides, get_db, isolated_db)
    get_auth_settings.cache_clear()
    try:
        with TestClient(app) as test_client:
            yield test_client
    finally:
        get_auth_settings.cache_clear()
