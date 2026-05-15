from __future__ import annotations

from fastapi import Header, HTTPException


def require_admin(x_bodega_rol: str | None = Header(default=None, alias="X-Bodega-Rol")) -> str:
    """Solo rol admin (cabecera enviada por el cliente de confianza)."""
    rol = (x_bodega_rol or "").strip().lower()
    if rol != "admin":
        raise HTTPException(status_code=403, detail="Solo administradores pueden realizar esta acción")
    return rol
