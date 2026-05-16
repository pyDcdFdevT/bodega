"""Sugerencia de apertura: oro retirado a fundición y caja por distribuciones."""

from datetime import timedelta
from unittest.mock import patch

ADMIN_HEADERS = {"X-Bodega-Rol": "admin"}


def _abrir(client, caja=500.0, oro=10.0):
    return client.post(
        "/api/apertura/",
        headers=ADMIN_HEADERS,
        json={
            "caja_inicial_reales": caja,
            "oro_operativo_inicial": oro,
            "abierto_por": "Sugerencia test",
        },
    )


def _cerrar(client, *, se_deja_reales=200.0, se_deja_oro=8.0, retirar_oro=False):
    dia = client.get("/api/cierre/dia").json()
    conc = dia["conciliacion"]
    return client.post(
        "/api/cierre/generar",
        headers=ADMIN_HEADERS,
        json={
            "cerrado_por": "Sugerencia test",
            "reales_contados": float(conc["reales_esperados"]),
            "oro_contado": float(conc["oro_esperado"]),
            "se_deja_reales": se_deja_reales,
            "se_deja_oro": se_deja_oro,
            "retirar_oro_para_fundicion": retirar_oro,
        },
    )


def _flujo_venta_distrib_se_deja_caja(client, monto_caja=75.0):
    crea = client.post(
        "/api/fundicion/lotes",
        headers=ADMIN_HEADERS,
        json={"gramos_brutos": 50.0, "origen": "Test sugerencia", "estado": "ACUMULANDO"},
    )
    lote_id = crea.json()["lote"]["id"]
    fund = client.post(
        "/api/fundicion/fundiciones",
        headers=ADMIN_HEADERS,
        json={
            "lote_oro_id": lote_id,
            "gramos_brutos": 50.0,
            "ley": 0.9,
            "gramos_finos": 45.0,
            "casa_fundicion": "Casa",
        },
    )
    fund_id = fund.json()["fundicion"]["id"]
    monto_total = 1000.0
    vp = client.post(
        "/api/fundicion/ventas-pieza",
        headers=ADMIN_HEADERS,
        json={
            "fundicion_id": fund_id,
            "gramos_vendidos": 40.0,
            "tasa_venta": 25.0,
            "monto_total": monto_total,
            "moneda": "reales",
            "comprador": "X",
        },
    )
    vp_id = vp.json()["venta_pieza"]["id"]
    resto = monto_total - monto_caja
    client.post(
        "/api/fundicion/distribuciones",
        headers=ADMIN_HEADERS,
        json={
            "venta_pieza_id": vp_id,
            "lineas": [
                {"tipo": "se_deja_caja", "monto": monto_caja},
                {"tipo": "ganancia_dueno", "monto": resto},
            ],
        },
    )


def test_sugerencia_oro_cero_si_oro_retirado_en_cierre(client):
    from services.apertura_context import fecha_operativa_hoy

    assert _abrir(client).status_code == 200
    bruto = float(client.get("/api/cierre/dia").json()["oro_recolectado"]["bruto_total_gramos"])
    if bruto <= 0:
        return
    assert _cerrar(client, se_deja_reales=100.0, se_deja_oro=5.0, retirar_oro=True).status_code == 200

    manana = fecha_operativa_hoy() + timedelta(days=1)
    with patch("services.apertura_context.fecha_operativa_hoy", return_value=manana):
        sug = client.get("/api/apertura/").json()["sugerencia"]
    assert sug is not None
    assert sug["oro_operativo_inicial"] == 0.0
    assert sug["oro_retirado_fundicion"] is True


def test_sugerencia_caja_suma_distribuciones_se_deja_caja(client):
    from services.apertura_context import fecha_operativa_hoy

    assert _abrir(client).status_code == 200
    assert _cerrar(client, se_deja_reales=100.0, se_deja_oro=3.0, retirar_oro=False).status_code == 200
    _flujo_venta_distrib_se_deja_caja(client, monto_caja=75.0)

    manana = fecha_operativa_hoy() + timedelta(days=1)
    with patch("services.apertura_context.fecha_operativa_hoy", return_value=manana):
        sug = client.get("/api/apertura/").json()["sugerencia"]
    assert sug is not None
    assert sug["caja_distribuciones_se_deja_caja"] == 75.0
    assert sug["caja_inicial_reales"] == 175.0
    assert sug["oro_operativo_inicial"] == 3.0
