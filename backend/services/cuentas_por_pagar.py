"""Cuentas por pagar: compras a crédito vigentes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models import Compra
from services.query_operativa import compra_no_anulada


def build_cuentas_por_pagar(db: Session) -> dict:
    compras = (
        db.query(Compra)
        .filter(compra_no_anulada(), Compra.tipo_pago_compra == "credito")
        .order_by(Compra.fecha.desc(), Compra.id.desc())
        .all()
    )

    por_proveedor_map: dict[str, dict] = {}
    items: list[dict] = []
    total = 0.0

    for c in compras:
        proveedor = (c.proveedor or "Proveedor").strip() or "Proveedor"
        monto = float(c.total_reales)
        total += monto
        fecha_iso = c.fecha.isoformat() if c.fecha else None

        items.append(
            {
                "id": c.id,
                "proveedor": proveedor,
                "total_reales": round(monto, 2),
                "fecha": fecha_iso,
            }
        )

        if proveedor not in por_proveedor_map:
            por_proveedor_map[proveedor] = {
                "proveedor": proveedor,
                "total_credito": 0.0,
                "cantidad_compras": 0,
            }
        por_proveedor_map[proveedor]["total_credito"] += monto
        por_proveedor_map[proveedor]["cantidad_compras"] += 1

    por_proveedor = sorted(
        por_proveedor_map.values(),
        key=lambda x: (-float(x["total_credito"]), str(x["proveedor"])),
    )
    for row in por_proveedor:
        row["total_credito"] = round(float(row["total_credito"]), 2)

    return {
        "total_pendiente": round(total, 2),
        "cantidad_compras": len(items),
        "por_proveedor": por_proveedor,
        "compras": items,
    }
