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


def _ensure_aperturas_caja_table(conn, dialect: str) -> None:
    from sqlalchemy import text

    if dialect == "postgresql":
        for stmt in (
            """
CREATE TABLE IF NOT EXISTS aperturas_caja (
    id SERIAL PRIMARY KEY,
    fecha_operativa DATE NOT NULL UNIQUE,
    caja_inicial_reales DOUBLE PRECISION NOT NULL,
    oro_operativo_inicial DOUBLE PRECISION NOT NULL DEFAULT 0,
    abierto_por VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
""",
            "CREATE INDEX IF NOT EXISTS ix_aperturas_caja_fecha ON aperturas_caja (fecha_operativa)",
        ):
            conn.execute(text(stmt.strip()))
        return

    if dialect == "sqlite":
        for stmt in (
            """
CREATE TABLE IF NOT EXISTS aperturas_caja (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_operativa DATE NOT NULL UNIQUE,
    caja_inicial_reales REAL NOT NULL,
    oro_operativo_inicial REAL NOT NULL DEFAULT 0,
    abierto_por VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""",
            "CREATE INDEX IF NOT EXISTS ix_aperturas_caja_fecha ON aperturas_caja (fecha_operativa)",
        ):
            conn.execute(text(stmt.strip()))


def _ensure_cierres_diarios_table(conn, dialect: str) -> None:
    from sqlalchemy import text

    ddl_pg = """
CREATE TABLE IF NOT EXISTS cierres_diarios (
    id SERIAL PRIMARY KEY,
    fecha_operativa DATE NOT NULL UNIQUE,
    ventas_reales DOUBLE PRECISION NOT NULL,
    ventas_oro DOUBLE PRECISION NOT NULL,
    compras_reales DOUBLE PRECISION NOT NULL,
    gastos_reales DOUBLE PRECISION NOT NULL,
    oro_recolectado DOUBLE PRECISION NOT NULL,
    reales_esperados DOUBLE PRECISION NOT NULL,
    oro_esperado DOUBLE PRECISION NOT NULL,
    reales_contados DOUBLE PRECISION NOT NULL,
    oro_contado DOUBLE PRECISION NOT NULL,
    diferencia_reales DOUBLE PRECISION NOT NULL,
    diferencia_oro DOUBLE PRECISION NOT NULL,
    justificacion TEXT NOT NULL DEFAULT '',
    retiro_dueno_reales DOUBLE PRECISION NOT NULL DEFAULT 0,
    retiro_dueno_oro DOUBLE PRECISION NOT NULL DEFAULT 0,
    se_deja_reales DOUBLE PRECISION NOT NULL DEFAULT 0,
    se_deja_oro DOUBLE PRECISION NOT NULL DEFAULT 0,
    cerrado_por VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    snapshot_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_cierres_diarios_fecha_op ON cierres_diarios (fecha_operativa);
"""

    ddl_sqlite = """
CREATE TABLE IF NOT EXISTS cierres_diarios (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_operativa DATE NOT NULL UNIQUE,
    ventas_reales REAL NOT NULL,
    ventas_oro REAL NOT NULL,
    compras_reales REAL NOT NULL,
    gastos_reales REAL NOT NULL,
    oro_recolectado REAL NOT NULL,
    reales_esperados REAL NOT NULL,
    oro_esperado REAL NOT NULL,
    reales_contados REAL NOT NULL,
    oro_contado REAL NOT NULL,
    diferencia_reales REAL NOT NULL,
    diferencia_oro REAL NOT NULL,
    justificacion TEXT NOT NULL DEFAULT '',
    retiro_dueno_reales REAL NOT NULL DEFAULT 0,
    retiro_dueno_oro REAL NOT NULL DEFAULT 0,
    se_deja_reales REAL NOT NULL DEFAULT 0,
    se_deja_oro REAL NOT NULL DEFAULT 0,
    cerrado_por VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    snapshot_json TEXT
);
CREATE INDEX IF NOT EXISTS ix_cierres_diarios_fecha_op ON cierres_diarios (fecha_operativa);
"""

    if dialect == "postgresql":
        for stmt in ddl_pg.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))
        return

    if dialect == "sqlite":
        for stmt in ddl_sqlite.strip().split(";"):
            s = stmt.strip()
            if s:
                conn.execute(text(s))


