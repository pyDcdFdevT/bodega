from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _texto_requerido(valor: str) -> str:
    limpio = " ".join(valor.strip().split())
    if not limpio:
        raise ValueError("El valor no puede estar vacio")
    return limpio


def _unidad_medida(valor: str) -> str:
    n = _texto_requerido(valor).lower()
    if n not in ("unidad", "kg", "litro"):
        raise ValueError("Debe ser unidad, kg o litro")
    return n


class PinVerifyRequest(BaseModel):
    pin: str = Field(..., min_length=4, max_length=4)

    _pin = field_validator("pin")(_texto_requerido)


class TasasConfigUpdate(BaseModel):
    araparita: float = Field(..., gt=0)
    uruman: float = Field(..., gt=0)
    santa_elena_minero: float = Field(..., gt=0)
    santa_elena_fundido: float = Field(..., gt=0)


class TasaCambioOut(ORMModel):
    id: int
    nombre: str
    tasa_reales: float
    actualizado_en: datetime


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


class ProductoCreate(BaseModel):
    nombre: str = Field(..., min_length=2, max_length=100)
    categoria_nombre: str = Field(..., min_length=2, max_length=100)
    presentacion: str = Field(default="unidad", min_length=2, max_length=20)
    unidad_venta: str = Field(default="unidad", min_length=2, max_length=20)
    stock_actual: float = Field(default=0, ge=0)
    stock_minimo: float = Field(default=5, ge=0)
    precio_venta_reales: float = Field(..., ge=0)

    _nombre = field_validator("nombre")(_texto_requerido)
    _categoria = field_validator("categoria_nombre")(_texto_requerido)
    _presentacion = field_validator("presentacion")(_unidad_medida)
    _unidad_venta = field_validator("unidad_venta")(_unidad_medida)


class ProductoUpdate(BaseModel):
    nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    categoria_nombre: Optional[str] = Field(default=None, min_length=2, max_length=100)
    presentacion: Optional[str] = Field(default=None, min_length=2, max_length=20)
    unidad_venta: Optional[str] = Field(default=None, min_length=2, max_length=20)
    stock_actual: Optional[float] = Field(default=None, ge=0)
    stock_minimo: Optional[float] = Field(default=None, ge=0)
    precio_venta_reales: Optional[float] = Field(default=None, ge=0)
    activo: Optional[bool] = None

    @field_validator("nombre", "categoria_nombre")
    @classmethod
    def limpiar_texto_opcional(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return valor
        return _texto_requerido(valor)

    @field_validator("presentacion", "unidad_venta")
    @classmethod
    def limpiar_medida_opcional(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return valor
        return _unidad_medida(valor)


class ItemVenta(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)


class VentaCreate(BaseModel):
    items: List[ItemVenta] = Field(..., min_length=1)
    tasa_cambio_id: int = Field(..., gt=0)
    tipo_pago: str = Field(..., min_length=3, max_length=20)
    tipo_oro: Optional[str] = Field(default=None, max_length=50)
    cliente: str = Field(default="Mostrador", max_length=100)
    monto_recibido_oro: float = Field(default=0, ge=0)
    monto_recibido_reales: float = Field(default=0, ge=0)

    _tipo_pago = field_validator("tipo_pago")(_texto_requerido)
    _cliente = field_validator("cliente")(_texto_requerido)

    @field_validator("tipo_oro")
    @classmethod
    def limpiar_tipo_oro(cls, valor: Optional[str]) -> Optional[str]:
        if valor is None:
            return valor
        return _texto_requerido(valor).lower()


class CompraCreate(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)
    precio_reales: float = Field(..., gt=0)
    proveedor: str = Field(default="Proveedor", max_length=100)
    observaciones: Optional[str] = Field(default=None, max_length=500)

    _proveedor = field_validator("proveedor")(_texto_requerido)


class GasolinaVenta(BaseModel):
    litros: float = Field(..., gt=0)
    tasa_cambio_id: int = Field(..., gt=0)
    tipo_pago: str = Field(default="oro", min_length=3, max_length=20)
    monto_recibido_oro: float = Field(default=0, ge=0)
    monto_recibido_reales: float = Field(default=0, ge=0)

    _tipo_pago = field_validator("tipo_pago")(_texto_requerido)


class GasolinaConfigUpdate(BaseModel):
    tipo: str = Field(default="Gasolina", min_length=3, max_length=50)
    litros_disponibles: Optional[float] = Field(default=None, ge=0)
    precio_por_litro_oro: Optional[float] = Field(default=None, ge=0)

    _tipo = field_validator("tipo")(_texto_requerido)


class CompraOroCreate(BaseModel):
    tipo_oro: str = Field(..., min_length=3, max_length=50)
    gramos: float = Field(..., gt=0)
    tasa_compra_reales: float = Field(..., gt=0)

    _tipo_oro = field_validator("tipo_oro")(_texto_requerido)


class CompraOroOut(ORMModel):
    id: int
    tipo_oro: str
    gramos: float
    tasa_compra_reales: float
    total_reales: float
    fecha: datetime


class SalidaCreate(BaseModel):
    producto_id: int = Field(..., gt=0)
    cantidad: float = Field(..., gt=0)
    motivo: str = Field(..., min_length=3, max_length=50)

    _motivo = field_validator("motivo")(_texto_requerido)


class SalidaOut(ORMModel):
    id: int
    producto_id: int
    cantidad: float
    valor_oro: float
    motivo: str
    fecha: datetime
