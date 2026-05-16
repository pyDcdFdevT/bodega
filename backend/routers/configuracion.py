"""Configuración de la aplicación (nombre de bodega, etc.)."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from routers.deps import require_admin
from services.config_store import (
    NOMBRE_BODEGA_DEFAULT,
    NOMBRE_BODEGA_MAX_LEN,
    guardar_nombre_bodega,
    obtener_nombre_bodega,
)

router = APIRouter(prefix="/configuracion", tags=["Configuracion"])


class NombreBodegaUpdate(BaseModel):
    nombre: str = Field(..., min_length=1, max_length=NOMBRE_BODEGA_MAX_LEN)


@router.get("/app")
def configuracion_app(db: Session = Depends(get_db)):
    """Datos públicos de la app (nombre de bodega)."""
    return {
        "nombre_bodega": obtener_nombre_bodega(db),
        "nombre_bodega_default": NOMBRE_BODEGA_DEFAULT,
    }


@router.put("/nombre-bodega")
def actualizar_nombre_bodega(
    payload: NombreBodegaUpdate,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    nombre = guardar_nombre_bodega(payload.nombre, db)
    return {"status": "ok", "nombre_bodega": nombre}
