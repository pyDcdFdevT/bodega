from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import LogTasaCambio
from backend.schemas import TasaRequest, TasaUpdateRequest
from backend.services.calculos import CalculosMonetarios
from backend.services.gestor_tasas import GestorTasas


router = APIRouter(prefix="/tasas", tags=["Tasas"])


@router.post("/iniciar-dia")
def iniciar_tasa(tasa: TasaRequest, db: Session = Depends(get_db)):
    try:
        gestor = GestorTasas(db)
        nueva = gestor.establecer_inicial(tasa.tasa_reales, tasa.motivo)
        db.commit()
        db.refresh(nueva)
        return {
            "status": "success",
            "message": f"Tasa configurada en R$ {nueva.tasa_reales}/g",
            "data": {
                "id": nueva.id,
                "fecha": nueva.fecha.isoformat(),
                "tasa_reales": nueva.tasa_reales,
            },
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible configurar la tasa") from exc


@router.put("/actualizar")
def actualizar_tasa(tasa: TasaUpdateRequest, db: Session = Depends(get_db)):
    try:
        gestor = GestorTasas(db)
        resultado = gestor.actualizar(tasa.tasa_reales, tasa.motivo)
        db.commit()
        return {
            "status": "success",
            "message": f"Tasa actualizada a R$ {tasa.tasa_reales}/g",
            "data": resultado,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible actualizar la tasa") from exc


@router.get("/actual")
def tasa_actual(db: Session = Depends(get_db)):
    tasa = CalculosMonetarios.obtener_tasa_actual(db)
    if not tasa:
        return {"configurado": False, "mensaje": "No hay tasa configurada"}
    return {
        "configurado": True,
        "tasa": tasa.tasa_reales,
        "fecha": tasa.fecha.isoformat(),
        "id": tasa.id,
    }


@router.get("/estado")
def estado_sistema(db: Session = Depends(get_db)):
    tasa = CalculosMonetarios.obtener_tasa_actual(db)
    return {
        "sistema_operativo": tasa is not None,
        "tasa_actual": tasa.tasa_reales if tasa else None,
        "fecha": tasa.fecha.isoformat() if tasa else None,
    }


@router.get("/historial")
def historial_tasas(
    limit: int = Query(default=30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    registros = (
        db.query(LogTasaCambio)
        .order_by(LogTasaCambio.fecha_cambio.desc(), LogTasaCambio.id.desc())
        .limit(limit)
        .all()
    )
    return registros
