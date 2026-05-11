from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import CompraOro
from schemas import CompraOroCreate
from services.calculos import CalculosMonetarios
from services.validaciones import ValidacionesSistema


router = APIRouter(prefix="/compras-oro", tags=["Compra de Oro"])


@router.post("")
def registrar_compra_oro(data: CompraOroCreate, db: Session = Depends(get_db)):
    try:
        tipo_oro = ValidacionesSistema.validar_tipo_oro(data.tipo_oro)
        total_reales = CalculosMonetarios.redondear(data.gramos * data.tasa_compra_reales, 2)

        compra = CompraOro(
            tipo_oro=tipo_oro,
            gramos=CalculosMonetarios.redondear(data.gramos),
            tasa_compra_reales=CalculosMonetarios.redondear(data.tasa_compra_reales),
            total_reales=total_reales,
        )
        db.add(compra)
        db.commit()
        db.refresh(compra)

        return {
            "status": "success",
            "message": "Compra de oro registrada",
            "data": {
                "id": compra.id,
                "tipo_oro": compra.tipo_oro,
                "gramos": compra.gramos,
                "tasa_compra_reales": compra.tasa_compra_reales,
                "total_reales": compra.total_reales,
            },
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar la compra de oro") from exc


@router.get("")
def listar_compras_oro(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    compras = (
        db.query(CompraOro)
        .order_by(CompraOro.fecha.desc(), CompraOro.id.desc())
        .limit(limit)
        .all()
    )
    return compras
