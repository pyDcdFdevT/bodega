"""Filtros de texto para listados de historial."""

from __future__ import annotations

from sqlalchemy import func, or_


HISTORIAL_LIMIT_MAX = 50


def normalizar_buscar(q: str | None) -> str | None:
    texto = (q or "").strip()
    return texto if texto else None


def patron_ilike(q: str) -> str:
    return f"%{q.lower()}%"


def filtro_ilike_columnas(pat: str, *columnas):
    """OR de LIKE insensible a mayúsculas sobre columnas SQL."""
    return or_(*[func.lower(col).like(pat) for col in columnas])
