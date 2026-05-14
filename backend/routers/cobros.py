from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import PagoVenta, Venta
from schemas import PagoVentaCreate
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion


router = APIRouter(prefix="/cobros", tags=["Cobros"])


def _inicio_dia_hoy() -> datetime:
    d = datetime.now(UTC).replace(tzinfo=None)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def _monto_pago_a_reales(venta: Venta, monto: float, moneda: str) -> float:
    m = moneda.lower().strip()
    if m == "reales":
        return CalculosMonetarios.redondear(float(monto), 2)
    if m == "oro":
        tasa = venta.tasa_cambio
        if not tasa:
            return 0.0
        return CalculosMonetarios.redondear(float(monto) * float(tasa.tasa_reales), 2)
    return 0.0


def _abono_en_reales(venta: Venta, body: PagoVentaCreate) -> float:
    m = body.moneda.lower().strip()
    if m not in ("reales", "oro"):
        raise ValueError("Moneda invalida")
    if m == "oro" and not venta.tasa_cambio:
        raise ValueError("La venta no tiene tasa de cambio asociada; no se puede registrar pago en oro")
    return _monto_pago_a_reales(venta, body.monto, body.moneda)


@router.get("/pendientes")
def listar_pendientes(db: Session = Depends(get_db)):
    rows = (
        db.query(Venta)
        .options(joinedload(Venta.tasa_cambio))
        .filter(Venta.saldo_pendiente > 0)
        .order_by(Venta.fecha.desc(), Venta.id.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "fecha": v.fecha,
            "cliente": v.cliente,
            "cliente_fiado": v.cliente_fiado,
            "telefono_fiado": v.telefono_fiado,
            "total_reales": float(v.total_reales),
            "total_oro": float(v.total_oro),
            "tipo_pago": v.tipo_pago,
            "tipo_oro": v.tipo_oro,
            "tasa_nombre": v.tasa_cambio.nombre if v.tasa_cambio else None,
            "estado_pago": v.estado_pago,
            "monto_pagado": float(v.monto_pagado),
            "saldo_pendiente": float(v.saldo_pendiente),
        }
        for v in rows
    ]


@router.get("/cliente/{nombre}")
def deudas_por_cliente(nombre: str, db: Session = Depends(get_db)):
    q = nombre.strip()
    if len(q) < 2:
        raise HTTPException(status_code=400, detail="Indique al menos 2 caracteres")
    like = f"%{q.lower()}%"
    rows = (
        db.query(Venta)
        .options(joinedload(Venta.tasa_cambio))
        .filter(
            Venta.saldo_pendiente > 0,
            or_(
                func.lower(Venta.cliente).like(like),
                func.lower(func.coalesce(Venta.cliente_fiado, "")).like(like),
            ),
        )
        .order_by(Venta.fecha.desc())
        .all()
    )
    return [
        {
            "id": v.id,
            "fecha": v.fecha,
            "cliente": v.cliente,
            "cliente_fiado": v.cliente_fiado,
            "telefono_fiado": v.telefono_fiado,
            "total_reales": float(v.total_reales),
            "saldo_pendiente": float(v.saldo_pendiente),
            "estado_pago": v.estado_pago,
        }
        for v in rows
    ]


@router.get("/pagos-hoy")
def pagos_recibidos_hoy(db: Session = Depends(get_db)):
    inicio = _inicio_dia_hoy()
    rows = (
        db.query(PagoVenta)
        .options(joinedload(PagoVenta.venta))
        .filter(PagoVenta.fecha >= inicio)
        .order_by(PagoVenta.fecha.desc(), PagoVenta.id.desc())
        .all()
    )
    out = []
    for p in rows:
        v = p.venta
        equiv = _monto_pago_a_reales(v, float(p.monto), p.moneda)
        out.append(
            {
                "id": p.id,
                "venta_id": p.venta_id,
                "monto": float(p.monto),
                "moneda": p.moneda,
                "tipo_pago": p.tipo_pago,
                "fecha": p.fecha,
                "registrado_por": p.registrado_por,
                "cliente": v.cliente if v else "",
                "monto_reales_equivalente": equiv,
            }
        )
    return out


@router.post("/registrar-pago")
def registrar_pago(body: PagoVentaCreate, db: Session = Depends(get_db)):
    try:
        venta = (
            db.query(Venta)
            .options(joinedload(Venta.tasa_cambio))
            .filter(Venta.id == body.venta_id)
            .first()
        )
        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        if float(venta.saldo_pendiente) <= 0:
            raise ValueError("La venta no tiene saldo pendiente")

        abono_reales = _abono_en_reales(venta, body)
        if abono_reales <= 0:
            raise ValueError("El monto del abono debe ser mayor a cero")
        saldo = float(venta.saldo_pendiente)
        if abono_reales > saldo + 0.05:
            raise ValueError("El monto supera el saldo pendiente")

        venta.monto_pagado = CalculosMonetarios.redondear(float(venta.monto_pagado) + abono_reales, 2)
        venta.saldo_pendiente = CalculosMonetarios.redondear(saldo - abono_reales, 2)
        if venta.saldo_pendiente <= 0.009:
            venta.saldo_pendiente = 0.0
            venta.estado_pago = "PAGADO"
        else:
            venta.estado_pago = "PARCIAL"

        tipo_pago_txt = body.tipo_pago.strip()[:30]
        if not tipo_pago_txt:
            raise ValueError("Indique el tipo de pago")

        db.add(
            PagoVenta(
                venta_id=venta.id,
                monto=float(body.monto),
                moneda=body.moneda.lower().strip(),
                tipo_pago=tipo_pago_txt,
                registrado_por=body.registrado_por.strip() or "Admin",
            )
        )

        moneda_ledger = body.moneda.lower().strip()
        gramos = float(body.monto) if moneda_ledger == "oro" else 0.0

        registrar_transaccion(
            db,
            tipo="cobro_fiado",
            modulo_origen="bodega",
            referencia_id=venta.id,
            moneda=moneda_ledger,
            monto_reales=float(abono_reales),
            gramos_oro=gramos,
            tipo_oro=venta.tipo_oro,
            tasa_usada=float(venta.tasa_cambio.tasa_reales) if venta.tasa_cambio else None,
            descripcion=f"Cobro fiado venta #{venta.id} ({tipo_pago_txt})",
        )

        db.commit()
        return {
            "status": "success",
            "venta_id": venta.id,
            "estado_pago": venta.estado_pago,
            "monto_pagado": float(venta.monto_pagado),
            "saldo_pendiente": float(venta.saldo_pendiente),
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
