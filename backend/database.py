from __future__ import annotations

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

USE_POSTGRES = os.getenv("USE_POSTGRES", "false").lower() == "true"

if USE_POSTGRES:
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        raise ValueError("DATABASE_URL no configurada")
    engine = create_engine(DATABASE_URL, future=True)
else:
    from pathlib import Path
    BASE_DIR = Path(__file__).resolve().parent.parent
    DATA_DIR = BASE_DIR / "data"
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    SQLALCHEMY_DATABASE_URL = f"sqlite:///{DATA_DIR / 'bodega.db'}"
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        future=True,
    )

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    expire_on_commit=False,
)

class Base(DeclarativeBase):
    pass

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
