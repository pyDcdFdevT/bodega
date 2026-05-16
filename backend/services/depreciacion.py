"""Depreciación lineal de activos fijos."""

from __future__ import annotations

from datetime import UTC, date, datetime

from models import Activo


def calcular_depreciacion_mensual(monto_reales: float, valor_residual: float, vida_util_anios: int) -> float:
    if vida_util_anios < 1:
        raise ValueError("La vida util debe ser al menos 1 año")
    if valor_residual < 0:
        raise ValueError("El valor residual no puede ser negativo")
    if monto_reales < valor_residual:
        raise ValueError("El monto no puede ser menor al valor residual")
    meses = vida_util_anios * 12
    base_depreciable = float(monto_reales) - float(valor_residual)
    if meses <= 0 or base_depreciable <= 0:
        return 0.0
    return round(base_depreciable / meses, 2)


def _meses_depreciados(fecha_activo: datetime, hasta: date | None = None) -> int:
    ref = hasta or datetime.now(UTC).date()
    if isinstance(fecha_activo, datetime):
        inicio = fecha_activo.date()
    else:
        inicio = fecha_activo
    return max(0, (ref.year - inicio.year) * 12 + (ref.month - inicio.month))


def estado_depreciacion_activo(activo: Activo, hasta: date | None = None) -> dict:
    monto = float(activo.monto_reales)
    residual = float(activo.valor_residual or 0)
    vida = int(activo.vida_util_anios or 5)
    dep_mensual = float(activo.depreciacion_mensual or 0)
    if dep_mensual <= 0:
        dep_mensual = calcular_depreciacion_mensual(monto, residual, vida)

    meses = _meses_depreciados(activo.fecha, hasta)
    base_max = max(monto - residual, 0.0)
    dep_acum = round(min(base_max, dep_mensual * meses), 2)
    valor_actual = round(max(residual, monto - dep_acum), 2)

    return {
        "id": activo.id,
        "descripcion": activo.descripcion,
        "categoria": activo.categoria,
        "fecha": activo.fecha.isoformat() if activo.fecha else None,
        "monto_reales": round(monto, 2),
        "vida_util_anios": vida,
        "valor_residual": round(residual, 2),
        "depreciacion_mensual": round(dep_mensual, 2),
        "meses_depreciados": meses,
        "depreciacion_acumulada": dep_acum,
        "valor_actual": valor_actual,
        "observaciones": activo.observaciones or "",
    }


def totales_depreciacion(activos: list[Activo], hasta: date | None = None) -> dict:
    filas = [estado_depreciacion_activo(a, hasta) for a in activos]
    monto_original = sum(float(f["monto_reales"]) for f in filas)
    dep_acum = sum(float(f["depreciacion_acumulada"]) for f in filas)
    valor_actual = sum(float(f["valor_actual"]) for f in filas)
    dep_mensual = sum(float(f["depreciacion_mensual"]) for f in filas)
    return {
        "cantidad_activos": len(filas),
        "monto_original": round(monto_original, 2),
        "depreciacion_acumulada": round(dep_acum, 2),
        "valor_actual": round(valor_actual, 2),
        "depreciacion_mensual_total": round(dep_mensual, 2),
        "activos": filas,
    }


def build_reporte_depreciacion(activos: list[Activo]) -> dict:
    hoy = datetime.now(UTC).date()
    data = totales_depreciacion(activos, hoy)
    return {
        "fecha": hoy.isoformat(),
        "totales": {
            "cantidad_activos": data["cantidad_activos"],
            "monto_original": data["monto_original"],
            "depreciacion_acumulada": data["depreciacion_acumulada"],
            "valor_actual": data["valor_actual"],
            "depreciacion_mensual_total": data["depreciacion_mensual_total"],
        },
        "activos": data["activos"],
    }
