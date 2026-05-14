from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Activo
from routers.deps import require_admin
from schemas import ActivoCreate


router = APIRouter(prefix="/activos", tags=["Activos"])


@router.get("")
def listar_activos(limit: int = Query(default=200, ge=1, le=500), db: Session = Depends(get_db)):
    rows = db.query(Activo).order_by(Activo.fecha.desc(), Activo.id.desc()).limit(limit).all()
    return [
        {
            "id": r.id,
            "descripcion": r.descripcion,
            "categoria": r.categoria,
            "monto_reales": float(r.monto_reales),
            "fecha": r.fecha,
            "observaciones": r.observaciones or "",
        }
        for r in rows
    ]


@router.post("")
def registrar_activo(
    data: ActivoCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    obs = (data.observaciones or "").strip()
    row = Activo(
        descripcion=data.descripcion.strip()[:500],
        categoria=data.categoria,
        monto_reales=float(data.monto_reales),
        observaciones=obs[:2000] if obs else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return {
        "status": "success",
        "id": row.id,
        "descripcion": row.descripcion,
        "categoria": row.categoria,
        "monto_reales": float(row.monto_reales),
        "fecha": row.fecha,
        "observaciones": row.observaciones or "",
    }
