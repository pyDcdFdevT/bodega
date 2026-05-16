"""Estado de resultados (P&L) por mes."""

from __future__ import annotations

import calendar
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Activo, DetalleVenta, GastoOperativo, GasolinaReposicion, Producto, Venta, VentaGasolina
from services.depreciacion import _meses_depreciados, calcular_depreciacion_mensual
from services.query_operativa import venta_no_anulada

_MESES = (
    "Enero",
    "Febrero",
    "Marzo",
    "Abril",
    "Mayo",
    "Junio",
    "Julio",
    "Agosto",
    "Septiembre",
    "Octubre",
    "Noviembre",
    "Diciembre",
)

_ETIQUETAS_GASTO = {
    "viaje": "Viajes",
    "comida": "Comida",
    "repuestos": "Repuestos",
    "estadia": "Estadia",
    "insumos": "Insumos",
    "otro": "Otro",
}

_ORDEN_GASTOS = ("viaje", "comida", "repuestos", "estadia", "insumos", "otro")


def _rango_mes(mes: int, anio: int) -> tuple[datetime, datetime]:
    ultimo = calendar.monthrange(anio, mes)[1]
    inicio = datetime(anio, mes, 1, tzinfo=UTC).replace(tzinfo=None)
    fin = datetime(anio, mes, ultimo, 23, 59, 59, 999999, tzinfo=UTC).replace(tzinfo=None)
    return inicio, fin


def _linea(concepto: str, monto: float) -> dict:
    return {"concepto": concepto, "monto": round(float(monto), 2)}


def _costo_mercancia_periodo(db: Session, inicio: datetime, fin: datetime) -> float:
    filas = (
        db.query(DetalleVenta, Venta, Producto)
        .join(Venta, DetalleVenta.venta_id == Venta.id)
        .join(Producto, DetalleVenta.producto_id == Producto.id)
        .filter(venta_no_anulada(), Venta.fecha >= inicio, Venta.fecha <= fin)
        .all()
    )
    costo = 0.0
    for det, _venta, producto in filas:
        cantidad = float(det.cantidad)
        costo_u = float(det.costo_unitario_reales or 0)
        if costo_u <= 0:
            costo_u = float(producto.costo_promedio_reales or producto.precio_costo_reales or 0)
        costo += costo_u * cantidad
    return round(costo, 2)


def _depreciacion_periodo_mes(db: Session, mes: int, anio: int) -> float:
    primer = date(anio, mes, 1)
    ultimo = date(anio, mes, calendar.monthrange(anio, mes)[1])
    antes_mes = primer - timedelta(days=1)
    total = 0.0
    for activo in db.query(Activo).all():
        f_activo = activo.fecha.date() if activo.fecha else ultimo
        if f_activo > ultimo:
            continue
        dep_m = float(activo.depreciacion_mensual or 0)
        if dep_m <= 0:
            dep_m = calcular_depreciacion_mensual(
                float(activo.monto_reales),
                float(activo.valor_residual or 0),
                int(activo.vida_util_anios or 5),
            )
        meses_fin = _meses_depreciados(activo.fecha, ultimo)
        meses_ini = _meses_depreciados(activo.fecha, antes_mes) if antes_mes >= f_activo else 0
        if meses_fin > meses_ini:
            total += dep_m
    return round(total, 2)


def build_estado_resultados(db: Session, mes: int, anio: int) -> dict:
    inicio, fin = _rango_mes(mes, anio)

    ventas_bodega = float(
        db.query(func.coalesce(func.sum(Venta.total_reales), 0))
        .filter(Venta.fecha >= inicio, Venta.fecha <= fin, venta_no_anulada())
        .scalar()
        or 0
    )
    ventas_gasolina = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_reales), 0))
        .filter(VentaGasolina.fecha >= inicio, VentaGasolina.fecha <= fin)
        .scalar()
        or 0
    )
    total_ingresos = round(ventas_bodega + ventas_gasolina, 2)

    costo_mercancia = _costo_mercancia_periodo(db, inicio, fin)

    costo_gasolina = float(
        db.query(func.coalesce(func.sum(GasolinaReposicion.total_reales), 0))
        .filter(GasolinaReposicion.fecha >= inicio, GasolinaReposicion.fecha <= fin)
        .scalar()
        or 0
    )
    total_costo_ventas = round(costo_mercancia + costo_gasolina, 2)
    utilidad_bruta = round(total_ingresos - total_costo_ventas, 2)

    gastos_map: dict[str, float] = {k: 0.0 for k in _ORDEN_GASTOS}
    rows_gasto = (
        db.query(GastoOperativo.categoria, func.coalesce(func.sum(GastoOperativo.monto_reales), 0))
        .filter(GastoOperativo.fecha >= inicio, GastoOperativo.fecha <= fin)
        .group_by(GastoOperativo.categoria)
        .all()
    )
    for cat, monto in rows_gasto:
        key = str(cat or "otro").strip().lower()
        if key not in gastos_map:
            gastos_map[key] = 0.0
        gastos_map[key] += float(monto)

    depreciacion = _depreciacion_periodo_mes(db, mes, anio)

    lineas_gastos: list[dict] = [
        _linea("Viajes", gastos_map.get("viaje", 0.0)),
        _linea("Comida", gastos_map.get("comida", 0.0)),
        _linea("Repuestos", gastos_map.get("repuestos", 0.0)),
    ]
    for key in ("estadia", "insumos", "otro"):
        m = gastos_map.get(key, 0.0)
        if m > 0.009:
            lineas_gastos.append(_linea(_ETIQUETAS_GASTO[key], m))
    lineas_gastos.append(_linea("Depreciacion", depreciacion))

    total_gastos_op = round(sum(float(l["monto"]) for l in lineas_gastos), 2)
    utilidad_neta = round(utilidad_bruta - total_gastos_op, 2)

    return {
        "periodo": {
            "mes": mes,
            "anio": anio,
            "mes_nombre": _MESES[mes - 1],
            "etiqueta": f"{_MESES[mes - 1]} {anio}",
            "desde": inicio.date().isoformat(),
            "hasta": fin.date().isoformat(),
        },
        "ingresos_operacionales": {
            "titulo": "INGRESOS OPERACIONALES",
            "lineas": [
                _linea("Ventas bodega", ventas_bodega),
                _linea("Ventas gasolina", ventas_gasolina),
            ],
            "total": total_ingresos,
        },
        "costo_ventas": {
            "titulo": "(-) COSTO DE VENTAS",
            "lineas": [
                _linea("Costo mercancia (CPP)", costo_mercancia),
                _linea("Costo gasolina", costo_gasolina),
            ],
            "total": total_costo_ventas,
            "utilidad_bruta": utilidad_bruta,
        },
        "gastos_operativos": {
            "titulo": "(-) GASTOS OPERATIVOS",
            "lineas": lineas_gastos,
            "total": total_gastos_op,
        },
        "utilidad_neta": utilidad_neta,
    }
