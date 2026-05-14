from __future__ import annotations

from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from models import Transaccion


router = APIRouter(prefix="/transacciones", tags=["Transacciones"])


def _serializar(row: Transaccion) -> dict:
    return {
        "id": row.id,
        "uuid": row.uuid,
        "tipo": row.tipo,
        "modulo_origen": row.modulo_origen,
        "referencia_id": row.referencia_id,
        "moneda": row.moneda,
        "monto_reales": row.monto_reales,
        "gramos_oro": row.gramos_oro,
        "tipo_oro": row.tipo_oro,
        "tasa_usada": row.tasa_usada,
        "descripcion": row.descripcion,
        "fecha": row.fecha,
        "created_at": row.created_at,
    }


def _rango_dia_naive(fecha_iso: str) -> tuple[datetime, datetime]:
    try:
        base = datetime.strptime(fecha_iso, "%Y-%m-%d")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="fecha debe ser YYYY-MM-DD") from exc
    inicio = base.replace(hour=0, minute=0, second=0, microsecond=0)
    fin = inicio + timedelta(days=1)
    return inicio, fin


@router.get("")
def listar_transacciones(
    fecha: str | None = Query(default=None, description="YYYY-MM-DD (zona servidor, dia calendario)"),
    tipo: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    q = db.query(Transaccion).order_by(Transaccion.fecha.desc(), Transaccion.id.desc())
    if fecha:
        inicio, fin = _rango_dia_naive(fecha)
        q = q.filter(Transaccion.fecha >= inicio, Transaccion.fecha < fin)
    if tipo:
        q = q.filter(Transaccion.tipo == tipo.strip())
    rows = q.limit(limit).all()
    return [_serializar(r) for r in rows]


@router.get("/hoy")
def listar_transacciones_hoy(
    tipo: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=200, ge=1, le=1000),
    db: Session = Depends(get_db),
):
    hoy = datetime.now(UTC).replace(tzinfo=None).date().isoformat()
    inicio, fin = _rango_dia_naive(hoy)
    q = db.query(Transaccion).filter(Transaccion.fecha >= inicio, Transaccion.fecha < fin)
    if tipo:
        q = q.filter(Transaccion.tipo == tipo.strip())
    rows = q.order_by(Transaccion.fecha.desc(), Transaccion.id.desc()).limit(limit).all()
    return {"fecha": hoy, "items": [_serializar(r) for r in rows]}
