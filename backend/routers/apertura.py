from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import AperturaCaja, CierreDiario
from routers.deps import require_admin
from schemas import AperturaCajaCreate


router = APIRouter(prefix="/apertura", tags=["Apertura"])


def _fecha_operativa_hoy() -> date:
    return datetime.now(UTC).replace(tzinfo=None).date()


@router.get("/")
def obtener_apertura_y_sugerencia(db: Session = Depends(get_db)):
    hoy = _fecha_operativa_hoy()
    ayer = hoy - timedelta(days=1)
    cierre_ayer = db.query(CierreDiario).filter(CierreDiario.fecha_operativa == ayer).first()
    sug_reales = float(cierre_ayer.se_deja_reales) if cierre_ayer else 0.0
    sug_oro = float(cierre_ayer.se_deja_oro) if cierre_ayer else 0.0
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
        "sugerencia": {
            "caja_inicial_reales": round(sug_reales, 2),
            "oro_operativo_inicial": round(sug_oro, 2),
        },
        "apertura_hoy": out_ap,
    }


@router.post("/")
def registrar_apertura(
    payload: AperturaCajaCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hoy = _fecha_operativa_hoy()
    if db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first():
        raise HTTPException(status_code=400, detail="La apertura de hoy ya fue registrada")
    row = AperturaCaja(
        fecha_operativa=hoy,
        caja_inicial_reales=float(payload.caja_inicial_reales),
        oro_operativo_inicial=float(payload.oro_operativo_inicial),
        abierto_por=payload.abierto_por.strip()[:100],
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "status": "success",
        "apertura": {
            "id": row.id,
            "fecha_operativa": row.fecha_operativa.isoformat(),
            "caja_inicial_reales": float(row.caja_inicial_reales),
            "oro_operativo_inicial": float(row.oro_operativo_inicial),
            "abierto_por": row.abierto_por,
        },
    }
