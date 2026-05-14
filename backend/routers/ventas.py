from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import DetalleVenta, MovimientoInventario, PagoVenta, Producto, TasaCambio, Venta
from routers.deps import require_admin
from schemas import VentaCreate
from services.apertura_context import exigir_apertura_del_dia
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion
from services.query_operativa import venta_no_anulada
from services.validaciones import ValidacionesSistema


router = APIRouter(prefix="/ventas", tags=["Ventas"])


def _validar_invariante_venta_balanceada(
    *,
    tipo_pago: str,
    consolidados: dict[int, float],
    subtotales_oro: dict[int, float],
    total_oro: float,
    total_reales: float,
    total_reales_directo: float,
    tasa,
    db: Session,
) -> None:
    suma_det_oro = CalculosMonetarios.redondear_oro(sum(subtotales_oro[pid] for pid in consolidados))
    if tipo_pago == "reales":
        if abs(total_oro) > 1e-5:
            raise ValueError("Invariante venta balanceada: con pago en reales total_oro debe ser cero")
        if abs(total_reales - total_reales_directo) > 0.05:
            raise ValueError("Invariante venta balanceada: total_reales no coincide con la suma de lineas")
        return
    if not tasa:
        raise ValueError("Invariante venta balanceada: falta tasa para validar totales en oro/mixto")
    if abs(total_oro - suma_det_oro) > 0.001:
        raise ValueError("Invariante venta balanceada: total_oro debe coincidir con la suma de subtotales oro")
    esperado_reales = CalculosMonetarios.oro_a_reales(total_oro, db, tasa=tasa)
    if abs(float(total_reales) - float(esperado_reales)) > 0.15:
        raise ValueError(
            "Invariante venta balanceada: total_reales no coincide con total_oro valorizado a la tasa del cobro"
        )


