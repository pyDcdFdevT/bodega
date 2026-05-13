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


def apply_schema_patches() -> None:
    """Agrega columnas nuevas en SQLite sin migraciones Alembic."""
    if engine.dialect.name != "sqlite":
        return
    from sqlalchemy import inspect, text

    insp = inspect(engine)
    if not insp.has_table("ventas_gasolina"):
        return
    existing = {c["name"] for c in insp.get_columns("ventas_gasolina")}
    stmts: list[str] = []
    if "tipo_oro" not in existing:
        stmts.append("ALTER TABLE ventas_gasolina ADD COLUMN tipo_oro VARCHAR(50)")
    if "unidad_precio_venta" not in existing:
        stmts.append("ALTER TABLE ventas_gasolina ADD COLUMN unidad_precio_venta VARCHAR(20) DEFAULT 'oro_litro'")
    if "precio_litro_venta" not in existing:
        stmts.append("ALTER TABLE ventas_gasolina ADD COLUMN precio_litro_venta REAL DEFAULT 0")
    if not stmts:
        return
    with engine.begin() as conn:
        for sql in stmts:
            conn.execute(text(sql))
