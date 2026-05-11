from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from backend.models import TasaCambio


class CalculosMonetarios:
    ROUND_DIGITS = 3
    TASA_REFERENCIA_COMPRAS = "araparita"
    TASAS_PREDEFINIDAS = {
        "araparita": 37.000,
        "uruman": 38.000,
        "santa_elena_minero": 35.000,
        "santa_elena_fundido": 39.000,
    }
    ETIQUETAS_TASAS = {
        "araparita": "Araparita",
        "uruman": "Uruman",
        "santa_elena_minero": "Santa Elena Minero",
        "santa_elena_fundido": "Santa Elena Fundido",
    }

    @staticmethod
    def redondear(valor: float, decimales: int | None = None) -> float:
        precision = decimales if decimales is not None else CalculosMonetarios.ROUND_DIGITS
        return round(float(valor), precision)

    @staticmethod
    def ordenar_tasas(tasas: list[TasaCambio]) -> list[TasaCambio]:
        orden = list(CalculosMonetarios.TASAS_PREDEFINIDAS.keys())
        indice = {nombre: posicion for posicion, nombre in enumerate(orden)}
        return sorted(tasas, key=lambda tasa: indice.get(tasa.nombre, 999))

    @staticmethod
    def asegurar_tasas_predefinidas(db: Session) -> list[TasaCambio]:
        existentes = {tasa.nombre: tasa for tasa in db.query(TasaCambio).all()}
        for nombre, valor in CalculosMonetarios.TASAS_PREDEFINIDAS.items():
            if nombre not in existentes:
                nueva = TasaCambio(nombre=nombre, tasa_reales=valor)
                db.add(nueva)
                existentes[nombre] = nueva
        db.flush()
        return CalculosMonetarios.ordenar_tasas(list(existentes.values()))

    @staticmethod
    def listar_tasas(db: Session) -> list[TasaCambio]:
        return CalculosMonetarios.asegurar_tasas_predefinidas(db)

    @staticmethod
    def obtener_tasa_por_id(db: Session, tasa_id: int) -> TasaCambio | None:
        return db.query(TasaCambio).filter(TasaCambio.id == tasa_id).first()

    @staticmethod
    def obtener_tasa_por_nombre(db: Session, nombre: str) -> TasaCambio | None:
        return db.query(TasaCambio).filter(TasaCambio.nombre == nombre).first()

    @staticmethod
    def obtener_tasa_referencia(db: Session) -> TasaCambio:
        tasa = CalculosMonetarios.obtener_tasa_por_nombre(db, CalculosMonetarios.TASA_REFERENCIA_COMPRAS)
        if tasa:
            return tasa
        tasas = CalculosMonetarios.listar_tasas(db)
        if not tasas:
            raise ValueError("No hay tasas de cambio configuradas")
        return tasas[0]

    @staticmethod
    def reales_a_oro(
        reales: float,
        db: Session,
        tasa_id: int | None = None,
        tasa_nombre: str | None = None,
        tasa: TasaCambio | None = None,
    ) -> float:
        tasa_obj = tasa
        if tasa_obj is None and tasa_id is not None:
            tasa_obj = CalculosMonetarios.obtener_tasa_por_id(db, tasa_id)
        if tasa_obj is None and tasa_nombre is not None:
            tasa_obj = CalculosMonetarios.obtener_tasa_por_nombre(db, tasa_nombre)
        if tasa_obj is None:
            tasa_obj = CalculosMonetarios.obtener_tasa_referencia(db)
        if tasa_obj.tasa_reales <= 0:
            raise ValueError("La tasa de cambio es invalida")
        return CalculosMonetarios.redondear(reales / tasa_obj.tasa_reales)

    @staticmethod
    def oro_a_reales(
        oro: float,
        db: Session,
        tasa_id: int | None = None,
        tasa_nombre: str | None = None,
        tasa: TasaCambio | None = None,
    ) -> float:
        tasa_obj = tasa
        if tasa_obj is None and tasa_id is not None:
            tasa_obj = CalculosMonetarios.obtener_tasa_por_id(db, tasa_id)
        if tasa_obj is None and tasa_nombre is not None:
            tasa_obj = CalculosMonetarios.obtener_tasa_por_nombre(db, tasa_nombre)
        if tasa_obj is None:
            tasa_obj = CalculosMonetarios.obtener_tasa_referencia(db)
        if tasa_obj.tasa_reales <= 0:
            raise ValueError("La tasa de cambio es invalida")
        return CalculosMonetarios.redondear(oro * tasa_obj.tasa_reales, 2)

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
