from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    Activo,
    Compra,
    Gasolina,
    GasolinaReposicion,
    GastoOperativo,
    LogTasaCambio,
    MovimientoInventario,
    Producto,
    Salida,
    Venta,
    VentaGasolina,
)
from routers.productos import serializar_producto
from services.balance import build_balance_general
from services.cuentas_por_pagar import build_cuentas_por_pagar
from services.depreciacion import build_reporte_depreciacion
from services.calculos import CalculosMonetarios, ganancia_neta_dia
from services.estado_resultados import build_estado_resultados
from services.reporte_periodo import build_reporte_anual, build_reporte_mensual
from services.query_operativa import compra_no_anulada, venta_no_anulada


router = APIRouter(prefix="/reportes", tags=["Dashboard"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    inicio_hoy = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    total_productos = db.query(func.count(Producto.id)).filter(Producto.activo.is_(True)).scalar() or 0
    stock_bajo = (
        db.query(func.count(Producto.id))
        .filter(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_minimo)
        .scalar()
        or 0
    )
    valor_stock_reales = (
        db.query(
            func.coalesce(
                func.sum(
                    Producto.stock_actual
                    * func.coalesce(Producto.costo_promedio_reales, Producto.precio_costo_reales, 0)
                ),
                0,
            )
        )
        .filter(Producto.activo.is_(True))
        .scalar()
        or 0
    )
    valor_stock_oro = (
        db.query(func.coalesce(func.sum(Producto.stock_actual * Producto.precio_costo_oro), 0))
        .filter(Producto.activo.is_(True))
        .scalar()
        or 0
    )
    ventas_hoy_oro = (
        db.query(func.coalesce(func.sum(Venta.total_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, venta_no_anulada())
        .scalar()
        or 0
    )
    compras_hoy_oro = (
        db.query(func.coalesce(func.sum(Compra.total_oro), 0))
        .filter(Compra.fecha >= inicio_hoy, compra_no_anulada())
        .scalar()
        or 0
    )
    salidas_hoy_oro = db.query(func.coalesce(func.sum(Salida.valor_oro), 0)).filter(Salida.fecha >= inicio_hoy).scalar() or 0
    gasolina_hoy_oro = (
        db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0))
        .filter(VentaGasolina.fecha >= inicio_hoy)
        .scalar()
        or 0
    )
    ventas_hoy_reales = (
        db.query(func.coalesce(func.sum(Venta.total_reales), 0))
        .filter(Venta.fecha >= inicio_hoy, venta_no_anulada())
        .scalar()
        or 0
    )
    oro_araparita = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "araparita", venta_no_anulada())
        .scalar()
        or 0
    )
    oro_uruman = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "uruman", venta_no_anulada())
        .scalar()
        or 0
    )
    oro_santa_elena_minero = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "santa_elena_minero", venta_no_anulada())
        .scalar()
        or 0
    )
    oro_santa_elena_fundido = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "santa_elena_fundido", venta_no_anulada())
        .scalar()
        or 0
    )
    gastos_hoy_reales = float(
        db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0))
        .filter(GastoOperativo.fecha >= inicio_hoy)
        .scalar()
        or 0
    )
    tasa_ref = CalculosMonetarios.obtener_tasa_referencia(db)
    gastos_hoy_oro = (
        CalculosMonetarios.reales_a_oro(gastos_hoy_reales, db, tasa=tasa_ref) if gastos_hoy_reales > 0 else 0.0
    )
    oro_total = oro_araparita + oro_uruman + oro_santa_elena_minero + oro_santa_elena_fundido
    ganancia_neta = ganancia_neta_dia(
        float(ventas_hoy_oro),
        float(compras_hoy_oro),
        float(salidas_hoy_oro),
        float(gasolina_hoy_oro),
        float(gastos_hoy_oro),
    )

    compras_hoy_reales = (
        float(
            db.query(func.coalesce(func.sum(Compra.total_reales), 0))
            .filter(Compra.fecha >= inicio_hoy, compra_no_anulada())
            .scalar()
            or 0
        )
    )
    activos_hoy_reales = float(
        db.query(func.coalesce(func.sum(Activo.monto_reales), 0))
        .filter(Activo.fecha >= inicio_hoy)
        .scalar()
        or 0
    )
    ganancia_neta_reales = round(
        float(ventas_hoy_reales) - compras_hoy_reales - gastos_hoy_reales - activos_hoy_reales,
        2,
    )
    stock_bajo_rows = (
        db.query(Producto)
        .filter(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_minimo)
        .order_by(Producto.stock_actual.asc())
        .limit(15)
        .all()
    )
    stock_bajo_alertas = [
        {"nombre": p.nombre, "stock": round(float(p.stock_actual), 3), "minimo": round(float(p.stock_minimo), 3)}
        for p in stock_bajo_rows
    ]
    ultimas_ventas = (
        db.query(Venta).filter(Venta.fecha >= inicio_hoy).order_by(Venta.fecha.desc(), Venta.id.desc()).limit(5).all()
    )
    ultimas_ventas_out = [
        {
            "id": v.id,
            "cliente": v.cliente,
            "total_reales": round(float(v.total_reales), 2),
            "total_oro": round(float(v.total_oro), 2),
            "estado": v.estado or "VIGENTE",
            "fecha": v.fecha.isoformat() if v.fecha else None,
        }
        for v in ultimas_ventas
    ]
    ultimos_mov = (
        db.query(MovimientoInventario)
        .options(joinedload(MovimientoInventario.producto))
        .filter(MovimientoInventario.fecha >= inicio_hoy)
        .order_by(MovimientoInventario.fecha.desc(), MovimientoInventario.id.desc())
        .limit(5)
        .all()
    )
    ultimos_mov_out = [
        {
            "id": m.id,
            "producto": m.producto.nombre if m.producto else None,
            "tipo": m.tipo,
            "cantidad": m.cantidad,
            "fecha": m.fecha.isoformat() if m.fecha else None,
        }
        for m in ultimos_mov
    ]

    return {
        "fecha": inicio_hoy.date().isoformat(),
        "inventario": {
            "productos_activos": total_productos,
            "stock_bajo": stock_bajo,
            "stock_bajo_alertas": stock_bajo_alertas,
            "valor_stock_reales": round(valor_stock_reales, 2),
            "valor_stock_oro": round(valor_stock_oro, 2),
        },
        "operaciones_hoy": {
            "ventas_oro": round(ventas_hoy_oro, 2),
            "ventas_reales": round(ventas_hoy_reales, 2),
            "compras_oro": round(compras_hoy_oro, 2),
            "compras_reales": round(compras_hoy_reales, 2),
            "salidas_oro": round(salidas_hoy_oro, 2),
            "gasolina_oro": round(gasolina_hoy_oro, 2),
            "oro_araparita": round(oro_araparita, 2),
            "oro_uruman": round(oro_uruman, 2),
            "oro_santa_elena_minero": round(oro_santa_elena_minero, 2),
            "oro_santa_elena_fundido": round(oro_santa_elena_fundido, 2),
            "oro_total": round(oro_total, 2),
            "gastos_reales": round(gastos_hoy_reales, 2),
            "gastos_oro_equiv": round(gastos_hoy_oro, 2),
            "activos_reales": round(activos_hoy_reales, 2),
            "ganancia_neta": ganancia_neta,
            "ganancia_neta_reales": ganancia_neta_reales,
        },
        "ultimas_ventas": ultimas_ventas_out,
        "ultimos_movimientos": ultimos_mov_out,
    }


