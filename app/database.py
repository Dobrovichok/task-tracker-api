from collections.abc import Iterator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import DatabaseSettings


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    engine = create_engine(DatabaseSettings().url, pool_pre_ping=True)
    return sessionmaker(engine, expire_on_commit=False)


def get_db() -> Iterator[Session]:
    with get_session_factory()() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db)]