def _migrate_cierres_diarios_legacy(conn, dialect: str) -> None:
    """Reemplaza esquema antiguo (fecha, total_oro, ...) por reforma apertura/cierre."""
    from sqlalchemy import inspect, text

    insp = inspect(conn.engine)
    if not insp.has_table("cierres_diarios"):
        return

    cols = {c["name"] for c in insp.get_columns("cierres_diarios")}
    if "ventas_reales" in cols:
        return
    if "fecha" not in cols:
        return

    if dialect == "sqlite":
        stmts = [
            """
CREATE TABLE cierres_diarios_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha_operativa DATE NOT NULL UNIQUE,
    ventas_reales REAL NOT NULL,
    ventas_oro REAL NOT NULL,
    compras_reales REAL NOT NULL,
    gastos_reales REAL NOT NULL,
    oro_recolectado REAL NOT NULL,
    reales_esperados REAL NOT NULL,
    oro_esperado REAL NOT NULL,
    reales_contados REAL NOT NULL,
    oro_contado REAL NOT NULL,
    diferencia_reales REAL NOT NULL,
    diferencia_oro REAL NOT NULL,
    justificacion TEXT NOT NULL DEFAULT '',
    retiro_dueno_reales REAL NOT NULL DEFAULT 0,
    retiro_dueno_oro REAL NOT NULL DEFAULT 0,
    se_deja_reales REAL NOT NULL DEFAULT 0,
    se_deja_oro REAL NOT NULL DEFAULT 0,
    cerrado_por VARCHAR(100) NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    snapshot_json TEXT
)
""",
            """
INSERT INTO cierres_diarios_new (
    id, fecha_operativa, ventas_reales, ventas_oro, compras_reales, gastos_reales,
    oro_recolectado, reales_esperados, oro_esperado, reales_contados, oro_contado,
    diferencia_reales, diferencia_oro, justificacion,
    retiro_dueno_reales, retiro_dueno_oro, se_deja_reales, se_deja_oro,
    cerrado_por, created_at, snapshot_json
)
SELECT
    id, fecha,
    COALESCE(total_reales, 0), COALESCE(total_oro, 0), 0, COALESCE(gastos, 0),
    COALESCE(total_oro, 0), COALESCE(total_reales, 0), COALESCE(total_oro, 0),
    COALESCE(total_reales, 0), COALESCE(total_oro, 0),
    0, 0, '',
    0, 0, 0, 0,
    cerrado_por, created_at, NULL
FROM cierres_diarios
""",
            "DROP TABLE cierres_diarios",
            "ALTER TABLE cierres_diarios_new RENAME TO cierres_diarios",
            "CREATE INDEX IF NOT EXISTS ix_cierres_diarios_fecha_op ON cierres_diarios (fecha_operativa)",
        ]
        for sql in stmts:
            conn.execute(text(sql.strip()))
        return

    if dialect == "postgresql":
        stmts = [
            """
CREATE TABLE cierres_diarios_new (
    id SERIAL PRIMARY KEY,
    fecha_operativa DATE NOT NULL UNIQUE,
    ventas_reales DOUBLE PRECISION NOT NULL,
    ventas_oro DOUBLE PRECISION NOT NULL,
    compras_reales DOUBLE PRECISION NOT NULL,
    gastos_reales DOUBLE PRECISION NOT NULL,
    oro_recolectado DOUBLE PRECISION NOT NULL,
    reales_esperados DOUBLE PRECISION NOT NULL,
    oro_esperado DOUBLE PRECISION NOT NULL,
    reales_contados DOUBLE PRECISION NOT NULL,
    oro_contado DOUBLE PRECISION NOT NULL,
    diferencia_reales DOUBLE PRECISION NOT NULL,
    diferencia_oro DOUBLE PRECISION NOT NULL,
    justificacion TEXT NOT NULL DEFAULT '',
    retiro_dueno_reales DOUBLE PRECISION NOT NULL DEFAULT 0,
    retiro_dueno_oro DOUBLE PRECISION NOT NULL DEFAULT 0,
    se_deja_reales DOUBLE PRECISION NOT NULL DEFAULT 0,
    se_deja_oro DOUBLE PRECISION NOT NULL DEFAULT 0,
    cerrado_por VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    snapshot_json TEXT
)
""",
            """
INSERT INTO cierres_diarios_new (
    id, fecha_operativa, ventas_reales, ventas_oro, compras_reales, gastos_reales,
    oro_recolectado, reales_esperados, oro_esperado, reales_contados, oro_contado,
    diferencia_reales, diferencia_oro, justificacion,
    retiro_dueno_reales, retiro_dueno_oro, se_deja_reales, se_deja_oro,
    cerrado_por, created_at, snapshot_json
)
SELECT
    id, fecha,
    COALESCE(total_reales, 0), COALESCE(total_oro, 0), 0, COALESCE(gastos, 0),
    COALESCE(total_oro, 0), COALESCE(total_reales, 0), COALESCE(total_oro, 0),
    COALESCE(total_reales, 0), COALESCE(total_oro, 0),
    0, 0, '',
    0, 0, 0, 0,
    cerrado_por, created_at, NULL
FROM cierres_diarios
""",
            "DROP TABLE cierres_diarios CASCADE",
            "ALTER TABLE cierres_diarios_new RENAME TO cierres_diarios",
            "CREATE INDEX IF NOT EXISTS ix_cierres_diarios_fecha_op ON cierres_diarios (fecha_operativa)",
        ]
        for sql in stmts:
            conn.execute(text(sql.strip()))


