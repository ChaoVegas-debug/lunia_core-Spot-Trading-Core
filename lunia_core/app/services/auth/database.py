from __future__ import annotations

import os
from pathlib import Path
from typing import Callable

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

BASE_DIR = Path(__file__).resolve().parents[3]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_SQLITE_PATH = DATA_DIR / "lunia.db"
DATABASE_URL = os.getenv("DATABASE_URL") or f"sqlite:///{DEFAULT_SQLITE_PATH}"
DB_MODE = os.getenv("DB_MODE", "sqlite")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, echo=False, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


def get_session():
    return SessionLocal()


def init_db(create_func: Callable[[], None]) -> None:
    """Initialize database schema using provided creation function."""
    create_func()
