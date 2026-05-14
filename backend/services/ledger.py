from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from models import Transaccion


def registrar_transaccion(
    db: Session,
    *,
    tipo: str,
    modulo_origen: str,
    referencia_id: Optional[int],
    moneda: str,
    monto_reales: float = 0.0,
    gramos_oro: float = 0.0,
    tipo_oro: Optional[str] = None,
    tasa_usada: Optional[float] = None,
    descripcion: Optional[str] = None,
) -> Transaccion:
    desc = (descripcion or "")[:255] if descripcion else None
    row = Transaccion(
        uuid=str(uuid.uuid4()),
        tipo=tipo,
        modulo_origen=modulo_origen,
        referencia_id=referencia_id,
        moneda=moneda,
        monto_reales=float(monto_reales or 0),
        gramos_oro=float(gramos_oro or 0),
        tipo_oro=tipo_oro.strip().lower() if tipo_oro else None,
        tasa_usada=float(tasa_usada) if tasa_usada is not None else None,
        descripcion=desc,
    )
    db.add(row)
    return row
