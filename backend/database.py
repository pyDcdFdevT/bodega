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


def _ensure_configuracion_table(conn, dialect: str) -> None:
    from sqlalchemy import text

    if dialect == "postgresql":
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS configuracion (
    id SERIAL PRIMARY KEY,
    clave VARCHAR(50) NOT NULL UNIQUE,
    valor VARCHAR(255) NOT NULL
)
"""
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_configuracion_clave ON configuracion (clave)"))
        return

    if dialect == "sqlite":
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS configuracion (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    clave VARCHAR(50) NOT NULL UNIQUE,
    valor VARCHAR(255) NOT NULL
)
"""
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_configuracion_clave ON configuracion (clave)"))


def _ensure_activos_table(conn, dialect: str) -> None:
    from sqlalchemy import text

    if dialect == "postgresql":
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS activos (
    id SERIAL PRIMARY KEY,
    descripcion VARCHAR(500) NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    monto_reales DOUBLE PRECISION NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    observaciones TEXT,
    CONSTRAINT ck_activo_monto_reales CHECK (monto_reales >= 0),
    CONSTRAINT ck_activo_categoria CHECK (categoria IN ('equipo','construccion','vehiculo','otro'))
)
"""
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_activos_fecha ON activos (fecha)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_activos_categoria ON activos (categoria)"))
        return

    if dialect == "sqlite":
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS activos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descripcion VARCHAR(500) NOT NULL,
    categoria VARCHAR(40) NOT NULL,
    monto_reales REAL NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    observaciones TEXT,
    CHECK (monto_reales >= 0),
    CHECK (categoria IN ('equipo','construccion','vehiculo','otro'))
)
"""
            )
        )
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_activos_fecha ON activos (fecha)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS ix_activos_categoria ON activos (categoria)"))
        return


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


def _migrate_venta_compra_estado_anulacion(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn.engine)

    if dialect == "postgresql":
        if insp.has_table("ventas"):
            conn.execute(text("ALTER TABLE ventas ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NOT NULL DEFAULT 'VIGENTE'"))
        if insp.has_table("compras"):
            conn.execute(text("ALTER TABLE compras ADD COLUMN IF NOT EXISTS estado VARCHAR(20) NOT NULL DEFAULT 'VIGENTE'"))
        return

    if dialect == "sqlite":
        if insp.has_table("ventas"):
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(ventas)"))}
            if "estado" not in cols:
                conn.execute(text("ALTER TABLE ventas ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'VIGENTE'"))
        if insp.has_table("compras"):
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(compras)"))}
            if "estado" not in cols:
                conn.execute(text("ALTER TABLE compras ADD COLUMN estado VARCHAR(20) NOT NULL DEFAULT 'VIGENTE'"))
        return


def _backfill_activos_depreciacion_mensual(conn) -> None:
    """Calcula depreciacion_mensual en Python (compatible PG y SQLite)."""
    from sqlalchemy import text

    rows = conn.execute(
        text(
            """
SELECT id, monto_reales, valor_residual, vida_util_anios
FROM activos
WHERE depreciacion_mensual = 0 AND monto_reales > 0
"""
        )
    ).fetchall()
    upd = text("UPDATE activos SET depreciacion_mensual = :dep WHERE id = :id")
    for row in rows:
        vida = int(row[3] or 5)
        meses = max(vida * 12, 1)
        base = max(float(row[1]) - float(row[2] or 0), 0.0)
        dep = round(base / meses, 2)
        conn.execute(upd, {"dep": dep, "id": int(row[0])})


