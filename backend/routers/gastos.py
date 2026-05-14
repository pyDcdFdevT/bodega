from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from database import get_db
from models import GastoOperativo
from schemas import GastoCreate
from services.ledger import registrar_transaccion


router = APIRouter(prefix="/gastos", tags=["Gastos"])


@router.post("")
def registrar_gasto(data: GastoCreate, db: Session = Depends(get_db)):
    g = GastoOperativo(
        categoria=data.categoria,
        descripcion=data.descripcion.strip(),
        monto_reales=float(data.monto_reales),
    )
    db.add(g)
    db.flush()
    registrar_transaccion(
        db,
        tipo="gasto",
        modulo_origen="gastos",
        referencia_id=g.id,
        moneda="reales",
        monto_reales=float(g.monto_reales),
        gramos_oro=0.0,
        tipo_oro=None,
        tasa_usada=None,
        descripcion=f"Gasto {g.categoria}: {g.descripcion}"[:255],
    )
    db.commit()
    db.refresh(g)
    return {"status": "success", "id": g.id}


@router.get("/hoy")
def listar_gastos_hoy(db: Session = Depends(get_db)):
    inicio = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    rows = (
        db.query(GastoOperativo)
        .filter(GastoOperativo.fecha >= inicio)
        .order_by(GastoOperativo.fecha.desc(), GastoOperativo.id.desc())
        .all()
    )
    total = float(db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0)).filter(GastoOperativo.fecha >= inicio).scalar() or 0)
    return {
        "fecha": inicio.date().isoformat(),
        "total_reales": round(total, 2),
        "items": [
            {
                "id": r.id,
                "categoria": r.categoria,
                "descripcion": r.descripcion,
                "monto_reales": r.monto_reales,
                "fecha": r.fecha,
            }
            for r in rows
        ],
    }


@router.get("")
def listar_gastos(limit: int = Query(default=100, ge=1, le=500), db: Session = Depends(get_db)):
    rows = (
        db.query(GastoOperativo)
        .order_by(GastoOperativo.fecha.desc(), GastoOperativo.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "categoria": r.categoria,
            "descripcion": r.descripcion,
            "monto_reales": r.monto_reales,
            "fecha": r.fecha,
        }
        for r in rows
    ]
