from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _nuevo_uuid_transaccion() -> str:
    return str(uuid.uuid4())


class Categoria(Base):
    __tablename__ = "categorias"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), unique=True, nullable=False, index=True)
    descripcion = Column(String(255))
    icono = Column(String(20), default="BOX")
    color = Column(String(20), default="#D5E6F7")
    created_at = Column(DateTime, default=utc_now, nullable=False)

    productos = relationship("Producto", back_populates="categoria_rel")


class Producto(Base):
    __tablename__ = "productos"
    __table_args__ = (
        UniqueConstraint("nombre", "categoria_id", "presentacion", name="uq_producto_nombre_categoria_presentacion"),
        CheckConstraint("presentacion IN ('unidad','kg','litro')", name="ck_producto_presentacion"),
        CheckConstraint("unidad_venta IN ('unidad','kg','litro')", name="ck_producto_unidad_venta"),
        CheckConstraint("stock_actual >= 0", name="ck_producto_stock_actual"),
        CheckConstraint("stock_minimo >= 0", name="ck_producto_stock_minimo"),
        CheckConstraint("precio_costo_oro >= 0", name="ck_producto_precio_costo_oro"),
        CheckConstraint("precio_costo_reales >= 0", name="ck_producto_precio_costo_reales"),
        CheckConstraint("precio_venta_reales >= 0", name="ck_producto_precio_venta_reales"),
        CheckConstraint("precio_venta_oro >= 0", name="ck_producto_precio_venta_oro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, index=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False, index=True)
    presentacion = Column(String(20), default="unidad", nullable=False)
    unidad_venta = Column(String(20), default="unidad", nullable=False)
    stock_actual = Column(Float, default=0, nullable=False)
    stock_minimo = Column(Float, default=5, nullable=False)
    precio_costo_oro = Column(Float, default=0, nullable=False)
    precio_costo_reales = Column(Float, default=0, nullable=False)
    precio_venta_reales = Column(Float, default=0, nullable=False)
    precio_venta_oro = Column(Float, default=0, nullable=False)
    activo = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    categoria_rel = relationship("Categoria", back_populates="productos")
    movimientos = relationship("MovimientoInventario", back_populates="producto")
    detalles_venta = relationship("DetalleVenta", back_populates="producto")
    detalles_compra = relationship("DetalleCompra", back_populates="producto")
    salidas = relationship("Salida", back_populates="producto")


class TasaCambio(Base):
    __tablename__ = "tasas_cambio"
    __table_args__ = (
        UniqueConstraint("nombre", name="uq_tasa_cambio_nombre"),
        CheckConstraint("tasa_reales > 0", name="ck_tasa_cambio_reales"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(50), nullable=False, unique=True, index=True)
    tasa_reales = Column(Float, nullable=False)
    actualizado_en = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    ventas = relationship("Venta", back_populates="tasa_cambio")
    ventas_gasolina = relationship("VentaGasolina", back_populates="tasa_cambio")
    reposiciones_gasolina = relationship("GasolinaReposicion", back_populates="tasa_cambio")


class LogTasaCambio(Base):
    __tablename__ = "log_tasas_cambio"

    id = Column(Integer, primary_key=True, index=True)
    nombre_tasa = Column(String(50), nullable=False)
    fecha_cambio = Column(DateTime, default=utc_now, nullable=False)
    tasa_anterior = Column(Float)
    tasa_nueva = Column(Float, nullable=False)
    variacion_porcentaje = Column(Float)
    motivo = Column(String(255), default="Actualizacion manual")


class Venta(Base):
    __tablename__ = "ventas"
    __table_args__ = (
        CheckConstraint("total_oro >= 0", name="ck_venta_total_oro"),
        CheckConstraint("total_reales >= 0", name="ck_venta_total_reales"),
        CheckConstraint("monto_recibido_oro >= 0", name="ck_venta_monto_recibido_oro"),
        CheckConstraint("monto_recibido_reales >= 0", name="ck_venta_monto_recibido_reales"),
        CheckConstraint("vuelto_oro >= 0", name="ck_venta_vuelto_oro"),
        CheckConstraint("vuelto_reales >= 0", name="ck_venta_vuelto_reales"),
        CheckConstraint("estado IN ('VIGENTE','ANULADA')", name="ck_venta_estado"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(String(100), default="Mostrador", nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    total_oro = Column(Float, nullable=False)
    total_reales = Column(Float, nullable=False)
    tipo_pago = Column(String(20), nullable=False)
    monto_recibido_oro = Column(Float, default=0, nullable=False)
    monto_recibido_reales = Column(Float, default=0, nullable=False)
    tipo_oro = Column(String(50), nullable=True)
    vuelto_oro = Column(Float, default=0, nullable=False)
    vuelto_reales = Column(Float, default=0, nullable=False)
    tasa_cambio_id = Column(Integer, ForeignKey("tasas_cambio.id"), nullable=True)
    estado_pago = Column(String(20), default="PAGADO", nullable=False)
    monto_pagado = Column(Float, default=0, nullable=False)
    saldo_pendiente = Column(Float, default=0, nullable=False)
    cliente_fiado = Column(String(100), nullable=True)
    telefono_fiado = Column(String(20), nullable=True)
    tipo_venta = Column(String(20), default="contado", nullable=False)
    estado = Column(String(20), default="VIGENTE", nullable=False)

    tasa_cambio = relationship("TasaCambio", back_populates="ventas")
    detalles = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")
    pagos = relationship("PagoVenta", back_populates="venta", cascade="all, delete-orphan")


class PagoVenta(Base):
    __tablename__ = "pagos_venta"
    __table_args__ = (
        CheckConstraint("monto > 0", name="ck_pago_venta_monto"),
        CheckConstraint("moneda IN ('reales','oro')", name="ck_pago_venta_moneda"),
    )

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False, index=True)
    monto = Column(Float, nullable=False)
    moneda = Column(String(10), nullable=False)
    tipo_pago = Column(String(30), nullable=False)
    tipo_oro = Column(String(50), nullable=True)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    registrado_por = Column(String(100), nullable=False, default="Admin")
    created_at = Column(DateTime, default=utc_now, nullable=False)

    venta = relationship("Venta", back_populates="pagos")


class DetalleVenta(Base):
    __tablename__ = "detalles_venta"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_venta_cantidad"),
        CheckConstraint("precio_unitario_oro >= 0", name="ck_detalle_venta_precio_unitario"),
        CheckConstraint("subtotal_oro >= 0", name="ck_detalle_venta_subtotal"),
    )

    id = Column(Integer, primary_key=True, index=True)
    venta_id = Column(Integer, ForeignKey("ventas.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    precio_unitario_oro = Column(Float, nullable=False)
    subtotal_oro = Column(Float, nullable=False)

    venta = relationship("Venta", back_populates="detalles")
    producto = relationship("Producto", back_populates="detalles_venta")


class Compra(Base):
    __tablename__ = "compras"
    __table_args__ = (
        CheckConstraint("total_reales >= 0", name="ck_compra_total_reales"),
        CheckConstraint("total_oro >= 0", name="ck_compra_total_oro"),
        CheckConstraint("tasa_cambio_usada > 0", name="ck_compra_tasa_cambio"),
        CheckConstraint("estado IN ('VIGENTE','ANULADA')", name="ck_compra_estado"),
    )

    id = Column(Integer, primary_key=True, index=True)
    proveedor = Column(String(100), default="Proveedor", nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    total_reales = Column(Float, nullable=False)
    total_oro = Column(Float, nullable=False)
    tasa_cambio_usada = Column(Float, nullable=False)
    observaciones = Column(Text)
    estado = Column(String(20), default="VIGENTE", nullable=False)

    detalles = relationship("DetalleCompra", back_populates="compra", cascade="all, delete-orphan")


class DetalleCompra(Base):
    __tablename__ = "detalles_compras"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_detalle_compra_cantidad"),
        CheckConstraint("precio_reales_total >= 0", name="ck_detalle_compra_precio_reales_total"),
        CheckConstraint("precio_reales_unitario >= 0", name="ck_detalle_compra_precio_reales_unitario"),
        CheckConstraint("precio_oro_unitario >= 0", name="ck_detalle_compra_precio_oro_unitario"),
        CheckConstraint("subtotal_oro >= 0", name="ck_detalle_compra_subtotal_oro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad = Column(Float, nullable=False)
    precio_reales_total = Column(Float, nullable=False)
    precio_reales_unitario = Column(Float, nullable=False)
    precio_oro_unitario = Column(Float, nullable=False)
    subtotal_oro = Column(Float, nullable=False)

    compra = relationship("Compra", back_populates="detalles")
    producto = relationship("Producto", back_populates="detalles_compra")


class Gasolina(Base):
    __tablename__ = "gasolina"
    __table_args__ = (
        CheckConstraint("litros_disponibles >= 0", name="ck_gasolina_litros"),
        CheckConstraint("precio_por_litro_reales >= 0", name="ck_gasolina_precio_litro_reales"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), default="Gasolina", nullable=False)
    litros_disponibles = Column(Float, default=0, nullable=False)
    precio_por_litro_reales = Column(Float, default=0, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    ventas = relationship("VentaGasolina", back_populates="gasolina")
    reposiciones = relationship("GasolinaReposicion", back_populates="gasolina")


class GastoOperativo(Base):
    __tablename__ = "gastos_operativos"
    __table_args__ = (
        CheckConstraint("monto_reales >= 0", name="ck_gasto_monto_reales"),
    )

    id = Column(Integer, primary_key=True, index=True)
    categoria = Column(String(40), nullable=False, index=True)
    descripcion = Column(Text, nullable=False)
    monto_reales = Column(Float, nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)


class Activo(Base):
    __tablename__ = "activos"
    __table_args__ = (
        CheckConstraint("monto_reales >= 0", name="ck_activo_monto_reales"),
        CheckConstraint(
            "categoria IN ('equipo','construccion','vehiculo','otro')",
            name="ck_activo_categoria",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    descripcion = Column(String(500), nullable=False)
    categoria = Column(String(40), nullable=False, index=True)
    monto_reales = Column(Float, nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    observaciones = Column(Text, nullable=True)


class GasolinaReposicion(Base):
    __tablename__ = "gasolina_reposiciones"
    __table_args__ = (
        CheckConstraint("litros > 0", name="ck_gasolina_repo_litros"),
        CheckConstraint("precio_reales_litro > 0", name="ck_gasolina_repo_precio_litro"),
        CheckConstraint("total_reales >= 0", name="ck_gasolina_repo_total_reales"),
        CheckConstraint("total_oro >= 0", name="ck_gasolina_repo_total_oro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    gasolina_id = Column(Integer, ForeignKey("gasolina.id"), nullable=False, index=True)
    litros = Column(Float, nullable=False)
    precio_reales_litro = Column(Float, nullable=False)
    total_reales = Column(Float, nullable=False)
    total_oro = Column(Float, nullable=False)
    tasa_cambio_id = Column(Integer, ForeignKey("tasas_cambio.id"), nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)

    gasolina = relationship("Gasolina", back_populates="reposiciones")
    tasa_cambio = relationship("TasaCambio", back_populates="reposiciones_gasolina")


class VentaGasolina(Base):
    __tablename__ = "ventas_gasolina"
    __table_args__ = (
        CheckConstraint("litros > 0", name="ck_venta_gasolina_litros"),
        CheckConstraint("total_oro >= 0", name="ck_venta_gasolina_total_oro"),
        CheckConstraint("total_reales >= 0", name="ck_venta_gasolina_total_reales"),
        CheckConstraint(
            "unidad_precio_venta IN ('reales_litro','oro_litro')",
            name="ck_venta_gasolina_unidad_precio",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    gasolina_id = Column(Integer, ForeignKey("gasolina.id"), nullable=False)
    tasa_cambio_id = Column(Integer, ForeignKey("tasas_cambio.id"), nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    litros = Column(Float, nullable=False)
    total_oro = Column(Float, nullable=False)
    total_reales = Column(Float, nullable=False)
    tipo_pago = Column(String(20), nullable=False)
    tipo_oro = Column(String(50), nullable=True)
    unidad_precio_venta = Column(String(20), default="reales_litro", nullable=False)
    precio_litro_venta = Column(Float, default=0, nullable=False)
    monto_recibido_oro = Column(Float, default=0, nullable=False)
    monto_recibido_reales = Column(Float, default=0, nullable=False)
    vuelto_oro = Column(Float, default=0, nullable=False)
    vuelto_reales = Column(Float, default=0, nullable=False)

    gasolina = relationship("Gasolina", back_populates="ventas")
    tasa_cambio = relationship("TasaCambio", back_populates="ventas_gasolina")


class CompraOro(Base):
    __tablename__ = "compras_oro"
    __table_args__ = (
        CheckConstraint("gramos > 0", name="ck_compra_oro_gramos"),
        CheckConstraint("tasa_compra_reales > 0", name="ck_compra_oro_tasa"),
        CheckConstraint("total_reales >= 0", name="ck_compra_oro_total"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tipo_oro = Column(String(50), nullable=False, index=True)
    gramos = Column(Float, nullable=False)
    tasa_compra_reales = Column(Float, nullable=False)
    total_reales = Column(Float, nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)


class MovimientoInventario(Base):
    __tablename__ = "movimientos_inventario"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_movimiento_cantidad"),
    )

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False, index=True)
    tipo = Column(String(20), nullable=False)
    cantidad = Column(Float, nullable=False)
    stock_anterior = Column(Float, default=0)
    stock_nuevo = Column(Float, default=0)
    motivo = Column(String(255))
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)

    producto = relationship("Producto", back_populates="movimientos")


class Salida(Base):
    __tablename__ = "salidas"
    __table_args__ = (
        CheckConstraint("cantidad > 0", name="ck_salida_cantidad"),
        CheckConstraint("valor_oro >= 0", name="ck_salida_valor_oro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False, index=True)
    cantidad = Column(Float, nullable=False)
    valor_oro = Column(Float, nullable=False)
    motivo = Column(String(50), nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)

    producto = relationship("Producto", back_populates="salidas")


class AperturaCaja(Base):
    __tablename__ = "aperturas_caja"
    __table_args__ = (UniqueConstraint("fecha_operativa", name="uq_apertura_fecha_operativa"),)

    id = Column(Integer, primary_key=True, index=True)
    fecha_operativa = Column(Date, nullable=False, index=True)
    caja_inicial_reales = Column(Float, nullable=False)
    oro_operativo_inicial = Column(Float, nullable=False, default=0)
    abierto_por = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)


class CierreDiario(Base):
    __tablename__ = "cierres_diarios"
    __table_args__ = (UniqueConstraint("fecha_operativa", name="uq_cierre_fecha_operativa"),)

    id = Column(Integer, primary_key=True, index=True)
    fecha_operativa = Column(Date, nullable=False, index=True)
    ventas_reales = Column(Float, nullable=False)
    ventas_oro = Column(Float, nullable=False)
    compras_reales = Column(Float, nullable=False)
    gastos_reales = Column(Float, nullable=False)
    oro_recolectado = Column(Float, nullable=False)
    reales_esperados = Column(Float, nullable=False)
    oro_esperado = Column(Float, nullable=False)
    reales_contados = Column(Float, nullable=False)
    oro_contado = Column(Float, nullable=False)
    diferencia_reales = Column(Float, nullable=False)
    diferencia_oro = Column(Float, nullable=False)
    justificacion = Column(Text, nullable=False, default="")
    retiro_dueno_reales = Column(Float, nullable=False, default=0)
    retiro_dueno_oro = Column(Float, nullable=False, default=0)
    se_deja_reales = Column(Float, nullable=False, default=0)
    se_deja_oro = Column(Float, nullable=False, default=0)
    cerrado_por = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=utc_now, nullable=False)
    snapshot_json = Column(Text, nullable=True)


class LoteOro(Base):
    __tablename__ = "lotes_oro"
    __table_args__ = (
        CheckConstraint(
            "estado IN ('ACUMULANDO','ENVIADO','FUNDIDO','VENDIDO','CERRADO')",
            name="ck_lote_oro_estado",
        ),
        CheckConstraint("gramos_brutos >= 0", name="ck_lote_oro_gramos"),
    )

    id = Column(Integer, primary_key=True, index=True)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    gramos_brutos = Column(Float, nullable=False)
    origen = Column(String(255), nullable=False, default="")
    estado = Column(String(20), nullable=False, default="ACUMULANDO")
    created_at = Column(DateTime, default=utc_now, nullable=False)

    fundiciones = relationship("Fundicion", back_populates="lote")


class Fundicion(Base):
    __tablename__ = "fundiciones"
    __table_args__ = (
        CheckConstraint("gramos_brutos >= 0", name="ck_fundicion_brutos"),
        CheckConstraint("ley >= 0", name="ck_fundicion_ley"),
        CheckConstraint("gramos_finos >= 0", name="ck_fundicion_finos"),
    )

    id = Column(Integer, primary_key=True, index=True)
    lote_oro_id = Column(Integer, ForeignKey("lotes_oro.id"), nullable=False, index=True)
    gramos_brutos = Column(Float, nullable=False)
    ley = Column(Float, nullable=False)
    gramos_finos = Column(Float, nullable=False)
    casa_fundicion = Column(String(200), nullable=False, default="")
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)

    lote = relationship("LoteOro", back_populates="fundiciones")
    venta_pieza = relationship("VentaPieza", back_populates="fundicion", uselist=False)


class VentaPieza(Base):
    __tablename__ = "ventas_pieza"
    __table_args__ = (
        CheckConstraint("gramos_vendidos > 0", name="ck_venta_pieza_gramos"),
        CheckConstraint("tasa_venta >= 0", name="ck_venta_pieza_tasa"),
        CheckConstraint("monto_total >= 0", name="ck_venta_pieza_monto"),
        CheckConstraint("moneda IN ('reales','USD')", name="ck_venta_pieza_moneda"),
    )

    id = Column(Integer, primary_key=True, index=True)
    fundicion_id = Column(Integer, ForeignKey("fundiciones.id"), nullable=False, index=True)
    gramos_vendidos = Column(Float, nullable=False)
    tasa_venta = Column(Float, nullable=False)
    monto_total = Column(Float, nullable=False)
    moneda = Column(String(10), nullable=False, default="reales")
    comprador = Column(String(200), nullable=False, default="")
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)

    fundicion = relationship("Fundicion", back_populates="venta_pieza")
    distribuciones = relationship("DistribucionFondos", back_populates="venta_pieza")


class DistribucionFondos(Base):
    __tablename__ = "distribuciones_fondos"
    __table_args__ = (
        CheckConstraint("monto >= 0", name="ck_distrib_monto"),
        CheckConstraint(
            "tipo IN ('reposicion_bodega','reposicion_gasolina','gastos_operativos','pago_socio','ganancia_dueno','se_deja_caja')",
            name="ck_distrib_tipo",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    venta_pieza_id = Column(Integer, ForeignKey("ventas_pieza.id"), nullable=False, index=True)
    tipo = Column(String(40), nullable=False)
    monto = Column(Float, nullable=False)
    descripcion = Column(String(255), nullable=True)

    venta_pieza = relationship("VentaPieza", back_populates="distribuciones")


class Transaccion(Base):
    __tablename__ = "transacciones"
    __table_args__ = (
        CheckConstraint(
            "tipo IN ('venta','compra','salida','gasto','compra_oro','venta_gasolina','reposicion_gasolina','ajuste','correccion','cobro_fiado')",
            name="ck_transaccion_tipo",
        ),
        CheckConstraint(
            "modulo_origen IN ('bodega','gasolina','oro','gastos')",
            name="ck_transaccion_modulo",
        ),
        CheckConstraint(
            "moneda IN ('reales','oro','mixto')",
            name="ck_transaccion_moneda",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(String(36), unique=True, nullable=False, default=_nuevo_uuid_transaccion)
    tipo = Column(String(30), nullable=False, index=True)
    modulo_origen = Column(String(30), nullable=False, index=True)
    referencia_id = Column(Integer, nullable=True)
    moneda = Column(String(10), nullable=False)
    monto_reales = Column(Float, default=0, nullable=False)
    gramos_oro = Column(Float, default=0, nullable=False)
    tipo_oro = Column(String(50), nullable=True)
    tasa_usada = Column(Float, nullable=True)
    descripcion = Column(String(255), nullable=True)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_now, nullable=False)
