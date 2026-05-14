from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import PagoVenta, TasaCambio, Venta
from schemas import PagoVentaCreate
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cobros", tags=["Cobros"])

_CANAL_ETIQUETA = {"efectivo": "Efectivo", "oro": "Oro"}


def _inicio_dia_hoy() -> datetime:
    d = datetime.now(UTC).replace(tzinfo=None)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


def _tasa_por_nombre(db: Session, nombre: str) -> TasaCambio | None:
    return db.query(TasaCambio).filter(TasaCambio.nombre == nombre).first()


def _equiv_pago_reales(db: Session, p: PagoVenta) -> float:
    if (p.moneda or "reales").lower() == "reales":
        return CalculosMonetarios.redondear(float(p.monto), 2)
    nombre = getattr(p, "tipo_oro", None) or (p.venta.tipo_oro if p.venta else None)
    if not nombre:
        return 0.0
    tasa = _tasa_por_nombre(db, nombre)
    if not tasa or float(tasa.tasa_reales) <= 0:
        return 0.0
    return CalculosMonetarios.redondear(float(p.monto) * float(tasa.tasa_reales), 2)


def _abono_en_reales(db: Session, body: PagoVentaCreate) -> float:
    if body.tipo_pago == "efectivo":
        return CalculosMonetarios.redondear(float(body.monto), 2)
    tasa = _tasa_por_nombre(db, body.tipo_oro or "")
    if not tasa:
        raise ValueError("No hay tasa operativa registrada para ese tipo de oro")
    tr = float(tasa.tasa_reales)
    if tr <= 0:
        raise ValueError("La tasa operativa es invalida (cero o negativa)")
    return CalculosMonetarios.redondear(float(body.monto) * tr, 2)


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
        equiv = _equiv_pago_reales(db, p)
        out.append(
            {
                "id": p.id,
                "venta_id": p.venta_id,
                "monto": float(p.monto),
                "moneda": p.moneda,
                "tipo_pago": p.tipo_pago,
                "tipo_oro": getattr(p, "tipo_oro", None),
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

        abono_reales = _abono_en_reales(db, body)
        if abono_reales <= 0:
            raise ValueError("El monto del abono debe ser mayor a cero")
        saldo = float(venta.saldo_pendiente)
        applied_reales = min(abono_reales, saldo)
        applied_reales = CalculosMonetarios.redondear(applied_reales, 2)

        if body.tipo_pago == "oro":
            tasa_o = _tasa_por_nombre(db, body.tipo_oro or "")
            if not tasa_o:
                raise ValueError("No hay tasa operativa registrada para ese tipo de oro")
            tr = float(tasa_o.tasa_reales)
            if tr <= 0:
                raise ValueError("La tasa operativa es invalida (cero o negativa)")
            monto_registro = CalculosMonetarios.redondear(applied_reales / tr, 4)
        else:
            monto_registro = applied_reales

        venta.monto_pagado = CalculosMonetarios.redondear(float(venta.monto_pagado) + applied_reales, 2)
        venta.saldo_pendiente = CalculosMonetarios.redondear(saldo - applied_reales, 2)
        if venta.saldo_pendiente <= 0.009:
            venta.saldo_pendiente = 0.0
            venta.estado_pago = "PAGADO"
        else:
            venta.estado_pago = "PARCIAL"

        moneda_val = "oro" if body.tipo_pago == "oro" else "reales"
        etiqueta = _CANAL_ETIQUETA[body.tipo_pago]
        reg = (body.registrado_por or "Admin").strip() or "Admin"

        db.add(
            PagoVenta(
                venta_id=venta.id,
                monto=float(monto_registro),
                moneda=moneda_val,
                tipo_pago=etiqueta,
                tipo_oro=body.tipo_oro if body.tipo_pago == "oro" else None,
                registrado_por=reg,
            )
        )

        gramos = float(monto_registro) if body.tipo_pago == "oro" else 0.0
        ledger_tipo_oro = body.tipo_oro if body.tipo_pago == "oro" else venta.tipo_oro
        tasa_row = _tasa_por_nombre(db, body.tipo_oro) if body.tipo_pago == "oro" else venta.tasa_cambio
        tasa_usada = float(tasa_row.tasa_reales) if tasa_row and tasa_row.tasa_reales else None

        registrar_transaccion(
            db,
            tipo="cobro_fiado",
            modulo_origen="bodega",
            referencia_id=venta.id,
            moneda=moneda_val,
            monto_reales=float(applied_reales),
            gramos_oro=gramos,
            tipo_oro=ledger_tipo_oro,
            tasa_usada=tasa_usada,
            descripcion=f"Cobro fiado venta #{venta.id} ({etiqueta})",
        )

        db.commit()
        return {
            "status": "success",
            "venta_id": venta.id,
            "estado_pago": venta.estado_pago,
            "monto_pagado": float(venta.monto_pagado),
            "saldo_pendiente": float(venta.saldo_pendiente),
            "abono_reales": float(applied_reales),
            "abono_capado_a_saldo": applied_reales + 0.001 < abono_reales,
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("registrar_pago failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
