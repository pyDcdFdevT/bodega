from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import case, func
from sqlalchemy.orm import Session, joinedload

from models import (
    Compra,
    CompraOro,
    GastoOperativo,
    GasolinaReposicion,
    PagoVenta,
    Producto,
    Salida,
    Transaccion,
    Venta,
    VentaGasolina,
)
from services.calculos import CalculosMonetarios, equivalencia_pago_reales, ganancia_neta_dia
from services.query_operativa import compra_no_anulada, venta_no_anulada


def _inicio_dia_hoy() -> datetime:
    """Medianoche UTC naive (misma convención que `utc_now()` en modelos)."""
    return datetime.now(UTC).replace(tzinfo=None).replace(hour=0, minute=0, second=0, microsecond=0)


def _sum_reposicion_gasolina_reales_dia(db: Session, inicio: datetime) -> float:
    """R$ repuestos hoy: suma `GasolinaReposicion.total_reales` (no litros × precio × tasa)."""
    return float(
        db.query(func.coalesce(func.sum(GasolinaReposicion.total_reales), 0))
        .filter(GasolinaReposicion.fecha >= inicio)
        .scalar()
        or 0
    )


def _sum_salidas_reales_dia(db: Session, inicio: datetime) -> float:
    """Pérdida en R$ del día: `Salida.valor_oro` (columna legacy, valor en reales)."""
    desde_ledger = float(
        db.query(func.coalesce(func.sum(Transaccion.monto_reales), 0))
        .filter(
            Transaccion.fecha >= inicio,
            Transaccion.tipo == "salida",
            Transaccion.modulo_origen == "bodega",
        )
        .scalar()
        or 0
    )
    if desde_ledger > 0:
        return desde_ledger
    return float(
        db.query(
            func.coalesce(
                func.sum(
                    case(
                        (Salida.valor_oro >= 1.0, Salida.valor_oro),
                        else_=Salida.cantidad * Producto.precio_costo_reales,
                    )
                ),
                0,
            )
        )
        .join(Producto, Salida.producto_id == Producto.id)
        .filter(Salida.fecha >= inicio)
        .scalar()
        or 0
    )


def _venta_oro_recibido_por_tipo(db: Session, inicio: datetime) -> dict[str, float]:
    rows = (
        db.query(Venta.tipo_oro, func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, venta_no_anulada())
        .group_by(Venta.tipo_oro)
        .all()
    )
    return {(tipo or ""): float(total) for tipo, total in rows}


def _compra_oro_gramos_por_tipo(db: Session, inicio: datetime) -> tuple[dict[str, float], float, float]:
    """Gramos por tipo_oro, total gramos y total reales en una sola query."""
    rows = (
        db.query(
            CompraOro.tipo_oro,
            func.coalesce(func.sum(CompraOro.gramos), 0),
            func.coalesce(func.sum(CompraOro.total_reales), 0),
        )
        .filter(CompraOro.fecha >= inicio)
        .group_by(CompraOro.tipo_oro)
        .all()
    )
    por_tipo: dict[str, float] = {}
    co_gramos = 0.0
    co_reales = 0.0
    for tipo, gramos, reales in rows:
        por_tipo[str(tipo)] = float(gramos)
        co_gramos += float(gramos)
        co_reales += float(reales)
    return por_tipo, co_gramos, co_reales


