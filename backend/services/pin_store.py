"""Persistencia de PINs: archivo JSON en data/ con fallback a variables de entorno."""

from __future__ import annotations

import json
import os
from pathlib import Path

_PIN_FILE = Path(__file__).resolve().parent.parent / "data" / "pins.json"


def _pins_desde_env() -> dict[str, str]:
    return {
        "admin": os.getenv("PIN_ADMIN", "1696"),
        "vendedor": os.getenv("PIN_VENDEDOR", "1111"),
    }


def obtener_pins() -> dict[str, str]:
    if _PIN_FILE.exists():
        try:
            data = json.loads(_PIN_FILE.read_text(encoding="utf-8"))
            admin = str(data.get("admin", "")).strip()
            vendedor = str(data.get("vendedor", "")).strip()
            if len(admin) == 4 and len(vendedor) == 4 and admin.isdigit() and vendedor.isdigit():
                return {"admin": admin, "vendedor": vendedor}
        except (json.JSONDecodeError, OSError):
            pass
    return _pins_desde_env()


def guardar_pins(admin: str, vendedor: str) -> None:
    _PIN_FILE.parent.mkdir(parents=True, exist_ok=True)
    _PIN_FILE.write_text(
        json.dumps({"admin": admin, "vendedor": vendedor}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
