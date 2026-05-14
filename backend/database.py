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


def _migrate_gasolina_precio_column(conn, dialect: str) -> None:
    from sqlalchemy import text

    if dialect == "postgresql":
        conn.execute(
            text(
                """
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'gasolina' AND column_name = 'precio_por_litro_oro'
  ) THEN
    ALTER TABLE gasolina RENAME COLUMN precio_por_litro_oro TO precio_por_litro_reales;
  ELSIF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'public' AND table_name = 'gasolina' AND column_name = 'precio_por_litro_reales'
  ) THEN
    ALTER TABLE gasolina ADD COLUMN precio_por_litro_reales DOUBLE PRECISION NOT NULL DEFAULT 20;
  END IF;
END $$;
"""
            )
        )
        return

    if dialect == "sqlite":
        result = conn.execute(text("PRAGMA table_info(gasolina)"))
        cols = {row[1] for row in result}
        if "precio_por_litro_reales" in cols:
            return
        if "precio_por_litro_oro" in cols:
            conn.execute(text("ALTER TABLE gasolina RENAME COLUMN precio_por_litro_oro TO precio_por_litro_reales"))
        else:
            conn.execute(
                text("ALTER TABLE gasolina ADD COLUMN precio_por_litro_reales REAL NOT NULL DEFAULT 20")
            )


def _ensure_gastos_table(conn, dialect: str) -> None:
    from sqlalchemy import text

    if dialect == "postgresql":
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS gastos_operativos (
    id SERIAL PRIMARY KEY,
    categoria VARCHAR(40) NOT NULL,
    descripcion TEXT NOT NULL,
    monto_reales DOUBLE PRECISION NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT NOW()
);
"""
            )
        )
        return

    if dialect == "sqlite":
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS gastos_operativos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    categoria VARCHAR(40) NOT NULL,
    descripcion TEXT NOT NULL,
    monto_reales REAL NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""
            )
        )


def _ensure_transacciones_table(conn, dialect: str) -> None:
    from sqlalchemy import text

    if dialect == "postgresql":
        stmts = [
            """
CREATE TABLE IF NOT EXISTS transacciones (
    id SERIAL PRIMARY KEY,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    tipo VARCHAR(30) NOT NULL,
    modulo_origen VARCHAR(30) NOT NULL,
    referencia_id INTEGER,
    moneda VARCHAR(10) NOT NULL,
    monto_reales DOUBLE PRECISION NOT NULL DEFAULT 0,
    gramos_oro DOUBLE PRECISION NOT NULL DEFAULT 0,
    tipo_oro VARCHAR(50),
    tasa_usada DOUBLE PRECISION,
    descripcion VARCHAR(255),
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
""",
            "CREATE INDEX IF NOT EXISTS ix_transacciones_tipo ON transacciones (tipo)",
            "CREATE INDEX IF NOT EXISTS ix_transacciones_modulo ON transacciones (modulo_origen)",
            "CREATE INDEX IF NOT EXISTS ix_transacciones_fecha ON transacciones (fecha)",
        ]
        for sql in stmts:
            conn.execute(text(sql))
        return

    if dialect == "sqlite":
        stmts = [
            """
CREATE TABLE IF NOT EXISTS transacciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uuid VARCHAR(36) NOT NULL UNIQUE,
    tipo VARCHAR(30) NOT NULL,
    modulo_origen VARCHAR(30) NOT NULL,
    referencia_id INTEGER,
    moneda VARCHAR(10) NOT NULL,
    monto_reales REAL NOT NULL DEFAULT 0,
    gramos_oro REAL NOT NULL DEFAULT 0,
    tipo_oro VARCHAR(50),
    tasa_usada REAL,
    descripcion VARCHAR(255),
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""",
            "CREATE INDEX IF NOT EXISTS ix_transacciones_tipo ON transacciones (tipo)",
            "CREATE INDEX IF NOT EXISTS ix_transacciones_modulo ON transacciones (modulo_origen)",
            "CREATE INDEX IF NOT EXISTS ix_transacciones_fecha ON transacciones (fecha)",
        ]
        for sql in stmts:
            conn.execute(text(sql))


def apply_schema_patches() -> None:
    """Migraciones ligeras tras create_all (columnas/tablas que faltan en bases ya existentes)."""
    from sqlalchemy import inspect, text

    dialect = engine.dialect.name

    if dialect == "postgresql":
        insp = inspect(engine)
        with engine.begin() as conn:
            _migrate_gasolina_precio_column(conn, dialect)
            _ensure_gastos_table(conn, dialect)
            if insp.has_table("ventas_gasolina"):
                alters = [
                    "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS tipo_oro VARCHAR(50)",
                    "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS unidad_precio_venta VARCHAR(20) DEFAULT 'reales_litro'",
                    "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS precio_litro_venta FLOAT DEFAULT 0",
                ]
                for sql in alters:
                    conn.execute(text(sql))
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
            conn.execute(text(create_reposiciones))
            _ensure_transacciones_table(conn, dialect)
        return

    if dialect == "sqlite":
        insp = inspect(engine)
        with engine.begin() as conn:
            if insp.has_table("gasolina"):
                _migrate_gasolina_precio_column(conn, dialect)
            _ensure_gastos_table(conn, dialect)
            if insp.has_table("ventas_gasolina"):
                result = conn.execute(text("PRAGMA table_info(ventas_gasolina)"))
                existing = {row[1] for row in result}
                stmts: list[str] = []
                if "tipo_oro" not in existing:
                    stmts.append("ALTER TABLE ventas_gasolina ADD COLUMN tipo_oro VARCHAR(50)")
                if "unidad_precio_venta" not in existing:
                    stmts.append(
                        "ALTER TABLE ventas_gasolina ADD COLUMN unidad_precio_venta VARCHAR(20) DEFAULT 'reales_litro'"
                    )
                if "precio_litro_venta" not in existing:
                    stmts.append("ALTER TABLE ventas_gasolina ADD COLUMN precio_litro_venta REAL DEFAULT 0")
                for sql in stmts:
                    conn.execute(text(sql))
            _ensure_transacciones_table(conn, dialect)
        return
