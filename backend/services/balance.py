"""Balance general: activos, pasivos y patrimonio."""

from __future__ import annotations

from datetime import UTC, date, datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models import (
    Activo,
    AperturaCaja,
    CierreDiario,
    Configuracion,
    Gasolina,
    Producto,
    Transaccion,
)
from services.calculos import CalculosMonetarios
from services.depreciacion import totales_depreciacion
from services.operativa import construir_payload_cierre

CAPITAL_INICIAL_KEY = "capital_inicial_reales"

TIPOS_ORO_BALANCE = (
    "araparita",
    "uruman",
    "santa_elena_minero",
    "santa_elena_fundido",
)


def _inicio_dia(fecha: date) -> datetime:
    return datetime(fecha.year, fecha.month, fecha.day, tzinfo=UTC).replace(tzinfo=None)


def _obtener_capital_inicial(db: Session) -> float:
    """Capital aportado: caja inicial de la apertura operativa más antigua."""
    primera = (
        db.query(AperturaCaja)
        .order_by(AperturaCaja.fecha_operativa.asc(), AperturaCaja.id.asc())
        .first()
    )
    if primera:
        return round(float(primera.caja_inicial_reales), 2)
    row = db.query(Configuracion).filter(Configuracion.clave == CAPITAL_INICIAL_KEY).first()
    if row and str(row.valor or "").strip():
        try:
            return round(float(row.valor), 2)
        except ValueError:
            pass
    return 0.0


def _valor_stock_gasolina(db: Session) -> float:
    """Valor del stock de combustible: litros disponibles × precio por litro (R$)."""
    gasolina = db.query(Gasolina).order_by(Gasolina.id.asc()).first()
    if not gasolina:
        return 0.0
    litros = float(gasolina.litros_disponibles or 0)
    precio = float(gasolina.precio_por_litro_reales or 0)
    return CalculosMonetarios.redondear(litros * precio, 2)


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


def _gramos_oro_ledger(db: Session, antes_de: datetime | None = None) -> dict[str, float]:
    """Suma neta de gramos por tipo desde el ledger (transacciones)."""
    por_tipo = {t: 0.0 for t in TIPOS_ORO_BALANCE}
    q = db.query(
        Transaccion.tipo_oro,
        func.coalesce(func.sum(Transaccion.gramos_oro), 0),
    )
    if antes_de is not None:
        q = q.filter(Transaccion.fecha < antes_de)
    sin_tipo = 0.0
    for tipo, gramos in q.group_by(Transaccion.tipo_oro).all():
        key = str(tipo or "").strip().lower()
        g = float(gramos)
        if key in por_tipo:
            por_tipo[key] += g
        else:
            sin_tipo += g
    if sin_tipo:
        por_tipo["araparita"] += sin_tipo
    return {k: round(v, 4) for k, v in por_tipo.items()}


def _flujos_oro_dia_desde_payload(payload: dict) -> dict[str, float]:
    block = payload.get("oro_recolectado") or {}
    return {
        "araparita": float(block.get("araparita", 0)) + float(block.get("comprado_araparita", 0)),
        "uruman": float(block.get("uruman", 0)) + float(block.get("comprado_uruman", 0)),
        "santa_elena_minero": float(block.get("santa_elena_minero", 0))
        + float(block.get("comprado_santa_elena_minero", 0)),
        "santa_elena_fundido": float(block.get("santa_elena_fundido", 0))
        + float(block.get("comprado_santa_elena_fundido", 0)),
    }


def _distribuir_oro_inicial(oro_ini: float, hist: dict[str, float]) -> dict[str, float]:
    total_hist = sum(float(hist.get(t, 0)) for t in TIPOS_ORO_BALANCE)
    if total_hist <= 0:
        out = {t: 0.0 for t in TIPOS_ORO_BALANCE}
        out["araparita"] = round(float(oro_ini), 4)
        return out
    return {
        t: round(float(oro_ini) * float(hist.get(t, 0)) / total_hist, 4) for t in TIPOS_ORO_BALANCE
    }


def _sumar_oro_por_tipo(a: dict[str, float], b: dict[str, float]) -> dict[str, float]:
    return {t: round(float(a.get(t, 0)) + float(b.get(t, 0)), 4) for t in TIPOS_ORO_BALANCE}


def _reconciliar_oro_por_tipo(por_tipo: dict[str, float], oro_total: float) -> dict[str, float]:
    objetivo = round(float(oro_total), 4)
    if objetivo <= 0:
        return {t: 0.0 for t in TIPOS_ORO_BALANCE}
    suma = round(sum(float(por_tipo.get(t, 0)) for t in TIPOS_ORO_BALANCE), 4)
    if suma <= 0:
        out = {t: 0.0 for t in TIPOS_ORO_BALANCE}
        out["araparita"] = objetivo
        return out
    if abs(suma - objetivo) < 0.02:
        return {t: round(float(por_tipo.get(t, 0)), 4) for t in TIPOS_ORO_BALANCE}
    factor = objetivo / suma
    return {t: round(float(por_tipo.get(t, 0)) * factor, 4) for t in TIPOS_ORO_BALANCE}