@router.get("/balance")
def balance_general(db: Session = Depends(get_db)):
    """Balance general: activos, pasivos (cuentas por pagar) y patrimonio."""
    return build_balance_general(db)


@router.get("/cuentas-por-pagar")
def cuentas_por_pagar(db: Session = Depends(get_db)):
    """Compras a crédito vigentes, agrupadas por proveedor."""
    return build_cuentas_por_pagar(db)


@router.get("/depreciacion")
def reporte_depreciacion(db: Session = Depends(get_db)):
    """Activos fijos con depreciación mensual, acumulada y valor actual."""
    rows = db.query(Activo).order_by(Activo.fecha.desc(), Activo.id.desc()).all()
    return build_reporte_depreciacion(rows)


@router.get("/estado-resultados")
def estado_resultados(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    """Estado de resultados (P&L) del mes: ingresos, costos, gastos y utilidad neta."""
    return build_estado_resultados(db, mes, anio)


@router.get("/mensual")
def reporte_mensual(
    mes: int = Query(..., ge=1, le=12),
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    """Suma cierres diarios del mes: ventas, compras, gastos, oro y ganancia neta."""
    return build_reporte_mensual(db, mes, anio)


@router.get("/anual")
def reporte_anual(
    anio: int = Query(..., ge=2000, le=2100),
    db: Session = Depends(get_db),
):
    """Suma cierres diarios del año, con desglose por mes."""
    return build_reporte_anual(db, anio)


@router.get("/gasolina")
def reporte_gasolina(db: Session = Depends(get_db)):
    inicio_hoy = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    gasolina = db.query(Gasolina).order_by(Gasolina.id.asc()).first()
    litros_disponibles = float(gasolina.litros_disponibles) if gasolina else 0.0

    litros_vendidos_hoy = (
        float(db.query(func.coalesce(func.sum(VentaGasolina.litros), 0)).filter(VentaGasolina.fecha >= inicio_hoy).scalar() or 0)
    )
    litros_repuestos_hoy = (
        float(db.query(func.coalesce(func.sum(GasolinaReposicion.litros), 0)).filter(GasolinaReposicion.fecha >= inicio_hoy).scalar() or 0)
    )
    ventas_hoy_oro = (
        float(db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0)).filter(VentaGasolina.fecha >= inicio_hoy).scalar() or 0)
    )
    ventas_hoy_reales = (
        float(db.query(func.coalesce(func.sum(VentaGasolina.total_reales), 0)).filter(VentaGasolina.fecha >= inicio_hoy).scalar() or 0)
    )
    reposicion_hoy_reales = (
        float(db.query(func.coalesce(func.sum(GasolinaReposicion.total_reales), 0)).filter(GasolinaReposicion.fecha >= inicio_hoy).scalar() or 0)
    )
    reposicion_hoy_oro = (
        float(db.query(func.coalesce(func.sum(GasolinaReposicion.total_oro), 0)).filter(GasolinaReposicion.fecha >= inicio_hoy).scalar() or 0)
    )
    ganancia_reales = round(ventas_hoy_reales - reposicion_hoy_reales, 2)
    ganancia_oro = round(ventas_hoy_oro - reposicion_hoy_oro, 2)

    return {
        "fecha": inicio_hoy.date().isoformat(),
        "litros_disponibles": round(litros_disponibles, 3),
        "hoy": {
            "litros_vendidos": round(litros_vendidos_hoy, 3),
            "litros_repuestos": round(litros_repuestos_hoy, 3),
            "total_ventas_oro": round(ventas_hoy_oro, 2),
            "total_ventas_reales": round(ventas_hoy_reales, 2),
            "total_reposicion_reales": round(reposicion_hoy_reales, 2),
            "total_reposicion_oro": round(reposicion_hoy_oro, 2),
            "ganancia_reales": ganancia_reales,
            "ganancia_oro": ganancia_oro,
        },
    }


