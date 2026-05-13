from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import (
    Compra,
    CompraOro,
    GastoOperativo,
    GasolinaReposicion,
    Salida,
    Venta,
    VentaGasolina,
)


router = APIRouter(prefix="/cierre", tags=["Cierre"])


@router.get("/dia")
def cierre_del_dia(
    saldo_inicial_reales: float = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    inicio = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)

    ventas_reales = float(
        db.query(func.coalesce(func.sum(Venta.total_reales), 0)).filter(Venta.fecha >= inicio).scalar() or 0
    )
    ventas_oro = float(
        db.query(func.coalesce(func.sum(Venta.total_oro), 0)).filter(Venta.fecha >= inicio).scalar() or 0
    )
    oro_araparita = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "araparita")
        .scalar()
        or 0
    )
    oro_uruman = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "uruman")
        .scalar()
        or 0
    )
    oro_se_min = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "santa_elena_minero")
        .scalar()
        or 0
    )
    oro_se_fun = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "santa_elena_fundido")
        .scalar()
        or 0
    )

    compras_reales = float(
        db.query(func.coalesce(func.sum(Compra.total_reales), 0)).filter(Compra.fecha >= inicio).scalar() or 0
    )
    compras_oro = float(
        db.query(func.coalesce(func.sum(Compra.total_oro), 0)).filter(Compra.fecha >= inicio).scalar() or 0
    )
    salidas_oro = float(
        db.query(func.coalesce(func.sum(Salida.valor_oro), 0)).filter(Salida.fecha >= inicio).scalar() or 0
    )

    gas_ventas_reales = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_reales), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gas_ventas_oro = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gas_repo_reales = float(
        db.query(func.coalesce(func.sum(GasolinaReposicion.total_reales), 0))
        .filter(GasolinaReposicion.fecha >= inicio)
        .scalar()
        or 0
    )

    co_gramos = float(
        db.query(func.coalesce(func.sum(CompraOro.gramos), 0)).filter(CompraOro.fecha >= inicio).scalar() or 0
    )
    co_reales = float(
        db.query(func.coalesce(func.sum(CompraOro.total_reales), 0)).filter(CompraOro.fecha >= inicio).scalar() or 0
    )

    gastos_total = float(
        db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0))
        .filter(GastoOperativo.fecha >= inicio)
        .scalar()
        or 0
    )

    oro_recolectado_bruto = oro_araparita + oro_uruman + oro_se_min + oro_se_fun
    ingresos_reales = ventas_reales + gas_ventas_reales
    egresos_reales = compras_reales + co_reales + gas_repo_reales + gastos_total
    saldo_final = round(saldo_inicial_reales + ingresos_reales - egresos_reales, 2)

    return {
        "fecha": inicio.date().isoformat(),
        "bodega": {
            "ventas_reales": round(ventas_reales, 2),
            "ventas_oro": round(ventas_oro, 2),
            "compras_mercancia_reales": round(compras_reales, 2),
            "compras_mercancia_oro": round(compras_oro, 2),
            "salidas_oro": round(salidas_oro, 2),
        },
        "gasolina": {
            "ventas_reales": round(gas_ventas_reales, 2),
            "ventas_oro": round(gas_ventas_oro, 2),
            "reposicion_reales": round(gas_repo_reales, 2),
        },
        "compra_oro": {
            "gramos": round(co_gramos, 2),
            "reales_usados": round(co_reales, 2),
        },
        "gastos": {
            "total_reales": round(gastos_total, 2),
        },
        "oro_recolectado": {
            "araparita": round(oro_araparita, 2),
            "uruman": round(oro_uruman, 2),
            "santa_elena_minero": round(oro_se_min, 2),
            "santa_elena_fundido": round(oro_se_fun, 2),
            "comprado_gramos": round(co_gramos, 2),
            "bruto_total_gramos": round(oro_recolectado_bruto + co_gramos, 2),
        },
        "caja": {
            "saldo_inicial_reales": round(saldo_inicial_reales, 2),
            "ingresos_reales": round(ingresos_reales, 2),
            "egresos_reales": round(egresos_reales, 2),
            "saldo_final_reales": saldo_final,
        },
        "fundicion": {
            "nota": "Ley y fino son valores manuales en pantalla",
            "bruto_gramos": round(oro_recolectado_bruto, 2),
        },
        "venta_pieza": {
            "nota": "Fino manual x tasa en frontend",
        },
    }