@router.post("")
def registrar_venta(venta: VentaCreate, db: Session = Depends(get_db)):
    try:
        exigir_apertura_del_dia(db)
        es_fiado = venta.tipo_venta == "fiado"
        tipo_pago = ValidacionesSistema.normalizar_tipo_pago(venta.tipo_pago)
        if es_fiado and tipo_pago != "reales":
            raise ValueError("La venta fiada solo esta disponible con tipo de pago en reales")
        cli_fiado_nombre = (venta.cliente_fiado or "").strip()
        if es_fiado and not cli_fiado_nombre:
            raise ValueError("Indique el nombre del cliente para venta fiada")

        tipo_oro = None
        tasa = None
        if not es_fiado and tipo_pago in {"oro", "mixto"}:
            if not venta.tipo_oro:
                raise ValueError("Debe seleccionar el tipo de oro")
            tipo_oro = venta.tipo_oro.strip().lower()
            tasa = ValidacionesSistema.validar_tasa(db, tasa_nombre=tipo_oro)
        consolidados = ValidacionesSistema.validar_venta(venta.items, db)

        productos: dict[int, Producto] = {}
        subtotales_oro: dict[int, float] = {}
        subtotales_reales: dict[int, float] = {}
        for producto_id, cantidad in consolidados.items():
            producto = ValidacionesSistema.validar_stock(producto_id, cantidad, db)
            productos[producto_id] = producto
            subtotales_oro[producto_id] = CalculosMonetarios.redondear_oro(producto.precio_venta_oro * cantidad)
            subtotales_reales[producto_id] = CalculosMonetarios.redondear(producto.precio_venta_reales * cantidad, 2)

        total_oro = CalculosMonetarios.consolidar_total_oro(subtotales_oro.values())
        total_reales_convertido = (
            CalculosMonetarios.oro_a_reales(total_oro, db, tasa=tasa) if tasa else 0.0
        )
        total_reales_directo = CalculosMonetarios.redondear(sum(subtotales_reales.values()), 2)

        monto_inicial_registrado = 0.0
        if es_fiado:
            total_oro = 0.0
            total_reales = total_reales_directo
            monto_inicial = CalculosMonetarios.redondear(float(venta.monto_inicial), 2)
            if monto_inicial < 0:
                monto_inicial = 0.0
            if monto_inicial > total_reales + 0.02:
                raise ValueError("El monto inicial no puede superar el total de la venta")
            monto_inicial = min(monto_inicial, total_reales)
            monto_rec_oro = 0.0
            monto_rec_reales = monto_inicial
            vuelto_oro = 0.0
            vuelto_reales = 0.0
            if total_reales <= monto_inicial + 1e-6:
                estado_pago = "PAGADO"
                saldo_pendiente = 0.0
                monto_pagado = total_reales
            elif monto_inicial > 1e-6:
                estado_pago = "PARCIAL"
                saldo_pendiente = CalculosMonetarios.redondear(total_reales - monto_inicial, 2)
                monto_pagado = monto_inicial
            else:
                estado_pago = "PENDIENTE"
                saldo_pendiente = total_reales
                monto_pagado = 0.0
            monto_inicial_registrado = monto_inicial
            _validar_invariante_venta_balanceada(
                tipo_pago="reales",
                consolidados=consolidados,
                subtotales_oro=subtotales_oro,
                total_oro=total_oro,
                total_reales=total_reales,
                total_reales_directo=total_reales_directo,
                tasa=None,
                db=db,
            )
        elif tipo_pago == "reales":
            total_oro = 0.0
            total_reales = total_reales_directo
            if venta.monto_recibido_reales <= 0:
                raise ValueError("Debe indicar monto recibido en reales")
            if venta.monto_recibido_reales + 1e-9 < total_reales:
                raise ValueError("Monto recibido insuficiente para completar la operacion")
            vuelto_oro = 0.0
            vuelto_reales = CalculosMonetarios.redondear(venta.monto_recibido_reales - total_reales, 2)
            monto_rec_oro = venta.monto_recibido_oro
            monto_rec_reales = venta.monto_recibido_reales
            estado_pago = "PAGADO"
            monto_pagado = total_reales
            saldo_pendiente = 0.0
        else:
            total_reales = total_reales_convertido
            vuelto_oro, vuelto_reales = ValidacionesSistema.validar_pago(
                tipo_pago=tipo_pago,
                total_oro=total_oro,
                monto_recibido_oro=venta.monto_recibido_oro,
                monto_recibido_reales=venta.monto_recibido_reales,
                tasa_reales=tasa.tasa_reales,
            )
            monto_rec_oro = venta.monto_recibido_oro
            monto_rec_reales = venta.monto_recibido_reales
            estado_pago = "PAGADO"
            monto_pagado = total_reales
            saldo_pendiente = 0.0

        if not es_fiado:
            _validar_invariante_venta_balanceada(
                tipo_pago=tipo_pago,
                consolidados=consolidados,
                subtotales_oro=subtotales_oro,
                total_oro=total_oro,
                total_reales=total_reales,
                total_reales_directo=total_reales_directo,
                tasa=tasa,
                db=db,
            )

        tel_f = (venta.telefono_fiado or "").strip() or None
        cliente_nombre = cli_fiado_nombre if es_fiado else venta.cliente.strip()

        nueva = Venta(
            cliente=cliente_nombre,
            total_oro=total_oro,
            total_reales=total_reales,
            tipo_pago=tipo_pago,
            tipo_oro=tipo_oro,
            monto_recibido_oro=monto_rec_oro,
            monto_recibido_reales=monto_rec_reales,
            vuelto_oro=vuelto_oro,
            vuelto_reales=vuelto_reales,
            tasa_cambio_id=tasa.id if tasa else None,
            estado_pago=estado_pago,
            monto_pagado=monto_pagado,
            saldo_pendiente=saldo_pendiente,
            cliente_fiado=cli_fiado_nombre if es_fiado else None,
            telefono_fiado=tel_f if es_fiado else None,
            tipo_venta="fiado" if es_fiado else "contado",
        )
        db.add(nueva)
        db.flush()

        detalles_resumen = []
        for producto_id, cantidad in consolidados.items():
            producto = productos[producto_id]
            subtotal_oro = subtotales_oro[producto_id]
            ValidacionesSistema.validar_descuento_stock_antes_de_aplicar(producto, cantidad)
            stock_anterior = producto.stock_actual
            producto.stock_actual = CalculosMonetarios.redondear(producto.stock_actual - cantidad)

            detalle = DetalleVenta(
                venta_id=nueva.id,
                producto_id=producto.id,
                cantidad=cantidad,
                precio_unitario_oro=producto.precio_venta_oro,
                subtotal_oro=subtotal_oro,
            )
            db.add(detalle)
            db.add(
                MovimientoInventario(
                    producto_id=producto.id,
                    tipo="salida",
                    cantidad=cantidad,
                    stock_anterior=stock_anterior,
                    stock_nuevo=producto.stock_actual,
                    motivo=f"Venta registrada #{nueva.id}",
                )
            )
            detalles_resumen.append(
                {
                    "producto_id": producto.id,
                    "producto": producto.nombre,
                    "cantidad": cantidad,
                    "precio_unitario_oro": producto.precio_venta_oro,
                    "subtotal_oro": subtotal_oro,
                }
            )

        if es_fiado:
            if monto_pagado > 0:
                registrar_transaccion(
                    db,
                    tipo="cobro_fiado",
                    modulo_origen="bodega",
                    referencia_id=nueva.id,
                    moneda="reales",
                    monto_reales=float(monto_pagado),
                    gramos_oro=0.0,
                    tipo_oro=None,
                    tasa_usada=None,
                    descripcion=f"Cobro fiado venta #{nueva.id} {cliente_nombre}",
                )
        else:
            registrar_transaccion(
                db,
                tipo="venta",
                modulo_origen="bodega",
                referencia_id=nueva.id,
                moneda=tipo_pago,
                monto_reales=float(total_reales),
                gramos_oro=float(total_oro),
                tipo_oro=tipo_oro,
                tasa_usada=float(tasa.tasa_reales) if tasa else None,
                descripcion=f"Venta #{nueva.id} {venta.cliente}",
            )

        if es_fiado and monto_inicial_registrado > 1e-6:
            db.add(
                PagoVenta(
                    venta_id=nueva.id,
                    monto=float(monto_inicial_registrado),
                    moneda="reales",
                    tipo_pago="inicial",
                    tipo_oro=None,
                    registrado_por="Admin",
                )
            )

        db.commit()
        db.refresh(nueva)

        return {
            "status": "success",
            "message": "Venta registrada correctamente",
            "data": {
                "venta_id": nueva.id,
                "cliente": nueva.cliente,
                "total_oro": total_oro,
                "total_reales": total_reales,
                "tipo_pago": tipo_pago,
                "tipo_oro": tipo_oro,
                "tasa_nombre": tasa.nombre if tasa else None,
                "tasa_reales": tasa.tasa_reales if tasa else None,
                "vuelto_oro": vuelto_oro,
                "vuelto_reales": vuelto_reales,
                "detalles": detalles_resumen,
                "tipo_venta": nueva.tipo_venta,
                "estado_pago": nueva.estado_pago,
                "saldo_pendiente": nueva.saldo_pendiente,
                "monto_pagado": nueva.monto_pagado,
            },
        }
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible registrar la venta") from exc


