from sqlalchemy import inspect, text

from app.db.base import Base
from app.db.session import engine
from app.models import entities  # noqa: F401


def init_db() -> None:
    Base.metadata.create_all(bind=engine)
    _ensure_auth_columns()


def _ensure_auth_columns() -> None:
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return
    user_columns = {column["name"] for column in inspector.get_columns("users")}
    if "password_hash" in user_columns:
        return
    with engine.begin() as connection:
        connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
