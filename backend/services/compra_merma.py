"""Compras por kg: pesaje real y merma por transporte."""

from __future__ import annotations

from sqlalchemy.orm import Session

from models import Producto, Salida
from services.calculos import CalculosMonetarios
from services.ledger import registrar_transaccion

MOTIVO_MERMA_TRANSPORTE = "Merma por transporte"


def producto_compra_por_kg(producto: Producto) -> bool:
    return str(producto.presentacion or "").strip().lower() == "kg"


def resolver_kilos_compra(
    producto: Producto,
    cantidad: float,
    kilos_factura: float | None,
    kilos_recibidos: float | None,
) -> tuple[float, float]:
    """Devuelve (kilos_factura, kilos_recibidos) validados."""
    if not producto_compra_por_kg(producto):
        return float(cantidad), float(cantidad)

    kf = float(kilos_factura if kilos_factura is not None else cantidad)
    kr = float(kilos_recibidos if kilos_recibidos is not None else kf)
    if kf <= 0 or kr <= 0:
        raise ValueError("Los kilos de factura y recibidos deben ser mayores a cero")
    if kr > kf + 0.0001:
        raise ValueError("Los kilos recibidos no pueden superar los de la factura")
    return round(kf, 3), round(kr, 3)


def observaciones_con_unidades(observaciones: str | None, unidades: float | None) -> str | None:
    base = (observaciones or "").strip()
    if unidades is None or unidades <= 0:
        return base or None
    extra = f"Unidades: {round(float(unidades), 3)}"
    return f"{base} — {extra}" if base else extra


def registrar_merma_transporte(
    db: Session,
    *,
    producto: Producto,
    diferencia_kg: float,
    costo_unitario_reales: float,
    compra_id: int,
) -> Salida | None:
    """Registra pérdida por merma sin descontar stock (nunca ingresó al inventario)."""
    diff = round(float(diferencia_kg), 3)
    if diff <= 0.0001:
        return None

    valor_perdida = CalculosMonetarios.redondear(float(costo_unitario_reales) * diff, 2)
    salida = Salida(
        producto_id=producto.id,
        cantidad=diff,
        valor_oro=valor_perdida,
        motivo=MOTIVO_MERMA_TRANSPORTE,
    )
    db.add(salida)
    db.flush()

    registrar_transaccion(
        db,
        tipo="salida",
        modulo_origen="bodega",
        referencia_id=salida.id,
        moneda="reales",
        monto_reales=float(valor_perdida),
        gramos_oro=0.0,
        tipo_oro=None,
        tasa_usada=None,
        descripcion=(
            f"Merma transporte compra #{compra_id} {producto.nombre}: "
            f"{diff} kg (R$ {valor_perdida})"
        )[:255],
    )
    return salida
