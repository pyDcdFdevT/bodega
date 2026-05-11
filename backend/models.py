from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
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
        CheckConstraint("unidades_por_bulto > 0", name="ck_producto_unidades_por_bulto"),
        CheckConstraint("stock_actual >= 0", name="ck_producto_stock_actual"),
        CheckConstraint("stock_minimo >= 0", name="ck_producto_stock_minimo"),
        CheckConstraint("precio_costo_oro >= 0", name="ck_producto_precio_costo_oro"),
        CheckConstraint("precio_costo_reales >= 0", name="ck_producto_precio_costo_reales"),
        CheckConstraint("precio_venta_oro >= 0", name="ck_producto_precio_venta_oro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False, index=True)
    categoria_id = Column(Integer, ForeignKey("categorias.id"), nullable=False, index=True)
    presentacion = Column(String(20), default="unidad", nullable=False)
    unidades_por_bulto = Column(Float, default=1, nullable=False)
    stock_actual = Column(Float, default=0, nullable=False)
    stock_minimo = Column(Float, default=5, nullable=False)
    precio_costo_oro = Column(Float, default=0, nullable=False)
    precio_costo_reales = Column(Float, default=0, nullable=False)
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
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente = Column(String(100), default="Mostrador", nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    total_oro = Column(Float, nullable=False)
    total_reales = Column(Float, nullable=False)
    tipo_pago = Column(String(20), nullable=False)
    monto_recibido_oro = Column(Float, default=0, nullable=False)
    monto_recibido_reales = Column(Float, default=0, nullable=False)
    vuelto_oro = Column(Float, default=0, nullable=False)
    vuelto_reales = Column(Float, default=0, nullable=False)
    tasa_cambio_id = Column(Integer, ForeignKey("tasas_cambio.id"), nullable=False)

    tasa_cambio = relationship("TasaCambio", back_populates="ventas")
    detalles = relationship("DetalleVenta", back_populates="venta", cascade="all, delete-orphan")


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
    )

    id = Column(Integer, primary_key=True, index=True)
    proveedor = Column(String(100), default="Proveedor", nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    total_reales = Column(Float, nullable=False)
    total_oro = Column(Float, nullable=False)
    tasa_cambio_usada = Column(Float, nullable=False)
    observaciones = Column(Text)

    detalles = relationship("DetalleCompra", back_populates="compra", cascade="all, delete-orphan")


class DetalleCompra(Base):
    __tablename__ = "detalles_compras"
    __table_args__ = (
        CheckConstraint("cantidad_bultos > 0", name="ck_detalle_compra_cantidad"),
        CheckConstraint("precio_reales_total >= 0", name="ck_detalle_compra_precio_reales_total"),
        CheckConstraint("precio_reales_unitario >= 0", name="ck_detalle_compra_precio_reales_unitario"),
        CheckConstraint("precio_oro_unitario >= 0", name="ck_detalle_compra_precio_oro_unitario"),
        CheckConstraint("unidades_reales > 0", name="ck_detalle_compra_unidades_reales"),
        CheckConstraint("subtotal_oro >= 0", name="ck_detalle_compra_subtotal_oro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    compra_id = Column(Integer, ForeignKey("compras.id"), nullable=False)
    producto_id = Column(Integer, ForeignKey("productos.id"), nullable=False)
    cantidad_bultos = Column(Float, nullable=False)
    tipo_cantidad = Column(String(20), default="bulto", nullable=False)
    precio_reales_total = Column(Float, nullable=False)
    precio_reales_unitario = Column(Float, nullable=False)
    precio_oro_unitario = Column(Float, nullable=False)
    unidades_reales = Column(Float, nullable=False)
    subtotal_oro = Column(Float, nullable=False)

    compra = relationship("Compra", back_populates="detalles")
    producto = relationship("Producto", back_populates="detalles_compra")


class Gasolina(Base):
    __tablename__ = "gasolina"
    __table_args__ = (
        CheckConstraint("litros_disponibles >= 0", name="ck_gasolina_litros"),
        CheckConstraint("precio_por_litro_oro >= 0", name="ck_gasolina_precio_litro"),
    )

    id = Column(Integer, primary_key=True, index=True)
    tipo = Column(String(50), default="Gasolina", nullable=False)
    litros_disponibles = Column(Float, default=0, nullable=False)
    precio_por_litro_oro = Column(Float, default=0, nullable=False)
    updated_at = Column(DateTime, default=utc_now, onupdate=utc_now, nullable=False)

    ventas = relationship("VentaGasolina", back_populates="gasolina")


class VentaGasolina(Base):
    __tablename__ = "ventas_gasolina"
    __table_args__ = (
        CheckConstraint("litros > 0", name="ck_venta_gasolina_litros"),
        CheckConstraint("total_oro >= 0", name="ck_venta_gasolina_total_oro"),
        CheckConstraint("total_reales >= 0", name="ck_venta_gasolina_total_reales"),
    )

    id = Column(Integer, primary_key=True, index=True)
    gasolina_id = Column(Integer, ForeignKey("gasolina.id"), nullable=False)
    tasa_cambio_id = Column(Integer, ForeignKey("tasas_cambio.id"), nullable=False)
    fecha = Column(DateTime, default=utc_now, nullable=False, index=True)
    litros = Column(Float, nullable=False)
    total_oro = Column(Float, nullable=False)
    total_reales = Column(Float, nullable=False)
    tipo_pago = Column(String(20), nullable=False)
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
