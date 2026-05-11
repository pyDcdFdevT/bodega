from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _texto_requerido(valor: str) -> str:
    limpio = " ".join(valor.strip().split())
    if not limpio:
        raise ValueError("El valor no puede estar vacio")
    return limpio


class TasaRequest(BaseModel):
    tasa_reales: float = Field(..., gt=0)
    motivo: str = Field(default="Inicio del dia", max_length=255)

    _motivo = field_validator("motivo")(_texto_requerido)


class TasaUpdateRequest(BaseModel):
    tasa_reales: float = Field(..., gt=0)
    motivo: str = Field(default="Actualizacion manual", max_length=255)

    _motivo = field_validator("motivo")(_texto_requerido)


class TasaOut(ORMModel):
    id: int
    fecha: date
    tasa_reales: float
    activo: bool
    created_at: datetime


class LogTasaOut(ORMModel):
    id: int
    fecha_cambio: datetime
    tasa_anterior: Optional[float] = None
    tasa_nueva: float
    variacion_porcentaje: Optional[float] = None
    motivo: Optional[str] = None


class CategoriaCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    descripcion: Optional[str] = Field(default=None, max_length=255)
    icono: str = Field(default="BOX", max_length=20)
    color: str = Field(default="#D5E6F7", max_length=20)

    _nombre = field_validator("nombre")(_texto_requerido)


class CategoriaOut(ORMModel):
    id: int
    nombre: str
    descripcion: Optional[str] = None
    icono: Optional[str] = None
    color: Optional[str] = None
    created_at: datetime


class CategoriaResumen(CategoriaOut):
    total_productos: int = 0
    productos_activos: int = 0


class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    categoria_nombre: str = Field(..., min_length=2, max_length=100)
    presentacion: str = Field(default="unidad", min_length=2, max_length=20)
    unidades_por_bulto: float = Field(default=1, gt=0)
    stock_actual: float = Field(default=0, ge=0)
    stock_minimo: float = Field(default=5, ge=0)
    precio_venta_oro: float = Field(..., ge=0)

    _nombre = field_validator("nombre")(_texto_requerido)
    _categoria = field_validator("categoria_nombre")(_texto_requerido)
    _presentacion = field_validator("presentacion")(_texto_requerido)


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    categoria_nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    presentacion: Optional[str] = Field(default=None, min_length=2, max_length=20)
    unidades_por_bulto: Optional[float] = Field(default=None, gt=0)
    stock_actual: Optional[float] = Field(default=None, ge=0)
    stock_minimo: Optional[float] = Field(default=None, ge=0)
    precio_venta_oro: Optional[float] = Field(default=None, ge=0)
    activo: Optional[bool] = None

    @field_validator("nombre", "categoria_nombre", "presentacion")
    @classmethod
    def limpiar_opcionales(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return valor
        return _texto_requerido(valor)


class ProductoOut(ORMModel):
    id: int
    nombre: str
    categoria_id: int
    presentacion: str
    unidades_por_bulto: float
    stock_actual: float
    stock_minimo: float
    precio_costo_oro: float
    precio_costo_reales: float
    precio_venta_oro: float
    activo: bool
    created_at: datetime
    updated_at: datetime


class ProductoDetalle(ProductoOut):
    categoria_nombre: str
    estado_stock: str


class ItemVenta(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)


class VentaCreate(BaseModel):
    items: List[ItemVenta] = Field(..., min_length=1)
    tipo_pago: str = Field(..., min_length=3, max_length=20)
    cliente: str = Field(default="Mostrador", max_length=100)
    monto_recibido_oro: float = Field(default=0, ge=0)
    monto_recibido_reales: float = Field(default=0, ge=0)

    _tipo_pago = field_validator("tipo_pago")(_texto_requerido)
    _cliente = field_validator("cliente")(_texto_requerido)


class DetalleVentaOut(ORMModel):
    id: int
    producto_id: int
    cantidad: float
    precio_unitario_oro: float
    subtotal_oro: float


class VentaOut(ORMModel):
    id: int
    cliente: str
    fecha: datetime
    total_oro: float
    total_reales: float
    tipo_pago: str
    monto_recibido_oro: float
    monto_recibido_reales: float
    vuelto_oro: float
    vuelto_reales: float
    tasa_cambio_id: int
    detalles: List[DetalleVentaOut]


class CompraCreate(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)
    tipo_cantidad: str = Field(default="bulto", min_length=4, max_length=20)
    precio_reales: float = Field(..., gt=0)
    proveedor: str = Field(default="Proveedor", max_length=100)
    observaciones: Optional[str] = Field(default=None, max_length=500)

    _tipo_cantidad = field_validator("tipo_cantidad")(_texto_requerido)
    _proveedor = field_validator("proveedor")(_texto_requerido)


class DetalleCompraOut(ORMModel):
    id: int
    producto_id: int
    cantidad_bultos: float
    tipo_cantidad: str
    precio_reales_total: float
    precio_reales_unitario: float
    precio_oro_unitario: float
    unidades_reales: float
    subtotal_oro: float


class CompraOut(ORMModel):
    id: int
    proveedor: str
    fecha: datetime
    total_reales: float
    total_oro: float
    tasa_cambio_usada: float
    observaciones: Optional[str] = None
    detalles: List[DetalleCompraOut]


class GasolinaVenta(BaseModel):
    litros: float = Field(..., gt=0)
    tipo_pago: str = Field(default="oro", min_length=3, max_length=20)
    monto_recibido_oro: float = Field(default=0, ge=0)
    monto_recibido_reales: float = Field(default=0, ge=0)

    _tipo_pago = field_validator("tipo_pago")(_texto_requerido)


class GasolinaConfigUpdate(BaseModel):
    tipo: str = Field(default="Gasolina", min_length=3, max_length=50)
    litros_disponibles: Optional[float] = Field(default=None, ge=0)
    precio_por_litro_oro: Optional[float] = Field(default=None, ge=0)
    precio_por_kg_oro: Optional[float] = Field(default=None, ge=0)

    _tipo = field_validator("tipo")(_texto_requerido)


class GasolinaOut(ORMModel):
    id: int
    tipo: str
    litros_disponibles: float
    kg_disponibles: float
    precio_por_litro_oro: float
    precio_por_kg_oro: float
    updated_at: datetime


class VentaGasolinaOut(ORMModel):
    id: int
    gasolina_id: int
    fecha: datetime
    litros: float
    kg_estimados: float
    total_oro: float
    total_reales: float
    tipo_pago: str
    monto_recibido_oro: float
    monto_recibido_reales: float
    vuelto_oro: float
    vuelto_reales: float


class MovimientoInventarioOut(ORMModel):
    id: int
    producto_id: int
    tipo: str
    cantidad: float
    stock_anterior: float
    stock_nuevo: float
    motivo: Optional[str] = None
    fecha: datetime
