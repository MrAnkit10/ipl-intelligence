"""PostgreSQL connection helper (blueprint section 31)."""

import os
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import Engine, create_engine

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

DEFAULT_DATABASE_URL = "postgresql+psycopg2://localhost:5432/ipl_intelligence"


def get_engine(database_url: str | None = None) -> Engine:
    url = database_url or os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    return create_engine(url)