@router.get("/inventario")
def reporte_inventario(db: Session = Depends(get_db)):
    productos = (
        db.query(Producto)
        .options(joinedload(Producto.categoria_rel))
        .filter(Producto.activo.is_(True))
        .order_by(Producto.nombre.asc())
        .all()
    )
    return [serializar_producto(producto) for producto in productos]


@router.get("/ventas")
def reporte_ventas(dias: int = Query(default=7, ge=1, le=90), db: Session = Depends(get_db)):
    desde = datetime.now(UTC) - timedelta(days=dias)
    ventas = (
        db.query(Venta)
        .filter(Venta.fecha >= desde, venta_no_anulada())
        .order_by(Venta.fecha.desc())
        .all()
    )
    total_oro = sum(float(v.total_oro) for v in ventas)
    total_reales = sum(float(v.total_reales) for v in ventas)
    return {
        "desde": desde.isoformat(),
        "cantidad": len(ventas),
        "total_oro": round(total_oro, 2),
        "total_reales": round(total_reales, 2),
        "ventas": ventas,
    }


@router.get("/compras")
def reporte_compras(dias: int = Query(default=7, ge=1, le=90), db: Session = Depends(get_db)):
    desde = datetime.now(UTC) - timedelta(days=dias)
    compras = (
        db.query(Compra)
        .filter(Compra.fecha >= desde, compra_no_anulada())
        .order_by(Compra.fecha.desc())
        .all()
    )
    total_oro = sum(float(c.total_oro) for c in compras)
    total_reales = sum(float(c.total_reales) for c in compras)
    return {
        "desde": desde.isoformat(),
        "cantidad": len(compras),
        "total_oro": round(total_oro, 2),
        "total_reales": round(total_reales, 2),
        "compras": compras,
    }


@router.get("/movimientos")
def reporte_movimientos(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    movimientos = (
        db.query(MovimientoInventario)
        .options(joinedload(MovimientoInventario.producto))
        .order_by(MovimientoInventario.fecha.desc(), MovimientoInventario.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": movimiento.id,
            "producto_id": movimiento.producto_id,
            "producto": movimiento.producto.nombre if movimiento.producto else None,
            "tipo": movimiento.tipo,
            "cantidad": movimiento.cantidad,
            "stock_anterior": movimiento.stock_anterior,
            "stock_nuevo": movimiento.stock_nuevo,
            "motivo": movimiento.motivo,
            "fecha": movimiento.fecha,
        }
        for movimiento in movimientos
    ]


@router.get("/tasas")
def reporte_tasas(limit: int = Query(default=30, ge=1, le=200), db: Session = Depends(get_db)):
    return (
        db.query(LogTasaCambio)
        .order_by(LogTasaCambio.fecha_cambio.desc(), LogTasaCambio.id.desc())
        .limit(limit)
        .all()
    )
