from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import Compra, Gasolina, LogTasaCambio, MovimientoInventario, Producto, Salida, Venta, VentaGasolina
from routers.productos import serializar_producto


router = APIRouter(prefix="/reportes", tags=["Reportes"])


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    inicio_hoy = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    total_productos = db.query(func.count(Producto.id)).filter(Producto.activo.is_(True)).scalar() or 0
    stock_bajo = (
        db.query(func.count(Producto.id))
        .filter(Producto.activo.is_(True), Producto.stock_actual <= Producto.stock_minimo)
        .scalar()
        or 0
    )
    valor_stock_reales = (
        db.query(func.coalesce(func.sum(Producto.stock_actual * Producto.precio_costo_reales), 0))
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
    ventas_hoy_oro = db.query(func.coalesce(func.sum(Venta.total_oro), 0)).filter(Venta.fecha >= inicio_hoy).scalar() or 0
    compras_hoy_oro = db.query(func.coalesce(func.sum(Compra.total_oro), 0)).filter(Compra.fecha >= inicio_hoy).scalar() or 0
    salidas_hoy_oro = db.query(func.coalesce(func.sum(Salida.valor_oro), 0)).filter(Salida.fecha >= inicio_hoy).scalar() or 0
    gasolina = db.query(Gasolina).order_by(Gasolina.id.asc()).first()
    gasolina_hoy_oro = (
        db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0))
        .filter(VentaGasolina.fecha >= inicio_hoy)
        .scalar()
        or 0
    )
    ventas_hoy_reales = (
        db.query(func.coalesce(func.sum(Venta.total_reales), 0))
        .filter(Venta.fecha >= inicio_hoy)
        .scalar()
        or 0
    )
    oro_araparita = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "araparita")
        .scalar()
        or 0
    )
    oro_uruman = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "uruman")
        .scalar()
        or 0
    )
    oro_santa_elena_minero = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "santa_elena_minero")
        .scalar()
        or 0
    )
    oro_santa_elena_fundido = (
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio_hoy, Venta.tipo_oro == "santa_elena_fundido")
        .scalar()
        or 0
    )
    oro_total = oro_araparita + oro_uruman + oro_santa_elena_minero + oro_santa_elena_fundido
    ganancia_neta = round(ventas_hoy_oro - compras_hoy_oro - salidas_hoy_oro, 3)

    return {
        "fecha": inicio_hoy.date().isoformat(),
        "inventario": {
            "productos_activos": total_productos,
            "stock_bajo": stock_bajo,
            "valor_stock_reales": round(valor_stock_reales, 2),
            "valor_stock_oro": round(valor_stock_oro, 3),
        },
        "operaciones_hoy": {
            "ventas_oro": round(ventas_hoy_oro, 3),
            "ventas_reales": round(ventas_hoy_reales, 2),
            "compras_oro": round(compras_hoy_oro, 3),
            "salidas_oro": round(salidas_hoy_oro, 3),
            "gasolina_oro": round(gasolina_hoy_oro, 3),
            "oro_araparita": round(oro_araparita, 3),
            "oro_uruman": round(oro_uruman, 3),
            "oro_santa_elena_minero": round(oro_santa_elena_minero, 3),
            "oro_santa_elena_fundido": round(oro_santa_elena_fundido, 3),
            "oro_total": round(oro_total, 3),
            "ganancia_neta": ganancia_neta,
        },
        "gasolina": {
            "litros_disponibles": gasolina.litros_disponibles if gasolina else 0,
            "precio_por_litro_oro": gasolina.precio_por_litro_oro if gasolina else 0,
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
    desde = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=dias)
    ventas = db.query(Venta).filter(Venta.fecha >= desde).order_by(Venta.fecha.desc()).all()
    total_oro = sum(venta.total_oro for venta in ventas)
    total_reales = sum(venta.total_reales for venta in ventas)
    return {
        "desde": desde.isoformat(),
        "cantidad": len(ventas),
        "total_oro": round(total_oro, 3),
        "total_reales": round(total_reales, 2),
        "ventas": ventas,
    }


@router.get("/compras")
def reporte_compras(dias: int = Query(default=7, ge=1, le=90), db: Session = Depends(get_db)):
    desde = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=dias)
    compras = db.query(Compra).filter(Compra.fecha >= desde).order_by(Compra.fecha.desc()).all()
    total_oro = sum(compra.total_oro for compra in compras)
    total_reales = sum(compra.total_reales for compra in compras)
    return {
        "desde": desde.isoformat(),
        "cantidad": len(compras),
        "total_oro": round(total_oro, 3),
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
