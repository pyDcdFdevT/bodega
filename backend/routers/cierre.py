from __future__ import annotations

from datetime import UTC, date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import (
    CierreDiario,
    Compra,
    CompraOro,
    GastoOperativo,
    GasolinaReposicion,
    Salida,
    Venta,
    VentaGasolina,
)
from routers.deps import require_admin
from schemas import CierreGenerarCreate
from services.calculos import CalculosMonetarios


router = APIRouter(prefix="/cierre", tags=["Cierre"])


def _ganancia_neta_dia(db: Session, inicio: datetime) -> float:
    """Misma formula que el dashboard de reportes para el dia `inicio`."""
    ventas_hoy_oro = float(
        db.query(func.coalesce(func.sum(Venta.total_oro), 0)).filter(Venta.fecha >= inicio).scalar() or 0
    )
    compras_hoy_oro = float(
        db.query(func.coalesce(func.sum(Compra.total_oro), 0)).filter(Compra.fecha >= inicio).scalar() or 0
    )
    salidas_hoy_oro = float(
        db.query(func.coalesce(func.sum(Salida.valor_oro), 0)).filter(Salida.fecha >= inicio).scalar() or 0
    )
    gasolina_hoy_oro = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gastos_hoy_reales = float(
        db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0))
        .filter(GastoOperativo.fecha >= inicio)
        .scalar()
        or 0
    )
    tasa_ref = CalculosMonetarios.obtener_tasa_referencia(db)
    gastos_hoy_oro = (
        float(CalculosMonetarios.reales_a_oro(gastos_hoy_reales, db, tasa=tasa_ref)) if gastos_hoy_reales > 0 else 0.0
    )
    return round(ventas_hoy_oro - compras_hoy_oro - salidas_hoy_oro + gasolina_hoy_oro - gastos_hoy_oro, 2)


def construir_payload_cierre(db: Session, inicio: datetime, saldo_inicial_reales: float) -> dict:
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
        "_totales_cierre_row": {
            "total_oro": round(ventas_oro + gas_ventas_oro, 2),
            "total_reales": round(ventas_reales + gas_ventas_reales, 2),
            "gastos": round(gastos_total, 2),
            "ganancia_neta": _ganancia_neta_dia(db, inicio),
        },
    }


@router.get("/dia")
def cierre_del_dia(
    saldo_inicial_reales: float = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    inicio = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    data = construir_payload_cierre(db, inicio, saldo_inicial_reales)
    data.pop("_totales_cierre_row", None)
    return data


@router.post("/generar")
def generar_cierre_diario(
    payload: CierreGenerarCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Persiste un cierre unico por fecha calendario (servidor). Requiere cabecera X-Bodega-Rol: admin."""
    inicio = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    fe: date = inicio.date()
    if db.query(CierreDiario).filter(CierreDiario.fecha == fe).first():
        raise HTTPException(status_code=400, detail="El cierre de hoy ya fue generado")

    data = construir_payload_cierre(db, inicio, payload.saldo_inicial_reales)
    tot = data.pop("_totales_cierre_row")

    row = CierreDiario(
        fecha=fe,
        total_oro=float(tot["total_oro"]),
        total_reales=float(tot["total_reales"]),
        gastos=float(tot["gastos"]),
        ganancia_neta=float(tot["ganancia_neta"]),
        cerrado_por=payload.cerrado_por.strip()[:100],
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    return {
        "status": "success",
        "cierre_id": row.id,
        "fecha": fe.isoformat(),
        "cerrado_por": row.cerrado_por,
        "totales_guardados": tot,
        "detalle": data,
    }