def _ensure_fundicion_tables(conn, dialect: str) -> None:
    from sqlalchemy import text

    if dialect == "postgresql":
        stmts = [
            """
CREATE TABLE IF NOT EXISTS lotes_oro (
    id SERIAL PRIMARY KEY,
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    gramos_brutos DOUBLE PRECISION NOT NULL,
    origen VARCHAR(255) NOT NULL DEFAULT '',
    estado VARCHAR(20) NOT NULL DEFAULT 'ACUMULANDO',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
""",
            """
CREATE TABLE IF NOT EXISTS fundiciones (
    id SERIAL PRIMARY KEY,
    lote_oro_id INTEGER NOT NULL REFERENCES lotes_oro(id),
    gramos_brutos DOUBLE PRECISION NOT NULL,
    ley DOUBLE PRECISION NOT NULL,
    gramos_finos DOUBLE PRECISION NOT NULL,
    casa_fundicion VARCHAR(200) NOT NULL DEFAULT '',
    fecha TIMESTAMP NOT NULL DEFAULT NOW()
)
""",
            """
CREATE TABLE IF NOT EXISTS ventas_pieza (
    id SERIAL PRIMARY KEY,
    fundicion_id INTEGER NOT NULL REFERENCES fundiciones(id),
    gramos_vendidos DOUBLE PRECISION NOT NULL,
    tasa_venta DOUBLE PRECISION NOT NULL,
    monto_total DOUBLE PRECISION NOT NULL,
    moneda VARCHAR(10) NOT NULL DEFAULT 'reales',
    comprador VARCHAR(200) NOT NULL DEFAULT '',
    fecha TIMESTAMP NOT NULL DEFAULT NOW()
)
""",
            """
CREATE TABLE IF NOT EXISTS distribuciones_fondos (
    id SERIAL PRIMARY KEY,
    venta_pieza_id INTEGER NOT NULL REFERENCES ventas_pieza(id),
    tipo VARCHAR(50) NOT NULL,
    monto DOUBLE PRECISION NOT NULL,
    descripcion VARCHAR(255)
)
""",
            "CREATE INDEX IF NOT EXISTS ix_fundiciones_lote ON fundiciones (lote_oro_id)",
            "CREATE INDEX IF NOT EXISTS ix_ventas_pieza_fund ON ventas_pieza (fundicion_id)",
            "CREATE INDEX IF NOT EXISTS ix_distrib_venta ON distribuciones_fondos (venta_pieza_id)",
        ]
        for sql in stmts:
            conn.execute(text(sql.strip()))
        return

    if dialect == "sqlite":
        stmts = [
            """
CREATE TABLE IF NOT EXISTS lotes_oro (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    gramos_brutos REAL NOT NULL,
    origen VARCHAR(255) NOT NULL DEFAULT '',
    estado VARCHAR(20) NOT NULL DEFAULT 'ACUMULANDO',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""",
            """
CREATE TABLE IF NOT EXISTS fundiciones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lote_oro_id INTEGER NOT NULL REFERENCES lotes_oro(id),
    gramos_brutos REAL NOT NULL,
    ley REAL NOT NULL,
    gramos_finos REAL NOT NULL,
    casa_fundicion VARCHAR(200) NOT NULL DEFAULT '',
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""",
            """
CREATE TABLE IF NOT EXISTS ventas_pieza (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fundicion_id INTEGER NOT NULL REFERENCES fundiciones(id),
    gramos_vendidos REAL NOT NULL,
    tasa_venta REAL NOT NULL,
    monto_total REAL NOT NULL,
    moneda VARCHAR(10) NOT NULL DEFAULT 'reales',
    comprador VARCHAR(200) NOT NULL DEFAULT '',
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
""",
            """
CREATE TABLE IF NOT EXISTS distribuciones_fondos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_pieza_id INTEGER NOT NULL REFERENCES ventas_pieza(id),
    tipo VARCHAR(50) NOT NULL,
    monto REAL NOT NULL,
    descripcion VARCHAR(255)
)
""",
            "CREATE INDEX IF NOT EXISTS ix_fundiciones_lote ON fundiciones (lote_oro_id)",
            "CREATE INDEX IF NOT EXISTS ix_ventas_pieza_fund ON ventas_pieza (fundicion_id)",
            "CREATE INDEX IF NOT EXISTS ix_distrib_venta ON distribuciones_fondos (venta_pieza_id)",
        ]
        for sql in stmts:
            conn.execute(text(sql.strip()))


