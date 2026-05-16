"""Balance general: activos, pasivos y patrimonio."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models import Activo, AperturaCaja, CierreDiario, Compra, CompraOro, Configuracion, GastoOperativo, Producto
from services.calculos import CalculosMonetarios
from services.depreciacion import totales_depreciacion
from services.operativa import _ganancia_mercancia_cpp_reales, construir_payload_cierre
from services.query_operativa import compra_no_anulada

CAPITAL_INICIAL_KEY = "capital_inicial_reales"


def _inicio_dia(fecha: date) -> datetime:
    return datetime(fecha.year, fecha.month, fecha.day, tzinfo=UTC).replace(tzinfo=None)


def _obtener_capital_inicial(db: Session) -> float:
    row = db.query(Configuracion).filter(Configuracion.clave == CAPITAL_INICIAL_KEY).first()
    if row and str(row.valor or "").strip():
        try:
            return round(float(row.valor), 2)
        except ValueError:
            pass
    primera = (
        db.query(AperturaCaja)
        .order_by(AperturaCaja.fecha_operativa.asc(), AperturaCaja.id.asc())
        .first()
    )
    if primera:
        valor = round(float(primera.caja_inicial_reales), 2)
        if row:
            row.valor = str(valor)
        else:
            db.add(Configuracion(clave=CAPITAL_INICIAL_KEY, valor=str(valor)))
        db.commit()
        return valor
    return 0.0


def _valor_inventario_cpp(db: Session) -> float:
    total = (
        db.query(
            func.coalesce(
                func.sum(
                    Producto.stock_actual
                    * func.coalesce(Producto.costo_promedio_reales, Producto.precio_costo_reales, 0)
                ),
                0,
            )
        )
        .filter(Producto.activo.is_(True))
        .scalar()
        or 0
    )
    return round(float(total), 2)


def _caja_y_oro_operativo(db: Session, hoy: date) -> tuple[float, float]:
    """Caja y oro operativo (gramos) según cierre del día o último cierre registrado."""
    apertura_hoy = db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first()
    if apertura_hoy:
        inicio = _inicio_dia(hoy)
        payload = construir_payload_cierre(
            db,
            inicio,
            float(apertura_hoy.caja_inicial_reales),
            float(apertura_hoy.oro_operativo_inicial or 0),
        )
        caja = float(payload["caja"]["saldo_final_reales"])
        oro_g = float(payload["conciliacion"]["oro_esperado"])
        return round(caja, 2), round(oro_g, 4)

    ultimo_cierre = (
        db.query(CierreDiario)
        .order_by(CierreDiario.fecha_operativa.desc(), CierreDiario.id.desc())
        .first()
    )
    if ultimo_cierre:
        return round(float(ultimo_cierre.se_deja_reales), 2), round(float(ultimo_cierre.se_deja_oro), 4)

    primera_ap = (
        db.query(AperturaCaja)
        .order_by(AperturaCaja.fecha_operativa.asc(), AperturaCaja.id.asc())
        .first()
    )
    if primera_ap:
        return round(float(primera_ap.caja_inicial_reales), 2), round(float(primera_ap.oro_operativo_inicial or 0), 4)
    return 0.0, 0.0


def _cuentas_por_pagar(db: Session) -> float:
    total = (
        db.query(func.coalesce(func.sum(Compra.total_reales), 0))
        .filter(compra_no_anulada(), Compra.tipo_pago_compra == "credito")
        .scalar()
        or 0
    )
    return round(float(total), 2)


def _ganancia_acumulada_reales(db: Session) -> float:
    ingresos, costo_cpp = _ganancia_mercancia_cpp_reales(db, inicio=None)
    gastos = float(
        db.query(func.coalesce(func.sum(GastoOperativo.monto_reales), 0)).scalar() or 0
    )
    compras_oro = float(
        db.query(func.coalesce(func.sum(CompraOro.total_reales), 0)).scalar() or 0
    )
    return round(ingresos - costo_cpp - gastos - compras_oro, 2)


def build_balance_general(db: Session) -> dict:
    hoy = datetime.now(UTC).date()
    tasa_ref = CalculosMonetarios.obtener_tasa_referencia(db)

    caja, oro_gramos = _caja_y_oro_operativo(db, hoy)
    oro_reales = round(float(CalculosMonetarios.oro_a_reales(oro_gramos, db, tasa=tasa_ref)), 2)
    inventario = _valor_inventario_cpp(db)
    activos_rows = db.query(Activo).order_by(Activo.fecha.asc(), Activo.id.asc()).all()
    dep = totales_depreciacion(activos_rows, hoy)
    activos_fijos_valor_actual = dep["valor_actual"]
    activos_fijos_monto_original = dep["monto_original"]
    activos_fijos_dep_acum = dep["depreciacion_acumulada"]

    activos_total = round(caja + oro_reales + inventario + activos_fijos_valor_actual, 2)
    activos = {
        "caja_reales": caja,
        "oro": {
            "gramos": oro_gramos,
            "valor_reales": oro_reales,
            "tasa_referencia": tasa_ref.nombre,
            "tasa_reales": float(tasa_ref.tasa_reales),
        },
        "inventario_reales": inventario,
        "activos_fijos_reales": activos_fijos_valor_actual,
        "activos_fijos_monto_original": activos_fijos_monto_original,
        "activos_fijos_depreciacion_acumulada": activos_fijos_dep_acum,
        "total": activos_total,
    }

    cuentas_por_pagar = _cuentas_por_pagar(db)
    pasivos = {
        "cuentas_por_pagar": cuentas_por_pagar,
        "total": cuentas_por_pagar,
    }

    capital_inicial = _obtener_capital_inicial(db)
    ganancia_acumulada = _ganancia_acumulada_reales(db)
    patrimonio_total = round(capital_inicial + ganancia_acumulada, 2)
    patrimonio = {
        "capital_inicial": capital_inicial,
        "ganancia_acumulada": ganancia_acumulada,
        "total": patrimonio_total,
    }

    pasivos_patrimonio = round(pasivos["total"] + patrimonio_total, 2)
    diferencia = round(activos_total - pasivos_patrimonio, 2)
    cuadra = abs(diferencia) < 0.05

    return {
        "fecha": hoy.isoformat(),
        "activos": activos,
        "pasivos": pasivos,
        "patrimonio": patrimonio,
        "ecuacion": {
            "activos": activos_total,
            "pasivos_mas_patrimonio": pasivos_patrimonio,
            "diferencia": diferencia,
            "cuadra": cuadra,
        },
    }
