"""Cuentas por pagar: compras a crédito con saldo pendiente."""

from __future__ import annotations

from sqlalchemy.orm import Session

from services.pagos_proveedores import build_deudas_proveedores


def build_cuentas_por_pagar(db: Session) -> dict:
    data = build_deudas_proveedores(db)
    deudas = data.get("deudas") or []
    compras = [
        {
            "id": d["compra_id"],
            "proveedor": d["proveedor"],
            "total_reales": d["saldo_pendiente"],
            "total_compra": d["total_reales"],
            "monto_pagado": d["monto_pagado"],
            "fecha": d["fecha"],
        }
        for d in deudas
    ]
    por_proveedor = [
        {
            "proveedor": p["proveedor"],
            "total_credito": p["total_pendiente"],
            "cantidad_compras": p["cantidad_compras"],
        }
        for p in data.get("por_proveedor") or []
    ]
    return {
        "total_pendiente": data.get("total_pendiente", 0),
        "cantidad_compras": data.get("cantidad_compras", 0),
        "por_proveedor": por_proveedor,
        "compras": compras,
    }
