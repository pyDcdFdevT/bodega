from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from models import Gasolina, Producto, TasaCambio
from services.calculos import CalculosMonetarios


class ValidacionesSistema:
    TIPOS_PAGO = {"oro", "reales", "mixto"}
    TIPOS_CANTIDAD = {"bulto", "caja", "unidad"}

    @staticmethod
    def validar_tasa(db: Session) -> TasaCambio:
        tasa = CalculosMonetarios.obtener_tasa_actual(db)
        if not tasa:
            raise ValueError("No hay tasa de cambio configurada")
        if tasa.tasa_reales <= 0:
            raise ValueError(f"Tasa invalida: R$ {tasa.tasa_reales}")
        if tasa.tasa_reales < 10 or tasa.tasa_reales > 100:
            raise ValueError(f"Tasa sospechosa: R$ {tasa.tasa_reales}")
        return tasa

    @staticmethod
    def normalizar_tipo_pago(tipo_pago: str) -> str:
        tipo = tipo_pago.strip().lower()
        if tipo not in ValidacionesSistema.TIPOS_PAGO:
            raise ValueError("Tipo de pago invalido. Use oro, reales o mixto")
        return tipo

    @staticmethod
    def normalizar_tipo_cantidad(tipo_cantidad: str) -> str:
        tipo = tipo_cantidad.strip().lower()
        if tipo not in ValidacionesSistema.TIPOS_CANTIDAD:
            raise ValueError("Tipo de cantidad invalido. Use bulto, caja o unidad")
        return tipo

    @staticmethod
    def obtener_producto_activo(producto_id: int, db: Session) -> Producto:
        producto = db.query(Producto).filter(Producto.id == producto_id, Producto.activo.is_(True)).first()
        if not producto:
            raise ValueError("Producto no encontrado o inactivo")
        return producto

    @staticmethod
    def validar_stock(producto_id: int, cantidad: float, db: Session) -> Producto:
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        producto = ValidacionesSistema.obtener_producto_activo(producto_id, db)
        if producto.stock_actual < cantidad:
            raise ValueError(
                f"Stock insuficiente para {producto.nombre}. Disponible: {producto.stock_actual}"
            )
        return producto

    @staticmethod
    def consolidar_items(items: list) -> dict[int, float]:
        consolidados: dict[int, float] = defaultdict(float)
        for item in items:
            if item.cantidad <= 0:
                raise ValueError("Todas las cantidades deben ser mayores a cero")
            consolidados[item.producto_id] += item.cantidad
        return dict(consolidados)

    @staticmethod
    def validar_venta(items: list, db: Session) -> dict[int, float]:
        if not items:
            raise ValueError("Incluya al menos un producto")
        consolidados = ValidacionesSistema.consolidar_items(items)
        for producto_id, cantidad in consolidados.items():
            ValidacionesSistema.validar_stock(producto_id, cantidad, db)
        return consolidados

    @staticmethod
    def validar_pago(
        tipo_pago: str,
        total_oro: float,
        monto_recibido_oro: float,
        monto_recibido_reales: float,
        tasa_reales: float,
    ) -> tuple[float, float]:
        tipo = ValidacionesSistema.normalizar_tipo_pago(tipo_pago)
        recibido_oro = monto_recibido_oro + (monto_recibido_reales / tasa_reales)
        if tipo == "oro" and monto_recibido_oro <= 0:
            raise ValueError("Debe indicar monto recibido en oro")
        if tipo == "reales" and monto_recibido_reales <= 0:
            raise ValueError("Debe indicar monto recibido en reales")
        if tipo == "mixto" and recibido_oro <= 0:
            raise ValueError("Debe indicar al menos un monto recibido")
        if recibido_oro + 1e-9 < total_oro:
            raise ValueError("Monto recibido insuficiente para completar la operacion")
        excedente_oro = CalculosMonetarios.redondear(recibido_oro - total_oro)
        return CalculosMonetarios.calcular_vuelto(tipo, excedente_oro, tasa_reales)

    @staticmethod
    def calcular_unidades_compra(cantidad: float, tipo_cantidad: str, producto: Producto) -> float:
        tipo = ValidacionesSistema.normalizar_tipo_cantidad(tipo_cantidad)
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if tipo in {"bulto", "caja"}:
            return cantidad * producto.unidades_por_bulto
        return cantidad

    @staticmethod
    def validar_gasolina(db: Session) -> Gasolina:
        gasolina = db.query(Gasolina).order_by(Gasolina.id.asc()).first()
        if not gasolina:
            raise ValueError("No hay configuracion de gasolina disponible")
        return gasolina

    @staticmethod
    def validar_stock_gasolina(litros: float, db: Session) -> Gasolina:
        gasolina = ValidacionesSistema.validar_gasolina(db)
        if litros <= 0:
            raise ValueError("Los litros deben ser mayores a cero")
        if gasolina.litros_disponibles < litros:
            raise ValueError(
                f"Stock insuficiente de gasolina. Disponible: {gasolina.litros_disponibles} litros"
            )
        return gasolina
