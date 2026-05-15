from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models import (
    Compra,
    CompraOro,
    GastoOperativo,
    GasolinaReposicion,
    PagoVenta,
    Salida,
    Venta,
    VentaGasolina,
)
from services.calculos import CalculosMonetarios, equivalencia_pago_reales, ganancia_neta_dia
from services.query_operativa import compra_no_anulada, venta_no_anulada


def _inicio_dia_hoy() -> datetime:
    d = datetime.now(UTC)
    return d.replace(hour=0, minute=0, second=0, microsecond=0)


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
    oro_araparita = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "araparita", venta_no_anulada())
        .scalar()
        or 0
    )
    oro_uruman = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "uruman", venta_no_anulada())
        .scalar()
        or 0
    )
    oro_se_min = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "santa_elena_minero", venta_no_anulada())
        .scalar()
        or 0
    )
    oro_se_fun = float(
        db.query(func.coalesce(func.sum(Venta.monto_recibido_oro), 0))
        .filter(Venta.fecha >= inicio, Venta.tipo_oro == "santa_elena_fundido", venta_no_anulada())
        .scalar()
        or 0
    )

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
    salidas_oro = float(
        db.query(func.coalesce(func.sum(Salida.valor_oro), 0)).filter(Salida.fecha >= inicio).scalar() or 0
    )

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
    gas_repo_reales = float(
        db.query(func.coalesce(func.sum(GasolinaReposicion.total_reales), 0))
        .filter(GasolinaReposicion.fecha >= inicio)
        .scalar()
        or 0
    )

    co_gramos = float(
        db.query(func.coalesce(func.sum(CompraOro.gramos), 0)).filter(CompraOro.fecha >= inicio).scalar() or 0
    )
    co_reales = float(
        db.query(func.coalesce(func.sum(CompraOro.total_reales), 0)).filter(CompraOro.fecha >= inicio).scalar() or 0
    )

    def _comprado_gramos_tipo(tipo_oro: str) -> float:
        return float(
            db.query(func.coalesce(func.sum(CompraOro.gramos), 0))
            .filter(CompraOro.fecha >= inicio, CompraOro.tipo_oro == tipo_oro)
            .scalar()
            or 0
        )

    comprado_araparita = _comprado_gramos_tipo("araparita")
    comprado_uruman = _comprado_gramos_tipo("uruman")
    comprado_santa_elena_minero = _comprado_gramos_tipo("santa_elena_minero")
    comprado_santa_elena_fundido = _comprado_gramos_tipo("santa_elena_fundido")
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
    egresos_reales = compras_reales + co_reales + gas_repo_reales + gastos_total
    saldo_final = round(saldo_inicial_reales + ingresos_reales - egresos_reales, 2)

    oro_recolectado_bruto_r = round(oro_recolectado_bruto, 2)
    co_gramos_r = round(co_gramos, 2)
    bruto_total_gramos = round(oro_recolectado_bruto + co_gramos, 2)
    salidas_oro_r = round(salidas_oro, 2)
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
            "salidas_oro": salidas_oro_r,
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
        "ganancia_neta_dia": ganancia_neta_dia(ventas_oro, compras_oro, salidas_oro, gas_ventas_oro, gastos_oro_equiv),
        "cuentas_por_cobrar": round(cuentas_por_cobrar, 2),
        "cobros_del_dia": round(cobros_del_dia, 2),
    }
