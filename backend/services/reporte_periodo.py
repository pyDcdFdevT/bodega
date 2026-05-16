"""Agregación de cierres diarios para reportes mensual y anual."""

from __future__ import annotations

import calendar
import json
from datetime import date

from sqlalchemy.orm import Session

from models import CierreDiario

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


def _rango_mes(mes: int, anio: int) -> tuple[date, date]:
    ultimo = calendar.monthrange(anio, mes)[1]
    return date(anio, mes, 1), date(anio, mes, ultimo)


def _rango_anio(anio: int) -> tuple[date, date]:
    return date(anio, 1, 1), date(anio, 12, 31)


def _vacios() -> dict:
    return {
        "ventas_reales": 0.0,
        "ventas_oro": 0.0,
        "compras_reales": 0.0,
        "gastos_reales": 0.0,
        "oro_recolectado": 0.0,
        "ganancia_neta_oro": 0.0,
        "ganancia_neta_reales": 0.0,
        "dias_con_cierre": 0,
        "bodega": {
            "ventas_reales": 0.0,
            "ventas_oro": 0.0,
            "compras_mercancia_reales": 0.0,
            "salidas_reales": 0.0,
        },
        "gasolina": {
            "ventas_reales": 0.0,
            "ventas_oro": 0.0,
            "reposicion_reales": 0.0,
        },
        "compra_oro": {"gramos": 0.0, "reales_usados": 0.0},
        "oro_recolectado_detalle": {
            "araparita": 0.0,
            "uruman": 0.0,
            "santa_elena_minero": 0.0,
            "santa_elena_fundido": 0.0,
            "comprado_gramos": 0.0,
            "bruto_total_gramos": 0.0,
        },
    }


def _sumar_snapshot(dest: dict, snap: dict) -> None:
    b = snap.get("bodega") or {}
    g = snap.get("gasolina") or {}
    co = snap.get("compra_oro") or {}
    oro = snap.get("oro_recolectado") or {}

    dest["bodega"]["ventas_reales"] += float(b.get("ventas_reales") or 0)
    dest["bodega"]["ventas_oro"] += float(b.get("ventas_oro") or 0)
    dest["bodega"]["compras_mercancia_reales"] += float(b.get("compras_mercancia_reales") or 0)
    dest["bodega"]["salidas_reales"] += float(b.get("salidas_reales") or b.get("salidas_oro") or 0)

    dest["gasolina"]["ventas_reales"] += float(g.get("ventas_reales") or 0)
    dest["gasolina"]["ventas_oro"] += float(g.get("ventas_oro") or 0)
    dest["gasolina"]["reposicion_reales"] += float(g.get("reposicion_reales") or 0)

    dest["compra_oro"]["gramos"] += float(co.get("gramos") or 0)
    dest["compra_oro"]["reales_usados"] += float(co.get("reales_usados") or 0)

    od = dest["oro_recolectado_detalle"]
    od["araparita"] += float(oro.get("araparita") or 0)
    od["uruman"] += float(oro.get("uruman") or 0)
    od["santa_elena_minero"] += float(oro.get("santa_elena_minero") or 0)
    od["santa_elena_fundido"] += float(oro.get("santa_elena_fundido") or 0)
    od["comprado_gramos"] += float(oro.get("comprado_gramos") or 0)
    od["bruto_total_gramos"] += float(oro.get("bruto_total_gramos") or 0)

    if snap.get("ganancia_neta_dia") is not None:
        dest["ganancia_neta_oro"] += float(snap["ganancia_neta_dia"])
    if snap.get("ganancia_neta_cpp_reales") is not None:
        dest["ganancia_neta_reales"] += float(snap["ganancia_neta_cpp_reales"])