@router.put("/{venta_id}/anular")
def anular_venta(
    venta_id: int,
    _rol: str = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        venta = (
            db.query(Venta)
            .options(joinedload(Venta.detalles).joinedload(DetalleVenta.producto))
            .filter(Venta.id == venta_id)
            .first()
        )
        if not venta:
            raise HTTPException(status_code=404, detail="Venta no encontrada")
        if (venta.estado or "VIGENTE") == "ANULADA":
            raise ValueError("La venta ya esta anulada")

        for det in venta.detalles:
            producto = det.producto
            if not producto:
                producto = db.query(Producto).filter(Producto.id == det.producto_id).first()
            if not producto:
                raise ValueError("Producto de un detalle de venta no encontrado")
            cant = float(det.cantidad)
            stock_ant = float(producto.stock_actual)
            producto.stock_actual = CalculosMonetarios.redondear(stock_ant + cant)
            db.add(
                MovimientoInventario(
                    producto_id=producto.id,
                    tipo="entrada",
                    cantidad=cant,
                    stock_anterior=stock_ant,
                    stock_nuevo=producto.stock_actual,
                    motivo=f"Anulacion venta #{venta_id}",
                )
            )

        venta.estado = "ANULADA"
        venta.saldo_pendiente = 0.0
        venta.estado_pago = "ANULADA"

        moneda_led = venta.tipo_pago if venta.tipo_pago in ("reales", "oro", "mixto") else "reales"
        tasa_row = None
        if venta.tasa_cambio_id:
            tasa_row = db.query(TasaCambio).filter(TasaCambio.id == venta.tasa_cambio_id).first()
        tasa_usada = float(tasa_row.tasa_reales) if tasa_row and tasa_row.tasa_reales else None

        registrar_transaccion(
            db,
            tipo="correccion",
            modulo_origen="bodega",
            referencia_id=venta.id,
            moneda=moneda_led,
            monto_reales=-float(venta.total_reales),
            gramos_oro=-float(venta.total_oro),
            tipo_oro=venta.tipo_oro,
            tasa_usada=tasa_usada,
            descripcion=f"Anulacion venta #{venta.id}",
        )
        db.commit()
        db.refresh(venta)
        return {"status": "success", "venta_id": venta.id, "estado": venta.estado}
    except ValueError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except HTTPException:
        db.rollback()
        raise
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail="No fue posible anular la venta") from exc


@router.get("")
def listar_ventas(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    ventas = (
        db.query(Venta)
        .options(joinedload(Venta.detalles), joinedload(Venta.tasa_cambio))
        .order_by(Venta.fecha.desc(), Venta.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": venta.id,
            "fecha": venta.fecha,
            "cliente": venta.cliente,
            "total_oro": venta.total_oro,
            "total_reales": venta.total_reales,
            "tipo_pago": venta.tipo_pago,
            "tipo_oro": venta.tipo_oro,
            "tasa_nombre": venta.tasa_cambio.nombre if venta.tasa_cambio else None,
            "tasa_reales": venta.tasa_cambio.tasa_reales if venta.tasa_cambio else None,
            "tipo_venta": venta.tipo_venta,
            "estado_pago": venta.estado_pago,
            "estado": venta.estado or "VIGENTE",
            "saldo_pendiente": float(venta.saldo_pendiente or 0),
        }
        for venta in ventas
    ]


@router.get("/resumen/hoy")
def resumen_ventas_hoy(db: Session = Depends(get_db)):
    inicio = datetime.now(UTC).replace(tzinfo=None, hour=0, minute=0, second=0, microsecond=0)
    total_oro, total_reales, cantidad = (
        db.query(
            func.coalesce(func.sum(Venta.total_oro), 0),
            func.coalesce(func.sum(Venta.total_reales), 0),
            func.count(Venta.id),
        )
        .filter(Venta.fecha >= inicio, venta_no_anulada())
        .one()
    )
    return {
        "fecha": inicio.date().isoformat(),
        "ventas": cantidad,
        "total_oro": total_oro,
        "total_reales": total_reales,
    }
