"""Historial operativo filtrado por día/mes/año (últimos N registros)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    Compra,
    DetalleCompra,
    GasolinaReposicion,
    PagoVenta,
    Salida,
    Venta,
    VentaGasolina,
)
from services.calculos import equivalencia_pago_reales
from services.historial_filtro import rango_filtro_historial
from services.query_operativa import venta_no_anulada


router = APIRouter(prefix="/historial", tags=["Historial"])


def _filtros_fecha(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
) -> tuple[int | None, int | None, int | None]:
    return anio, mes, dia


@router.get("/compras")
def historial_compras(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    rows = (
        db.query(Compra)
        .options(joinedload(Compra.detalles).joinedload(DetalleCompra.producto))
        .filter(Compra.fecha >= inicio, Compra.fecha < fin)
        .order_by(Compra.fecha.desc(), Compra.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": c.id,
            "fecha": c.fecha,
            "proveedor": c.proveedor,
            "total_reales": float(c.total_reales),
            "tipo_pago_compra": c.tipo_pago_compra or "contado",
            "producto": c.detalles[0].producto.nombre if c.detalles and c.detalles[0].producto else None,
        }
        for c in rows
    ]


@router.get("/ventas")
def historial_ventas(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    rows = (
        db.query(Venta)
        .options(joinedload(Venta.tasa_cambio))
        .filter(Venta.fecha >= inicio, Venta.fecha < fin, venta_no_anulada())
        .order_by(Venta.fecha.desc(), Venta.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": v.id,
            "fecha": v.fecha,
            "cliente": v.cliente,
            "total_reales": float(v.total_reales),
            "total_oro": float(v.total_oro),
            "tipo_pago": v.tipo_pago,
            "estado_pago": v.estado_pago,
        }
        for v in rows
    ]


@router.get("/cobros")
def historial_cobros(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    rows = (
        db.query(PagoVenta)
        .join(Venta, PagoVenta.venta_id == Venta.id)
        .options(joinedload(PagoVenta.venta))
        .filter(PagoVenta.fecha >= inicio, PagoVenta.fecha < fin, venta_no_anulada())
        .order_by(PagoVenta.fecha.desc(), PagoVenta.id.desc())
        .limit(limit)
        .all()
    )
    out = []
    for p in rows:
        v = p.venta
        out.append(
            {
                "id": p.id,
                "fecha": p.fecha,
                "venta_id": p.venta_id,
                "cliente": v.cliente if v else "",
                "tipo_pago": p.tipo_pago,
                "monto": float(p.monto),
                "moneda": p.moneda,
                "monto_reales_equivalente": equivalencia_pago_reales(db, p),
            }
        )
    return out


@router.get("/salidas")
def historial_salidas(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    rows = (
        db.query(Salida)
        .options(joinedload(Salida.producto))
        .filter(Salida.fecha >= inicio, Salida.fecha < fin)
        .order_by(Salida.fecha.desc(), Salida.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": s.id,
            "fecha": s.fecha,
            "motivo": s.motivo,
            "producto": s.producto.nombre if s.producto else None,
            "cantidad": float(s.cantidad),
            "valor_oro": float(s.valor_oro),
        }
        for s in rows
    ]


@router.get("/gasolina")
def historial_gasolina(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    ventas = (
        db.query(VentaGasolina)
        .options(joinedload(VentaGasolina.tasa_cambio))
        .filter(VentaGasolina.fecha >= inicio, VentaGasolina.fecha < fin)
        .order_by(VentaGasolina.fecha.desc(), VentaGasolina.id.desc())
        .limit(limit)
        .all()
    )
    repos = (
        db.query(GasolinaReposicion)
        .filter(GasolinaReposicion.fecha >= inicio, GasolinaReposicion.fecha < fin)
        .order_by(GasolinaReposicion.fecha.desc(), GasolinaReposicion.id.desc())
        .limit(limit)
        .all()
    )
    return {
        "ventas": [
            {
                "id": v.id,
                "fecha": v.fecha,
                "litros": float(v.litros),
                "total_reales": float(v.total_reales),
                "total_oro": float(v.total_oro),
                "tipo_pago": v.tipo_pago,
            }
            for v in ventas
        ],
        "reposiciones": [
            {
                "id": r.id,
                "fecha": r.fecha,
                "litros": float(r.litros),
                "precio_reales_litro": float(r.precio_reales_litro),
                "total_reales": float(r.litros * r.precio_reales_litro),
            }
            for r in repos
        ],
    }
