"""Historial operativo filtrado por día/mes/año y búsqueda por texto."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import (
    Compra,
    DetalleCompra,
    DetalleVenta,
    GasolinaReposicion,
    PagoVenta,
    Producto,
    Salida,
    Venta,
    VentaGasolina,
)
from services.calculos import equivalencia_pago_reales
from services.historial_busqueda import (
    HISTORIAL_LIMIT_MAX,
    filtro_ilike_columnas,
    normalizar_buscar,
    patron_ilike,
)
from services.historial_filtro import rango_filtro_historial
from services.query_operativa import venta_no_anulada


router = APIRouter(prefix="/historial", tags=["Historial"])


def _nombres_productos_venta(venta: Venta) -> str:
    nombres: list[str] = []
    for d in venta.detalles or []:
        if d.producto and d.producto.nombre:
            nombres.append(d.producto.nombre)
    return ", ".join(nombres) if nombres else "—"


@router.get("/compras")
def historial_compras(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
    buscar: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=HISTORIAL_LIMIT_MAX, ge=1, le=HISTORIAL_LIMIT_MAX),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    q = (
        db.query(Compra)
        .options(joinedload(Compra.detalles).joinedload(DetalleCompra.producto))
        .filter(Compra.fecha >= inicio, Compra.fecha < fin)
    )
    texto = normalizar_buscar(buscar)
    if texto:
        pat = patron_ilike(texto)
        q = (
            q.outerjoin(Compra.detalles)
            .outerjoin(DetalleCompra.producto)
            .filter(
                filtro_ilike_columnas(
                    pat,
                    Compra.proveedor,
                    Producto.nombre,
                )
            )
            .distinct()
        )
    rows = q.order_by(Compra.fecha.desc(), Compra.id.desc()).limit(limit).all()
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
    buscar: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=HISTORIAL_LIMIT_MAX, ge=1, le=HISTORIAL_LIMIT_MAX),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    q = (
        db.query(Venta)
        .options(joinedload(Venta.detalles).joinedload(DetalleVenta.producto))
        .filter(Venta.fecha >= inicio, Venta.fecha < fin, venta_no_anulada())
    )
    texto = normalizar_buscar(buscar)
    if texto:
        pat = patron_ilike(texto)
        q = (
            q.join(Venta.detalles)
            .join(DetalleVenta.producto)
            .filter(
                filtro_ilike_columnas(
                    pat,
                    Venta.cliente,
                    Producto.nombre,
                )
            )
            .distinct()
        )
    rows = q.order_by(Venta.fecha.desc(), Venta.id.desc()).limit(limit).all()
    return [
        {
            "id": v.id,
            "fecha": v.fecha,
            "cliente": v.cliente,
            "productos": _nombres_productos_venta(v),
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
    buscar: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=HISTORIAL_LIMIT_MAX, ge=1, le=HISTORIAL_LIMIT_MAX),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    q = (
        db.query(PagoVenta)
        .join(Venta, PagoVenta.venta_id == Venta.id)
        .options(joinedload(PagoVenta.venta))
        .filter(PagoVenta.fecha >= inicio, PagoVenta.fecha < fin, venta_no_anulada())
    )
    texto = normalizar_buscar(buscar)
    if texto:
        pat = patron_ilike(texto)
        q = q.filter(filtro_ilike_columnas(pat, Venta.cliente))
    rows = q.order_by(PagoVenta.fecha.desc(), PagoVenta.id.desc()).limit(limit).all()
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
    buscar: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=HISTORIAL_LIMIT_MAX, ge=1, le=HISTORIAL_LIMIT_MAX),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    q = (
        db.query(Salida)
        .options(joinedload(Salida.producto))
        .filter(Salida.fecha >= inicio, Salida.fecha < fin)
    )
    texto = normalizar_buscar(buscar)
    if texto:
        pat = patron_ilike(texto)
        q = q.outerjoin(Salida.producto).filter(
            filtro_ilike_columnas(
                pat,
                Salida.motivo,
                Producto.nombre,
            )
        )
    rows = q.order_by(Salida.fecha.desc(), Salida.id.desc()).limit(limit).all()
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


def _gasolina_coincide_tipo(movimiento: str, texto: str) -> bool:
    t = texto.lower()
    mov = movimiento.lower()
    if t in mov:
        return True
    if "repo" in t and "repos" in mov:
        return True
    if "venta" in t and "venta" in mov:
        return True
    return False


@router.get("/gasolina")
def historial_gasolina(
    anio: int | None = Query(default=None, ge=2000, le=2100),
    mes: int | None = Query(default=None, ge=1, le=12),
    dia: int | None = Query(default=None, ge=1, le=31),
    buscar: str | None = Query(default=None, max_length=120),
    limit: int = Query(default=HISTORIAL_LIMIT_MAX, ge=1, le=HISTORIAL_LIMIT_MAX),
    db: Session = Depends(get_db),
):
    inicio, fin = rango_filtro_historial(anio, mes, dia)
    texto = normalizar_buscar(buscar)

    incluye_ventas = not texto or _gasolina_coincide_tipo("Venta", texto)
    incluye_repos = not texto or _gasolina_coincide_tipo("Reposicion", texto)
    if incluye_ventas and not incluye_repos:
        lim_ventas, lim_repos = limit, 0
    elif incluye_repos and not incluye_ventas:
        lim_ventas, lim_repos = 0, limit
    else:
        lim_ventas = (limit + 1) // 2
        lim_repos = limit // 2

    ventas_q = (
        db.query(VentaGasolina)
        .options(joinedload(VentaGasolina.tasa_cambio))
        .filter(VentaGasolina.fecha >= inicio, VentaGasolina.fecha < fin)
    )
    if not incluye_ventas or lim_ventas == 0:
        ventas_rows = []
    else:
        ventas_rows = (
            ventas_q.order_by(VentaGasolina.fecha.desc(), VentaGasolina.id.desc())
            .limit(lim_ventas)
            .all()
        )

    repos_q = db.query(GasolinaReposicion).filter(
        GasolinaReposicion.fecha >= inicio, GasolinaReposicion.fecha < fin
    )
    if not incluye_repos or lim_repos == 0:
        repos_rows = []
    else:
        repos_rows = (
            repos_q.order_by(GasolinaReposicion.fecha.desc(), GasolinaReposicion.id.desc())
            .limit(lim_repos)
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
                "movimiento": "Venta",
            }
            for v in ventas_rows
        ],
        "reposiciones": [
            {
                "id": r.id,
                "fecha": r.fecha,
                "litros": float(r.litros),
                "precio_reales_litro": float(r.precio_reales_litro),
                "total_reales": float(r.litros * r.precio_reales_litro),
                "movimiento": "Reposicion",
            }
            for r in repos_rows
        ],
    }
