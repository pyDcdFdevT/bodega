"""Persistencia de PINs en tabla configuracion (PostgreSQL / SQLite)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from sqlalchemy.orm import Session

from database import SessionLocal
from models import Configuracion

PIN_ADMIN_KEY = "pin_admin"
PIN_VENDEDOR_KEY = "pin_vendedor"
_PIN_FILE = Path(__file__).resolve().parent.parent / "data" / "pins.json"


def _pins_desde_env() -> dict[str, str]:
    return {
        "admin": os.getenv("PIN_ADMIN", "1696"),
        "vendedor": os.getenv("PIN_VENDEDOR", "1111"),
    }


def _pin_valido(valor: str) -> bool:
    s = str(valor or "").strip()
    return len(s) == 4 and s.isdigit()


def _leer_pin_db(db: Session, clave: str) -> str | None:
    row = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if not row:
        return None
    valor = str(row.valor or "").strip()
    return valor if _pin_valido(valor) else None


def _upsert_pin(db: Session, clave: str, valor: str) -> None:
    row = db.query(Configuracion).filter(Configuracion.clave == clave).first()
    if row:
        row.valor = valor
    else:
        db.add(Configuracion(clave=clave, valor=valor))


def _migrar_desde_json_si_aplica(db: Session) -> None:
    """Importa pins.json legacy una vez si la BD aún no tiene PINs."""
    if _leer_pin_db(db, PIN_ADMIN_KEY) and _leer_pin_db(db, PIN_VENDEDOR_KEY):
        return
    if not _PIN_FILE.exists():
        return
    try:
        data = json.loads(_PIN_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return
    admin = str(data.get("admin", "")).strip()
    vendedor = str(data.get("vendedor", "")).strip()
    changed = False
    if _pin_valido(admin) and not _leer_pin_db(db, PIN_ADMIN_KEY):
        _upsert_pin(db, PIN_ADMIN_KEY, admin)
        changed = True
    if _pin_valido(vendedor) and not _leer_pin_db(db, PIN_VENDEDOR_KEY):
        _upsert_pin(db, PIN_VENDEDOR_KEY, vendedor)
        changed = True
    if changed:
        db.commit()


def obtener_pins() -> dict[str, str]:
    db = SessionLocal()
    try:
        _migrar_desde_json_si_aplica(db)
        admin = _leer_pin_db(db, PIN_ADMIN_KEY)
        vendedor = _leer_pin_db(db, PIN_VENDEDOR_KEY)
        fallback = _pins_desde_env()
        return {
            "admin": admin or fallback["admin"],
            "vendedor": vendedor or fallback["vendedor"],
        }
    finally:
        db.close()


def guardar_pins(admin: str, vendedor: str) -> None:
    db = SessionLocal()
    try:
        _upsert_pin(db, PIN_ADMIN_KEY, admin)
        _upsert_pin(db, PIN_VENDEDOR_KEY, vendedor)
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
