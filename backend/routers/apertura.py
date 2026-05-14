from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import AperturaCaja
from routers.deps import require_admin
from schemas import AperturaCajaCreate
from services.apertura_context import build_apertura_pantalla_payload, fecha_operativa_hoy


router = APIRouter(prefix="/apertura", tags=["Apertura"])


@router.get("/")
def obtener_apertura_y_sugerencia(db: Session = Depends(get_db)):
    return build_apertura_pantalla_payload(db)


@router.post("/")
def registrar_apertura(
    payload: AperturaCajaCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    hoy = fecha_operativa_hoy()
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