def _migrate_activos_depreciacion(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if not insp.has_table("activos"):
        return

    if dialect == "postgresql":
        for stmt in (
            "ALTER TABLE activos ADD COLUMN IF NOT EXISTS vida_util_anios INTEGER NOT NULL DEFAULT 5",
            "ALTER TABLE activos ADD COLUMN IF NOT EXISTS valor_residual DOUBLE PRECISION NOT NULL DEFAULT 0",
            "ALTER TABLE activos ADD COLUMN IF NOT EXISTS depreciacion_mensual DOUBLE PRECISION NOT NULL DEFAULT 0",
        ):
            conn.execute(text(stmt))
        _backfill_activos_depreciacion_mensual(conn)
        return

    if dialect == "sqlite":
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(activos)"))}
        if "vida_util_anios" not in cols:
            conn.execute(text("ALTER TABLE activos ADD COLUMN vida_util_anios INTEGER NOT NULL DEFAULT 5"))
        if "valor_residual" not in cols:
            conn.execute(text("ALTER TABLE activos ADD COLUMN valor_residual REAL NOT NULL DEFAULT 0"))
        if "depreciacion_mensual" not in cols:
            conn.execute(text("ALTER TABLE activos ADD COLUMN depreciacion_mensual REAL NOT NULL DEFAULT 0"))
        _backfill_activos_depreciacion_mensual(conn)


def _backfill_detalles_venta_subtotal_reales(conn) -> None:
    """Calcula subtotal_reales en Python (compatible PG y SQLite)."""
    from sqlalchemy import text

    rows = conn.execute(
        text(
            """
SELECT dv.id, p.precio_venta_reales, dv.cantidad
FROM detalles_venta dv
JOIN productos p ON p.id = dv.producto_id
WHERE dv.subtotal_reales IS NULL OR dv.subtotal_reales = 0
"""
        )
    ).fetchall()
    upd = text("UPDATE detalles_venta SET subtotal_reales = :sub WHERE id = :id")
    for row in rows:
        subtotal = round(float(row[1] or 0) * float(row[2] or 0), 2)
        conn.execute(upd, {"sub": subtotal, "id": int(row[0])})


def _migrate_ventas_devoluciones_descuento(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if dialect == "postgresql":
        if insp.has_table("ventas"):
            conn.execute(
                text(
                    "ALTER TABLE ventas ADD COLUMN IF NOT EXISTS descuento_reales "
                    "DOUBLE PRECISION NOT NULL DEFAULT 0"
                )
            )
        if insp.has_table("detalles_venta"):
            conn.execute(
                text(
                    "ALTER TABLE detalles_venta ADD COLUMN IF NOT EXISTS cantidad_devuelta "
                    "DOUBLE PRECISION NOT NULL DEFAULT 0"
                )
            )
            conn.execute(
                text(
                    "ALTER TABLE detalles_venta ADD COLUMN IF NOT EXISTS subtotal_reales "
                    "DOUBLE PRECISION NOT NULL DEFAULT 0"
                )
            )
            _backfill_detalles_venta_subtotal_reales(conn)
        _migrate_transaccion_tipo_reabrir(conn, dialect)
        return

    if insp.has_table("ventas"):
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(ventas)"))}
        if "descuento_reales" not in cols:
            conn.execute(text("ALTER TABLE ventas ADD COLUMN descuento_reales REAL NOT NULL DEFAULT 0"))
    if insp.has_table("detalles_venta"):
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(detalles_venta)"))}
        if "cantidad_devuelta" not in cols:
            conn.execute(text("ALTER TABLE detalles_venta ADD COLUMN cantidad_devuelta REAL NOT NULL DEFAULT 0"))
        if "subtotal_reales" not in cols:
            conn.execute(text("ALTER TABLE detalles_venta ADD COLUMN subtotal_reales REAL NOT NULL DEFAULT 0"))
        _backfill_detalles_venta_subtotal_reales(conn)


def _migrate_transaccion_tipo_reabrir(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if not insp.has_table("transacciones"):
        return
    if dialect != "postgresql":
        return
    conn.execute(text("ALTER TABLE transacciones DROP CONSTRAINT IF EXISTS ck_transaccion_tipo"))
    conn.execute(
        text(
            """
ALTER TABLE transacciones ADD CONSTRAINT ck_transaccion_tipo
CHECK (tipo IN (
    'venta','compra','salida','gasto','compra_oro','venta_gasolina',
    'reposicion_gasolina','ajuste','correccion','cobro_fiado','reabrir_dia','pago_proveedor','devolucion'
))
"""
        )
    )


def _saldo_inicial_desde_snapshot(snapshot_json: str | None) -> tuple[float, float] | None:
    import json

    if not snapshot_json:
        return None
    try:
        snap = json.loads(snapshot_json)
    except (json.JSONDecodeError, TypeError):
        return None
    caja = (snap.get("caja") or {}).get("saldo_inicial_reales")
    if caja is None:
        return None
    valor = float(caja)
    if valor <= 0.009:
        return None
    oro = float((snap.get("caja") or {}).get("oro_operativo_inicial") or 0)
    return round(valor, 2), round(oro, 4)


def _resolver_caja_inicial_primera_apertura(conn, fecha_op) -> tuple[float, float] | None:
    from sqlalchemy import text

    cierre_prev = conn.execute(
        text(
            """
SELECT se_deja_reales, se_deja_oro
FROM cierres_diarios
WHERE fecha_operativa < :fecha
ORDER BY fecha_operativa DESC, id DESC
LIMIT 1
"""
        ),
        {"fecha": fecha_op},
    ).fetchone()
    if cierre_prev:
        caja = round(float(cierre_prev[0] or 0), 2)
        if caja > 0.009:
            return caja, round(float(cierre_prev[1] or 0), 4)

    cierre_mismo = conn.execute(
        text(
            """
SELECT snapshot_json
FROM cierres_diarios
WHERE fecha_operativa = :fecha
ORDER BY id DESC
LIMIT 1
"""
        ),
        {"fecha": fecha_op},
    ).fetchone()
    if cierre_mismo:
        desde_snap = _saldo_inicial_desde_snapshot(cierre_mismo[0])
        if desde_snap:
            return desde_snap

    cfg = conn.execute(
        text(
            "SELECT valor FROM configuracion WHERE clave = 'capital_inicial_reales' LIMIT 1"
        )
    ).fetchone()
    if cfg and cfg[0]:
        try:
            caja = round(float(cfg[0]), 2)
        except (TypeError, ValueError):
            caja = 0.0
        if caja > 0.009:
            return caja, 0.0
    return None


def _sync_config_capital_inicial(conn, dialect: str, nuevo_caja: float) -> None:
    from sqlalchemy import inspect, text

    if not inspect(conn).has_table("configuracion"):
        return
    if dialect == "postgresql":
        conn.execute(
            text(
                """
INSERT INTO configuracion (clave, valor)
VALUES ('capital_inicial_reales', :valor)
ON CONFLICT (clave) DO UPDATE SET valor = EXCLUDED.valor
"""
            ),
            {"valor": str(nuevo_caja)},
        )
    else:
        existe = conn.execute(
            text("SELECT 1 FROM configuracion WHERE clave = 'capital_inicial_reales' LIMIT 1")
        ).fetchone()
        if existe:
            conn.execute(
                text("UPDATE configuracion SET valor = :valor WHERE clave = 'capital_inicial_reales'"),
                {"valor": str(nuevo_caja)},
            )
        else:
            conn.execute(
                text(
                    "INSERT INTO configuracion (clave, valor) VALUES ('capital_inicial_reales', :valor)"
                ),
                {"valor": str(nuevo_caja)},
            )


def _migrate_tasas_mercado_y_historicos(conn, dialect: str) -> None:
    """Tasas operativas de mercado y correccion de ventas_pieza #2/#3 y compra_oro #6."""
    from sqlalchemy import text

    updates_tasas = [
        ("araparita", 467.50),
        ("uruman", 505.00),
        ("santa_elena_minero", 430.00),
        ("santa_elena_fundido", 655.00),
    ]
    for nombre, tasa in updates_tasas:
        conn.execute(
            text("UPDATE tasas_cambio SET tasa_reales = :tasa WHERE nombre = :nombre"),
            {"tasa": tasa, "nombre": nombre},
        )

    conn.execute(
        text("UPDATE ventas_pieza SET tasa_venta = 655.00, monto_total = 2751.00 WHERE id = 2")
    )
    conn.execute(
        text("UPDATE ventas_pieza SET tasa_venta = 655.00, monto_total = 2076.35 WHERE id = 3")
    )
    conn.execute(
        text(
            """
            UPDATE compras_oro
            SET tasa_compra_reales = 467.50, total_reales = 1402.50
            WHERE id = 6 AND tipo_oro = 'uruman'
            """
        )
    )


DISTRIBUCIONES_VENTA_PIEZA_2 = (
    ("reposicion_bodega", 800.0),
    ("reposicion_gasolina", 400.0),
    ("gastos_operativos", 200.0),
    ("pago_socio", 500.0),
    ("ganancia_dueno", 500.0),
    ("se_deja_caja", 351.0),
)
MONTO_TOTAL_VENTA_PIEZA_2 = sum(m for _, m in DISTRIBUCIONES_VENTA_PIEZA_2)


def _migrate_nombre_bodega_default(conn, dialect: str) -> None:
    """Valor por defecto del nombre visible en la app."""
    from sqlalchemy import inspect, text

    if not inspect(conn).has_table("configuracion"):
        return
    existe = conn.execute(
        text("SELECT 1 FROM configuracion WHERE clave = 'nombre_bodega' LIMIT 1")
    ).fetchone()
    if existe:
        return
    conn.execute(
        text(
            "INSERT INTO configuracion (clave, valor) VALUES ('nombre_bodega', 'Bodega Minera')"
        )
    )


def _migrate_distribuciones_venta_pieza_2(conn, dialect: str) -> None:
    """Reemplaza distribuciones de venta pieza #2 para cuadrar con monto_total R$ 2,751."""
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if not insp.has_table("distribuciones_fondos") or not insp.has_table("ventas_pieza"):
        return

    vp = conn.execute(
        text("SELECT id, monto_total FROM ventas_pieza WHERE id = 2")
    ).fetchone()
    if not vp:
        return

    esperado = float(MONTO_TOTAL_VENTA_PIEZA_2)
    suma = float(
        conn.execute(
            text(
                "SELECT COALESCE(SUM(monto), 0) FROM distribuciones_fondos WHERE venta_pieza_id = 2"
            )
        ).scalar()
        or 0
    )
    count = int(
        conn.execute(
            text("SELECT COUNT(*) FROM distribuciones_fondos WHERE venta_pieza_id = 2")
        ).scalar()
        or 0
    )
    if count == len(DISTRIBUCIONES_VENTA_PIEZA_2) and round(suma, 2) == round(esperado, 2):
        caja = conn.execute(
            text(
                """
                SELECT monto FROM distribuciones_fondos
                WHERE venta_pieza_id = 2 AND tipo = 'se_deja_caja'
                LIMIT 1
                """
            )
        ).fetchone()
        if caja and round(float(caja[0]), 2) == 351.0:
            return

    conn.execute(text("DELETE FROM distribuciones_fondos WHERE venta_pieza_id = 2"))
    for tipo, monto in DISTRIBUCIONES_VENTA_PIEZA_2:
        conn.execute(
            text(
                """
                INSERT INTO distribuciones_fondos (venta_pieza_id, tipo, monto)
                VALUES (2, :tipo, :monto)
                """
            ),
            {"tipo": tipo, "monto": monto},
        )


def _migrate_apertura_caja_inicial_cero(conn, dialect: str) -> None:
    """
    Corrige la primera apertura con caja_inicial_reales = 0:
    - se_deja_* del último cierre anterior, o
    - saldo_inicial del snapshot del cierre del mismo día (primer día operativo), o
    - configuracion.capital_inicial_reales.
    Si no hay fila de apertura pero sí cierre con snapshot, la recrea.
    """
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if not insp.has_table("aperturas_caja") or not insp.has_table("cierres_diarios"):
        return

    primera = conn.execute(
        text(
            """
SELECT id, fecha_operativa, caja_inicial_reales, oro_operativo_inicial
FROM aperturas_caja
ORDER BY fecha_operativa ASC, id ASC
LIMIT 1
"""
        )
    ).fetchone()

    if not primera:
        cierre_ini = conn.execute(
            text(
                """
SELECT fecha_operativa, snapshot_json, cerrado_por
FROM cierres_diarios
ORDER BY fecha_operativa ASC, id ASC
LIMIT 1
"""
            )
        ).fetchone()
        if not cierre_ini:
            return
        resuelto = _saldo_inicial_desde_snapshot(cierre_ini[1])
        if not resuelto:
            return
        nuevo_caja, nuevo_oro = resuelto
        conn.execute(
            text(
                """
INSERT INTO aperturas_caja
    (fecha_operativa, caja_inicial_reales, oro_operativo_inicial, abierto_por, created_at)
VALUES (:fecha, :caja, :oro, :por, CURRENT_TIMESTAMP)
"""
            ),
            {
                "fecha": cierre_ini[0],
                "caja": nuevo_caja,
                "oro": nuevo_oro,
                "por": (cierre_ini[2] or "Sistema")[:100],
            },
        )
        _sync_config_capital_inicial(conn, dialect, nuevo_caja)
        return

    ap_id = int(primera[0])
    fecha_op = primera[1]
    caja_actual = float(primera[2] or 0)
    if caja_actual > 0.009:
        return

    resuelto = _resolver_caja_inicial_primera_apertura(conn, fecha_op)
    if not resuelto:
        return
    nuevo_caja, nuevo_oro = resuelto

    conn.execute(
        text(
            """
UPDATE aperturas_caja
SET caja_inicial_reales = :caja,
    oro_operativo_inicial = CASE
        WHEN oro_operativo_inicial IS NULL OR oro_operativo_inicial = 0 THEN :oro
        ELSE oro_operativo_inicial
    END
WHERE id = :id
"""
        ),
        {"caja": nuevo_caja, "oro": nuevo_oro, "id": ap_id},
    )

    _sync_config_capital_inicial(conn, dialect, nuevo_caja)


def _migrate_pagos_proveedores(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if dialect == "postgresql":
        conn.execute(
            text(
                """
CREATE TABLE IF NOT EXISTS pagos_proveedores (
    id SERIAL PRIMARY KEY,
    compra_id INTEGER NOT NULL REFERENCES compras(id),
    monto DOUBLE PRECISION NOT NULL,
    fecha TIMESTAMP NOT NULL DEFAULT NOW(),
    proveedor VARCHAR(100) NOT NULL,
    CONSTRAINT ck_pago_proveedor_monto CHECK (monto > 0)
)
"""
            )
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_pagos_proveedores_compra ON pagos_proveedores (compra_id)")
        )
        conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_pagos_proveedores_fecha ON pagos_proveedores (fecha)")
        )
        if insp.has_table("compras"):
            conn.execute(
                text(
                    "ALTER TABLE compras ADD COLUMN IF NOT EXISTS estado_credito "
                    "VARCHAR(20) NOT NULL DEFAULT 'pagada'"
                )
            )
            conn.execute(
                text(
                    """
UPDATE compras SET estado_credito = 'pendiente'
WHERE tipo_pago_compra = 'credito' AND (estado_credito IS NULL OR estado_credito = 'pagada')
"""
                )
            )
            conn.execute(
                text(
                    """
UPDATE compras SET estado_credito = 'pagada'
WHERE tipo_pago_compra = 'contado' OR tipo_pago_compra IS NULL
"""
                )
            )
        return

    if dialect == "sqlite":
        if not insp.has_table("pagos_proveedores"):
            conn.execute(
                text(
                    """
CREATE TABLE pagos_proveedores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    compra_id INTEGER NOT NULL REFERENCES compras(id),
    monto REAL NOT NULL,
    fecha DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    proveedor VARCHAR(100) NOT NULL,
    CHECK (monto > 0)
)
"""
                )
            )
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pagos_proveedores_compra ON pagos_proveedores (compra_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS ix_pagos_proveedores_fecha ON pagos_proveedores (fecha)"))
        if insp.has_table("compras"):
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(compras)"))}
            if "estado_credito" not in cols:
                conn.execute(
                    text("ALTER TABLE compras ADD COLUMN estado_credito VARCHAR(20) NOT NULL DEFAULT 'pagada'")
                )
            conn.execute(
                text(
                    "UPDATE compras SET estado_credito = 'pendiente' WHERE tipo_pago_compra = 'credito'"
                )
            )
            conn.execute(
                text(
                    "UPDATE compras SET estado_credito = 'pagada' WHERE tipo_pago_compra = 'contado'"
                )
            )


def _migrate_compra_tipo_pago(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if not insp.has_table("compras"):
        return
    if dialect == "postgresql":
        conn.execute(
            text(
                "ALTER TABLE compras ADD COLUMN IF NOT EXISTS tipo_pago_compra "
                "VARCHAR(20) NOT NULL DEFAULT 'contado'"
            )
        )
        conn.execute(
            text(
                """
UPDATE compras SET tipo_pago_compra = 'contado'
WHERE tipo_pago_compra IS NULL OR tipo_pago_compra = ''
"""
            )
        )
        return
    if dialect == "sqlite":
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(compras)"))}
        if "tipo_pago_compra" not in cols:
            conn.execute(
                text(
                    "ALTER TABLE compras ADD COLUMN tipo_pago_compra VARCHAR(20) NOT NULL DEFAULT 'contado'"
                )
            )


def _backfill_gasolina_costo_promedio(conn) -> None:
    """CPP inicial desde último precio de reposición (compatible PG y SQLite)."""
    from sqlalchemy import inspect, text

    if not inspect(conn).has_table("gasolina"):
        return

    gasolinas = conn.execute(
        text("SELECT id, costo_promedio_reales FROM gasolina")
    ).fetchall()
    upd = text("UPDATE gasolina SET costo_promedio_reales = :cpp WHERE id = :id")
    for gid, cpp_actual in gasolinas:
        if float(cpp_actual or 0) > 0.009:
            continue
        ultimo = conn.execute(
            text(
                """
SELECT precio_reales_litro FROM gasolina_reposiciones
WHERE gasolina_id = :gid
ORDER BY fecha DESC, id DESC
LIMIT 1
"""
            ),
            {"gid": int(gid)},
        ).fetchone()
        if ultimo and float(ultimo[0] or 0) > 0:
            conn.execute(upd, {"cpp": round(float(ultimo[0]), 2), "id": int(gid)})


def _migrate_gasolina_costo_promedio(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    if not insp.has_table("gasolina"):
        return
    if dialect == "postgresql":
        conn.execute(
            text(
                "ALTER TABLE gasolina ADD COLUMN IF NOT EXISTS costo_promedio_reales "
                "DOUBLE PRECISION NOT NULL DEFAULT 0"
            )
        )
    else:
        cols = {row[1] for row in conn.execute(text("PRAGMA table_info(gasolina)"))}
        if "costo_promedio_reales" not in cols:
            conn.execute(
                text("ALTER TABLE gasolina ADD COLUMN costo_promedio_reales REAL NOT NULL DEFAULT 0")
            )
    _backfill_gasolina_costo_promedio(conn)


def _migrate_costo_promedio_columns(conn, dialect: str) -> None:
    from sqlalchemy import inspect, text

    insp = inspect(conn)
    _migrate_gasolina_costo_promedio(conn, dialect)
    if dialect == "postgresql":
        if insp.has_table("productos"):
            conn.execute(
                text(
                    "ALTER TABLE productos ADD COLUMN IF NOT EXISTS costo_promedio_reales "
                    "DOUBLE PRECISION NOT NULL DEFAULT 0"
                )
            )
            conn.execute(
                text(
                    """
UPDATE productos
SET costo_promedio_reales = precio_costo_reales
WHERE costo_promedio_reales = 0 AND precio_costo_reales > 0
"""
                )
            )
        if insp.has_table("detalles_venta"):
            conn.execute(
                text(
                    "ALTER TABLE detalles_venta ADD COLUMN IF NOT EXISTS costo_unitario_reales "
                    "DOUBLE PRECISION NOT NULL DEFAULT 0"
                )
            )
        return

    if dialect == "sqlite":
        if insp.has_table("productos"):
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(productos)"))}
            if "costo_promedio_reales" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE productos ADD COLUMN costo_promedio_reales REAL NOT NULL DEFAULT 0"
                    )
                )
            conn.execute(
                text(
                    """
UPDATE productos
SET costo_promedio_reales = precio_costo_reales
WHERE costo_promedio_reales = 0 AND precio_costo_reales > 0
"""
                )
            )
        if insp.has_table("detalles_venta"):
            cols = {row[1] for row in conn.execute(text("PRAGMA table_info(detalles_venta)"))}
            if "costo_unitario_reales" not in cols:
                conn.execute(
                    text(
                        "ALTER TABLE detalles_venta ADD COLUMN costo_unitario_reales REAL NOT NULL DEFAULT 0"
                    )
                )
        return


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
            _ensure_configuracion_table(conn, dialect)
            _ensure_activos_table(conn, dialect)
            _migrate_activos_depreciacion(conn, dialect)
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
            if insp.has_table("ventas_gasolina"):
                alters = [
                    "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS tipo_oro VARCHAR(50)",
                    "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS unidad_precio_venta VARCHAR(20) DEFAULT 'reales_litro'",
                    "ALTER TABLE ventas_gasolina ADD COLUMN IF NOT EXISTS precio_litro_venta FLOAT DEFAULT 0",
                ]
                for sql in alters:
                    conn.execute(text(sql))
            conn.execute(text(create_reposiciones))
            _ensure_transacciones_table(conn, dialect)
            _migrate_cierres_diarios_legacy(conn, dialect)
            _ensure_cierres_diarios_table(conn, dialect)
            _ensure_aperturas_caja_table(conn, dialect)
            _ensure_fundicion_tables(conn, dialect)
            _migrate_ventas_fiado_y_pagos_venta(conn, dialect)
            _migrate_venta_compra_estado_anulacion(conn, dialect)
            _migrate_costo_promedio_columns(conn, dialect)
            _migrate_compra_tipo_pago(conn, dialect)
            _migrate_transaccion_tipo_reabrir(conn, dialect)
            _migrate_ventas_devoluciones_descuento(conn, dialect)
            _migrate_pagos_proveedores(conn, dialect)
            _migrate_apertura_caja_inicial_cero(conn, dialect)
            _migrate_tasas_mercado_y_historicos(conn, dialect)
            _migrate_distribuciones_venta_pieza_2(conn, dialect)
            _migrate_nombre_bodega_default(conn, dialect)
        return

    if dialect == "sqlite":
        insp = inspect(engine)
        with engine.begin() as conn:
            if insp.has_table("gasolina"):
                _migrate_gasolina_precio_column(conn, dialect)
            _ensure_gastos_table(conn, dialect)
            _ensure_configuracion_table(conn, dialect)
            _ensure_activos_table(conn, dialect)
            _migrate_activos_depreciacion(conn, dialect)
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
            _migrate_venta_compra_estado_anulacion(conn, dialect)
            _migrate_costo_promedio_columns(conn, dialect)
            _migrate_compra_tipo_pago(conn, dialect)
            _migrate_transaccion_tipo_reabrir(conn, dialect)
            _migrate_ventas_devoluciones_descuento(conn, dialect)
            _migrate_pagos_proveedores(conn, dialect)
            _migrate_apertura_caja_inicial_cero(conn, dialect)
            _migrate_tasas_mercado_y_historicos(conn, dialect)
            _migrate_distribuciones_venta_pieza_2(conn, dialect)
            _migrate_nombre_bodega_default(conn, dialect)
        return