def _oro_operativo_por_tipo(db: Session, hoy: date, oro_total: float) -> dict[str, float]:
    """Gramos operativos por tipo, reconciliados al total físico esperado."""
    inicio_hoy = _inicio_dia(hoy)
    apertura_hoy = db.query(AperturaCaja).filter(AperturaCaja.fecha_operativa == hoy).first()
    if apertura_hoy:
        hist = _gramos_oro_ledger(db, antes_de=inicio_hoy)
        ini = _distribuir_oro_inicial(float(apertura_hoy.oro_operativo_inicial or 0), hist)
        payload = construir_payload_cierre(
            db,
            inicio_hoy,
            float(apertura_hoy.caja_inicial_reales),
            float(apertura_hoy.oro_operativo_inicial or 0),
        )
        flows = _flujos_oro_dia_desde_payload(payload)
        por_tipo = _sumar_oro_por_tipo(ini, flows)
    else:
        por_tipo = _gramos_oro_ledger(db)
    return _reconciliar_oro_por_tipo(por_tipo, oro_total)


def _valorar_oro_balance(db: Session, por_tipo: dict[str, float]) -> dict:
    tasas = {t.nombre: t for t in CalculosMonetarios.consultar_tasas(db)}
    filas: list[dict] = []
    valor_total = 0.0
    gramos_total = 0.0
    for nombre in TIPOS_ORO_BALANCE:
        gramos = round(float(por_tipo.get(nombre, 0)), 4)
        tasa_row = tasas.get(nombre)
        tasa_reales = (
            float(tasa_row.tasa_reales)
            if tasa_row and float(tasa_row.tasa_reales) > 0
            else float(CalculosMonetarios.TASAS_PREDEFINIDAS.get(nombre, 0))
        )
        valor = round(gramos * tasa_reales, 2) if gramos > 0 and tasa_reales > 0 else 0.0
        filas.append(
            {
                "tipo": nombre,
                "etiqueta": CalculosMonetarios.ETIQUETAS_TASAS.get(nombre, nombre),
                "gramos": gramos,
                "tasa_nombre": nombre,
                "tasa_reales": round(tasa_reales, 2),
                "valor_reales": valor,
            }
        )
        valor_total += valor
        gramos_total += gramos
    return {
        "gramos": round(gramos_total, 4),
        "valor_reales": round(valor_total, 2),
        "por_tipo": filas,
    }


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
    from services.pagos_proveedores import build_deudas_proveedores

    data = build_deudas_proveedores(db)
    return round(float(data.get("total_pendiente") or 0), 2)


def _ganancia_acumulada_reales(activos_total: float, pasivos_total: float, capital_inicial: float) -> float:
    """
    Resultado acumulado coherente con la ecuación contable:
    Activos = Pasivos + Capital inicial + Ganancia acumulada.
    """
    return round(float(activos_total) - float(pasivos_total) - float(capital_inicial), 2)


def build_balance_general(db: Session) -> dict:
    hoy = datetime.now(UTC).date()

    caja, oro_gramos = _caja_y_oro_operativo(db, hoy)
    oro_por_tipo = _oro_operativo_por_tipo(db, hoy, oro_gramos)
    oro_valorado = _valorar_oro_balance(db, oro_por_tipo)
    oro_reales = float(oro_valorado["valor_reales"])
    inventario = _valor_inventario_cpp(db)
    gasolina_stock = _valor_stock_gasolina(db)
    activos_rows = db.query(Activo).order_by(Activo.fecha.asc(), Activo.id.asc()).all()
    dep = totales_depreciacion(activos_rows, hoy)
    activos_fijos_valor_actual = dep["valor_actual"]
    activos_fijos_monto_original = dep["monto_original"]
    activos_fijos_dep_acum = dep["depreciacion_acumulada"]

    activos_total = round(
        caja + oro_reales + inventario + gasolina_stock + activos_fijos_valor_actual, 2
    )
    activos = {
        "caja_reales": caja,
        "oro": {
            "gramos": oro_valorado["gramos"],
            "valor_reales": oro_reales,
            "por_tipo": oro_valorado["por_tipo"],
        },
        "inventario_reales": inventario,
        "gasolina_stock_reales": gasolina_stock,
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
    ganancia_acumulada = _ganancia_acumulada_reales(activos_total, pasivos["total"], capital_inicial)
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
