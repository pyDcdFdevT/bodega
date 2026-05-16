from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from database import get_db
from schemas import PagoProveedorCreate
from services.apertura_context import exigir_apertura_del_dia
from services.ledger import registrar_transaccion
from services.operativa import verificar_dia_abierto
from services.pagos_proveedores import (
    build_deudas_proveedores,
    build_historial_pagos,
    registrar_pago_proveedor,
)


router = APIRouter(prefix="/proveedores", tags=["Proveedores"])


@router.get("/deudas")
def listar_deudas_proveedores(db: Session = Depends(get_db)):
    """Compras a crédito con saldo pendiente."""
    return build_deudas_proveedores(db)


@router.get("/pagos")
def historial_pagos_proveedores(
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """Historial de abonos a proveedores."""
    return build_historial_pagos(db, limit)


@router.post("/pagar")
def pagar_proveedor(data: PagoProveedorCreate, db: Session = Depends(get_db)):
    """Registra abono a proveedor, descuenta caja y actualiza deuda."""
    try:
        verificar_dia_abierto(db)
        exigir_apertura_del_dia(db)
        resultado = registrar_pago_proveedor(db, data.compra_id, data.monto)
        registrar_transaccion(
            db,
            tipo="pago_proveedor",
            modulo_origen="bodega",
            referencia_id=resultado["pago_id"],
            moneda="reales",
            monto_reales=float(resultado["monto"]),
            gramos_oro=0.0,
            tipo_oro=None,
            descripcion=(
                f"Pago proveedor #{resultado['pago_id']} compra #{resultado['compra_id']} "
                f"{resultado['proveedor']}"
            )[:255],
        )
        db.commit()
        return {
            "status": "success",
            "message": "Pago registrado",
            **resultado,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar el pago") from exc
