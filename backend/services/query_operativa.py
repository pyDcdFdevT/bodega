"""Filtros SQL reutilizables para excluir filas anuladas de totales operativos."""

from __future__ import annotations

from sqlalchemy import func

from models import Compra, Venta


def venta_no_anulada() -> object:
    return func.coalesce(Venta.estado, "VIGENTE") != "ANULADA"


def compra_no_anulada() -> object:
    return func.coalesce(Compra.estado, "VIGENTE") != "ANULADA"
