from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Activo
from routers.deps import require_admin
from schemas import ActivoCreate
from services.depreciacion import calcular_depreciacion_mensual, estado_depreciacion_activo


router = APIRouter(prefix="/activos", tags=["Activos"])


def _serializar_activo(row: Activo) -> dict:
    base = estado_depreciacion_activo(row)
    return base


@router.get("")
def listar_activos(limit: int = Query(default=200, ge=1, le=500), db: Session = Depends(get_db)):
    rows = db.query(Activo).order_by(Activo.fecha.desc(), Activo.id.desc()).limit(limit).all()
    return [_serializar_activo(r) for r in rows]


@router.post("")
def registrar_activo(
    data: ActivoCreate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    obs = (data.observaciones or "").strip()
    dep_mensual = calcular_depreciacion_mensual(
        float(data.monto_reales),
        float(data.valor_residual),
        int(data.vida_util_anios),
    )
    row = Activo(
        descripcion=data.descripcion.strip()[:500],
        categoria=data.categoria,
        monto_reales=float(data.monto_reales),
        vida_util_anios=int(data.vida_util_anios),
        valor_residual=float(data.valor_residual),
        depreciacion_mensual=dep_mensual,
        observaciones=obs[:2000] if obs else None,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    out = _serializar_activo(row)
    return {
        "status": "success",
        **out,
    }
