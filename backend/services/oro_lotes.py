"""Oro asignado a lotes de fundición (retirado del balance operativo)."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import LoteOro


def origen_lote_desde_cierre(fecha: date) -> str:
    return f"Cierre del {fecha.isoformat()}"


def gramos_oro_en_lotes(db: Session) -> float:
    """Suma de gramos brutos en todos los lotes (oro ya retirado para fundición)."""
    total = (
        db.query(func.coalesce(func.sum(LoteOro.gramos_brutos), 0)).scalar() or 0
    )
    return round(float(total), 4)


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
