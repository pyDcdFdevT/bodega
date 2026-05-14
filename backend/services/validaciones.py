from __future__ import annotations

from collections import defaultdict

from sqlalchemy.orm import Session

from models import Gasolina, Producto, TasaCambio
from services.calculos import CalculosMonetarios


class ValidacionesSistema:
    TIPOS_PAGO = {"oro", "reales", "mixto"}
    TIPOS_ORO = set(CalculosMonetarios.TASAS_PREDEFINIDAS.keys())

    @staticmethod
    def validar_tasas_configuradas(db: Session) -> list[TasaCambio]:
        tasas = CalculosMonetarios.listar_tasas(db)
        if len(tasas) < len(CalculosMonetarios.TASAS_PREDEFINIDAS):
            raise ValueError("Faltan tasas de cambio por configurar")
        return tasas

    @staticmethod
    def validar_tasa(db: Session, tasa_id: int | None = None, tasa_nombre: str | None = None) -> TasaCambio:
        ValidacionesSistema.validar_tasas_configuradas(db)
        if tasa_id is not None:
            tasa = CalculosMonetarios.obtener_tasa_por_id(db, tasa_id)
        elif tasa_nombre is not None:
            tasa = CalculosMonetarios.obtener_tasa_por_nombre(db, tasa_nombre)
        else:
            tasa = CalculosMonetarios.obtener_tasa_referencia(db)
        if not tasa:
            raise ValueError("La tasa seleccionada no existe")
        if tasa.tasa_reales <= 0:
            raise ValueError("La tasa seleccionada es invalida")
        return tasa

    @staticmethod
    def validar_tipo_oro(tipo_oro: str) -> str:
        normalizado = tipo_oro.strip().lower()
        if normalizado not in ValidacionesSistema.TIPOS_ORO:
            raise ValueError("Tipo de oro invalido")
        return normalizado

    @staticmethod
    def normalizar_tipo_pago(tipo_pago: str) -> str:
        tipo = tipo_pago.strip().lower()
        if tipo not in ValidacionesSistema.TIPOS_PAGO:
            raise ValueError("Tipo de pago invalido. Use oro, reales o mixto")
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
                "Invariante stock: no se puede descontar mas del disponible (el stock no puede quedar negativo). "
                f"{producto.nombre}: stock_actual={producto.stock_actual}, solicitado={cantidad}"
            )
        return producto

    @staticmethod
    def validar_descuento_stock_antes_de_aplicar(producto: Producto, cantidad: float) -> None:
        """Doble chequeo antes de mutar stock (ventas concurrentes)."""
        if cantidad <= 0:
            raise ValueError("La cantidad debe ser mayor a cero")
        if producto.stock_actual < cantidad:
            raise ValueError(
                "Invariante stock: stock insuficiente en el momento del descuento "
                f"({producto.nombre}: {producto.stock_actual} < {cantidad})"
            )

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
        excedente_oro = CalculosMonetarios.redondear_oro(recibido_oro - total_oro)
        return CalculosMonetarios.calcular_vuelto(tipo, excedente_oro, tasa_reales)

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
                "Invariante stock: litros de gasolina insuficientes (no puede quedar stock negativo). "
                f"Disponible: {gasolina.litros_disponibles}, solicitado: {litros}"
            )
        return gasolina