def _migrate_ventas_fiado_y_pagos_venta(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)

    if dialect == "postgresql":
        if not insp.has_table("ventas"):
            return
        for stmt in (
            "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS estado_pago VARCHAR(20) NOT NULL DEFAULT 'PAGADO'",
            "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS monto_pagado DOUBLE PRECISION NOT NULL DEFAULT 0",
            "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS saldo_pendiente DOUBLE PRECISION NOT NULL DEFAULT 0",
            "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS cliente_fiado VARCHAR(100)",
            "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS telefono_fiado VARCHAR(20)",
            "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS tipo_venta VARCHAR(20) NOT NULL DEFAULT 'contado'",
        ):
            conn.execute(text(stmt))
        conn.execute(
            text(
                "UPDATE ventas SET tipo_venta = 'contado' WHERE tipo_venta IS NULL OR tipo_venta = ''"
            )
        )
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS pagos_venta (
    id SERIAL PRIMARY KEY,
    venta_id INTEGER NOT NULL REFERENCES ventas(id),
    monto DOUBLE PRECISION NOT NULL,
    moneda VARCHAR(10) NOT NULL,
    tipo_pago VARCHAR(30) NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    registrado_por VARCHAR(100) NOT NULL DEFAULT 'Admin',
    created_at TIMESTAMP NOT NULL DEFAULT NOW()
)
"""
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pagos_venta_venta ON pagos_venta (venta_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pagos_venta_fecha ON pagos_venta (fecha)"))
        _migrate_pagos_venta_tipo_oro_column(conn, dialect)
        return

    if dialect == "sqlite":
        if not insp.has_table("ventas"):
            return
        result = conn.execute(text("PRAGMA table_info(ventas)"))
        cols = {row[1] for row in result}
        alters: list[str] = []
        if "estado_pago" not in cols:
            alters.append("ALTER TABLE ventas ADD COLUMN estado_pago VARCHAR(20) NOT NULL DEFAULT 'PAGADO'")
        if "monto_pagado" not in cols:
            alters.append("ALTER TABLE ventas ADD COLUMN monto_pagado REAL NOT NULL DEFAULT 0")
        if "saldo_pendiente" not in cols:
            alters.append("ALTER TABLE ventas ADD COLUMN saldo_pendiente REAL NOT NULL DEFAULT 0")
        if "cliente_fiado" not in cols:
            alters.append("ALTER TABLE ventas ADD COLUMN cliente_fiado VARCHAR(100)")
        if "telefono_fiado" not in cols:
            alters.append("ALTER TABLE ventas ADD COLUMN telefono_fiado VARCHAR(20)")
        if "tipo_venta" not in cols:
            alters.append("ALTER TABLE ventas ADD COLUMN tipo_venta VARCHAR(20) NOT NULL DEFAULT 'contado'")
        for sql in alters:
            conn.execute(text(sql))
        conn.execute(text("UPDATE ventas SET tipo_venta = 'contado' WHERE tipo_venta IS NULL OR tipo_venta = ''"))
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS pagos_venta (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    venta_id INTEGER NOT NULL REFERENCES ventas(id),
    monto REAL NOT NULL,
    moneda VARCHAR(10) NOT NULL,
    tipo_pago VARCHAR(30) NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    registrado_por VARCHAR(100) NOT NULL DEFAULT 'Admin',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
)
"""
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pagos_venta_venta ON pagos_venta (venta_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pagos_venta_fecha ON pagos_venta (fecha)"))
        _migrate_pagos_venta_tipo_oro_column(conn, dialect)


def _migrate_pagos_venta_tipo_oro_column(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if not insp.has_table("pagos_venta"):
        return
    if dialect == "postgresql":
        conn.execute(text("ALTER TABLE pagos_venta ADD COLUMN IF NOT EXISTS tipo_oro VARCHAR(50)"))
        return
    result = conn.execute(text("PRAGMA table_info(pagos_venta)"))
    cols = {row[1] for row in result}
    if "tipo_oro" not in cols:
        conn.execute(text("ALTER TABLE pagos_venta ADD COLUMN tipo_oro VARCHAR(50)"))


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
            _migrate_cierres_diarios_legacy(conn, dialect)
            _ensure_cierres_diarios_table(conn, dialect)
            _ensure_aperturas_caja_table(conn, dialect)
            _ensure_fundicion_tables(conn, dialect)
            _migrate_ventas_fiado_y_pagos_venta(conn, dialect)
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
            _migrate_cierres_diarios_legacy(conn, dialect)
            _ensure_cierres_diarios_table(conn, dialect)
            _ensure_aperturas_caja_table(conn, dialect)
            _ensure_fundicion_tables(conn, dialect)
            _migrate_ventas_fiado_y_pagos_venta(conn, dialect)
        return
