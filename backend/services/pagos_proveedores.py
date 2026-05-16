"""Pagos a proveedores (cuentas por pagar)."""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.orm import Session

from models import Compra, PagoProveedor
from services.query_operativa import compra_no_anulada


def _pagos_por_compra(db: Session, compra_ids: list[int] | None = None) -> dict[int, float]:
    q = db.query(PagoProveedor.compra_id, func.coalesce(func.sum(PagoProveedor.monto), 0)).group_by(
        PagoProveedor.compra_id
    )
    if compra_ids is not None:
        if not compra_ids:
            return {}
        q = q.filter(PagoProveedor.compra_id.in_(compra_ids))
    return {int(cid): round(float(m), 2) for cid, m in q.all()}


def saldo_pendiente_compra(compra: Compra, monto_pagado: float) -> float:
    return round(max(0.0, float(compra.total_reales) - float(monto_pagado)), 2)


def _compras_credito_vigentes(db: Session) -> list[Compra]:
    return (
        db.query(Compra)
        .filter(
            compra_no_anulada(),
            Compra.tipo_pago_compra == "credito",
            Compra.estado_credito == "pendiente",
        )
        .order_by(Compra.fecha.desc(), Compra.id.desc())
        .all()
    )


def _fila_deuda(compra: Compra, pagado: float) -> dict | None:
    saldo = saldo_pendiente_compra(compra, pagado)
    if saldo <= 0.009:
        return None
    proveedor = (compra.proveedor or "Proveedor").strip() or "Proveedor"
    return {
        "compra_id": compra.id,
        "proveedor": proveedor,
        "total_reales": round(float(compra.total_reales), 2),
        "monto_pagado": round(pagado, 2),
        "saldo_pendiente": saldo,
        "fecha": compra.fecha.isoformat() if compra.fecha else None,
        "estado_credito": compra.estado_credito,
    }


def build_deudas_proveedores(db: Session) -> dict:
    compras = _compras_credito_vigentes(db)
    ids = [c.id for c in compras]
    pagos_map = _pagos_por_compra(db, ids)

    items: list[dict] = []
    por_proveedor_map: dict[str, dict] = {}
    total = 0.0

    for c in compras:
        pagado = pagos_map.get(c.id, 0.0)
        fila = _fila_deuda(c, pagado)
        if not fila:
            continue
        items.append(fila)
        total += fila["saldo_pendiente"]
        prov = fila["proveedor"]
        if prov not in por_proveedor_map:
            por_proveedor_map[prov] = {
                "proveedor": prov,
                "total_pendiente": 0.0,
                "cantidad_compras": 0,
            }
        por_proveedor_map[prov]["total_pendiente"] += fila["saldo_pendiente"]
        por_proveedor_map[prov]["cantidad_compras"] += 1

    por_proveedor = sorted(
        por_proveedor_map.values(),
        key=lambda x: (-float(x["total_pendiente"]), str(x["proveedor"])),
    )
    for row in por_proveedor:
        row["total_pendiente"] = round(float(row["total_pendiente"]), 2)

    return {
        "total_pendiente": round(total, 2),
        "cantidad_compras": len(items),
        "por_proveedor": por_proveedor,
        "deudas": items,
    }


def build_historial_pagos(db: Session, limit: int = 100) -> dict:
    rows = (
        db.query(PagoProveedor)
        .order_by(PagoProveedor.fecha.desc(), PagoProveedor.id.desc())
        .limit(limit)
        .all()
    )
    pagos = [
        {
            "id": p.id,
            "compra_id": p.compra_id,
            "proveedor": p.proveedor,
            "monto": round(float(p.monto), 2),
            "fecha": p.fecha.isoformat() if p.fecha else None,
        }
        for p in rows
    ]
    total = round(sum(float(p["monto"]) for p in pagos), 2)
    return {"total_pagado_listado": total, "cantidad": len(pagos), "pagos": pagos}


def registrar_pago_proveedor(db: Session, compra_id: int, monto: float) -> dict:
    compra = (
        db.query(Compra)
        .filter(Compra.id == compra_id, compra_no_anulada(), Compra.tipo_pago_compra == "credito")
        .first()
    )
    if not compra:
        raise ValueError("Compra a credito no encontrada o no vigente")
    if compra.estado_credito == "pagada":
        raise ValueError("Esta compra ya esta pagada")

    monto = round(float(monto), 2)
    if monto <= 0:
        raise ValueError("El monto del pago debe ser mayor a cero")

    pagado = _pagos_por_compra(db, [compra.id]).get(compra.id, 0.0)
    saldo = saldo_pendiente_compra(compra, pagado)
    if saldo <= 0.009:
        compra.estado_credito = "pagada"
        db.flush()
        raise ValueError("Esta compra ya no tiene saldo pendiente")

    if monto > saldo + 0.009:
        raise ValueError(f"El pago no puede superar el saldo pendiente ({saldo:.2f} R$)")

    proveedor = (compra.proveedor or "Proveedor").strip() or "Proveedor"
    pago = PagoProveedor(
        compra_id=compra.id,
        monto=monto,
        proveedor=proveedor,
    )
    db.add(pago)
    db.flush()

    nuevo_pagado = round(pagado + monto, 2)
    nuevo_saldo = saldo_pendiente_compra(compra, nuevo_pagado)
    pagada = nuevo_saldo <= 0.009
    if pagada:
        compra.estado_credito = "pagada"

    return {
        "pago_id": pago.id,
        "compra_id": compra.id,
        "proveedor": proveedor,
        "monto": monto,
        "monto_pagado_acumulado": nuevo_pagado,
        "saldo_pendiente": nuevo_saldo,
        "estado_credito": compra.estado_credito,
        "pagada": pagada,
    }