def construir_payload_cierre(
    db: Session,
    inicio: datetime,
    saldo_inicial_reales: float,
    oro_operativo_inicial: float = 0.0,
) -> dict:
    ventas_reales = float(
        db.query(func.coalesce(func.sum(Venta.total_reales), 0))
        .filter(Venta.fecha >= inicio, venta_no_anulada())
        .scalar()
        or 0
    )
    ventas_oro = float(
        db.query(func.coalesce(func.sum(Venta.total_oro), 0))
        .filter(Venta.fecha >= inicio, venta_no_anulada())
        .scalar()
        or 0
    )
    oro_por_tipo = _venta_oro_recibido_por_tipo(db, inicio)
    oro_araparita = oro_por_tipo.get("araparita", 0.0)
    oro_uruman = oro_por_tipo.get("uruman", 0.0)
    oro_se_min = oro_por_tipo.get("santa_elena_minero", 0.0)
    oro_se_fun = oro_por_tipo.get("santa_elena_fundido", 0.0)

    compras_reales = float(
        db.query(func.coalesce(func.sum(Compra.total_reales), 0))
        .filter(Compra.fecha >= inicio, compra_no_anulada())
        .scalar()
        or 0
    )
    compras_oro = float(
        db.query(func.coalesce(func.sum(Compra.total_oro), 0))
        .filter(Compra.fecha >= inicio, compra_no_anulada())
        .scalar()
        or 0
    )
    salidas_reales = _sum_salidas_reales_dia(db, inicio)

    gas_ventas_reales = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_reales), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gas_ventas_oro = float(
        db.query(func.coalesce(func.sum(VentaGasolina.total_oro), 0))
        .filter(VentaGasolina.fecha >= inicio)
        .scalar()
        or 0
    )
    gas_repo_reales = _sum_reposicion_gasolina_reales_dia(db, inicio)

    comprado_por_tipo, co_gramos, co_reales = _compra_oro_gramos_por_tipo(db, inicio)
    comprado_araparita = comprado_por_tipo.get("araparita", 0.0)
    comprado_uruman = comprado_por_tipo.get("uruman", 0.0)
    comprado_santa_elena_minero = comprado_por_tipo.get("santa_elena_minero", 0.0)
    comprado_santa_elena_fundido = comprado_por_tipo.get("santa_elena_fundido", 0.0)
    comprado_suma_tipos = comprado_araparita + comprado_uruman + comprado_santa_elena_minero + comprado_santa_elena_fundido
    comprado_otros_tipos_gramos = max(0.0, co_gramos - comprado_suma_tipos)

    gastos_total = float(
        db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0))
        .filter(GastoOperativo.fecha >= inicio)
        .scalar()
        or 0
    )

    ventas_contado_reales = float(
        db.query(func.coalesce(func.sum(Venta.total_reales), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_venta == "contado", venta_no_anulada())
        .scalar()
        or 0
    )

    pagos_venta_rows = (
        db.query(PagoVenta)
        .join(Venta, PagoVenta.venta_id == Venta.id)
        .options(joinedload(PagoVenta.venta).joinedload(Venta.tasa_cambio))
        .filter(PagoVenta.fecha >= inicio, venta_no_anulada())
        .all()
    )
    cobros_del_dia = sum(equivalencia_pago_reales(db, p) for p in pagos_venta_rows)

    cuentas_por_cobrar = float(
        db.query(func.coalesce(func.sum(Venta.saldo_pendiente), 0))
        .filter(Venta.saldo_pendiente > 0, venta_no_anulada())
        .scalar()
        or 0
    )

    oro_recolectado_bruto = oro_araparita + oro_uruman + oro_se_min + oro_se_fun
    ingresos_reales = ventas_contado_reales + gas_ventas_reales + cobros_del_dia
    egresos_reales = compras_reales + co_reales + gas_repo_reales + gastos_total + salidas_reales
    saldo_final = round(saldo_inicial_reales + ingresos_reales - egresos_reales, 2)

    oro_recolectado_bruto_r = round(oro_recolectado_bruto, 2)
    co_gramos_r = round(co_gramos, 2)
    bruto_total_gramos = round(oro_recolectado_bruto + co_gramos, 2)
    salidas_reales_r = round(salidas_reales, 2)
    oro_ini = float(oro_operativo_inicial or 0)
    oro_esperado = round(oro_ini + bruto_total_gramos, 2)

    oro_block = {
        "araparita": round(oro_araparita, 2),
        "uruman": round(oro_uruman, 2),
        "santa_elena_minero": round(oro_se_min, 2),
        "santa_elena_fundido": round(oro_se_fun, 2),
        "comprado_araparita": round(comprado_araparita, 2),
        "comprado_uruman": round(comprado_uruman, 2),
        "comprado_santa_elena_minero": round(comprado_santa_elena_minero, 2),
        "comprado_santa_elena_fundido": round(comprado_santa_elena_fundido, 2),
        "comprado_otros_tipos_gramos": round(comprado_otros_tipos_gramos, 4),
        "comprado_gramos": co_gramos_r,
        "bruto_total_gramos": bruto_total_gramos,
    }

    ventas_reales_tot = round(ventas_reales + gas_ventas_reales, 2)
    ventas_oro_tot = round(ventas_oro + gas_ventas_oro, 2)
    compras_reales_tot = round(compras_reales + co_reales + gas_repo_reales, 2)

    tasa_ref = CalculosMonetarios.obtener_tasa_referencia(db)
    gastos_oro_equiv = (
        float(CalculosMonetarios.reales_a_oro(gastos_total, db, tasa=tasa_ref)) if gastos_total > 0 else 0.0
    )

    return {
        "fecha": inicio.date().isoformat(),
        "bodega": {
            "ventas_reales": round(ventas_reales, 2),
            "ventas_oro": round(ventas_oro, 2),
            "compras_mercancia_reales": round(compras_reales, 2),
            "compras_mercancia_oro": round(compras_oro, 2),
            "salidas_reales": salidas_reales_r,
        },
        "gasolina": {
            "ventas_reales": round(gas_ventas_reales, 2),
            "ventas_oro": round(gas_ventas_oro, 2),
            "reposicion_reales": round(gas_repo_reales, 2),
        },
        "compra_oro": {
            "gramos": co_gramos_r,
            "reales_usados": round(co_reales, 2),
        },
        "gastos": {
            "total_reales": round(gastos_total, 2),
        },
        "oro_recolectado": oro_block,
        "caja": {
            "saldo_inicial_reales": round(saldo_inicial_reales, 2),
            "oro_operativo_inicial": round(oro_ini, 2),
            "ingresos_reales": round(ingresos_reales, 2),
            "egresos_reales": round(egresos_reales, 2),
            "saldo_final_reales": saldo_final,
        },
        "fundicion": {
            "nota": "Ley y fino son valores manuales en pantalla",
            "bruto_gramos": oro_recolectado_bruto_r,
        },
        "venta_pieza": {
            "nota": "Fino manual x tasa en frontend",
        },
        "conciliacion": {
            "reales_esperados": saldo_final,
            "oro_esperado": oro_esperado,
        },
        "totales_dia": {
            "ventas_reales": ventas_reales_tot,
            "ventas_oro": ventas_oro_tot,
            "compras_reales": compras_reales_tot,
            "gastos_reales": round(gastos_total, 2),
            "oro_recolectado_gramos": bruto_total_gramos,
        },
        "ganancia_neta_dia": ganancia_neta_dia(ventas_oro, compras_oro, 0.0, gas_ventas_oro, gastos_oro_equiv),
        "cuentas_por_cobrar": round(cuentas_por_cobrar, 2),
        "cobros_del_dia": round(cobros_del_dia, 2),
    }
