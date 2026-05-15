from __future__ import annotations

from typing import Iterable

from sqlalchemy.orm import Session

from models import PagoVenta, TasaCambio


class CalculosMonetarios:
    ROUND_DIGITS = 2
    ROUND_DIGITS_ORO = 4
    TASA_REFERENCIA_COMPRAS = "araparita"
    TASAS_PREDEFINIDAS = {
        "araparita": 652.80,
        "uruman": 691.20,
        "santa_elena_minero": 614.40,
        "santa_elena_fundido": 768.00,
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
    def redondear_oro(valor: float) -> float:
        return CalculosMonetarios.redondear(valor, CalculosMonetarios.ROUND_DIGITS_ORO)

    @staticmethod
    def ordenar_tasas(tasas: list[TasaCambio]) -> list[TasaCambio]:
        orden = list(CalculosMonetarios.TASAS_PREDEFINIDAS.keys())
        indice = {nombre: posicion for posicion, nombre in enumerate(orden)}
        return sorted(tasas, key=lambda tasa: indice.get(tasa.nombre, 999))

    @staticmethod
    def consultar_tasas(db: Session) -> list[TasaCambio]:
        """Solo lectura: no inserta ni hace flush (init_data / mutaciones crean filas)."""
        return CalculosMonetarios.ordenar_tasas(db.query(TasaCambio).all())

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
        return CalculosMonetarios.redondear_oro(reales / tasa_obj.tasa_reales)

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
        return CalculosMonetarios.redondear_oro(total_oro / unidades)

    @staticmethod
    def sugerir_precio_venta(costo_unitario_oro: float, margen: float = 0.30) -> float:
        if costo_unitario_oro < 0:
            raise ValueError("El costo unitario no puede ser negativo")
        if margen < 0:
            raise ValueError("El margen no puede ser negativo")
        return CalculosMonetarios.redondear_oro(costo_unitario_oro * (1 + margen))

    @staticmethod
    def consolidar_total_oro(subtotales: Iterable[float]) -> float:
        return CalculosMonetarios.redondear_oro(sum(subtotales))

    @staticmethod
    def calcular_vuelto(tipo_pago: str, excedente_oro: float, tasa_reales: float) -> tuple[float, float]:
        excedente_oro = CalculosMonetarios.redondear_oro(max(excedente_oro, 0))
        if tipo_pago == "oro":
            return excedente_oro, 0.0
        if tipo_pago == "reales":
            return 0.0, CalculosMonetarios.redondear(excedente_oro * tasa_reales, 2)
        return 0.0, CalculosMonetarios.redondear(excedente_oro * tasa_reales, 2)


def ganancia_neta_dia(
    ventas_oro: float,
    compras_oro: float,
    salidas_oro: float,
    gasolina_oro: float,
    gastos_oro_equiv: float,
) -> float:
    """Ganancia neta del día en oro: ventas + gasolina - compras - salidas - gastos (equiv. oro)."""
    return round(
        float(ventas_oro) - float(compras_oro) - float(salidas_oro) + float(gasolina_oro) - float(gastos_oro_equiv),
        2,
    )


def equivalencia_pago_reales(db: Session, pago: PagoVenta) -> float:
    """Equivalente en reales de un abono (efectivo u oro según tasa operativa)."""
    if (pago.moneda or "reales").lower() == "reales":
        return CalculosMonetarios.redondear(float(pago.monto), 2)
    nombre = getattr(pago, "tipo_oro", None) or (pago.venta.tipo_oro if pago.venta else None)
    if not nombre:
        return 0.0
    tasa = CalculosMonetarios.obtener_tasa_por_nombre(db, nombre)
    if not tasa or float(tasa.tasa_reales) <= 0:
        return 0.0
    return CalculosMonetarios.redondear(float(pago.monto) * float(tasa.tasa_reales), 2)
