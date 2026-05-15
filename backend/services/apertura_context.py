"""Contexto de pantalla de apertura: sugerencia desde cierre de hoy o ayer y apertura de hoy."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from models import AperturaCaja, CierreDiario


def fecha_operativa_hoy() -> date:
    return datetime.now(UTC).date()


def exigir_apertura_del_dia(db: Session) -> None:
    """Ventas y movimientos de caja del día operativo requieren apertura registrada."""
    hoy = fecha_operativa_hoy()
    if db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first() is None:
        raise ValueError("Debe registrar la apertura del día antes de vender")


def _sugerencia_desde_cierre(cierre: CierreDiario) -> dict:
    return {
        "caja_inicial_reales": round(float(cierre.se_deja_reales), 2),
        "oro_operativo_inicial": round(float(cierre.se_deja_oro), 4),
    }


def build_apertura_pantalla_payload(db: Session) -> dict:
    hoy = fecha_operativa_hoy()
    ayer = hoy - timedelta(days=1)
    cierre_hoy = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == hoy).first()
    cierre_ayer = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == ayer).first()

    sugerencia = None
    cierre_ref = cierre_hoy or cierre_ayer
    if cierre_ref:
        sugerencia = _sugerencia_desde_cierre(cierre_ref)

    apertura_hoy = db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first()
    out_ap = None
    if apertura_hoy:
        out_ap = {
            "id": apertura_hoy.id,
            "fecha_operativa": apertura_hoy.fecha_operativa.isoformat(),
            "caja_inicial_reales": float(apertura_hoy.caja_inicial_reales),
            "oro_operativo_inicial": float(apertura_hoy.oro_operativo_inicial),
            "abierto_por": apertura_hoy.abierto_por,
            "created_at": apertura_hoy.created_at.isoformat() if apertura_hoy.created_at else None,
        }

    return {
        "fecha_operativa": hoy.isoformat(),
        "sugerencia": sugerencia,
        "apertura_hoy": out_ap,
    }
