"""Contexto de pantalla de apertura: sugerencia desde cierre de hoy o ayer y apertura de hoy."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import AperturaCaja, CierreDiario, DistribucionFondos, LoteOro, VentaPieza
from services.oro_lotes import origen_lote_desde_cierre


def fecha_operativa_hoy() -> date:
    return datetime.now(UTC).date()


def _inicio_dia(fecha: date) -> datetime:
    return datetime(fecha.year, fecha.month, fecha.day, tzinfo=UTC).replace(tzinfo=None)


def exigir_apertura_del_dia(db: Session) -> None:
    """Ventas y movimientos de caja del día operativo requieren apertura registrada."""
    hoy = fecha_operativa_hoy()
    if db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first() is None:
        raise ValueError("Debe registrar la apertura del día antes de vender")


def _sum_distrib_se_deja_caja_post_cierre(
    db: Session, cierre: CierreDiario, hoy: date
) -> float:
    """Suma 'se_deja_caja' de distribuciones de ventas de pieza posteriores al cierre."""
    inicio = cierre.created_at
    if inicio is None:
        inicio = _inicio_dia(cierre.fecha_operativa + timedelta(days=1))
    fin = datetime.now(UTC).replace(tzinfo=None)

    total = (
        db.query(func.coalesce(func.sum(DistribucionFondos.monto), 0))
        .join(VentaPieza, DistribucionFondos.venta_pieza_id == VentaPieza.id)
        .filter(
            DistribucionFondos.tipo == "se_deja_caja",
            VentaPieza.fecha >= inicio,
            VentaPieza.fecha <= fin,
        )
        .scalar()
    )
    return round(float(total or 0), 2)


def _sugerencia_desde_cierre(db: Session, cierre: CierreDiario, hoy: date) -> dict:
    caja_cierre = round(float(cierre.se_deja_reales), 2)
    caja_distrib = _sum_distrib_se_deja_caja_post_cierre(db, cierre, hoy)
    fecha_cierre = cierre.fecha_operativa
    origen_cierre = origen_lote_desde_cierre(fecha_cierre)
    lote_retiro_cierre = (
        db.query(LoteOro).filter(LoteOro.origen == origen_cierre).first()
    )
    if lote_retiro_cierre is not None:
        oro_ini = 0.0
    else:
        oro_ini = round(float(cierre.se_deja_oro), 4)
    oro_retirado = lote_retiro_cierre is not None
    return {
        "caja_inicial_reales": round(caja_cierre + caja_distrib, 2),
        "oro_operativo_inicial": oro_ini,
        "oro_retirado_fundicion": oro_retirado,
        "caja_distribuciones_se_deja_caja": caja_distrib,
    }


def build_apertura_pantalla_payload(db: Session) -> dict:
    hoy = fecha_operativa_hoy()
    ayer = hoy - timedelta(days=1)
    cierre_hoy = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == hoy).first()
    cierre_ayer = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == ayer).first()

    sugerencia = None
    cierre_ref = cierre_hoy or cierre_ayer
    if cierre_ref:
        sugerencia = _sugerencia_desde_cierre(db, cierre_ref, hoy)

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
