"""Configuración persistente en tabla configuracion."""

from __future__ import annotations

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Configuracion

NOMBRE_BODEGA_KEY = "nombre_bodega"
NOMBRE_BODEGA_DEFAULT = "Bodega Minera"
NOMBRE_BODEGA_MAX_LEN = 100


def _normalizar_nombre(valor: str) -> str:
    nombre = " ".join(str(valor or "").strip().split())
    if not nombre:
        return NOMBRE_BODEGA_DEFAULT
    return nombre[:NOMBRE_BODEGA_MAX_LEN]


def obtener_config(db: Session, clave: str) -> str | None:
    row = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if not row:
        return None
    valor = str(row.valor or "").strip()
    return valor if valor else None


def guardar_config(db: Session, clave: str, valor: str) -> None:
    row = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if row:
        row.valor = valor
    else:
        db.add(Configuracion(clave=clave, valor=valor))


def obtener_nombre_bodega(db: Session | None = None) -> str:
    if db is not None:
        raw = obtener_config(db, NOMBRE_BODEGA_KEY)
        return _normalizar_nombre(raw) if raw else NOMBRE_BODEGA_DEFAULT
    session = SessionLocal()
    try:
        raw = obtener_config(session, NOMBRE_BODEGA_KEY)
        return _normalizar_nombre(raw) if raw else NOMBRE_BODEGA_DEFAULT
    finally:
        session.close()


def guardar_nombre_bodega(nombre: str, db: Session | None = None) -> str:
    valor = _normalizar_nombre(nombre)
    if db is not None:
        guardar_config(db, NOMBRE_BODEGA_KEY, valor)
        db.commit()
        return valor
    session = SessionLocal()
    try:
        guardar_config(session, NOMBRE_BODEGA_KEY, valor)
        session.commit()
        return valor
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
