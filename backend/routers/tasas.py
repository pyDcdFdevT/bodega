from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models import LogTasaCambio, TasaCambio
from schemas import TasasConfigUpdate
from services.calculos import CalculosMonetarios


router = APIRouter(prefix="/tasas", tags=["Tasas"])


def serializar_tasa(tasa: TasaCambio) -> dict:
    return {
        "id": tasa.id,
        "nombre": tasa.nombre,
        "etiqueta": CalculosMonetarios.ETIQUETAS_TASAS.get(tasa.nombre, tasa.nombre),
        "tasa_reales": tasa.tasa_reales,
        "actualizado_en": tasa.actualizado_en,
    }


@router.get("")
def listar_tasas(db: Session = Depends(get_db)):
    try:
        tasas = CalculosMonetarios.listar_tasas(db)
        db.commit()
        return [serializar_tasa(tasa) for tasa in tasas]
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible cargar las tasas") from exc


@router.put("")
def actualizar_tasas(data: TasasConfigUpdate, db: Session = Depends(get_db)):
    try:
        tasas = {tasa.nombre: tasa for tasa in CalculosMonetarios.listar_tasas(db)}

        for nombre in CalculosMonetarios.TASAS_PREDEFINIDAS:
            nueva_tasa = getattr(data, nombre)
            tasa = tasas[nombre]
            if tasa.tasa_reales != nueva_tasa:
                tasa_anterior = tasa.tasa_reales
                variacion = round(((nueva_tasa - tasa.tasa_reales) / tasa.tasa_reales) * 100, 2)
                db.add(
                    LogTasaCambio(
                        nombre_tasa=nombre,
                        tasa_anterior=tasa_anterior,
                        tasa_nueva=nueva_tasa,
                        variacion_porcentaje=variacion,
                        motivo="Actualizacion desde interfaz",
                    )
                )
                tasa.tasa_reales = nueva_tasa

        db.flush()
        resultado = [serializar_tasa(tasa) for tasa in CalculosMonetarios.listar_tasas(db)]
        db.commit()
        return {
            "status": "success",
            "message": "Las 4 tasas fueron actualizadas",
            "tasas": resultado,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible actualizar las tasas") from exc
