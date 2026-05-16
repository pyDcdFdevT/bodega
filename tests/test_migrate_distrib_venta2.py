"""Migración de distribuciones para venta pieza #2."""

from pathlib import Path
import sys

from sqlalchemy import create_engine, text

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from database import (  # noqa: E402
    DISTRIBUCIONES_VENTA_PIEZA_2,
    MONTO_TOTAL_VENTA_PIEZA_2,
    _ensure_fundicion_tables,
    _migrate_distribuciones_venta_pieza_2,
)


def test_distribuciones_venta_pieza_2_suman_monto_total():
    assert MONTO_TOTAL_VENTA_PIEZA_2 == 2751.0
    assert sum(m for _, m in DISTRIBUCIONES_VENTA_PIEZA_2) == MONTO_TOTAL_VENTA_PIEZA_2


def test_migrate_reemplaza_distribuciones_incorrectas(tmp_path):
    db_path = tmp_path / "migrate_vp2.db"
    engine = create_engine(f"sqlite:///{db_path}", future=True)
    with engine.begin() as conn:
        _ensure_fundicion_tables(conn, "sqlite")
        conn.execute(
            text("INSERT INTO lotes_oro (gramos_brutos, origen, estado) VALUES (10, 't', 'FUNDIDO')")
        )
        conn.execute(
            text(
                """
                INSERT INTO fundiciones (lote_oro_id, gramos_brutos, ley, gramos_finos, casa_fundicion)
                VALUES (1, 10, 0.9, 9, 'Casa')
                """
            )
        )
        conn.execute(
            text(
                """
                INSERT INTO ventas_pieza (id, fundicion_id, gramos_vendidos, tasa_venta, monto_total, moneda)
                VALUES (2, 1, 4.2, 655, 2751, 'reales')
                """
            )
        )
        for tipo, monto in [
            ("reposicion_bodega", 100.0),
            ("reposicion_gasolina", 100.0),
            ("gastos_operativos", 100.0),
            ("pago_socio", 110.0),
            ("ganancia_dueno", 110.0),
            ("se_deja_caja", 110.0),
        ]:
            conn.execute(
                text(
                    "INSERT INTO distribuciones_fondos (venta_pieza_id, tipo, monto) VALUES (2, :t, :m)"
                ),
                {"t": tipo, "m": monto},
            )

    with engine.begin() as conn:
        suma_antes = conn.execute(
            text("SELECT SUM(monto) FROM distribuciones_fondos WHERE venta_pieza_id = 2")
        ).scalar()
        assert round(float(suma_antes), 2) == 630.0
        _migrate_distribuciones_venta_pieza_2(conn, "sqlite")

    with engine.connect() as conn:
        rows = conn.execute(
            text(
                "SELECT tipo, monto FROM distribuciones_fondos WHERE venta_pieza_id = 2 ORDER BY id"
            )
        ).fetchall()
        assert len(rows) == 6
        assert sum(float(r[1]) for r in rows) == MONTO_TOTAL_VENTA_PIEZA_2
        by_tipo = {r[0]: float(r[1]) for r in rows}
        assert by_tipo["se_deja_caja"] == 351.0
        assert by_tipo["reposicion_bodega"] == 800.0

    engine.dispose()
