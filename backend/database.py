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
    """Migraciones ligeras tras create_all (columnas/tablas que faltan en bases ya existentes)."""
    from sqlalchemy import inspect, text

    dialect = engine.dialect.name

    if dialect == "postgresql":
        insp = inspect(engine)
        if not insp.has_table("ventas_gasolina"):
            return
        alters = [
            "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS tipo_oro VARCHAR(50)",
            "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS unidad_precio_venta VARCHAR(20) DEFAULT 'oro_litro'",
            "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS precio_litro_venta FLOAT DEFAULT 0",
        ]
        create_reposiciones = """
CREATE TABLE IF NOT EXISTS gasolina_reposiciones (
    id SERIAL PRIMARY KEY,
    gasolina_id INTEGER REFERENCES gasolina(id),
    litros FLOAT NOT NULL DEFAULT 0,
    precio_reales_litro FLOAT NOT NULL DEFAULT 0,
    total_reales FLOAT NOT NULL DEFAULT 0,
    total_oro FLOAT NOT NULL DEFAULT 0,
    tasa_cambio_id INTEGER REFERENCES tasas_cambio(id),
    fecha TIMESTAMP DEFAULT NOW()
);
"""
        with engine.begin() as conn:
            for sql in alters:
                conn.execute(text(sql))
            conn.execute(text(create_reposiciones))
        return

    if dialect == "sqlite":
        insp = inspect(engine)
        if not insp.has_table("ventas_gasolina"):
            return
        with engine.begin() as conn:
            result = conn.execute(text("PRAGMA table_info(ventas_gasolina)"))
            existing = {row[1] for row in result}
            stmts: list[str] = []
            if "tipo_oro" not in existing:
                stmts.append("ALTER TABLE ventas_gasolina ADD COLUMN tipo_oro VARCHAR(50)")
            if "unidad_precio_venta" not in existing:
                stmts.append(
                    "ALTER TABLE ventas_gasolina ADD COLUMN unidad_precio_venta VARCHAR(20) DEFAULT 'oro_litro'"
                )
            if "precio_litro_venta" not in existing:
                stmts.append("ALTER TABLE ventas_gasolina ADD COLUMN precio_litro_venta REAL DEFAULT 0")
            for sql in stmts:
                conn.execute(text(sql))
        return
