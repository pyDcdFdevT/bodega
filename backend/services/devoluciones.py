from __future__ import annotations

from sqlalchemy.orm import Session

from models import DetalleVenta, MovimientoInventario, Producto, TasaCambio, Venta
from schemas import DevolucionVentaCreate
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion
def _factor_neto_venta(venta: Venta, detalles: list[DetalleVenta]) -> tuple[float, float]:
    """Proporción del total cobrado vs subtotales de línea (descuento global)."""
    sub_oro = sum(float(d.subtotal_oro or 0) for d in detalles)
    sub_reales = sum(float(d.subtotal_reales or 0) for d in detalles)
    factor_oro = (float(venta.total_oro) / sub_oro) if sub_oro > 1e-9 else 1.0
    factor_reales = (float(venta.total_reales) / sub_reales) if sub_reales > 1e-9 else 1.0
    return factor_oro, factor_reales


def _consolidar_items_devolucion(body: DevolucionVentaCreate) -> dict[int, float]:
    out: dict[int, float] = {}
    for item in body.items:
        pid = int(item.producto_id)
        qty = float(item.cantidad)
        if qty <= 0:
            raise ValueError("La cantidad a devolver debe ser mayor a cero")
        out[pid] = CalculosMonetarios.redondear(out.get(pid, 0.0) + qty, 2)
    return out


def procesar_devolucion_venta(
    db: Session,
    venta: Venta,
    body: DevolucionVentaCreate,
) -> dict:
    if (venta.estado or "VIGENTE") == "ANULADA":
        raise ValueError("No se puede devolver una venta anulada")

    detalles = list(venta.detalles or [])
    if not detalles:
        raise ValueError("La venta no tiene detalles")

    por_producto: dict[int, DetalleVenta] = {}
    for det in detalles:
        if det.producto_id in por_producto:
            raise ValueError("Venta con lineas duplicadas por producto; contacte soporte")
        por_producto[int(det.producto_id)] = det

    consolidados = _consolidar_items_devolucion(body)
    factor_oro, factor_reales = _factor_neto_venta(venta, detalles)

    dev_oro = 0.0
    dev_reales = 0.0
    lineas_devueltas: list[dict] = []

    for producto_id, cantidad in consolidados.items():
        det = por_producto.get(producto_id)
        if not det:
            raise ValueError(f"El producto {producto_id} no pertenece a esta venta")
        devuelta_prev = float(det.cantidad_devuelta or 0)
        disponible = CalculosMonetarios.redondear(float(det.cantidad) - devuelta_prev, 2)
        if cantidad > disponible + 1e-6:
            raise ValueError(
                f"Cantidad a devolver ({cantidad}) supera lo disponible ({disponible}) del producto {producto_id}"
            )

        producto = det.producto
        if not producto:
            producto = db.query(Producto).filter(Producto.id == det.producto_id).first()
        if not producto:
            raise ValueError(f"Producto {producto_id} no encontrado")

        fraccion = cantidad / float(det.cantidad) if float(det.cantidad) > 0 else 0.0
        linea_oro = CalculosMonetarios.redondear_oro(float(det.subtotal_oro) * fraccion * factor_oro)
        linea_reales = CalculosMonetarios.redondear(float(det.subtotal_reales or 0) * fraccion * factor_reales, 2)

        stock_ant = float(producto.stock_actual)
        producto.stock_actual = CalculosMonetarios.redondear(stock_ant + cantidad)
        det.cantidad_devuelta = CalculosMonetarios.redondear(devuelta_prev + cantidad, 2)

        db.add(
            MovimientoInventario(
                producto_id=producto.id,
                tipo="entrada",
                cantidad=cantidad,
                stock_anterior=stock_ant,
                stock_nuevo=producto.stock_actual,
                motivo=f"Devolucion venta #{venta.id}",
            )
        )

        dev_oro += linea_oro
        dev_reales += linea_reales
        lineas_devueltas.append(
            {
                "producto_id": producto_id,
                "producto": producto.nombre,
                "cantidad": cantidad,
                "monto_oro": linea_oro,
                "monto_reales": linea_reales,
            }
        )

    dev_oro = CalculosMonetarios.redondear_oro(dev_oro)
    dev_reales = CalculosMonetarios.redondear(dev_reales, 2)
    if dev_oro <= 1e-9 and dev_reales <= 1e-6:
        raise ValueError("No hay montos que devolver")

    venta.total_oro = CalculosMonetarios.redondear_oro(max(0.0, float(venta.total_oro) - dev_oro))
    venta.total_reales = CalculosMonetarios.redondear(max(0.0, float(venta.total_reales) - dev_reales), 2)

    if venta.tipo_venta == "fiado":
        pagado = float(venta.monto_pagado or 0)
        venta.saldo_pendiente = CalculosMonetarios.redondear(max(0.0, float(venta.total_reales) - pagado), 2)
        if venta.saldo_pendiente <= 1e-6:
            venta.estado_pago = "PAGADO"
            venta.saldo_pendiente = 0.0
        elif pagado > 1e-6:
            venta.estado_pago = "PARCIAL"
        else:
            venta.estado_pago = "PENDIENTE"

    moneda_led = venta.tipo_pago if venta.tipo_pago in ("reales", "oro", "mixto") else "reales"
    tasa_row = None
    if venta.tasa_cambio_id:
        tasa_row = db.query(TasaCambio).filter(TasaCambio.id == venta.tasa_cambio_id).first()
    tasa_usada = float(tasa_row.tasa_reales) if tasa_row and tasa_row.tasa_reales else None

    registrar_transaccion(
        db,
        tipo="devolucion",
        modulo_origen="bodega",
        referencia_id=venta.id,
        moneda=moneda_led,
        monto_reales=-dev_reales,
        gramos_oro=-dev_oro,
        tipo_oro=venta.tipo_oro,
        tasa_usada=tasa_usada,
        descripcion=f"Devolucion venta #{venta.id}",
    )

    return {
        "venta_id": venta.id,
        "devolucion_oro": dev_oro,
        "devolucion_reales": dev_reales,
        "total_oro": venta.total_oro,
        "total_reales": venta.total_reales,
        "lineas": lineas_devueltas,
    }
