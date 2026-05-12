from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from database import get_db
from models import DetalleVenta, MovimientoInventario, Producto, Venta
from schemas import VentaCreate
from services.calculos import CalculosMonetarios
from services.validaciones import ValidacionesSistema


router = APIRouter(prefix="/ventas", tags=["Ventas"])


@router.post("")
def registrar_venta(venta: VentaCreate, db: Session = Depends(get_db)):
    try:
        tipo_pago = ValidacionesSistema.normalizar_tipo_pago(venta.tipo_pago)
        tipo_oro = None
        if tipo_pago == "oro":
            if not venta.tipo_oro:
                raise ValueError("Debe seleccionar el tipo de oro")
            tipo_oro = venta.tipo_oro.strip().lower()
            tasa = ValidacionesSistema.validar_tasa(db, tasa_nombre=tipo_oro)
        else:
            tasa = ValidacionesSistema.validar_tasa(db, tasa_id=venta.tasa_cambio_id)
        consolidados = ValidacionesSistema.validar_venta(venta.items, db)

        productos: dict[int, Producto] = {}
        subtotales: dict[int, float] = {}
        for producto_id, cantidad in consolidados.items():
            producto = ValidacionesSistema.validar_stock(producto_id, cantidad, db)
            productos[producto_id] = producto
            subtotales[producto_id] = CalculosMonetarios.redondear(producto.precio_venta_oro * cantidad)

        total_oro = CalculosMonetarios.consolidar_total_oro(subtotales.values())
        total_reales = CalculosMonetarios.oro_a_reales(total_oro, db, tasa=tasa)
        vuelto_oro, vuelto_reales = ValidacionesSistema.validar_pago(
            tipo_pago=tipo_pago,
            total_oro=total_oro,
            monto_recibido_oro=venta.monto_recibido_oro,
            monto_recibido_reales=venta.monto_recibido_reales,
            tasa_reales=tasa.tasa_reales,
        )

        nueva = Venta(
            cliente=venta.cliente,
            total_oro=total_oro,
            total_reales=total_reales,
            tipo_pago=tipo_pago,
            tipo_oro=tipo_oro,
            monto_recibido_oro=venta.monto_recibido_oro,
            monto_recibido_reales=venta.monto_recibido_reales,
            vuelto_oro=vuelto_oro,
            vuelto_reales=vuelto_reales,
            tasa_cambio_id=tasa.id,
        )
        db.add(nueva)
        db.flush()

        detalles_resumen = []
        for producto_id, cantidad in consolidados.items():
            producto = productos[producto_id]
            subtotal_oro = subtotales[producto_id]
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
                "tasa_nombre": tasa.nombre,
                "tasa_reales": tasa.tasa_reales,
                "vuelto_oro": vuelto_oro,
                "vuelto_reales": vuelto_reales,
                "detalles": detalles_resumen,
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
        .filter(Venta.fecha >= inicio)
        .one()
    )
    return {
        "fecha": inicio.date().isoformat(),
        "ventas": cantidad,
        "total_oro": total_oro,
        "total_reales": total_reales,
    }
