from collections.abc import AsyncGenerator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

database_url = settings.resolved_database_url
connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
engine = create_engine(database_url, connect_args=connect_args, echo=False, future=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False, class_=Session)


async def get_session() -> AsyncGenerator[Session, None]:
    with SessionLocal() as session:
        yield session
