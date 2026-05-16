"""Oro asignado a lotes de fundición (retirado del balance operativo)."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import LoteOro


def origen_lote_desde_cierre(fecha: date) -> str:
    return f"Cierre del {fecha.isoformat()}"


def _inicio_dia(fecha: date) -> datetime:
    return datetime(fecha.year, fecha.month, fecha.day, tzinfo=UTC).replace(tzinfo=None)


def _fin_dia(fecha: date) -> datetime:
    return _inicio_dia(fecha) + timedelta(days=1)


def gramos_oro_en_lotes(db: Session, fecha: date | None = None) -> float:
    """
    Suma de gramos brutos en lotes.

    Si `fecha` se indica, solo lotes creados ese día operativo (por `fecha` del lote).
    Los lotes de días anteriores no descuentan del oro disponible de hoy.
    """
    q = db.query(func.coalesce(func.sum(LoteOro.gramos_brutos), 0))
    if fecha is not None:
        inicio = _inicio_dia(fecha)
        fin = _fin_dia(fecha)
        q = q.filter(LoteOro.fecha >= inicio, LoteOro.fecha < fin)
    total = q.scalar() or 0
    return round(float(total), 4)


def oro_disponible_recolectado(db: Session, fecha: date, bruto_recolectado: float) -> float:
    """Oro recolectado del día menos lotes ya asignados hoy."""
    asignado = gramos_oro_en_lotes(db, fecha)
    return round(max(0.0, float(bruto_recolectado) - asignado), 4)


def lote_cierre_del_dia(db: Session, fecha: date) -> LoteOro | None:
    return (
        db.query(LoteOro)
        .filter(LoteOro.origen == origen_lote_desde_cierre(fecha))
        .first()
    )


def eliminar_lote_cierre_si_posible(db: Session, fecha: date) -> None:
    """Al reabrir el día: quita el lote auto-creado si aún no tiene fundición."""
    lote = lote_cierre_del_dia(db, fecha)
    if not lote:
        return
    if lote.fundiciones:
        raise ValueError(
            "No se puede reabrir: el lote de fundicion del cierre ya tiene operaciones"
        )
    db.delete(lote)
