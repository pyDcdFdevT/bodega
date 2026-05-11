from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from backend.models import TasaCambio


class CalculosMonetarios:
    ROUND_DIGITS = 3

    @staticmethod
    def redondear(valor: float, decimales: int | None = None) -> float:
        precision = decimales if decimales is not None else CalculosMonetarios.ROUND_DIGITS
        return round(float(valor), precision)

    @staticmethod
    def obtener_tasa_actual(db: Session) -> TasaCambio | None:
        return (
            db.query(TasaCambio)
            .filter(TasaCambio.activo.is_(True))
            .order_by(TasaCambio.created_at.desc(), TasaCambio.id.desc())
            .first()
        )

    @staticmethod
    def reales_a_oro(reales: float, db: Session) -> float:
        tasa = CalculosMonetarios.obtener_tasa_actual(db)
        if not tasa:
            raise ValueError("No hay tasa de cambio configurada")
        return CalculosMonetarios.redondear(reales / tasa.tasa_reales)

    @staticmethod
    def oro_a_reales(oro: float, db: Session) -> float:
        tasa = CalculosMonetarios.obtener_tasa_actual(db)
        if not tasa:
            raise ValueError("No hay tasa de cambio configurada")
        return CalculosMonetarios.redondear(oro * tasa.tasa_reales, 2)

    @staticmethod
    def calcular_costo_unitario(precio_reales_total: float, unidades: float, db: Session) -> float:
        if unidades <= 0:
            raise ValueError("Las unidades deben ser mayores a cero")
        total_oro = CalculosMonetarios.reales_a_oro(precio_reales_total, db)
        return CalculosMonetarios.redondear(total_oro / unidades)

    @staticmethod
    def sugerir_precio_venta(costo_unitario_oro: float, margen: float = 0.30) -> float:
        if costo_unitario_oro < 0:
            raise ValueError("El costo unitario no puede ser negativo")
        if margen < 0:
            raise ValueError("El margen no puede ser negativo")
        return CalculosMonetarios.redondear(costo_unitario_oro * (1 + margen))

    @staticmethod
    def consolidar_total_oro(subtotales: Iterable[float]) -> float:
        return CalculosMonetarios.redondear(sum(subtotales))

    @staticmethod
    def calcular_vuelto(tipo_pago: str, excedente_oro: float, tasa_reales: float) -> tuple[float, float]:
        excedente_oro = CalculosMonetarios.redondear(max(excedente_oro, 0))
        if tipo_pago == "oro":
            return excedente_oro, 0.0
        if tipo_pago == "reales":
            return 0.0, CalculosMonetarios.redondear(excedente_oro * tasa_reales, 2)
        return 0.0, CalculosMonetarios.redondear(excedente_oro * tasa_reales, 2)