def _redondear_totales(t: dict) -> dict:
    for key in ("ventas_reales", "ventas_oro", "compras_reales", "gastos_reales", "oro_recolectado"):
        t[key] = round(float(t[key]), 2)
    t["ganancia_neta_oro"] = round(float(t["ganancia_neta_oro"]), 2)
    t["ganancia_neta_reales"] = round(float(t["ganancia_neta_reales"]), 2)
    for block in (t["bodega"], t["gasolina"], t["compra_oro"]):
        for k in block:
            block[k] = round(float(block[k]), 2)
    for k in t["oro_recolectado_detalle"]:
        t["oro_recolectado_detalle"][k] = round(float(t["oro_recolectado_detalle"][k]), 2)
    return t


def agregar_cierres(cierres: list[CierreDiario]) -> dict:
    t = _vacios()
    t["dias_con_cierre"] = len(cierres)
    tiene_ganancia_snap = False

    for c in cierres:
        t["ventas_reales"] += float(c.ventas_reales)
        t["ventas_oro"] += float(c.ventas_oro)
        t["compras_reales"] += float(c.compras_reales)
        t["gastos_reales"] += float(c.gastos_reales)
        t["oro_recolectado"] += float(c.oro_recolectado)

        if c.snapshot_json:
            try:
                snap = json.loads(c.snapshot_json)
                if isinstance(snap, dict):
                    _sumar_snapshot(t, snap)
                    if snap.get("ganancia_neta_dia") is not None or snap.get("ganancia_neta_cpp_reales") is not None:
                        tiene_ganancia_snap = True
            except (json.JSONDecodeError, TypeError):
                pass

    if not tiene_ganancia_snap and t["dias_con_cierre"] > 0:
        t["ganancia_neta_reales"] = (
            t["ventas_reales"] - t["compras_reales"] - t["gastos_reales"] - t["bodega"]["salidas_reales"]
        )

    return _redondear_totales(t)


def _cierres_en_rango(db: Session, desde: date, hasta: date) -> list[CierreDiario]:
    return (
        db.query(CierreDiario)
        .filter(
            CierreDiario.fecha_operativa >= desde,
            CierreDiario.fecha_operativa <= hasta,
        )
        .order_by(CierreDiario.fecha_operativa.asc())
        .all()
    )


def build_reporte_mensual(db: Session, mes: int, anio: int) -> dict:
    desde, hasta = _rango_mes(mes, anio)
    cierres = _cierres_en_rango(db, desde, hasta)
    totales = agregar_cierres(cierres)
    return {
        "periodo": "mensual",
        "mes": mes,
        "anio": anio,
        "mes_nombre": _MESES[mes - 1],
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "totales": totales,
        "cierres": [
            {
                "fecha_operativa": c.fecha_operativa.isoformat(),
                "ventas_reales": float(c.ventas_reales),
                "compras_reales": float(c.compras_reales),
                "gastos_reales": float(c.gastos_reales),
                "oro_recolectado": float(c.oro_recolectado),
            }
            for c in cierres
        ],
    }


def build_reporte_anual(db: Session, anio: int) -> dict:
    desde, hasta = _rango_anio(anio)
    cierres = _cierres_en_rango(db, desde, hasta)
    totales = agregar_cierres(cierres)

    por_mes: dict[int, list[CierreDiario]] = {m: [] for m in range(1, 13)}
    for c in cierres:
        por_mes[c.fecha_operativa.month].append(c)

    meses = []
    for m in range(1, 13):
        sub = por_mes[m]
        if not sub:
            continue
        t_mes = agregar_cierres(sub)
        meses.append(
            {
                "mes": m,
                "mes_nombre": _MESES[m - 1],
                "dias_con_cierre": t_mes["dias_con_cierre"],
                "ventas_reales": t_mes["ventas_reales"],
                "compras_reales": t_mes["compras_reales"],
                "gastos_reales": t_mes["gastos_reales"],
                "oro_recolectado": t_mes["oro_recolectado"],
                "ganancia_neta_reales": t_mes["ganancia_neta_reales"],
                "ganancia_neta_oro": t_mes["ganancia_neta_oro"],
            }
        )

    return {
        "periodo": "anual",
        "anio": anio,
        "desde": desde.isoformat(),
        "hasta": hasta.isoformat(),
        "totales": totales,
        "meses": meses,
    }
